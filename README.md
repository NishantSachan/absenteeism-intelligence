# Absenteeism Intelligence & Workforce Planning System

A data-science capstone built on the public UCI *Absenteeism at work* dataset (740 absence events, 36 employees).
It connects three modules in one React + FastAPI application:

1. **Pattern discovery** – durations, reasons, calendar, an inferred 37-month timeline, and employee repetition (aggregates only).
2. **Prediction & explainability** – for an *already reported* absence, the probability that it lasts **8 hours or more**,
   shown next to the historical rate and a reason-only baseline.
3. **Workforce planning** – an assumption-driven what-if simulator that turns *your* assumptions into staffing gaps using the
   *measured* distribution of absence durations. It is never presented as a forecast.

> **Honest summary of the evidence.** The recorded reason explains almost everything the model can say. With 33 employees the deployed
> Random Forest cannot be statistically distinguished from a one-column baseline (PR-AUC difference 95% interval −0.006 to +0.050).
> The model is kept because nothing justifies replacing it, not because it is clearly better. See `docs/MODEL_EVALUATION.md` and the
> *Model Performance* page.

## Layout
```
src/            training + analysis library (config, data_loader, splitting, preprocessing, models, evaluate, train,
                predict, reason_codes, timeline, analytics, robustness, simulation, make_app_assets)
models/         absenteeism_pipeline.joblib (unchanged v1.0.0), model_metadata.json, metrics.json (+ evaluation_v2)
reports/        figures/, tables/ (original experiments), app_assets/*.json (aggregate-only data served by the API)
backend/        FastAPI app (backend/app) + backend/requirements.txt (RUNTIME dependencies only) + backend/tests
frontend/       React + Vite + TypeScript app (7 routes) + Vitest tests
notebooks/      01_eda, 02_model_comparison, 03_timeline_and_robustness
tests/          pipeline, evaluation, prediction, quality and v2 analytics/simulation tests
deployment/     EC2/nginx/systemd files, build_release.py, smoke_check.py, deploy_frontend.sh
data/raw/       the original CSV (git-ignored; never deployed)
```

## Run it locally (Python 3.12, Node 20+)
```bash
python -m venv .venv && source .venv/bin/activate          # Windows: .venv\Scripts\activate
pip install -r requirements-dev.txt

# optional: regenerate everything from the data (the repository already contains the results)
python -m src.train            # trains and writes models/ (deterministic: reproduces the shipped artifact)
python -m src.robustness       # adds evaluation_v2 to models/metrics.json
python -m src.make_app_assets  # writes reports/app_assets/*.json

# terminal 1 - API
uvicorn backend.app.main:app --reload --port 8000
# terminal 2 - frontend (proxies /api to port 8000)
cd frontend && npm install && npm run dev                   # http://localhost:5173
```
API docs: http://127.0.0.1:8000/api/docs

## Tests
```bash
python -m pytest -q                                          # Python: pipeline, API, analytics, simulation, quality
cd frontend && npm test                                      # React unit/integration tests (mocked API)
cd frontend && npm run build                                 # type-check + production build
# real end-to-end (needs the API running on port 8000):
cd frontend && LIVE_API=http://127.0.0.1:8000 npx vitest run
```

## Environment variables (no secrets are used anywhere)
| Where | Variable | Default | Purpose |
|---|---|---|---|
| backend | `CORS_ORIGINS` | `http://localhost:5173,http://127.0.0.1:5173` | browser origins allowed to call the API cross-origin |
| backend | `MODEL_PATH`, `METADATA_PATH`, `METRICS_PATH`, `ASSETS_DIR` | repository paths | locations of the artifacts |
| backend | `LOG_LEVEL` | `INFO` | logging |
| frontend | `VITE_API_BASE_URL` | `/api` | API base URL as seen by the browser |

## Documentation
`docs/METHODOLOGY.md` · `docs/MODEL_EVALUATION.md` · `docs/ARCHITECTURE.md` · `docs/LIMITATIONS.md` · `docs/RESUME.md` · `DEPLOYMENT.md` (AWS) · `TESTING.md`

Educational project. Not for hiring, firing, discipline or any decision about an individual.
