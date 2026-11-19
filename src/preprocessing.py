"""
preprocessing.py - the encoding/scaling recipe, as a scikit-learn ColumnTransformer.

KEY IDEA
The ColumnTransformer is later placed INSIDE a Pipeline together with the model.
Calling pipeline.fit(X_train, y_train) learns encodings/means ONLY from training
rows; pipeline.predict(new_row) re-applies exactly the same transformation. That
is how we avoid data leakage and guarantee training/inference consistency.
"""
from typing import List, Optional

from sklearn.compose import ColumnTransformer
from sklearn.preprocessing import OneHotEncoder, StandardScaler

from src import config


def build_preprocessor(
    categorical: Optional[List[str]] = None,
    binary: Optional[List[str]] = None,
    numeric: Optional[List[str]] = None,
) -> ColumnTransformer:
    """Create an UNFITTED preprocessor. Defaults come from config.

    Parameters are overridable so Phase 3 can run ablations (e.g. add the
    period features) without duplicating this function.
    """
    categorical = config.CATEGORICAL_FEATURES if categorical is None else categorical
    binary = config.BINARY_FEATURES if binary is None else binary
    numeric = config.NUMERIC_FEATURES if numeric is None else numeric

    # One-hot: Reason / Month / Day are labels, not quantities (code 26 is not
    # "bigger" than code 7). Parameters:
    #  - handle_unknown="infrequent_if_exist": a code never seen in training is
    #    routed to the infrequent bucket instead of crashing the app.
    #  - min_frequency: codes with < N training rows are pooled together, because
    #    a dummy column built from 1-3 rows cannot be learned reliably.
    #  - sparse_output=False: return a normal array (small data, easier to inspect).
    categorical_encoder = OneHotEncoder(
        handle_unknown="infrequent_if_exist",
        min_frequency=config.MIN_CATEGORY_FREQUENCY,
        sparse_output=False,
    )

    # Scaling puts features on comparable ranges. It is required by Logistic
    # Regression, SVM and KNN, and harmless for tree models.
    # No imputer on purpose: the data has 0 missing values, and at inference the
    # app validates inputs; silently filling a missing value would hide mistakes.
    return ColumnTransformer(
        transformers=[
            ("categorical", categorical_encoder, categorical),
            ("binary", "passthrough", binary),
            ("numeric", StandardScaler(), numeric),
        ],
        remainder="drop",             # anything not listed (e.g. ID) is discarded
        verbose_feature_names_out=False,
    )


def build_final_preprocessor() -> ColumnTransformer:
    """Preprocessor for the deployed 3-input model (Reason, Month, Day-of-week).

    All three are category codes, so all are one-hot encoded; there are no numeric or
    binary inputs. Reason codes with fewer than MIN_CATEGORY_FREQUENCY training rows
    are pooled into an 'infrequent' group (see build_preprocessor).
    """
    return build_preprocessor(categorical=config.MODEL_FEATURES, binary=[], numeric=[])
