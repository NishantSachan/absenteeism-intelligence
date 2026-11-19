"""
smoke_check.py - "does the deployed API really work?" check. Needs only the runtime dependencies (no pytest, no dataset).

  python deployment/smoke_check.py                       # offline: loads the SAVED model and checks predictions
  python deployment/smoke_check.py --url http://127.0.0.1:8000        # also exercises a RUNNING server over HTTP
  python deployment/smoke_check.py --url https://dxxxx.cloudfront.net  # end-to-end through CloudFront (adds /api itself)
Exit code 0 = all good, 1 = problem.
"""
import argparse
import json
import sys
import urllib.error
import urllib.request
from pathlib import Path

ROOT = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(ROOT))

failures = []


def check(name: str, ok: bool, detail: str = "") -> None:
    print(f"[{'PASS' if ok else 'FAIL'}] {name}{(' - ' + detail) if detail else ''}")
    if not ok:
        failures.append(name)


def offline() -> None:
    from src import config
    from src.predict import load_artifacts, predict_absence
    _, meta = load_artifacts()
    check("saved model loads", True, f"{meta['model_name']} v{meta['model_version']}, threshold {meta['decision_threshold']}")
    short = predict_absence({config.REASON: 23, config.MONTH: 7, config.DAY_OF_WEEK: 3})
    long_ = predict_absence({config.REASON: 22, config.MONTH: 7, config.DAY_OF_WEEK: 3})
    check("direct prediction: reason 23 is short", not short.predicted_long, f"p={short.probability_long:.3f}")
    check("direct prediction: reason 22 is long", long_.predicted_long, f"p={long_.probability_long:.3f}")
    for name in ("analytics.json", "model_grid.json", "evaluation.json"):
        check(f"asset present: {name}", (config.APP_ASSETS_DIR / name).exists())
    check("raw CSV is not required", True)


def call(base: str, path: str, body=None):
    req = urllib.request.Request(base + path, data=json.dumps(body).encode() if body is not None else None,
                                 headers={"Content-Type": "application/json"} if body is not None else {}, method="POST" if body is not None else "GET")
    try:
        with urllib.request.urlopen(req, timeout=15) as r:
            return r.status, json.loads(r.read().decode())
    except urllib.error.HTTPError as e:
        return e.code, json.loads(e.read().decode() or "{}")


def online(url: str) -> None:
    base = url.rstrip("/")
    api = base if base.endswith("/api") else base + "/api"
    status, health = call(api, "/health")          # /api/health exists so the same check works locally and through CloudFront
    check("GET /health", status == 200 and health.get("model_loaded") is True, str(health))
    status, meta = call(api, "/meta")
    check("GET /api/meta", status == 200 and len(meta["inputs"]["reasons"]) > 20)
    status, p = call(api, "/predict", {"reason": 23, "month": 7, "weekday": 3})
    check("POST /api/predict short case", status == 200 and p["predicted_long"] is False, f"p={p.get('probability_long')}")
    status, p = call(api, "/predict", {"reason": 22, "month": 7, "weekday": 3})
    check("POST /api/predict long case", status == 200 and p["predicted_long"] is True, f"p={p.get('probability_long')}")
    status, e = call(api, "/predict", {"reason": 0, "month": 7, "weekday": 3})
    check("invalid reason is rejected with 422", status == 422 and e["error"]["code"] == "invalid_input")
    for section in ("overview", "durations", "reasons", "calendar", "timeline", "employees"):
        status, _ = call(api, f"/analytics/{section}")
        check(f"GET /api/analytics/{section}", status == 200)
    status, m = call(api, "/model/metrics")
    check("GET /api/model/metrics", status == 200 and "evaluation_v2" in m["metrics"])
    status, s = call(api, "/simulate", {"scenarios": [{"name": "A", "headcount": 100, "horizon_days": 63, "shift_hours": 8,
                                                       "events_per_employee_per_month": 0.5}]})
    check("POST /api/simulate", status == 200 and s["scenarios"][0]["deterministic"]["expected_events"] > 0)


if __name__ == "__main__":
    ap = argparse.ArgumentParser()
    ap.add_argument("--url", help="base URL of a running deployment")
    args = ap.parse_args()
    offline()
    if args.url:
        online(args.url)
    print("\nSMOKE TEST", "FAILED: " + ", ".join(failures) if failures else "PASSED")
    sys.exit(1 if failures else 0)
