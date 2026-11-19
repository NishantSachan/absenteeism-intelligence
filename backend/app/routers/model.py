from fastapi import APIRouter, Depends

from backend.app.deps import get_state
from backend.app.state import AppState

router = APIRouter(prefix="/api/model", tags=["model"])


@router.get("/metrics")
def metrics(state: AppState = Depends(get_state)):
    m = state.metadata
    return {
        "model": {"name": m["model_name"], "version": m["model_version"], "created_utc": m["created_utc"],
                  "threshold": m["decision_threshold"], "threshold_rule": m["threshold_rule"],
                  "assumed_fn_to_fp_cost_ratio": m["assumed_fn_to_fp_cost_ratio"],
                  "threshold_sensitivity": m["threshold_sensitivity"], "training": m["training"],
                  "library_versions": m["library_versions"], "limitations": m["limitations"],
                  "feature_columns": m["feature_columns"]},
        "metrics": state.metrics,
        "evaluation": state.evaluation,
        "model_grid": state.model_grid,
    }
