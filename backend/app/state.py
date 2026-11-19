"""Everything loaded ONCE at startup: the model, metadata and the aggregate JSON assets."""
import json
import logging
from dataclasses import dataclass, field
from typing import Any, Dict, Optional

from backend.app.settings import Settings
from src.predict import ModelLoadError, load_artifacts
from src.simulation import DurationModel

log = logging.getLogger("absenteeism_api")


@dataclass
class AppState:
    pipeline: Any = None
    metadata: Dict = field(default_factory=dict)
    metrics: Dict = field(default_factory=dict)
    analytics: Dict = field(default_factory=dict)
    model_grid: Dict = field(default_factory=dict)
    evaluation: Dict = field(default_factory=dict)
    durations: Optional[DurationModel] = None
    error: Optional[str] = None

    @property
    def ready(self) -> bool:
        return self.error is None and self.pipeline is not None


def _read(path):
    return json.loads(path.read_text(encoding="utf-8"))


def load_state(s: Settings) -> AppState:
    state = AppState()
    try:
        state.pipeline, state.metadata = load_artifacts(s.model_path, s.metadata_path)
        state.metrics = _read(s.metrics_path)
        state.analytics = _read(s.assets_dir / "analytics.json")
        state.model_grid = _read(s.assets_dir / "model_grid.json")
        state.evaluation = _read(s.assets_dir / "evaluation.json")
        state.durations = DurationModel(state.analytics["reasons"]["hours_by_reason"])
        log.info("Loaded model %s v%s", state.metadata["model_name"], state.metadata["model_version"])
    except (ModelLoadError, FileNotFoundError, KeyError, ValueError) as exc:
        state.error = f"{type(exc).__name__}"
        log.exception("Startup load failed")
    return state
