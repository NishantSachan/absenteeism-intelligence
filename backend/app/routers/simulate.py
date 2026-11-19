from fastapi import APIRouter, Depends

from backend.app.deps import get_state
from backend.app.schemas import ErrorResponse, SimulateRequest
from backend.app.state import AppState
from src.simulation import Scenario, compare

router = APIRouter(prefix="/api", tags=["simulation"])


@router.post("/simulate", responses={422: {"model": ErrorResponse}})
def simulate(req: SimulateRequest, state: AppState = Depends(get_state)):
    scenarios = [Scenario(**s.model_dump()) for s in req.scenarios]
    out = compare(scenarios, state.durations, monte_carlo=req.monte_carlo, n_sims=req.n_sims, seed=req.seed)
    out["duration_data"] = {"events": state.analytics["overview"]["modelled_rows"], "employees": state.analytics["overview"]["modelled_employees"],
                            "source": "Historical absence events from one company (UCI Absenteeism at work)."}
    return out
