"""
Phase 4 tests: input validation, artifact loading, end-to-end prediction.
Artifact tests need the trained model: run  python -m src.train  once first.
"""
import json
from pathlib import Path

import pytest

from src import config
from src.predict import (InputValidationError, ModelLoadError, PredictionResult,
                         load_artifacts, predict_absence, validate_inputs)

R, M, D = config.REASON, config.MONTH, config.DAY_OF_WEEK
SCHEMA = {R: {"allowed": [1, 7, 23, 28]}, M: {"allowed": list(range(1, 13))}, D: {"allowed": [2, 3, 4, 5, 6]}}
GOOD = {R: 23, M: 7, D: 3}


# ---------- validation (no model needed) ----------
def test_valid_input_gives_one_row_in_schema_order():
    frame = validate_inputs({D: 3, M: 7, R: 23}, SCHEMA)     # deliberately shuffled keys
    assert list(frame.columns) == [R, M, D] and frame.iloc[0].tolist() == [23, 7, 3]


@pytest.mark.parametrize("value", ["5", 5.0, " 5 "])
def test_whole_numbers_in_other_forms_are_accepted(value):
    assert validate_inputs({**GOOD, D: value}, SCHEMA).iloc[0][D] == 5


@pytest.mark.parametrize("field,value,fragment", [
    (M, 13, "not supported"), (M, 0, "not supported"), (D, 1, "not supported"), (D, 7, "not supported"),
    (R, 99, "not supported"), (R, 0, "outside the model's scope"),
    (R, "abc", "whole number"), (M, 3.5, "whole number"), (M, True, "whole number"),
    (D, float("nan"), "whole number"), (R, None, "required"), (R, "", "required"),
])
def test_bad_values_are_rejected_with_friendly_message(field, value, fragment):
    with pytest.raises(InputValidationError) as err:
        validate_inputs({**GOOD, field: value}, SCHEMA)
    assert fragment in " ".join(err.value.messages)


def test_missing_and_extra_fields_rejected():
    with pytest.raises(InputValidationError) as err:
        validate_inputs({R: 23, "Age": 40}, SCHEMA)
    text = " ".join(err.value.messages)
    assert "Unexpected field 'Age'" in text and f"'{M}' is required" in text and f"'{D}' is required" in text


def test_all_problems_reported_together():
    with pytest.raises(InputValidationError) as err:
        validate_inputs({R: 99, M: 13, D: 1}, SCHEMA)
    assert len(err.value.messages) == 3


# ---------- artifacts and end-to-end ----------
@pytest.fixture(scope="module")
def artifacts():
    try:
        return load_artifacts()
    except ModelLoadError as exc:
        pytest.fail(f"{exc}  (Run `python -m src.train` before the tests.)")


def test_missing_model_gives_clear_error(tmp_path):
    with pytest.raises(ModelLoadError, match="python -m src.train"):
        load_artifacts(tmp_path / "none.joblib", tmp_path / "none.json")


def test_metadata_is_complete_and_consistent(artifacts):
    _, meta = artifacts
    for key in ["model_name", "model_version", "feature_columns", "input_schema", "decision_threshold",
                "target", "library_versions", "limitations", "created_utc"]:
        assert key in meta
    assert meta["feature_columns"] == config.FINAL_FEATURE_COLUMNS
    assert list(meta["input_schema"]) == config.FINAL_FEATURE_COLUMNS
    assert 0 < meta["decision_threshold"] < 1
    assert 0 not in meta["input_schema"][R]["allowed"]            # rule code is not a supported input
    assert meta["input_schema"][M]["allowed"] == list(range(1, 13))


def test_end_to_end_prediction_is_valid(artifacts):
    result = predict_absence(GOOD)
    assert isinstance(result, PredictionResult)
    assert 0.0 <= result.probability_long <= 1.0
    assert result.predicted_long == (result.probability_long >= result.threshold)
    assert result.label in artifacts[1]["target"]["class_labels"].values()


def test_prediction_is_deterministic(artifacts):
    assert predict_absence(GOOD) == predict_absence(GOOD)


def test_every_supported_reason_predicts(artifacts):
    _, meta = artifacts
    for code in meta["input_schema"][R]["allowed"]:
        assert 0 <= predict_absence({R: code, M: 5, D: 4}).probability_long <= 1


def test_reason_matters_in_the_expected_direction(artifacts):
    """Observed in the EDA: reason 23 (very common) is mostly short; reason 22 mostly long."""
    _, meta = artifacts
    allowed = meta["input_schema"][R]["allowed"]
    if 22 in allowed and 23 in allowed:
        assert predict_absence({R: 22, M: 5, D: 4}).probability_long > predict_absence({R: 23, M: 5, D: 4}).probability_long


def test_invalid_input_never_reaches_the_model(artifacts):
    with pytest.raises(InputValidationError):
        predict_absence({R: 23, M: 13, D: 3})
