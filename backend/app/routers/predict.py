import pandas as pd
from fastapi import APIRouter, Depends

from backend.app.deps import get_state
from backend.app.schemas import ErrorResponse, HistoricalReference, PredictRequest, PredictResponse, Sensitivity
from backend.app.state import AppState
from src import config
from src.predict import predict_absence
from src.reason_codes import DAY_LABELS, MONTH_LABELS, REASON_LABELS

router = APIRouter(prefix="/api", tags=["prediction"])


@router.post("/predict", response_model=PredictResponse, responses={422: {"model": ErrorResponse}, 503: {"model": ErrorResponse}})
def predict(req: PredictRequest, state: AppState = Depends(get_state)):
    inputs = {config.REASON: req.reason, config.MONTH: req.month, config.DAY_OF_WEEK: req.weekday}
    result = predict_absence(inputs, artifacts=(state.pipeline, state.metadata))     # raises InputValidationError -> 422

    row = next((r for r in state.analytics["reasons"]["rows"] if r["code"] == req.reason), None)
    historical = HistoricalReference(n=row["n"], long_rate=row["long_rate"], ci_low=row["ci_low"], ci_high=row["ci_high"],
                                     low_n=row["low_n"], tier=row["tier"]) if row else None
    ro = state.model_grid["reasons"].get(str(req.reason), {}).get("reason_only")

    # How much would the answer move if only month/weekday changed? (60 exact model evaluations)
    schema = state.metadata["input_schema"]
    combos = pd.DataFrame([(req.reason, m, d) for m in schema[config.MONTH]["allowed"] for d in schema[config.DAY_OF_WEEK]["allowed"]],
                          columns=config.FINAL_FEATURE_COLUMNS)
    p = state.pipeline.predict_proba(combos)[:, 1]
    flagged = float((p >= result.threshold).mean())
    return PredictResponse(
        reason=req.reason, month=req.month, weekday=req.weekday,
        reason_label=REASON_LABELS.get(req.reason, str(req.reason)), month_label=MONTH_LABELS[req.month],
        weekday_label=DAY_LABELS[req.weekday], probability_long=result.probability_long, predicted_long=result.predicted_long,
        threshold=result.threshold, label=result.label, reason_only_probability=ro, historical=historical,
        sensitivity=Sensitivity(min_probability=float(p.min()), max_probability=float(p.max()),
                                share_of_month_weekday_combinations_flagged=flagged,
                                flag_depends_on_month_or_weekday=0 < flagged < 1),
        model_name=result.model_name, model_version=result.model_version)
