"""
predict.py - reusable inference logic. The web app calls ONLY these functions.

Responsibilities:
  * load the saved pipeline + metadata once (and fail with a clear message if missing),
  * validate user input against the schema saved with the model,
  * return a prediction object (never raw exceptions, never internal paths).
Training code is not imported here, so opening the app can never retrain anything.
"""
import json
import math
import re
import warnings
from dataclasses import dataclass
from functools import lru_cache
from pathlib import Path
from typing import Any, Dict, List, Mapping, Optional

import joblib
import pandas as pd
import sklearn

from src import config


class ModelLoadError(RuntimeError):
    """The model files are missing or unreadable."""


class InputValidationError(ValueError):
    """The user's input is not acceptable. .messages holds one friendly line per problem."""

    def __init__(self, messages: List[str]):
        super().__init__("; ".join(messages))
        self.messages = messages


@dataclass(frozen=True)
class PredictionResult:
    predicted_long: bool          # True = flagged as a long absence (8+ hours)
    probability_long: float       # the model's estimated probability of a long absence
    threshold: float              # probability at/above which an absence is flagged
    label: str                    # human-readable class
    model_name: str
    model_version: str


@lru_cache(maxsize=2)
def load_artifacts(model_path: Path = config.MODEL_PATH, metadata_path: Path = config.METADATA_PATH):
    """Load (pipeline, metadata). Cached so each Streamlit/Flask rerun reuses the same objects."""
    model_path, metadata_path = Path(model_path), Path(metadata_path)
    if not model_path.exists() or not metadata_path.exists():
        raise ModelLoadError("The trained model files were not found. Run `python -m src.train` first.")
    try:
        pipeline = joblib.load(model_path)
        metadata = json.loads(metadata_path.read_text())
    except Exception as exc:                      # corrupt file, version problems, ...
        raise ModelLoadError("The trained model could not be loaded.") from exc
    saved = metadata.get("library_versions", {}).get("scikit-learn")
    if saved and saved != sklearn.__version__:
        warnings.warn(f"Model was saved with scikit-learn {saved} but {sklearn.__version__} is installed; "
                      "results may differ. Recreate the environment from requirements.txt.")
    return pipeline, metadata


def _to_whole_number(value: Any) -> int:
    """Accept 5, 5.0 or '5'; reject True/False, 5.5, 'abc', None, NaN."""
    if isinstance(value, bool):
        raise ValueError("must be a whole number")
    if isinstance(value, int):
        return value
    if isinstance(value, float):
        if math.isfinite(value) and value.is_integer():
            return int(value)
        raise ValueError("must be a whole number")
    if isinstance(value, str) and re.fullmatch(r"\s*[+-]?\d+\s*", value):
        return int(value)
    # numpy integers and similar
    try:
        if hasattr(value, "item") and float(value.item()).is_integer() and not isinstance(value, (str, bytes)):
            return int(value.item())
    except (TypeError, ValueError):
        pass
    raise ValueError("must be a whole number")


def validate_inputs(raw_inputs: Mapping[str, Any], schema: Mapping[str, Dict]) -> pd.DataFrame:
    """Check inputs against the saved schema and return a one-row DataFrame in the model's column order."""
    problems: List[str] = []
    expected = list(schema)
    for name in raw_inputs:
        if name not in schema:
            problems.append(f"Unexpected field '{name}'.")
    clean: Dict[str, int] = {}
    for name in expected:
        if name not in raw_inputs or raw_inputs[name] is None or raw_inputs[name] == "":
            problems.append(f"'{name}' is required.")
            continue
        try:
            value = _to_whole_number(raw_inputs[name])
        except ValueError:
            problems.append(f"'{name}' must be a whole number.")
            continue
        if name == config.REASON and value == config.RULE_REASON_CODE:
            problems.append("Reason code 0 is outside the model's scope: in the historical data every record "
                            "with this code has 0 hours of absence.")
            continue
        if value not in schema[name]["allowed"]:
            allowed = schema[name]["allowed"]
            shown = f"{min(allowed)} to {max(allowed)}" if len(allowed) > 12 else ", ".join(map(str, allowed))
            problems.append(f"'{name}' value {value} is not supported. Allowed values: {shown}.")
            continue
        clean[name] = value
    if problems:
        raise InputValidationError(problems)
    return pd.DataFrame([clean], columns=expected)       # exact column order the pipeline was trained with


def predict_absence(raw_inputs: Mapping[str, Any], artifacts: Optional[tuple] = None) -> PredictionResult:
    """Validate -> predict -> package. `artifacts` can be injected for testing."""
    pipeline, metadata = artifacts if artifacts is not None else load_artifacts()
    frame = validate_inputs(raw_inputs, metadata["input_schema"])
    probability = float(pipeline.predict_proba(frame)[0, 1])
    threshold = float(metadata["decision_threshold"])
    is_long = probability >= threshold
    labels = metadata["target"]["class_labels"]
    return PredictionResult(
        predicted_long=is_long, probability_long=probability, threshold=threshold,
        label=labels["1"] if is_long else labels["0"],
        model_name=metadata["model_name"], model_version=metadata["model_version"],
    )
