from fastapi import APIRouter, Request
from fastapi.responses import JSONResponse

from backend.app.schemas import HealthResponse

router = APIRouter(tags=["health"])


@router.get("/health", response_model=HealthResponse)
@router.get("/api/health", response_model=HealthResponse, include_in_schema=False)
def health(request: Request):
    state = request.app.state.data
    body = HealthResponse(status="ok" if state.ready else "degraded", model_loaded=state.ready,
                          model_name=state.metadata.get("model_name"), model_version=state.metadata.get("model_version"))
    return JSONResponse(status_code=200 if state.ready else 503, content=body.model_dump())
