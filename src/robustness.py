"""
robustness.py - stronger evidence around the (unchanged) deployed model.

Run after `python -m src.train`:   python -m src.robustness
Adds an "evaluation_v2" block to models/metrics.json (existing keys are never modified) and a
"metadata_revision" note to models/model_metadata.json. The model artifact is NOT touched.

Why: the original single 6-employee test set is very noisy. Here every one of the 33 employees is
used as validation exactly once per seed (repeated StratifiedGroupKFold), uncertainty comes from an
employee-level bootstrap, and a time-ordered check (earlier months -> later months) is added.
"""
import hashlib
import json
import warnings

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (average_precision_score as AP, brier_score_loss, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedGroupKFold

from src import config
from src.data_loader import add_target, build_modelling_dataset, flag_rule_rows, load_raw_data
from src.models import get_final_shortlist
from src.splitting import group_holdout_split
from src.timeline import add_period

warnings.filterwarnings("ignore")
T, G, F = config.TARGET_COLUMN, config.GROUP_COLUMN, config.FINAL_FEATURE_COLUMNS
REASON_ONLY = "Reason-only baseline (LR)"
LOOKUP = "Smoothed reason lookup"
PREVALENCE = "Prevalence baseline (no skill)"


def _lookup_scores(train: pd.DataFrame, test: pd.DataFrame, k: float = 5.0) -> np.ndarray:
    """Training long-rate per reason, shrunk towards the overall rate (k pseudo-records)."""
    prior = train[T].mean()
    t = train.groupby(config.REASON)[T].agg(["sum", "count"])
    rate = (t["sum"] + k * prior) / (t["count"] + k)
    return test[config.REASON].map(rate).fillna(prior).to_numpy()


def pooled_oof(df: pd.DataFrame, seeds) -> dict:
    shortlist = get_final_shortlist()
    y = df[T].to_numpy()
    out = {name: np.zeros((len(seeds), len(df))) for name in list(shortlist) + [LOOKUP]}
    for s, seed in enumerate(seeds):
        for tr, va in StratifiedGroupKFold(5, shuffle=True, random_state=seed).split(df[F], y, groups=df[G]):
            for name, pipe in shortlist.items():
                out[name][s, va] = clone(pipe).fit(df.iloc[tr][F], y[tr]).predict_proba(df.iloc[va][F])[:, 1]
            out[LOOKUP][s, va] = _lookup_scores(df.iloc[tr], df.iloc[va])
    out[PREVALENCE] = np.full((len(seeds), len(df)), y.mean())
    return out


def cluster_bootstrap(df, scores: dict, pairs, n_boot=2000, seed=0):
    y, ids = df[T].to_numpy(), df[G].to_numpy()
    uniq = np.unique(ids)
    index = {g: np.where(ids == g)[0] for g in uniq}
    rng = np.random.default_rng(seed)
    draws = {name: [] for name in scores}
    diffs = {f"{a} minus {b}": [] for a, b in pairs}
    for _ in range(n_boot):
        idx = np.concatenate([index[g] for g in rng.choice(uniq, len(uniq))])
        if len(np.unique(y[idx])) < 2:
            continue
        ap = {n: AP(y[idx], s[idx]) for n, s in scores.items()}
        for n, v in ap.items():
            draws[n].append(v)
        for a, b in pairs:
            diffs[f"{a} minus {b}"].append(ap[a] - ap[b])
    ci = lambda v: [float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5))]
    return {n: ci(v) for n, v in draws.items()}, {n: {"median": float(np.median(v)), "ci95": ci(v)} for n, v in diffs.items()}


def _binary_metrics(y, p, thr):
    pred = (p >= thr).astype(int)
    return {"recall": float(recall_score(y, pred, zero_division=0)), "precision": float(precision_score(y, pred, zero_division=0)),
            "f1": float(f1_score(y, pred, zero_division=0))}


def run(seeds=tuple(range(10)), n_boot=2000) -> dict:
    meta = json.loads(config.METADATA_PATH.read_text())
    thr = float(meta["decision_threshold"])
    raw = load_raw_data()
    with_period, consistency = add_period(raw)
    df = add_target(with_period.loc[~flag_rule_rows(raw)]).reset_index(drop=True)
    y = df[T].to_numpy()

    # ---- pooled repeated grouped CV over all employees
    oof = pooled_oof(df, list(seeds))
    rows = {}
    for name, P in oof.items():
        aps = [AP(y, p) for p in P]
        rows[name] = {"pr_auc": float(np.mean(aps)), "pr_auc_sd_over_seeds": float(np.std(aps)),
                      "roc_auc": float(np.mean([roc_auc_score(y, p) for p in P])),
                      "brier": float(np.mean([brier_score_loss(y, p) for p in P])),
                      **{k: float(np.mean([_binary_metrics(y, p, thr)[k] for p in P])) for k in ("recall", "precision", "f1")}}
    avg = {n: P.mean(axis=0) for n, P in oof.items()}
    ci, diffs = cluster_bootstrap(df, avg, [("Random Forest", REASON_ONLY), ("SVM (RBF kernel)", REASON_ONLY),
                                            ("Logistic Regression", REASON_ONLY), ("Random Forest", LOOKUP)], n_boot)
    for n in rows:
        rows[n]["pr_auc_ci95_employee_bootstrap"] = ci[n]

    # ---- calibration of the deployed model family (pooled out-of-fold, seed-averaged)
    p = avg["Random Forest"]
    q = pd.qcut(p, 8, duplicates="drop")
    cal = pd.DataFrame({"p": p, "y": y, "bin": q}).groupby("bin", observed=True).agg(
        mean_predicted=("p", "mean"), observed_rate=("y", "mean"), n=("y", "size")).reset_index(drop=True)

    # ---- time-ordered check: earlier months -> later months
    periods = sorted(df["period"].dropna().unique())
    cut = periods[int(len(periods) * config.TEMPORAL_TRAIN_FRACTION)]
    tr, te = df[df["period"] < cut], df[df["period"] >= cut]
    temporal = {"train_months": int(tr["period"].nunique()), "test_months": int(te["period"].nunique()),
                "train_rows": int(len(tr)), "test_rows": int(len(te)),
                "train_prevalence": float(tr[T].mean()), "test_prevalence": float(te[T].mean()),
                "test_employees": int(te[G].nunique()), "test_employees_also_in_train": int(len(set(tr[G]) & set(te[G]))),
                "models": {}}
    for name, pipe in get_final_shortlist().items():
        s = clone(pipe).fit(tr[F], tr[T]).predict_proba(te[F])[:, 1]
        temporal["models"][name] = {"pr_auc": float(AP(te[T], s)), "roc_auc": float(roc_auc_score(te[T], s)),
                                    **_binary_metrics(te[T].to_numpy(), s, thr)}
    temporal["note"] = ("Descriptive only: one split, and most test-period employees were also seen in training, "
                        "so this does not show performance for new employees.")

    # ---- like-for-like comparison on the original 6-employee test split (same threshold for both)
    model_df = build_modelling_dataset(raw)
    train_df, test_df = group_holdout_split(model_df)
    like = {}
    for name in ("Random Forest", REASON_ONLY):
        s = clone(get_final_shortlist()[name]).fit(train_df[F], train_df[T]).predict_proba(test_df[F])[:, 1]
        like[name] = {"pr_auc": float(AP(test_df[T], s)), **{f"at_{t}": _binary_metrics(test_df[T].to_numpy(), s, t) for t in (thr, 0.5)}}
    like["note"] = f"6 test employees, {len(test_df)} rows; both models scored at the same thresholds ({thr} and 0.5)."

    block = {
        "version": 2, "threshold_used": thr, "seeds": len(seeds), "rows": int(len(df)), "employees": int(df[G].nunique()),
        "prevalence": float(y.mean()),
        "pooled_grouped_cv": rows, "paired_pr_auc_differences": diffs, "calibration_random_forest": cal.to_dict("records"),
        "temporal_check": temporal, "original_test_split_like_for_like": like,
        "conclusion": ("The reason code carries almost all of the usable signal. Random Forest, SVM and the one-column "
                       "baselines are statistically hard to separate: the employee-level bootstrap intervals for their "
                       "PR-AUC differences include zero or are small. The deployed Random Forest is kept because nothing "
                       "here justifies replacing it, not because it is clearly better."),
        "timeline_consistency": consistency,
    }
    metrics = json.loads(config.METRICS_PATH.read_text())
    metrics["evaluation_v2"] = block
    config.METRICS_PATH.write_text(json.dumps(metrics, indent=2))
    meta["metadata_revision"] = {"revision": 2, "artifact_sha256": hashlib.sha256(config.MODEL_PATH.read_bytes()).hexdigest(), "note": ("Model artifact unchanged (v1.0.0, verified reproducible by retraining). "
                                "Evaluation extended: pooled grouped CV, temporal check; limitations updated."),
                                 "reason_code_labels": "From public UCI documentation (see src/reason_codes.py)."}
    meta["limitations"] = [
        "Only absence events are in the data; the model cannot predict whether an absence occurs.",
        "Built from 33 employees at one company; results are noisy and may not transfer to other workplaces or periods.",
        "The model is statistically hard to distinguish from a reason-code-only baseline.",
        "Reason-code labels come from public dataset documentation, not from the data file.",
        "Associations are not causes. Not for hiring, firing or disciplinary decisions."]
    config.METADATA_PATH.write_text(json.dumps(meta, indent=2))
    return block


if __name__ == "__main__":
    b = run()
    print(json.dumps({k: {m: round(v[m], 3) for m in ("pr_auc", "recall", "precision")} for k, v in b["pooled_grouped_cv"].items()}, indent=1))
    print(json.dumps(b["paired_pr_auc_differences"], indent=1))
    print(json.dumps(b["temporal_check"], indent=1))
    print(json.dumps(b["original_test_split_like_for_like"], indent=1))
