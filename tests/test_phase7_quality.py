"""
Phase 7 quality tests: secrets, configuration, dependency pinning, deployment files, performance.
Run from the project root:  python -m pytest -v
"""
import re
import time

import pytest

from src import config
from src.predict import load_artifacts, predict_absence

ROOT = config.PROJECT_ROOT
TEXT_SUFFIXES = {".py", ".md", ".txt", ".toml", ".json", ".sh", ".service", ".template", ".conf", ".ipynb"}
SKIP_DIRS = {".venv", "__pycache__", ".pytest_cache", ".git", ".ipynb_checkpoints", "node_modules", "dist", "release"}


def project_text_files():
    for path in ROOT.rglob("*"):
        if path.is_file() and path.suffix in TEXT_SUFFIXES and not (set(path.parts) & SKIP_DIRS):
            if path.name == "test_phase7_quality.py":
                continue                                   # this file contains the patterns themselves
            yield path


def test_no_credentials_in_the_project():
    patterns = [r"AKIA[0-9A-Z]{16}", r"aws_secret_access_key\s*=", r"BEGIN (RSA |OPENSSH |EC )?PRIVATE KEY"]
    for path in project_text_files():
        text = path.read_text(errors="ignore")
        for pattern in patterns:
            assert not re.search(pattern, text), f"possible secret ({pattern}) in {path}"


def test_gitignore_protects_sensitive_files():
    lines = (ROOT / ".gitignore").read_text().splitlines()
    for required in ["data/raw/*.csv", ".env", "*.pem", ".venv/"]:
        assert required in lines, f"{required} missing from .gitignore"


def test_every_dependency_is_pinned_to_an_exact_version():
    for name in ("requirements-train.txt", "backend/requirements.txt"):
        for line in (ROOT / name).read_text().splitlines():
            line = line.split("#")[0].strip()
            if line:
                assert "==" in line, f"not pinned in {name}: {line}"


def test_deployment_files_exist_and_service_restarts_automatically():
    for name in ["setup_ec2.sh", "smoke_check.py", "health_check.sh", "absenteeism-api.service.template",
                 "nginx-absenteeism.conf.template", "build_release.py", "deploy_frontend.sh"]:
        assert (ROOT / "deployment" / name).exists(), name
    unit = (ROOT / "deployment" / "absenteeism-api.service.template").read_text()
    assert "Restart=always" in unit and "WantedBy=multi-user.target" in unit
    assert "uvicorn backend.app.main:app" in unit and "--host 127.0.0.1" in unit and "__APP_DIR__" in unit
    assert "streamlit" not in unit.lower()


def test_runtime_requirements_have_no_training_or_streamlit_packages():
    lines = (ROOT / "backend" / "requirements.txt").read_text().lower().splitlines()
    text = "\n".join(line.split("#")[0] for line in lines)          # package lines only, not comments
    for banned in ("streamlit", "matplotlib", "seaborn", "jupyter", "pytest", "ipykernel"):
        assert banned not in text, banned
    for needed in ("fastapi", "uvicorn", "pydantic", "scikit-learn==1.5.2", "joblib"):
        assert needed in text, needed


def test_deployed_backend_does_not_need_the_raw_dataset():
    """Everything the API reads must be a shipped artifact, not data/raw."""
    for path in [config.MODEL_PATH, config.METADATA_PATH, config.METRICS_PATH, config.ANALYTICS_PATH,
                 config.MODEL_GRID_PATH, config.EVALUATION_PATH]:
        assert path.exists(), path
    for src_file in (ROOT / "backend").rglob("*.py"):
        text = src_file.read_text(encoding="utf-8")
        assert "RAW_DATA_PATH" not in text and "load_raw_data" not in text, src_file


def test_prediction_is_fast_enough_for_interactive_use():
    pipeline_meta = load_artifacts()
    predict_absence({config.REASON: 23, config.MONTH: 7, config.DAY_OF_WEEK: 3}, artifacts=pipeline_meta)  # warm-up
    start = time.perf_counter()
    for _ in range(20):
        predict_absence({config.REASON: 23, config.MONTH: 7, config.DAY_OF_WEEK: 3}, artifacts=pipeline_meta)
    average = (time.perf_counter() - start) / 20
    assert average < 0.5, f"average prediction time {average:.3f}s"
