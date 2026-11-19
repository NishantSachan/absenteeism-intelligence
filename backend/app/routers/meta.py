from fastapi import APIRouter, Depends

from backend.app.deps import get_state
from backend.app.state import AppState
from src import config
from src.reason_codes import DAY_LABELS, MONTH_LABELS, REASON_LABELS

router = APIRouter(prefix="/api", tags=["meta"])


@router.get("/meta")
def meta(state: AppState = Depends(get_state)):
    m, schema = state.metadata, state.metadata["input_schema"]
    rows = {str(r["code"]): r for r in state.analytics["reasons"]["rows"]}
    reasons = [{"code": c, "label": REASON_LABELS.get(c, str(c)), "n": rows[str(c)]["n"], "tier": rows[str(c)]["tier"]}
               for c in schema[config.REASON]["allowed"]]
    d = state.durations
    sim_keys = []
    for k in d.keys:
        r = rows.get(k)
        sim_keys.append({"key": k, "label": r["label"] if r else "Other reasons (fewer than 5 records each)",
                         "tier": r["tier"] if r else "pooled", "events": d.events[k],
                         "historical_share": d.historical_mix[k], "mean_hours": d.means[k]})
    return {
        "model": {"name": m["model_name"], "version": m["model_version"], "created_utc": m["created_utc"],
                  "threshold": m["decision_threshold"], "task": m["task"], "target": m["target"],
                  "training": m["training"], "limitations": m["limitations"],
                  "revision": m.get("metadata_revision", {}).get("revision", 1)},
        "inputs": {"reasons": reasons,
                   "months": [{"code": c, "label": MONTH_LABELS[c]} for c in schema[config.MONTH]["allowed"]],
                   "weekdays": [{"code": c, "label": DAY_LABELS[c]} for c in schema[config.DAY_OF_WEEK]["allowed"]]},
        "simulation": {"reason_keys": sim_keys,
                       "limits": {"headcount": [1, 100000], "horizon_days": [1, 366], "shift_hours": [0.5, 24],
                                  "events_per_employee_per_month": [0, 10], "required_capacity_pct": [0, 100],
                                  "max_scenarios": 4},
                       "working_days_per_month": config.WORKING_DAYS_PER_MONTH},
        "dataset": {"modelled_rows": state.analytics["overview"]["modelled_rows"],
                    "employees": state.analytics["overview"]["modelled_employees"],
                    "long_share": state.analytics["overview"]["long_share"]},
    }
