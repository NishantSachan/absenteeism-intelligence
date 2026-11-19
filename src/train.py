"""
train.py - Phase 4: select the final model, choose its threshold, test it ONCE, and save it.

Run from the project root:   python -m src.train        (takes a few minutes)

The script is deliberately a straight line of numbered steps so each can be explained:

  1. Load data and split by employee (test employees are set aside).
  2. Compare the shortlist with out-of-fold predictions on TRAINING employees only.
  3. Apply the pre-declared selection rule (config.SELECTION_*) to choose ONE model.
  4. Choose the decision threshold from out-of-fold predictions (cost-based).
  5. >>> ONLY NOW evaluate on the held-out test employees, once. <<<
  6. Explain the model (permutation importance, predicted vs observed rate per reason).
  7. Refit the chosen model on ALL employees and save it with its metadata.

Nothing after step 5 is allowed to change the choices made in steps 3-4.
"""
import json
import platform
import sys
from datetime import datetime, timezone

import joblib
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import numpy as np
import pandas as pd
import sklearn
from sklearn.base import clone
from sklearn.calibration import calibration_curve
from sklearn.inspection import permutation_importance
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                             brier_score_loss, confusion_matrix, f1_score, precision_score,
                             recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedGroupKFold

from src import config
from src.data_loader import build_modelling_dataset, load_raw_data
from src.evaluate import (cluster_bootstrap_ci, expected_calibration_error,
                          out_of_fold_probabilities, summarize_oof, threshold_cost_curve)
from src.models import SIMPLICITY_ORDER, get_final_shortlist
from src.splitting import group_holdout_split

TABLES_DIR = config.PROJECT_ROOT / "reports" / "tables"


def header(text):
    print("\n" + "=" * 78 + f"\n{text}\n" + "=" * 78, flush=True)


def apply_selection_rule(oof_table: pd.DataFrame):
    """Pre-declared rule: within tolerance of the best on PR-AUC AND Brier -> pick the simplest."""
    best_pr, best_brier = oof_table["pr_auc"].max(), oof_table["brier"].min()
    eligible = oof_table[(oof_table["pr_auc"] >= best_pr - config.SELECTION_PR_AUC_TOLERANCE)
                         & (oof_table["brier"] <= best_brier + config.SELECTION_BRIER_TOLERANCE)]
    for name in SIMPLICITY_ORDER:               # simplest first
        if name in eligible.index:
            return name, list(eligible.index)
    raise RuntimeError("No model satisfied the selection rule.")


def test_metrics(y_true, y_score, threshold):
    y_pred = (y_score >= threshold).astype(int)
    tn, fp, fn, tp = confusion_matrix(y_true, y_pred, labels=[0, 1]).ravel()
    return {"pr_auc": average_precision_score(y_true, y_score), "roc_auc": roc_auc_score(y_true, y_score),
            "recall": recall_score(y_true, y_pred, zero_division=0),
            "precision": precision_score(y_true, y_pred, zero_division=0),
            "f1": f1_score(y_true, y_pred, zero_division=0),
            "balanced_acc": balanced_accuracy_score(y_true, y_pred), "accuracy": accuracy_score(y_true, y_pred),
            "brier": brier_score_loss(y_true, y_score), "ece": expected_calibration_error(y_true, y_score),
            "tn": int(tn), "fp": int(fp), "fn": int(fn), "tp": int(tp)}


def to_py(obj):
    """Make numpy types JSON-serialisable."""
    if isinstance(obj, dict):
        return {str(k): to_py(v) for k, v in obj.items()}
    if isinstance(obj, (list, tuple)):
        return [to_py(v) for v in obj]
    if isinstance(obj, (np.integer,)):
        return int(obj)
    if isinstance(obj, (np.floating,)):
        return float(obj)
    return obj


def main():
    config.MODELS_DIR.mkdir(exist_ok=True)
    config.FIGURES_DIR.mkdir(parents=True, exist_ok=True)
    TABLES_DIR.mkdir(parents=True, exist_ok=True)
    feats = config.FINAL_FEATURE_COLUMNS

    # ---------------------------------------------------------------- 1. data
    header("1. Data and employee-grouped split")
    model_df = build_modelling_dataset(load_raw_data())
    train_df, test_df = group_holdout_split(model_df)
    X_tr, y_tr, g_tr = train_df[feats], train_df[config.TARGET_COLUMN], train_df[config.GROUP_COLUMN]
    print(f"train: {len(train_df)} rows / {g_tr.nunique()} employees | "
          f"test (locked): {len(test_df)} rows / {test_df[config.GROUP_COLUMN].nunique()} employees")

    # ---------------------------------------------------- 2. compare shortlist
    header("2. Shortlist compared with out-of-fold predictions (training employees only)")
    shortlist = get_final_shortlist()
    oof = {name: out_of_fold_probabilities(pipe, X_tr, y_tr, g_tr) for name, pipe in shortlist.items()}
    oof_table = pd.DataFrame({n: summarize_oof(p, y_tr) for n, p in oof.items()}).T
    oof_table.round(4).to_csv(TABLES_DIR / "final_shortlist_oof.csv")
    print(oof_table[["pr_auc", "roc_auc", "brier", "log_loss", "ece"]].round(3).to_string())

    # ---------------------------------------------------- 3. selection rule
    header("3. Selection rule (declared in config.py before the test set was used)")
    chosen_name, eligible = apply_selection_rule(oof_table)
    print(f"Tolerances: PR-AUC {config.SELECTION_PR_AUC_TOLERANCE}, Brier {config.SELECTION_BRIER_TOLERANCE}")
    print(f"Eligible models: {eligible}")
    print(f"CHOSEN (simplest eligible): {chosen_name}")

    # ---------------------------------------------------- 4. threshold
    header("4. Decision threshold from out-of-fold predictions")
    ratio = config.FN_TO_FP_COST_RATIO
    curve = threshold_cost_curve(oof[chosen_name], y_tr, ratio)
    best_row = curve.loc[curve["cost_per_100"].idxmin()]
    threshold = float(best_row["threshold"])
    print(f"Assumed cost ratio (missed long absence : false alarm) = {ratio}:1")
    print(f"Chosen threshold = {threshold:.2f}  -> OOF recall {best_row['recall']:.3f}, "
          f"precision {best_row['precision']:.3f}, cost/100 {best_row['cost_per_100']:.1f}")
    sens = {}
    for r in (1.0, 2.0, 3.0):
        c = threshold_cost_curve(oof[chosen_name], y_tr, r)
        sens[str(r)] = float(c.loc[c["cost_per_100"].idxmin(), "threshold"])
    print("Threshold under other cost ratios (sensitivity):", sens)
    print("Reference: threshold 0.50 -> recall "
          f"{curve.loc[curve.threshold == 0.5, 'recall'].iloc[0]:.3f}, precision "
          f"{curve.loc[curve.threshold == 0.5, 'precision'].iloc[0]:.3f}")
    curve.round(4).to_csv(TABLES_DIR / "final_threshold_curve.csv", index=False)

    # ---------------------------------------------------- 5. TEST (once)
    header("5. FINAL EVALUATION on held-out test employees (used once)")
    X_te, y_te, g_te = test_df[feats], test_df[config.TARGET_COLUMN], test_df[config.GROUP_COLUMN]
    fitted = clone(shortlist[chosen_name]).fit(X_tr, y_tr)
    score_te = fitted.predict_proba(X_te)[:, 1]
    chosen_test = test_metrics(y_te.to_numpy(), score_te, threshold)

    comparators = {}
    for name in ("Reason-only baseline (LR)",):
        m = clone(shortlist[name]).fit(X_tr, y_tr)
        comparators[name] = test_metrics(y_te.to_numpy(), m.predict_proba(X_te)[:, 1], 0.5)
    majority_pred_rate = float(y_te.mean())
    comparators["Majority class (always 'short')"] = {
        "pr_auc": majority_pred_rate, "recall": 0.0, "precision": 0.0, "f1": 0.0,
        "accuracy": 1 - majority_pred_rate}
    ci = cluster_bootstrap_ci(y_te.to_numpy(), score_te, threshold, g_te.to_numpy())
    test_table = pd.DataFrame({chosen_name: chosen_test, **comparators}).T
    test_table.round(3).to_csv(TABLES_DIR / "final_test_results.csv")
    print(test_table[["pr_auc", "recall", "precision", "f1", "accuracy"]].round(3).to_string())
    print(f"\nConfusion matrix for {chosen_name} at threshold {threshold:.2f}: "
          f"TN={chosen_test['tn']} FP={chosen_test['fp']} FN={chosen_test['fn']} TP={chosen_test['tp']}")
    print(f"Brier {chosen_test['brier']:.3f} | ECE {chosen_test['ece']:.3f}")
    print("95% employee-level bootstrap intervals (6 test employees -> expect WIDE):")
    for k, (lo, hi, n) in ci.items():
        print(f"   {k:10s} [{lo:.3f}, {hi:.3f}]  (valid resamples: {n})")
    per_emp = pd.DataFrame({"employee": g_te, "y": y_te, "pred": (score_te >= threshold).astype(int)}) \
        .groupby("employee").agg(rows=("y", "size"), long_share=("y", "mean"),
                                 accuracy=("pred", lambda s: np.nan))
    for emp, grp in pd.DataFrame({"employee": g_te, "y": y_te, "pred": (score_te >= threshold).astype(int)}).groupby("employee"):
        per_emp.loc[emp, "accuracy"] = (grp["y"] == grp["pred"]).mean()
    print("\nPer test employee:\n", per_emp.round(2).to_string())
    per_emp.round(3).to_csv(TABLES_DIR / "final_test_per_employee.csv")

    # ---------------------------------------------------- 6. explanations
    header("6. Explanations")
    # 6a. permutation importance on validation folds (grouped), averaged over folds
    importances = []
    for tr_idx, va_idx in StratifiedGroupKFold(5, shuffle=True, random_state=0).split(X_tr, y_tr, groups=g_tr):
        m = clone(shortlist[chosen_name]).fit(X_tr.iloc[tr_idx], y_tr.iloc[tr_idx])
        pi = permutation_importance(m, X_tr.iloc[va_idx], y_tr.iloc[va_idx], scoring="average_precision",
                                    n_repeats=10, random_state=0)
        importances.append(pi.importances_mean)
    imp = pd.Series(np.mean(importances, axis=0), index=feats, name="PR-AUC drop when shuffled").sort_values()
    print(imp.round(3).to_string())
    imp.round(4).to_csv(TABLES_DIR / "final_permutation_importance.csv")
    fig, ax = plt.subplots(figsize=(7, 3)); imp.plot.barh(ax=ax, color="#4C72B0")
    ax.set_xlabel("Drop in PR-AUC when the feature is shuffled (validation folds)")
    ax.set_title("What the final model relies on"); plt.tight_layout()
    plt.savefig(config.FIGURES_DIR / "16_final_permutation_importance.png", dpi=130); plt.close()

    # ---------------------------------------------------- 7. refit and save
    header("7. Refit on ALL employees and save")
    final_pipeline = clone(shortlist[chosen_name]).fit(model_df[feats], model_df[config.TARGET_COLUMN])

    # 6b. model-implied vs observed long-absence share per reason (illustration, uses final model)
    reasons = sorted(model_df[config.REASON].unique())
    grid = pd.DataFrame([(r, m, d) for r in reasons for m in range(1, 13) for d in range(2, 7)], columns=feats)
    grid["p"] = final_pipeline.predict_proba(grid)[:, 1]
    implied = grid.groupby(config.REASON)["p"].mean()
    obs = model_df.groupby(config.REASON)[config.TARGET_COLUMN].agg(["mean", "count"])
    cmp = pd.DataFrame({"observed_long_share": obs["mean"], "model_average_probability": implied, "records": obs["count"]})
    cmp.round(3).to_csv(TABLES_DIR / "final_reason_observed_vs_model.csv")
    big = cmp[cmp.records >= 10]
    fig, ax = plt.subplots(figsize=(11, 4)); x = np.arange(len(big))
    ax.bar(x - 0.2, big.observed_long_share * 100, 0.4, label="observed in data", color="#C44E52")
    ax.bar(x + 0.2, big.model_average_probability * 100, 0.4, label="model (average over months/days)", color="#4C72B0")
    ax.set_xticks(x); ax.set_xticklabels(big.index); ax.set_xlabel("Reason for absence (codes with >=10 records)")
    ax.set_ylabel("% long absences"); ax.set_title("Final model vs observed long-absence share by reason (illustration)")
    ax.legend(); plt.tight_layout(); plt.savefig(config.FIGURES_DIR / "17_final_reason_observed_vs_model.png", dpi=130); plt.close()

    # calibration plot (out-of-fold, seed 0)
    fig, ax = plt.subplots(figsize=(5.5, 5)); ax.plot([0, 1], [0, 1], "k--", label="perfectly calibrated")
    for name, p in oof.items():
        frac, mean_pred = calibration_curve(y_tr, p[0], n_bins=6, strategy="quantile")
        ax.plot(mean_pred, frac, marker="o", label=name)
    ax.set_xlabel("Predicted probability"); ax.set_ylabel("Observed long-absence share")
    ax.set_title("Calibration (out-of-fold, training employees)"); ax.legend(fontsize=7)
    plt.tight_layout(); plt.savefig(config.FIGURES_DIR / "14_final_calibration.png", dpi=130); plt.close()
    # threshold curve plot
    fig, ax = plt.subplots(figsize=(7, 4))
    for r in (1.0, 2.0, 3.0):
        c = threshold_cost_curve(oof[chosen_name], y_tr, r); ax.plot(c.threshold, c.cost_per_100, label=f"cost ratio {r:g}:1")
    ax.axvline(threshold, color="black", ls="--", label=f"chosen threshold {threshold:.2f}")
    ax.set_xlabel("Decision threshold"); ax.set_ylabel("Expected cost per 100 absences")
    ax.set_title("Choosing the threshold (out-of-fold)"); ax.legend(); plt.tight_layout()
    plt.savefig(config.FIGURES_DIR / "15_final_threshold_cost.png", dpi=130); plt.close()

    # ---------------------------------------------------- metadata
    schema = {
        config.REASON: {"type": "integer code", "allowed": sorted(int(v) for v in reasons),
                        "note": "Code 0 is outside the model's scope (always 0 hours in the data)."},
        config.MONTH: {"type": "integer code", "allowed": list(range(1, 13))},
        config.DAY_OF_WEEK: {"type": "integer code", "allowed": sorted(int(v) for v in model_df[config.DAY_OF_WEEK].unique())},
    }
    metadata = {
        "model_name": chosen_name, "model_version": config.MODEL_VERSION,
        "created_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "task": "Predict whether a reported absence will last 8 hours or more",
        "target": {"column": config.TARGET_COLUMN, "definition": f"{config.RAW_TARGET_COLUMN} >= {config.LONG_ABSENCE_THRESHOLD_HOURS}",
                   "class_labels": {"0": "short (<8 hours)", "1": "long (8+ hours)"}},
        "feature_columns": feats, "input_schema": schema,
        "decision_threshold": threshold, "threshold_rule": f"minimise FP + {ratio} x FN on out-of-fold predictions",
        "assumed_fn_to_fp_cost_ratio": ratio, "threshold_sensitivity": sens,
        "training": {"rows_used_for_deployed_model": int(len(model_df)), "employees": int(model_df[config.GROUP_COLUMN].nunique()),
                     "note": "Deployed model is refit on train+test employees; reported test metrics come from the train-only version."},
        "library_versions": {"python": platform.python_version(), "scikit-learn": sklearn.__version__,
                             "numpy": np.__version__, "pandas": pd.__version__},
        "probability_note": "Probabilities are the model's raw estimates; see calibration metrics in metrics.json.",
        "limitations": ["Only absence events are in the data; the model cannot predict whether an absence occurs.",
                        "Built from 33 employees; results are noisy and may not transfer to other workplaces.",
                        "Reason-code meanings are not documented in the dataset.",
                        "Not for hiring, firing or disciplinary decisions."],
    }
    metrics = {"shortlist_oof": oof_table.to_dict(orient="index"), "selection": {"eligible": eligible, "chosen": chosen_name},
               "threshold": {"chosen": threshold, "oof_recall": float(best_row["recall"]), "oof_precision": float(best_row["precision"]),
                             "sensitivity": sens},
               "test": {"chosen_model": chosen_test, "bootstrap_95ci": {k: [v[0], v[1]] for k, v in ci.items()},
                        "comparators": comparators, "test_rows": int(len(test_df)),
                        "test_employees": int(g_te.nunique())},
               "permutation_importance": imp.to_dict()}
    joblib.dump(final_pipeline, config.MODEL_PATH)
    config.METADATA_PATH.write_text(json.dumps(to_py(metadata), indent=2))
    config.METRICS_PATH.write_text(json.dumps(to_py(metrics), indent=2))
    print(f"Saved: {config.MODEL_PATH.name}, {config.METADATA_PATH.name}, {config.METRICS_PATH.name}")
    print("Done.")


if __name__ == "__main__":
    main()
