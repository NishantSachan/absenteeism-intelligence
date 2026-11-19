# Architecture

## Components
```
 TRAINING (offline, your computer)                         DEPLOYED (EC2 + S3/CloudFront)
 data/raw CSV ─▶ src.train ─▶ models/*.joblib,json          models/*, reports/app_assets/*.json  (read-only files)
              ─▶ src.robustness ─▶ metrics.json                 │
              ─▶ src.make_app_assets ─▶ app_assets/*.json       ▼
                                                    FastAPI (backend/app) ◀── nginx ◀── CloudFront ◀── React build (S3)
```
The deployed API never reads the raw CSV and never trains. All public data are aggregates built offline.

## Backend (`backend/app`)
| Module | Role |
|---|---|
| `main.py` | app factory, lifespan startup (loads the model and JSON assets **once**), CORS, router registration |
| `state.py` | loads and holds the pipeline, metadata, metrics, analytics, grid, evaluation and the `DurationModel`; failure leaves the app up in a degraded state (503 on model routes, `/health` reports it) |
| `schemas.py` | Pydantic v2 models (strict integers, unknown fields rejected, scenario bounds) |
| `errors.py` | one error shape `{"error":{"code","message","details":[{"field","message"}]}}` for 404/405/422/500; internals never leaked |
| `routers/` | `health`, `meta`, `predict`, `analytics`, `model`, `simulate` |
Inference and simulation logic lives in `src/predict.py` and `src/simulation.py` and is shared with the tests, so the API and a direct call give identical results (tested).

## Endpoints
| Method and path | Purpose |
|---|---|
| `GET /health`, `/api/health` | status, model loaded, name, version (503 if degraded) |
| `GET /api/meta` | allowed inputs and labels, threshold, simulator reason keys and limits |
| `POST /api/predict` | `{reason, month, weekday}` → probability, flag, threshold, historical rate with Wilson CI, reason-only comparison, month/weekday sensitivity |
| `GET /api/analytics/{overview,durations,reasons,calendar,timeline,employees,association,labels}` | aggregates for the Data Explorer and Insights |
| `GET /api/model/metrics` | metadata, metrics, evaluation tables, model grid |
| `POST /api/simulate` | 1–4 scenarios → deterministic result, optional seeded Monte Carlo, comparison and disclaimer |

## Frontend (`frontend`)
React 18 + Vite + TypeScript, React Router, Recharts. Seven routes: Home, Predict, Data Explorer, Model Performance, Insights, Workforce Planning, About.
`src/api/client.ts` is the only place that calls `fetch` (base URL from `VITE_API_BASE_URL`, default `/api`); `src/api/endpoints.ts` types every call;
`useApi` handles loading and error states; the original Streamlit palette and layout are ported in `styles/theme.css`.

## Security and privacy
* No employee IDs or rows in any response or static file (tested by recursively scanning every public response for forbidden keys).
* Small groups: public duration histograms pool reasons with fewer than 5 events; per-reason rates carry a low-count flag below 10.
* Strict input validation; request size capped in nginx; rate limit in nginx; docs at `/api/docs`.
* S3 bucket private (OAC); EC2 port 80 only from the CloudFront prefix list; nginx requires a secret header; SSH only from your IP; no credentials in the repository.

## Data and model contracts
Feature names, allowed values, labels, threshold and version come from `models/model_metadata.json` and are read by the backend at startup, so the saved model, API and frontend cannot drift apart.
`metadata_revision.artifact_sha256` pins the exact model file.
