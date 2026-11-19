"""
data_loader.py - load the raw CSV, validate it, and build the modelling dataset.

Responsibilities (and nothing else):
  1. Read the CSV and clean column names.
  2. Check the expected columns exist (fail early with a clear message).
  3. Apply the documented modelling rules (exclude rule rows, create the target).
Splitting lives in splitting.py; encoding/scaling lives in preprocessing.py.
"""
from pathlib import Path
from typing import List, Optional

import pandas as pd

from src import config


def load_raw_data(path: Path = config.RAW_DATA_PATH) -> pd.DataFrame:
    """Read the raw CSV and validate its columns.

    Raises FileNotFoundError / ValueError with an actionable message instead of
    letting pandas fail later with something cryptic.
    """
    path = Path(path)
    if not path.exists():
        raise FileNotFoundError(
            f"Dataset not found at {path}. Copy Absenteeism_at_work.csv into data/raw/."
        )

    df = pd.read_csv(path)
    # The raw header has a trailing space after 'Work load Average/day'.
    df.columns = df.columns.str.strip()

    missing = [c for c in config.EXPECTED_RAW_COLUMNS if c not in df.columns]
    if missing:
        raise ValueError(f"Dataset is missing expected columns: {missing}")
    return df


def flag_rule_rows(df: pd.DataFrame) -> pd.Series:
    """Boolean mask: rows whose outcome is fixed by a rule (always 0 hours).

    Evidence (EDA section 4): every row with Reason == 0 or Disciplinary
    failure == 1 has an absence of 0 hours. A model would learn this trivial
    rule and look accurate without learning anything about real absences.
    """
    return (df[config.REASON] == config.RULE_REASON_CODE) | (
        df[config.DISCIPLINARY_FAILURE] == config.RULE_DISCIPLINARY_VALUE
    )


def add_target(df: pd.DataFrame) -> pd.DataFrame:
    """Return a copy with the binary target: 1 if hours >= threshold, else 0."""
    out = df.copy()
    out[config.TARGET_COLUMN] = (
        out[config.RAW_TARGET_COLUMN] >= config.LONG_ABSENCE_THRESHOLD_HOURS
    ).astype(int)
    return out


def build_modelling_dataset(raw_df: pd.DataFrame, extra_columns: Optional[List[str]] = None) -> pd.DataFrame:
    """Raw data -> the dataset used for training and evaluation.

    Steps: drop rule rows -> create target -> keep only feature columns, the
    employee ID (for grouping) and the target. Index is reset so positions are
    simple 0..n-1.

    extra_columns lets experiments (e.g. the Phase 3 ablation) carry additional raw
    columns such as the period features. Rows and order are unchanged, so the
    employee-grouped split is identical with or without them.
    """
    kept = raw_df.loc[~flag_rule_rows(raw_df)]
    with_target = add_target(kept)
    columns = config.FEATURE_COLUMNS + (extra_columns or []) + [config.GROUP_COLUMN, config.TARGET_COLUMN]
    return with_target[columns].reset_index(drop=True)
