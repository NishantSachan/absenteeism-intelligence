"""
Phase 3 tests: metrics, grouped cross-validation, candidate models.
Run from the project root:  python -m pytest -v
"""
import numpy as np
import pandas as pd
import pytest

from src import config
from src.data_loader import build_modelling_dataset, load_raw_data
from src.evaluate import METRIC_NAMES, compute_metrics, cross_validate, paired_difference
from src.models import get_candidate_models
from src.splitting import group_holdout_split


@pytest.fixture(scope="module")
def train_df():
    model_df = build_modelling_dataset(load_raw_data())
    return group_holdout_split(model_df)[0]


def test_compute_metrics_known_values():
    y_true = np.array([1, 1, 0, 0])
    y_pred = np.array([1, 0, 0, 0])            # catches 1 of 2 long absences, no false alarms
    y_score = np.array([0.9, 0.4, 0.3, 0.1])   # perfect ranking
    m = compute_metrics(y_true, y_pred, y_score)
    assert m["recall"] == 0.5 and m["precision"] == 1.0 and m["accuracy"] == 0.75
    assert m["roc_auc"] == 1.0 and m["pr_auc"] == 1.0
    assert set(METRIC_NAMES) == set(m)


def test_all_candidates_fit_on_raw_dataframe_and_predict_binary(train_df):
    X, y = train_df[config.FEATURE_COLUMNS], train_df[config.TARGET_COLUMN]
    models = get_candidate_models()
    assert len(models) == 8
    for name, pipe in models.items():
        pipe.fit(X, y)
        pred = pipe.predict(X.iloc[:20])
        assert set(np.unique(pred)) <= {0, 1}, name


def test_majority_baseline_never_predicts_long(train_df):
    X, y = train_df[config.FEATURE_COLUMNS], train_df[config.TARGET_COLUMN]
    pipe = get_candidate_models()["Baseline: majority class"].fit(X, y)
    assert pipe.predict(X).sum() == 0


def test_grouped_cv_has_no_employee_overlap(train_df):
    """Re-create the grouped folds and confirm employees never straddle train/validation."""
    from sklearn.model_selection import StratifiedGroupKFold
    X, y, g = train_df[config.FEATURE_COLUMNS], train_df[config.TARGET_COLUMN], train_df[config.GROUP_COLUMN]
    for tr_idx, va_idx in StratifiedGroupKFold(5, shuffle=True, random_state=0).split(X, y, groups=g):
        assert set(g.iloc[tr_idx]).isdisjoint(set(g.iloc[va_idx]))


def test_cross_validate_output_shape(train_df):
    X, y, g = train_df[config.FEATURE_COLUMNS], train_df[config.TARGET_COLUMN], train_df[config.GROUP_COLUMN]
    pipe = get_candidate_models()["Logistic Regression"]
    result = cross_validate(pipe, X, y, g, seeds=(0, 1))
    assert len(result) == 10                       # 2 seeds x 5 folds
    assert result[METRIC_NAMES].notna().all().all()
    assert result["pr_auc"].between(0, 1).all()


def test_paired_difference_identical_results_is_zero(train_df):
    X, y, g = train_df[config.FEATURE_COLUMNS], train_df[config.TARGET_COLUMN], train_df[config.GROUP_COLUMN]
    r = cross_validate(get_candidate_models()["Logistic Regression"], X, y, g, seeds=(0,))
    out = paired_difference(r, r)
    assert out["mean_diff"] == 0 and out["ties_share"] == 1.0


def test_extra_columns_do_not_change_rows_or_split():
    raw = load_raw_data()
    base = build_modelling_dataset(raw)
    extra = build_modelling_dataset(raw, extra_columns=config.PERIOD_FEATURES)
    assert len(base) == len(extra)
    assert set(config.PERIOD_FEATURES) <= set(extra.columns)
    a_train, _ = group_holdout_split(base)
    b_train, _ = group_holdout_split(extra)
    assert a_train[config.GROUP_COLUMN].tolist() == b_train[config.GROUP_COLUMN].tolist()
