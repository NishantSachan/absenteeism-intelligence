"""
evaluate.py - metrics and cross-validation helpers shared by notebooks and training.

METRICS (positive class = long absence, 8+ hours)
  precision        of the absences we flag as long, how many really are
  recall           of the truly long absences, how many we catch  <- missing one is the costly error
  f1               balance of precision and recall
  balanced_acc     average of recall on each class (fair when classes are unequal)
  roc_auc          ranking quality across all thresholds
  pr_auc           (average precision) ranking quality focused on the long class;
                   our main model-selection metric because it ignores the easy negatives
  accuracy         reported for completeness only
Threshold-free scores (roc_auc, pr_auc) use predict_proba or decision_function.
"""
from typing import Dict, Iterable, List, Optional

import numpy as np
import pandas as pd
from sklearn.base import clone
from sklearn.metrics import (accuracy_score, average_precision_score, balanced_accuracy_score,
                             f1_score, precision_score, recall_score, roc_auc_score)
from sklearn.model_selection import StratifiedGroupKFold, StratifiedKFold

from src import config

METRIC_NAMES = ["pr_auc", "roc_auc", "recall", "precision", "f1", "balanced_acc", "accuracy"]


def get_scores(fitted_model, X) -> np.ndarray:
    """Continuous score for the positive class (probability if available)."""
    if hasattr(fitted_model, "predict_proba"):
        return fitted_model.predict_proba(X)[:, 1]
    return fitted_model.decision_function(X)   # e.g. SVC without probability=True


def compute_metrics(y_true, y_pred, y_score) -> Dict[str, float]:
    """All metrics for one set of predictions. zero_division=0 avoids warnings when
    a model predicts no positives (e.g. the majority-class baseline)."""
    return {
        "pr_auc": average_precision_score(y_true, y_score),
        "roc_auc": roc_auc_score(y_true, y_score),
        "recall": recall_score(y_true, y_pred, zero_division=0),
        "precision": precision_score(y_true, y_pred, zero_division=0),
        "f1": f1_score(y_true, y_pred, zero_division=0),
        "balanced_acc": balanced_accuracy_score(y_true, y_pred),
        "accuracy": accuracy_score(y_true, y_pred),
    }


def cross_validate(pipeline, X: pd.DataFrame, y: pd.Series, groups: pd.Series,
                   grouped: bool = True, n_splits: int = 5,
                   seeds: Iterable[int] = (0, 1, 2, 3, 4)) -> pd.DataFrame:
    """Repeated cross-validation; returns one row of metrics per fold.

    grouped=True  : StratifiedGroupKFold - an employee is never in train and validation
                    together. This is the honest estimate for NEW employees.
    grouped=False : ordinary stratified row-level folds. Only used to demonstrate how
                    optimistic a random split would be.
    Each repeat uses a different seed so the result does not hinge on one lucky split.
    """
    rows = []
    for seed in seeds:
        if grouped:
            splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
            splits = splitter.split(X, y, groups=groups)
        else:
            splits = StratifiedKFold(n_splits=n_splits, shuffle=True, random_state=seed).split(X, y)
        for fold, (train_idx, valid_idx) in enumerate(splits):
            model = clone(pipeline)                       # fresh, unfitted copy every fold
            model.fit(X.iloc[train_idx], y.iloc[train_idx])
            y_pred = model.predict(X.iloc[valid_idx])
            y_score = get_scores(model, X.iloc[valid_idx])
            row = compute_metrics(y.iloc[valid_idx], y_pred, y_score)
            row.update({"seed": seed, "fold": fold})
            rows.append(row)
    return pd.DataFrame(rows)


def summarize(fold_results: pd.DataFrame) -> pd.Series:
    """Mean and standard deviation of every metric across folds, as 'mean ± std'."""
    mean, std = fold_results[METRIC_NAMES].mean(), fold_results[METRIC_NAMES].std()
    return pd.Series({m: f"{mean[m]:.3f} ± {std[m]:.3f}" for m in METRIC_NAMES})


def nested_cv_tuning(pipeline, param_grid: dict, X: pd.DataFrame, y: pd.Series, groups: pd.Series,
                     seeds: Iterable[int] = (0, 1), outer_splits: int = 5, inner_splits: int = 3):
    """Honest estimate of a TUNED model's performance (nested cross-validation).

    Outer loop : grouped folds that act as unseen employees.
    Inner loop : on each outer-training part only, GridSearchCV picks hyperparameters
                 using grouped folds and PR-AUC. The outer validation fold is never
                 used for picking, so tuning cannot leak into the reported score.
    Returns (fold_metrics DataFrame, DataFrame of the hyperparameters chosen per fold).
    """
    from sklearn.model_selection import GridSearchCV  # local import: only needed here

    rows, chosen = [], []
    for seed in seeds:
        outer = StratifiedGroupKFold(n_splits=outer_splits, shuffle=True, random_state=seed)
        for train_idx, valid_idx in outer.split(X, y, groups=groups):
            search = GridSearchCV(
                clone(pipeline), param_grid, scoring="average_precision",
                cv=StratifiedGroupKFold(n_splits=inner_splits, shuffle=True, random_state=seed),
            )
            search.fit(X.iloc[train_idx], y.iloc[train_idx], groups=groups.iloc[train_idx])
            best = search.best_estimator_
            rows.append(compute_metrics(y.iloc[valid_idx], best.predict(X.iloc[valid_idx]),
                                        get_scores(best, X.iloc[valid_idx])))
            chosen.append({k.replace("model__", ""): v for k, v in search.best_params_.items()})
    return pd.DataFrame(rows), pd.DataFrame(chosen)


def paired_difference(results_a: pd.DataFrame, results_b: pd.DataFrame, metric: str = "pr_auc") -> dict:
    """Compare two models fold-by-fold. Both must come from cross_validate() with the
    same seeds, so row i of each is the SAME validation employees.
    Returns the mean difference (A - B), its spread, and how often A beat B."""
    diff = results_a[metric].to_numpy() - results_b[metric].to_numpy()
    return {"mean_diff": diff.mean(), "std_diff": diff.std(ddof=1),
            "A_wins_share": float((diff > 0).mean()), "ties_share": float((diff == 0).mean()),
            "n_folds": len(diff)}


# ============================================================================
# Phase 4 helpers: out-of-fold probabilities, calibration, thresholds, uncertainty
# ============================================================================
def calibration_metrics(y_true, proba) -> Dict[str, float]:
    """Brier score (mean squared error of the probability; lower is better, 0.24 = no skill
    at ~40% prevalence) and log loss (punishes confident mistakes)."""
    from sklearn.metrics import brier_score_loss, log_loss
    clipped = np.clip(proba, 1e-6, 1 - 1e-6)
    return {"brier": brier_score_loss(y_true, proba), "log_loss": log_loss(y_true, clipped)}


def threshold_table(y_true, proba, thresholds: Iterable[float]) -> pd.DataFrame:
    """What each possible cut-off would do: recall, precision, F1, F2 (recall counts more),
    and the share of absences flagged as 'long'."""
    from sklearn.metrics import fbeta_score
    y_true, proba = np.asarray(y_true), np.asarray(proba)
    rows = []
    for t in thresholds:
        pred = (proba >= t).astype(int)
        rows.append({"threshold": round(float(t), 3),
                     "recall": recall_score(y_true, pred, zero_division=0),
                     "precision": precision_score(y_true, pred, zero_division=0),
                     "f1": f1_score(y_true, pred, zero_division=0),
                     "f2": fbeta_score(y_true, pred, beta=2, zero_division=0),
                     "share_flagged": pred.mean()})
    return pd.DataFrame(rows)


def group_bootstrap_ci(y_true, y_pred, y_score, groups, n_boot: int = 2000, seed: int = 0,
                       metrics=("pr_auc", "recall", "precision", "f1", "accuracy")) -> pd.DataFrame:
    """95% interval for test metrics, resampling EMPLOYEES (not rows) with replacement.
    Rows of one employee are correlated, so resampling rows would give intervals that are
    far too narrow. Resamples that contain only one class are skipped."""
    y_true, y_pred, y_score = map(np.asarray, (y_true, y_pred, y_score))
    groups = np.asarray(groups)
    unique = np.unique(groups)
    index_by_group = {g: np.where(groups == g)[0] for g in unique}
    rng = np.random.default_rng(seed)
    draws = []
    for _ in range(n_boot):
        picked = rng.choice(unique, size=len(unique), replace=True)
        idx = np.concatenate([index_by_group[g] for g in picked])
        if len(np.unique(y_true[idx])) < 2:
            continue
        draws.append(compute_metrics(y_true[idx], y_pred[idx], y_score[idx]))
    draws = pd.DataFrame(draws)[list(metrics)]
    return pd.DataFrame({"2.5%": draws.quantile(0.025), "median": draws.median(),
                         "97.5%": draws.quantile(0.975), "resamples_used": len(draws)})


def grouped_permutation_importance(pipeline, X: pd.DataFrame, y: pd.Series, groups: pd.Series,
                                   seeds=(0, 1, 2), n_repeats: int = 10) -> pd.DataFrame:
    """How much does PR-AUC drop on UNSEEN employees when one input is shuffled?
    Bigger drop = the model relies on that input more. Computed on validation folds only."""
    rng = np.random.default_rng(0)
    drops = {col: [] for col in X.columns}
    for seed in seeds:
        splitter = StratifiedGroupKFold(n_splits=5, shuffle=True, random_state=seed)
        for train_idx, valid_idx in splitter.split(X, y, groups=groups):
            model = clone(pipeline).fit(X.iloc[train_idx], y.iloc[train_idx])
            X_valid, y_valid = X.iloc[valid_idx], y.iloc[valid_idx]
            base = average_precision_score(y_valid, model.predict_proba(X_valid)[:, 1])
            for col in X.columns:
                for _ in range(n_repeats):
                    shuffled = X_valid.copy()
                    shuffled[col] = rng.permutation(shuffled[col].to_numpy())
                    drops[col].append(base - average_precision_score(
                        y_valid, model.predict_proba(shuffled)[:, 1]))
    return pd.DataFrame({"mean PR-AUC drop": {c: np.mean(v) for c, v in drops.items()},
                         "std": {c: np.std(v) for c, v in drops.items()}}).sort_values(
                             "mean PR-AUC drop", ascending=False)


# ----------------------------------------------------------------------------
# Phase 4 helpers: out-of-fold probabilities, calibration, bootstrap uncertainty
# ----------------------------------------------------------------------------
from sklearn.metrics import brier_score_loss, log_loss  # noqa: E402


def out_of_fold_probabilities(pipeline, X: pd.DataFrame, y: pd.Series, groups: pd.Series,
                              seeds: Iterable[int] = (0, 1, 2, 3, 4), n_splits: int = 5) -> np.ndarray:
    """Probability of 'long absence' for every training row, each predicted by a model
    that never saw that row's EMPLOYEE. Shape: (number of seeds, number of rows).

    These honest predictions are what we use to compare models, check calibration and
    choose the decision threshold, all without touching the test set.
    """
    seeds = list(seeds)
    out = np.zeros((len(seeds), len(X)))
    for s, seed in enumerate(seeds):
        splitter = StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=seed)
        for train_idx, valid_idx in splitter.split(X, y, groups=groups):
            model = clone(pipeline).fit(X.iloc[train_idx], y.iloc[train_idx])
            out[s, valid_idx] = model.predict_proba(X.iloc[valid_idx])[:, 1]
    return out


def expected_calibration_error(y_true, y_prob, n_bins: int = 10) -> float:
    """Average gap between predicted probability and observed long-absence rate,
    weighted by how many rows fall in each probability bin (0 = perfectly calibrated)."""
    y_true, y_prob = np.asarray(y_true), np.asarray(y_prob)
    edges = np.linspace(0, 1, n_bins + 1)
    bin_ids = np.clip(np.digitize(y_prob, edges[1:-1]), 0, n_bins - 1)
    ece = 0.0
    for b in range(n_bins):
        in_bin = bin_ids == b
        if in_bin.any():
            ece += in_bin.mean() * abs(y_prob[in_bin].mean() - y_true[in_bin].mean())
    return float(ece)


def summarize_oof(oof: np.ndarray, y_true) -> Dict[str, float]:
    """Metrics of pooled out-of-fold predictions, averaged over seeds (std across seeds)."""
    y_true = np.asarray(y_true)
    per_seed = [{
        "pr_auc": average_precision_score(y_true, p), "roc_auc": roc_auc_score(y_true, p),
        "brier": brier_score_loss(y_true, p), "log_loss": log_loss(y_true, np.clip(p, 1e-6, 1 - 1e-6)),
        "ece": expected_calibration_error(y_true, p),
    } for p in oof]
    df = pd.DataFrame(per_seed)
    out = {f"{k}": float(df[k].mean()) for k in df}
    out.update({f"{k}_std": float(df[k].std(ddof=1)) for k in df})
    return out


def threshold_cost_curve(oof: np.ndarray, y_true, cost_ratio: float,
                         thresholds: Optional[np.ndarray] = None) -> pd.DataFrame:
    """Expected cost per 100 absences at each threshold.
    cost = false_positives + cost_ratio * false_negatives (a false alarm costs 1)."""
    y_true = np.asarray(y_true)
    thresholds = np.round(np.arange(0.05, 0.96, 0.01), 2) if thresholds is None else thresholds
    rows = []
    for t in thresholds:
        costs, recalls, precisions = [], [], []
        for p in oof:
            pred = (p >= t).astype(int)
            fp = int(((pred == 1) & (y_true == 0)).sum()); fn = int(((pred == 0) & (y_true == 1)).sum())
            costs.append((fp + cost_ratio * fn) / len(y_true) * 100)
            recalls.append(recall_score(y_true, pred, zero_division=0))
            precisions.append(precision_score(y_true, pred, zero_division=0))
        rows.append({"threshold": t, "cost_per_100": np.mean(costs),
                     "recall": np.mean(recalls), "precision": np.mean(precisions)})
    return pd.DataFrame(rows)


def cluster_bootstrap_ci(y_true, y_score, threshold: float, groups, n_boot: int = 2000,
                         seed: int = 0) -> Dict[str, tuple]:
    """95% interval for test metrics by resampling whole EMPLOYEES (not rows).

    Resampling rows would treat one employee's many rows as independent evidence and give
    falsely narrow intervals. With very few test employees this interval will be wide;
    that width is an honest statement of the uncertainty, not a flaw to hide.
    """
    y_true, y_score, groups = np.asarray(y_true), np.asarray(y_score), np.asarray(groups)
    rng = np.random.default_rng(seed)
    ids = np.unique(groups)
    rows_of = {g: np.where(groups == g)[0] for g in ids}
    collected = {"pr_auc": [], "recall": [], "precision": [], "f1": [], "accuracy": []}
    for _ in range(n_boot):
        sample = rng.choice(ids, size=len(ids), replace=True)
        idx = np.concatenate([rows_of[g] for g in sample])
        yt, ys = y_true[idx], y_score[idx]
        if yt.min() == yt.max():          # one class only: PR-AUC undefined, skip this resample
            continue
        yp = (ys >= threshold).astype(int)
        collected["pr_auc"].append(average_precision_score(yt, ys))
        collected["recall"].append(recall_score(yt, yp, zero_division=0))
        collected["precision"].append(precision_score(yt, yp, zero_division=0))
        collected["f1"].append(f1_score(yt, yp, zero_division=0))
        collected["accuracy"].append(accuracy_score(yt, yp))
    return {k: (float(np.percentile(v, 2.5)), float(np.percentile(v, 97.5)), len(v))
            for k, v in collected.items()}
