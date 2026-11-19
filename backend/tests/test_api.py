"""API tests: validation, consistency with the saved model, analytics, simulation, errors, CORS, privacy."""
import json
import random
from pathlib import Path

import pytest
from fastapi.testclient import TestClient

from backend.app.main import create_app
from backend.app.settings import Settings
from src import config
from src.predict import load_artifacts, predict_absence

OK = {"reason": 23, "month": 7, "weekday": 3}


# ---------------------------------------------------------------- health / startup
def test_health_reports_loaded_model(client):
    for path in ("/health", "/api/health"):
        r = client.get(path)
        assert r.status_code == 200
        assert r.json() == {"status": "ok", "model_loaded": True, "model_name": "Random Forest", "model_version": "1.0.0"}


def test_model_is_loaded_once_at_startup_not_per_request(client):
    before = client.app.state.data.pipeline
    for _ in range(3):
        client.post("/api/predict", json=OK)
    assert client.app.state.data.pipeline is before


def test_missing_model_gives_degraded_health_and_503_not_a_crash(tmp_path):
    bad = Settings(model_path=tmp_path / "nope.joblib", metadata_path=tmp_path / "nope.json")
    with TestClient(create_app(bad)) as c:
        h = c.get("/health")
        assert h.status_code == 503 and h.json()["status"] == "degraded"
        r = c.post("/api/predict", json=OK)
        assert r.status_code == 503 and r.json()["error"]["code"] == "model_unavailable"


# ---------------------------------------------------------------- prediction
def test_predict_matches_direct_model_prediction(client):
    """The API must agree exactly with calling the saved model directly (sampled across the whole input grid)."""
    _, meta = load_artifacts()
    sch = meta["input_schema"]
    combos = [(r, m, d) for r in sch[config.REASON]["allowed"] for m in sch[config.MONTH]["allowed"] for d in sch[config.DAY_OF_WEEK]["allowed"]]
    random.Random(0).shuffle(combos)
    for r, m, d in combos[:80] + [(23, 7, 3), (22, 7, 3), (13, 3, 2)]:
        api = client.post("/api/predict", json={"reason": r, "month": m, "weekday": d}).json()
        direct = predict_absence({config.REASON: r, config.MONTH: m, config.DAY_OF_WEEK: d})
        assert api["probability_long"] == pytest.approx(direct.probability_long, abs=1e-12)
        assert api["predicted_long"] == direct.predicted_long
        assert api["threshold"] == direct.threshold == meta["decision_threshold"]
        assert api["model_version"] == meta["model_version"]


def test_predict_response_content(client):
    r = client.post("/api/predict", json=OK).json()
    assert 0 <= r["probability_long"] <= 1 and r["predicted_long"] is False
    assert r["reason_label"] and r["month_label"] == "July" and r["weekday_label"] == "Tuesday"
    assert r["historical"]["n"] == 149 and r["historical"]["ci_low"] < r["historical"]["long_rate"] < r["historical"]["ci_high"]
    assert r["sensitivity"]["min_probability"] <= r["probability_long"] <= r["sensitivity"]["max_probability"]
    assert 0 <= r["reason_only_probability"] <= 1


@pytest.mark.parametrize("body, code", [
    ({"reason": 0, "month": 7, "weekday": 3}, "invalid_input"),        # outside model scope (rule row)
    ({"reason": 20, "month": 7, "weekday": 3}, "invalid_input"),       # code absent from the data
    ({"reason": 99, "month": 7, "weekday": 3}, "invalid_input"),
    ({"reason": 23, "month": 13, "weekday": 3}, "invalid_input"),
    ({"reason": 23, "month": 7, "weekday": 7}, "invalid_input"),       # Saturday not in the data
    ({"reason": 23, "month": 7, "weekday": 1}, "invalid_input"),
    ({"reason": "23", "month": 7, "weekday": 3}, "validation_error"),  # strict ints only
    ({"reason": 23.5, "month": 7, "weekday": 3}, "validation_error"),
    ({"reason": True, "month": 7, "weekday": 3}, "validation_error"),
    ({"reason": None, "month": 7, "weekday": 3}, "validation_error"),
    ({"reason": 23, "month": 7}, "validation_error"),
    ({"reason": 23, "month": 7, "weekday": 3, "age": 40}, "validation_error"),   # unknown fields refused
    ({}, "validation_error"),
])
def test_invalid_predict_inputs_are_rejected_with_consistent_errors(client, body, code):
    r = client.post("/api/predict", json=body)
    assert r.status_code == 422
    err = r.json()["error"]
    assert err["code"] == code and err["message"] and isinstance(err["details"], list) and err["details"]


def test_malformed_json_and_wrong_method(client):
    r = client.post("/api/predict", content="not json", headers={"Content-Type": "application/json"})
    assert r.status_code == 422 and "error" in r.json()
    r = client.get("/api/predict")
    assert r.status_code == 405 and r.json()["error"]["code"] == "method_not_allowed"


# ---------------------------------------------------------------- meta / analytics / metrics
def test_meta_exposes_schema_that_matches_the_model(client):
    m = client.get("/api/meta").json()
    _, meta = load_artifacts()
    assert [r["code"] for r in m["inputs"]["reasons"]] == meta["input_schema"][config.REASON]["allowed"]
    assert m["model"]["threshold"] == meta["decision_threshold"]
    assert abs(sum(k["historical_share"] for k in m["simulation"]["reason_keys"]) - 1) < 1e-9


@pytest.mark.parametrize("section", ["overview", "durations", "reasons", "calendar", "timeline", "employees", "association", "labels"])
def test_analytics_sections_respond(client, section):
    r = client.get(f"/api/analytics/{section}")
    assert r.status_code == 200 and r.json()


def test_unknown_analytics_section_is_a_clean_404(client):
    r = client.get("/api/analytics/raw_rows")
    assert r.status_code == 404 and r.json()["error"]["code"] == "not_found"


def test_analytics_numbers_are_internally_consistent(client):
    ov = client.get("/api/analytics/overview").json()
    rs = client.get("/api/analytics/reasons").json()["rows"]
    cal = client.get("/api/analytics/calendar").json()
    tl = client.get("/api/analytics/timeline").json()
    du = client.get("/api/analytics/durations").json()
    assert sum(r["n"] for r in rs) == ov["modelled_rows"] == 697
    assert sum(r["n"] for r in cal["by_month"]) == sum(r["n"] for r in cal["by_weekday"]) == sum(p["n"] for p in tl["periods"]) == 697
    assert sum(h["events"] for h in du["histogram"]) == 697
    assert tl["consistency"]["ok"] is True and len(tl["periods"]) == 37


def test_model_metrics_endpoint_matches_files_on_disk(client):
    r = client.get("/api/model/metrics").json()
    disk = json.loads(config.METRICS_PATH.read_text())
    assert r["metrics"]["test"] == disk["test"]
    assert r["metrics"]["permutation_importance"] == disk["permutation_importance"]
    assert r["model"]["threshold"] == r["metrics"]["threshold"]["chosen"]
    assert set(r["metrics"]["evaluation_v2"]["pooled_grouped_cv"]) >= {"Random Forest", "Reason-only baseline (LR)"}


# ---------------------------------------------------------------- simulation
SCN = {"name": "A", "headcount": 100, "horizon_days": 63, "shift_hours": 8, "events_per_employee_per_month": 0.5, "reserve_staff": 3, "required_capacity_pct": 90}


def test_simulate_returns_deterministic_and_monte_carlo(client):
    r = client.post("/api/simulate", json={"scenarios": [SCN, {**SCN, "name": "B", "events_per_employee_per_month": 2}]})
    assert r.status_code == 200
    out = r.json()
    a, b = (s["deterministic"] for s in out["scenarios"])
    assert a["scheduled_hours"] == 100 * 63 * 8 and a["required_hours"] == pytest.approx(0.9 * 50400)
    assert b["expected_lost_hours"] > a["expected_lost_hours"] and b["gap_hours"] > a["gap_hours"]
    assert out["comparison"][1]["gap_vs_first_hours"] == pytest.approx(b["gap_hours"] - a["gap_hours"])
    assert out["scenarios"][0]["monte_carlo"]["n_sims"] == 2000 and "disclaimer" in out


def test_simulate_is_reproducible(client):
    body = {"scenarios": [SCN], "seed": 7}
    assert client.post("/api/simulate", json=body).json() == client.post("/api/simulate", json=body).json()


@pytest.mark.parametrize("patch", [
    {"headcount": 0}, {"headcount": -5}, {"horizon_days": 0}, {"horizon_days": 400}, {"shift_hours": 0}, {"shift_hours": 30},
    {"events_per_employee_per_month": -1}, {"events_per_employee_per_month": 99}, {"required_capacity_pct": 150}, {"reserve_staff": -1},
    {"name": ""}, {"headcount": "many"}, {"unknown": 1},
])
def test_simulate_rejects_invalid_scenarios(client, patch):
    r = client.post("/api/simulate", json={"scenarios": [{**SCN, **patch}]})
    assert r.status_code == 422 and r.json()["error"]["details"]


def test_simulate_rejects_bad_scenario_counts_and_reason_keys(client):
    assert client.post("/api/simulate", json={"scenarios": []}).status_code == 422
    assert client.post("/api/simulate", json={"scenarios": [SCN] * 5}).status_code == 422
    r = client.post("/api/simulate", json={"scenarios": [{**SCN, "reason_weights": {"999": 1}}]})
    assert r.status_code == 422 and r.json()["error"]["code"] == "invalid_scenario"
    r = client.post("/api/simulate", json={"scenarios": [{**SCN, "reason_weights": {"23": 0}}]})
    assert r.status_code == 422


def test_huge_scenario_skips_monte_carlo_instead_of_exhausting_memory(client):
    huge = {**SCN, "headcount": 100000, "horizon_days": 366, "events_per_employee_per_month": 10}
    r = client.post("/api/simulate", json={"scenarios": [huge]})
    assert r.status_code == 200
    s = r.json()["scenarios"][0]
    assert "monte_carlo" not in s and any("Monte Carlo skipped" in w for w in s["warnings"])


# ---------------------------------------------------------------- CORS and privacy
def test_cors_allows_configured_origin_only(client):
    ok = client.options("/api/predict", headers={"Origin": "http://localhost:5173", "Access-Control-Request-Method": "POST"})
    assert ok.headers.get("access-control-allow-origin") == "http://localhost:5173"
    bad = client.options("/api/predict", headers={"Origin": "https://evil.example", "Access-Control-Request-Method": "POST"})
    assert "access-control-allow-origin" not in bad.headers


FORBIDDEN_KEYS = {"id", "employee", "employee_id", "ID"}


def _keys(node):
    if isinstance(node, dict):
        for k, v in node.items():
            yield k
            yield from _keys(v)
    elif isinstance(node, list):
        for v in node:
            yield from _keys(v)


@pytest.mark.parametrize("path", ["/api/meta", "/api/model/metrics", "/api/analytics/employees", "/api/analytics/reasons", "/api/analytics/timeline",
                                  "/api/analytics/calendar", "/api/analytics/durations", "/api/analytics/overview"])
def test_public_endpoints_expose_no_employee_ids_or_row_level_records(client, path):
    body = client.get(path).json()
    assert not (set(_keys(body)) & FORBIDDEN_KEYS)
    assert "Absenteeism_at_work" not in json.dumps(body)


def test_employee_endpoint_returns_only_anonymous_aggregates(client):
    e = client.get("/api/analytics/employees").json()
    assert all(isinstance(v, int) for v in e["records_per_employee_sorted"]) and sum(e["records_per_employee_sorted"]) == 697
    assert e["records_per_employee_sorted"] == sorted(e["records_per_employee_sorted"], reverse=True)


def test_unhandled_errors_do_not_leak_internals(client, monkeypatch):
    def boom(*a, **k):
        raise RuntimeError("secret internal path /opt/x")
    monkeypatch.setattr("backend.app.routers.predict.predict_absence", boom)
    with TestClient(client.app, raise_server_exceptions=False) as c:
        r = c.post("/api/predict", json=OK)
    assert r.status_code == 500 and "secret" not in r.text and r.json()["error"]["code"] == "internal_error"
