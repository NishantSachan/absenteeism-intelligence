"""One error shape for every failure:  {"error": {"code", "message", "details": [{"field", "message"}]}}"""
import logging

from fastapi import FastAPI, Request
from fastapi.exceptions import RequestValidationError
from fastapi.responses import JSONResponse
from starlette.exceptions import HTTPException as StarletteHTTPException

from src.predict import InputValidationError
from src.simulation import SimulationError

log = logging.getLogger("absenteeism_api")


class ApiError(Exception):
    def __init__(self, status: int, code: str, message: str, details=None):
        self.status, self.code, self.message, self.details = status, code, message, details or []


def body(code: str, message: str, details=None) -> dict:
    return {"error": {"code": code, "message": message, "details": details or []}}


def register_error_handlers(app: FastAPI) -> None:
    @app.exception_handler(ApiError)
    async def _api(_: Request, exc: ApiError):
        return JSONResponse(status_code=exc.status, content=body(exc.code, exc.message, exc.details))

    @app.exception_handler(InputValidationError)
    async def _input(_: Request, exc: InputValidationError):
        return JSONResponse(status_code=422, content=body("invalid_input", "The input is not supported by the model.",
                                                          [{"field": None, "message": m} for m in exc.messages]))

    @app.exception_handler(SimulationError)
    async def _sim(_: Request, exc: SimulationError):
        return JSONResponse(status_code=422, content=body("invalid_scenario", str(exc), [{"field": None, "message": str(exc)}]))

    @app.exception_handler(RequestValidationError)
    async def _val(_: Request, exc: RequestValidationError):
        details = [{"field": ".".join(str(p) for p in e["loc"] if p != "body"), "message": e["msg"]} for e in exc.errors()]
        return JSONResponse(status_code=422, content=body("validation_error", "The request is not valid.", details))

    @app.exception_handler(StarletteHTTPException)
    async def _http(_: Request, exc: StarletteHTTPException):
        code = {404: "not_found", 405: "method_not_allowed"}.get(exc.status_code, "http_error")
        return JSONResponse(status_code=exc.status_code, content=body(code, str(exc.detail)))

    @app.exception_handler(Exception)
    async def _unhandled(_: Request, exc: Exception):
        log.exception("Unhandled error")                       # details go to the log, never to the visitor
        return JSONResponse(status_code=500, content=body("internal_error", "Something went wrong. Please try again."))
