"""
models.py - the candidate algorithms, each wrapped in a full Pipeline.

Every candidate is  Pipeline([preprocessor, classifier]).  Because the preprocessor
is inside the pipeline, cross-validation re-learns encodings and scaling on each
fold's TRAINING rows only (no leakage), and the final saved object can take a raw
row of user inputs and return a prediction.

Settings are deliberately modest and fixed. Hyperparameter tuning is a separate,
explicit step (see tune_model in evaluate.py) done only on training data.
"""
from typing import Dict, List, Optional

from sklearn.base import BaseEstimator
from sklearn.dummy import DummyClassifier
from sklearn.ensemble import GradientBoostingClassifier, RandomForestClassifier
from sklearn.linear_model import LogisticRegression
from sklearn.neighbors import KNeighborsClassifier
from sklearn.pipeline import Pipeline
from sklearn.svm import SVC
from sklearn.tree import DecisionTreeClassifier

from src import config
from src.preprocessing import build_preprocessor


def make_pipeline(classifier: BaseEstimator, preprocessor=None) -> Pipeline:
    """Attach the (unfitted) preprocessor in front of a classifier."""
    preprocessor = build_preprocessor() if preprocessor is None else preprocessor
    return Pipeline([("preprocess", preprocessor), ("model", classifier)])


def get_candidate_models(random_state: int = config.RANDOM_STATE,
                         feature_kwargs: Optional[dict] = None) -> Dict[str, Pipeline]:
    """Return {display name: unfitted pipeline} for every compared algorithm.

    feature_kwargs is passed to build_preprocessor (categorical=, binary=, numeric=) so the
    SAME algorithms can be run on a different feature set. None = the config defaults.
    """
    def preprocessor():
        return build_preprocessor(**(feature_kwargs or {}))

    # Baseline 2 sees ONLY the reason code, to measure how much that single column explains.
    reason_only = build_preprocessor(categorical=[config.REASON], binary=[], numeric=[])

    return {
        # --- baselines: any real model must beat these ---
        "Baseline: majority class": make_pipeline(DummyClassifier(strategy="prior"), preprocessor()),
        "Baseline: reason code only": make_pipeline(
            LogisticRegression(max_iter=1000), preprocessor=reason_only),
        # --- candidate algorithms ---
        "Logistic Regression": make_pipeline(LogisticRegression(max_iter=1000), preprocessor()),
        "Decision Tree": make_pipeline(  # depth/leaf limits stop it memorising 575 rows
            DecisionTreeClassifier(max_depth=4, min_samples_leaf=10, random_state=random_state),
            preprocessor()),
        "Random Forest": make_pipeline(
            RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
                                   random_state=random_state, n_jobs=1), preprocessor()),
        "SVM (RBF kernel)": make_pipeline(SVC(C=1.0, kernel="rbf", gamma="scale"), preprocessor()),
        "K-Nearest Neighbors": make_pipeline(KNeighborsClassifier(n_neighbors=15), preprocessor()),
        "Gradient Boosting": make_pipeline(
            GradientBoostingClassifier(n_estimators=100, learning_rate=0.1, max_depth=2,
                                       random_state=random_state), preprocessor()),
    }


def get_final_pipeline(random_state: int = config.RANDOM_STATE) -> Pipeline:
    """The deployed model: Reason + Month + Day-of-week -> Random Forest.

    Chosen in Phase 4 (see reports/tables/final_shortlist_oof.csv and notebooks/03_timeline_and_robustness.ipynb): top-tier ranking quality,
    well-calibrated probabilities without an extra calibration layer, and explainable
    through the per-reason probabilities and permutation importance.
    """
    from src.preprocessing import build_final_preprocessor  # local import avoids a cycle
    return make_pipeline(
        RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
                               random_state=random_state, n_jobs=1),
        build_final_preprocessor(),
    )


# ----------------------------------------------------------------------------
# Phase 4: shortlist for the FINAL choice (3 inputs: Reason, Month, Day of week)
# ----------------------------------------------------------------------------
# Order = simplicity, simplest first. Used by the selection rule in train.py.
SIMPLICITY_ORDER = [
    "Reason-only baseline (LR)", "Logistic Regression", "Random Forest", "SVM (RBF kernel)",
]


def get_final_shortlist(random_state: int = config.RANDOM_STATE) -> Dict[str, Pipeline]:
    """Candidates for the deployed model. All can output probabilities.

    SVC needs probability=True here: it then fits an internal calibration step
    (Platt scaling) so the app can show a probability. That makes it slower to train.
    """
    reason_only = build_preprocessor(categorical=[config.REASON], binary=[], numeric=[])

    def three_inputs():
        return build_preprocessor(**config.FINAL_PREPROCESSOR_KWARGS)

    return {
        "Reason-only baseline (LR)": make_pipeline(LogisticRegression(max_iter=1000), reason_only),
        "Logistic Regression": make_pipeline(LogisticRegression(max_iter=1000), three_inputs()),
        "Random Forest": make_pipeline(
            RandomForestClassifier(n_estimators=300, min_samples_leaf=3,
                                   random_state=random_state, n_jobs=1), three_inputs()),
        "SVM (RBF kernel)": make_pipeline(
            SVC(C=1.0, kernel="rbf", gamma="scale", probability=True, random_state=random_state),
            three_inputs()),
    }
