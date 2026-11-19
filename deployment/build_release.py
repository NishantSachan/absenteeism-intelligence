"""
build_release.py - package ONLY what the server needs into release/absenteeism-api-release.tar.gz and build the React app.

  python deployment/build_release.py            # backend archive + frontend build (needs npm)
  python deployment/build_release.py --skip-frontend

The archive contains: backend/, the runtime subset of src/, models/, reports/app_assets/*.json and deployment/.
It never contains: data/raw, notebooks, tests, .venv, node_modules, caches, training code or Streamlit.
"""
import argparse
import subprocess
import sys
import tarfile
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
RUNTIME_SRC = ["__init__.py", "config.py", "predict.py", "reason_codes.py", "simulation.py"]
INCLUDE = [("backend/requirements.txt", None), ("backend/__init__.py", None),
           ("models/absenteeism_pipeline.joblib", None), ("models/model_metadata.json", None), ("models/metrics.json", None)]
SKIP_PARTS = {"__pycache__", ".pytest_cache", ".venv", "node_modules", "tests"}


def add(tar: tarfile.TarFile, path: Path) -> None:
    if path.is_dir():
        for p in sorted(path.rglob("*")):
            if p.is_file() and not (set(p.parts) & SKIP_PARTS) and p.suffix != ".pyc":
                tar.add(p, arcname=str(p.relative_to(ROOT)))
    else:
        tar.add(path, arcname=str(path.relative_to(ROOT)))


def main() -> None:
    ap = argparse.ArgumentParser()
    ap.add_argument("--skip-frontend", action="store_true")
    args = ap.parse_args()
    out = ROOT / "release"
    out.mkdir(exist_ok=True)
    archive = out / "absenteeism-api-release.tar.gz"
    (ROOT / "backend" / "__init__.py").touch()
    with tarfile.open(archive, "w:gz") as tar:
        add(tar, ROOT / "backend" / "app")
        for rel, _ in INCLUDE:
            add(tar, ROOT / rel)
        for name in RUNTIME_SRC:
            add(tar, ROOT / "src" / name)
        for p in sorted((ROOT / "reports" / "app_assets").glob("*.json")):
            add(tar, p)
        add(tar, ROOT / "deployment")
    print(f"wrote {archive.relative_to(ROOT)} ({archive.stat().st_size / 1e6:.1f} MB)")
    if not args.skip_frontend:
        npm = "npm.cmd" if sys.platform == "win32" else "npm"
        subprocess.run([npm, "ci"], cwd=ROOT / "frontend", check=True)
        subprocess.run([npm, "run", "build"], cwd=ROOT / "frontend", check=True)
        print("frontend build: frontend/dist")


if __name__ == "__main__":
    main()
