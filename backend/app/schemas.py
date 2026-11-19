"""Pydantic request/response models. Domain checks (allowed codes) use the schema saved with the model."""
from typing import Dict, List, Optional

from pydantic import BaseModel, ConfigDict, Field


class ErrorDetail(BaseModel):
    field: Optional[str] = None
    message: str


class ErrorBody(BaseModel):
    code: str
    message: str
    details: List[ErrorDetail] = []


class ErrorResponse(BaseModel):
    error: ErrorBody


class HealthResponse(BaseModel):
    status: str
    model_loaded: bool
    model_name: Optional[str] = None
    model_version: Optional[str] = None


class PredictRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    reason: int = Field(strict=True, description="Reason-for-absence code (1-28, 20 not present in the data)")
    month: int = Field(strict=True, description="Month of absence, 1-12")
    weekday: int = Field(strict=True, description="Day of week, 2=Monday ... 6=Friday")


class HistoricalReference(BaseModel):
    n: int
    long_rate: float
    ci_low: float
    ci_high: float
    low_n: bool
    tier: str


class Sensitivity(BaseModel):
    min_probability: float
    max_probability: float
    share_of_month_weekday_combinations_flagged: float
    flag_depends_on_month_or_weekday: bool


class PredictResponse(BaseModel):
    reason: int
    month: int
    weekday: int
    reason_label: str
    month_label: str
    weekday_label: str
    probability_long: float
    predicted_long: bool
    threshold: float
    label: str
    reason_only_probability: Optional[float] = None
    historical: Optional[HistoricalReference] = None
    sensitivity: Sensitivity
    model_name: str
    model_version: str


class ScenarioIn(BaseModel):
    model_config = ConfigDict(extra="forbid")
    name: str = Field(min_length=1, max_length=60)
    headcount: int = Field(ge=1, le=100000)
    horizon_days: int = Field(ge=1, le=366)
    shift_hours: float = Field(gt=0, le=24)
    events_per_employee_per_month: float = Field(ge=0, le=10)
    reserve_staff: int = Field(default=0, ge=0, le=100000)
    required_capacity_pct: float = Field(default=100.0, ge=0, le=100)
    reason_weights: Optional[Dict[str, float]] = None


class SimulateRequest(BaseModel):
    model_config = ConfigDict(extra="forbid")
    scenarios: List[ScenarioIn] = Field(min_length=1, max_length=4)
    monte_carlo: bool = True
    n_sims: int = Field(default=2000, ge=200, le=20000)
    seed: int = Field(default=42, ge=0, le=2**31 - 1)
