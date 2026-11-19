from fastapi import Request

from backend.app.errors import ApiError
from backend.app.state import AppState


def get_state(request: Request) -> AppState:
    state: AppState = request.app.state.data
    if not state.ready:
        raise ApiError(503, "model_unavailable", "The prediction service is not available right now.")
    return state
