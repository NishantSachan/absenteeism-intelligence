"""
Phase 2 tests: data loading, target definition, grouped split, preprocessing.
Run from the project root with:   python -m pytest -v
"""
import numpy as np
import pandas as pd
import pytest

from src import config
from src.data_loader import add_target, build_modelling_dataset, flag_rule_rows, load_raw_data
from src.preprocessing import build_preprocessor
from src.splitting import group_holdout_split


@pytest.fixture(scope="module")
def raw_df():
    return load_raw_data()


@pytest.fixture(scope="module")
def model_df(raw_df):
    return build_modelling_dataset(raw_df)


# ---------- loading ----------
def test_raw_data_shape_and_clean_headers(raw_df):
    assert raw_df.shape == (740, 21)
    assert config.WORKLOAD in raw_df.columns          # trailing space was stripped
    assert raw_df.isna().sum().sum() == 0


def test_missing_file_gives_clear_error(tmp_path):
    with pytest.raises(FileNotFoundError, match="Dataset not found"):
        load_raw_data(tmp_path / "nope.csv")


def test_missing_column_gives_clear_error(raw_df, tmp_path):
    bad = tmp_path / "bad.csv"
    raw_df.drop(columns=[config.AGE]).to_csv(bad, index=False)
    with pytest.raises(ValueError, match="Age"):
        load_raw_data(bad)


# ---------- target and exclusion rules ----------
def test_rule_rows_are_always_zero_hours(raw_df):
    rule = flag_rule_rows(raw_df)
    assert rule.sum() == 43
    assert (raw_df.loc[rule, config.RAW_TARGET_COLUMN] == 0).all()


def test_target_threshold():
    df = pd.DataFrame({config.RAW_TARGET_COLUMN: [0, 7, 8, 9, 120]})
    assert add_target(df)[config.TARGET_COLUMN].tolist() == [0, 0, 1, 1, 1]


def test_modelling_dataset_contents(model_df):
    assert model_df.shape == (697, len(config.FEATURE_COLUMNS) + 2)
    assert set(model_df[config.TARGET_COLUMN].unique()) == {0, 1}
    assert model_df[config.GROUP_COLUMN].nunique() == 33
    # the raw target (hours) must not be among the model's columns
    assert config.RAW_TARGET_COLUMN not in model_df.columns
    assert config.RAW_TARGET_COLUMN not in config.FEATURE_COLUMNS
    assert config.GROUP_COLUMN not in config.FEATURE_COLUMNS


# ---------- grouped split ----------
def test_no_employee_in_both_train_and_test(model_df):
    train_df, test_df = group_holdout_split(model_df)
    assert set(train_df[config.GROUP_COLUMN]).isdisjoint(set(test_df[config.GROUP_COLUMN]))
    assert len(train_df) + len(test_df) == len(model_df)


def test_split_is_reproducible(model_df):
    a_train, _ = group_holdout_split(model_df)
    b_train, _ = group_holdout_split(model_df)
    pd.testing.assert_frame_equal(a_train, b_train)


def test_split_keeps_both_classes_with_similar_balance(model_df):
    train_df, test_df = group_holdout_split(model_df)
    overall = model_df[config.TARGET_COLUMN].mean()
    for part in (train_df, test_df):
        assert abs(part[config.TARGET_COLUMN].mean() - overall) < 0.10


# ---------- preprocessing ----------
def test_preprocessor_fit_on_train_only_and_shapes(model_df):
    train_df, test_df = group_holdout_split(model_df)
    pre = build_preprocessor().fit(train_df[config.FEATURE_COLUMNS])
    X_train = pre.transform(train_df[config.FEATURE_COLUMNS])
    X_test = pre.transform(test_df[config.FEATURE_COLUMNS])
    assert X_train.shape[1] == X_test.shape[1] == len(pre.get_feature_names_out())
    assert not np.isnan(X_train).any() and not np.isnan(X_test).any()
    # Scaled numeric columns: mean ~0 on TRAIN (by construction), not necessarily on test
    numeric_idx = [list(pre.get_feature_names_out()).index(c) for c in config.NUMERIC_FEATURES]
    assert np.allclose(X_train[:, numeric_idx].mean(axis=0), 0, atol=1e-8)


def test_unseen_reason_code_does_not_crash(model_df):
    train_df, _ = group_holdout_split(model_df)
    pre = build_preprocessor().fit(train_df[config.FEATURE_COLUMNS])
    row = train_df[config.FEATURE_COLUMNS].iloc[[0]].copy()
    row[config.REASON] = 99                      # a code the model never saw
    assert pre.transform(row).shape[0] == 1


def test_id_is_never_passed_to_model(model_df):
    pre = build_preprocessor().fit(model_df[config.FEATURE_COLUMNS + [config.GROUP_COLUMN]])
    assert not any(config.GROUP_COLUMN in name for name in pre.get_feature_names_out())
