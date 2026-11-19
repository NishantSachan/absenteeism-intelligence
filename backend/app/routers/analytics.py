from fastapi import APIRouter, Depends

from backend.app.deps import get_state
from backend.app.errors import ApiError
from backend.app.state import AppState

router = APIRouter(prefix="/api/analytics", tags=["analytics"])
SECTIONS = ("overview", "durations", "reasons", "calendar", "timeline", "employees", "association", "labels")


@router.get("/{section}")
def analytics(section: str, state: AppState = Depends(get_state)):
    if section not in SECTIONS:
        raise ApiError(404, "not_found", f"Unknown analytics section. Available: {', '.join(SECTIONS)}.")
    data = state.analytics[section]
    if section == "reasons":                    # the per-reason histograms are for the simulator, not for charts
        data = {k: v for k, v in data.items() if k != "hours_by_reason"}
    return data
