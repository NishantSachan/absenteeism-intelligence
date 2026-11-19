"""Runtime settings, read from environment variables (no secrets are needed or stored)."""
import os
from dataclasses import dataclass, field
from pathlib import Path
from typing import List

from src import config as project_config


def _split(value: str) -> List[str]:
    return [v.strip() for v in value.split(",") if v.strip()]


@dataclass(frozen=True)
class Settings:
    model_path: Path = field(default_factory=lambda: Path(os.getenv("MODEL_PATH", project_config.MODEL_PATH)))
    metadata_path: Path = field(default_factory=lambda: Path(os.getenv("METADATA_PATH", project_config.METADATA_PATH)))
    metrics_path: Path = field(default_factory=lambda: Path(os.getenv("METRICS_PATH", project_config.METRICS_PATH)))
    assets_dir: Path = field(default_factory=lambda: Path(os.getenv("ASSETS_DIR", project_config.APP_ASSETS_DIR)))
    # Comma-separated browser origins allowed to call the API cross-origin (local dev, or a direct-API setup).
    cors_origins: List[str] = field(default_factory=lambda: _split(os.getenv("CORS_ORIGINS", "http://localhost:5173,http://127.0.0.1:5173")))
    log_level: str = field(default_factory=lambda: os.getenv("LOG_LEVEL", "INFO"))


def get_settings() -> Settings:
    return Settings()
