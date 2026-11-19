"""FastAPI application factory. Run:  uvicorn backend.app.main:app --host 127.0.0.1 --port 8000"""
import logging
from contextlib import asynccontextmanager
from typing import Optional

from fastapi import FastAPI
from fastapi.middleware.cors import CORSMiddleware

from backend.app.errors import register_error_handlers
from backend.app.routers import analytics, health, meta, model, predict, simulate
from backend.app.settings import Settings, get_settings
from backend.app.state import AppState, load_state


def create_app(settings: Optional[Settings] = None) -> FastAPI:
    settings = settings or get_settings()
    logging.basicConfig(level=settings.log_level, format="%(asctime)s %(levelname)s %(name)s %(message)s")

    @asynccontextmanager
    async def lifespan(app: FastAPI):
        app.state.data = load_state(settings)          # model + assets loaded ONCE, not per request
        yield

    app = FastAPI(title="Absenteeism Intelligence & Workforce Planning API", version="2.0.0", lifespan=lifespan,
                  docs_url="/api/docs", openapi_url="/api/openapi.json", redoc_url=None)
    app.state.data = AppState(error="not_started")
    app.add_middleware(CORSMiddleware, allow_origins=settings.cors_origins, allow_methods=["GET", "POST"],
                       allow_headers=["Content-Type"], allow_credentials=False)
    register_error_handlers(app)
    for r in (health.router, meta.router, predict.router, analytics.router, model.router, simulate.router):
        app.include_router(r)
    return app


app = create_app()
