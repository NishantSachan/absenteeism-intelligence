# Testing

See README.md for the commands. What is covered:

| Area | Where | What |
|---|---|---|
| Data pipeline, target, splitting | `tests/test_phase2_data_pipeline.py`, `tests/test_v2_analytics_simulation.py` | target = hours ≥ 8, rule rows excluded, employee-grouped splits, timeline reconstruction (and its failure on shuffled rows) |
| Evaluation code | `tests/test_phase3_evaluation.py` | metrics, bootstrap, calibration |
| Model loading / prediction | `tests/test_phase4_predict.py` | schema validation, unknown values, determinism |
| API | `backend/tests/test_api.py` | valid/invalid inputs, **API output equals direct model output** on 83 input combinations, analytics consistency, simulation, CORS, no IDs in any public response, error shape, 503 when the model is missing, model loaded once |
| Simulation maths | `tests/test_v2_analytics_simulation.py` | exact hand-checked arithmetic with toy durations, monotonicity, seeded Monte Carlo, validation |
| Metadata / metrics | `tests/test_v2_analytics_simulation.py` | artifact SHA-256 matches metadata, threshold consistent everywhere, evaluation_v2 internally consistent |
| Quality / deployment files | `tests/test_phase7_quality.py` | no credentials, pinned dependencies, runtime requirements free of training/Streamlit packages, deployment files, no raw-data access in the backend |
| Frontend | `frontend/src/test/*.test.ts(x)` | API client, form validation, error and loading states, simulator input checks and payloads, navigation |
| Live end-to-end | `frontend/src/test/live.integration.test.tsx` | renders the real app against a running API (skipped unless `LIVE_API` is set) |
| Deployment smoke | `deployment/smoke_check.py` | loads the saved model offline; with `--url`, exercises every endpoint of a running server or CloudFront URL |

Results of the last full run are listed in the delivery message, not here, so this file cannot go stale.
