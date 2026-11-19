"""
splitting.py - employee-aware train/test split and cross-validation splitter.

WHY GROUPED SPLITTING
Each employee appears many times (up to 112 rows) and their personal attributes
(age, BMI, distance, ...) never change. In a random split, the same employee ends
up in both train and test, and the model can "recognise" them from those
attributes. Scores then look better than they would for a genuinely new employee.
Keeping every employee entirely on one side of the split prevents this.

StratifiedGroupKFold = groups kept together AND the long/short class ratio kept
as similar as possible across folds.
"""
from typing import Tuple

import pandas as pd
from sklearn.model_selection import StratifiedGroupKFold

from src import config


def group_holdout_split(
    df: pd.DataFrame, n_folds: int = 5, random_state: int = config.RANDOM_STATE
) -> Tuple[pd.DataFrame, pd.DataFrame]:
    """Hold out roughly 1/n_folds of the EMPLOYEES as the final test set.

    The test set is touched once, in Phase 4, for the final evaluation.
    Model selection uses cross-validation on the training part only.
    """
    splitter = StratifiedGroupKFold(n_splits=n_folds, shuffle=True, random_state=random_state)
    # next(...) takes the first fold's (train, test) indices.
    train_idx, test_idx = next(
        splitter.split(df, df[config.TARGET_COLUMN], groups=df[config.GROUP_COLUMN])
    )
    train_df = df.iloc[train_idx].reset_index(drop=True)
    test_df = df.iloc[test_idx].reset_index(drop=True)
    return train_df, test_df


def get_cv_splitter(n_splits: int = 5, random_state: int = config.RANDOM_STATE):
    """Cross-validation splitter for model selection (Phase 3).

    Usage: cv.split(X, y, groups=train_df[config.GROUP_COLUMN])
    """
    return StratifiedGroupKFold(n_splits=n_splits, shuffle=True, random_state=random_state)
