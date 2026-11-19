"""
timeline.py - reconstruct a month index from row order.

The raw CSV has no date. Evidence that row order is chronological: the monthly company figure
"Work load Average/day" forms contiguous runs (one run per calendar month) and the 'Month of
absence' of successive runs advances by exactly one month (7, 8, ..., 12, 1, ..., 7).
This is an INFERENCE, not a recorded date: callers get a `consistency` report so it can be shown.
"""
from typing import Dict, Tuple

import pandas as pd

from src import config


def month_label(period: int) -> str:
    """period 1 -> '2007-07' (start month comes from config; see the note there)."""
    idx = (config.TIMELINE_START_YEAR * 12 + config.TIMELINE_START_MONTH - 1) + (int(period) - 1)
    return f"{idx // 12}-{idx % 12 + 1:02d}"


def add_period(raw: pd.DataFrame) -> Tuple[pd.DataFrame, Dict]:
    """Return (copy of raw with a 'period' column, consistency report).

    Rows in the trailing run whose month is 0 (the 3 reason-0 rule rows) get period = <NA>.
    """
    out = raw.copy()
    run = (out[config.WORKLOAD] != out[config.WORKLOAD].shift()).cumsum()
    first_month = out.groupby(run)[config.MONTH].first()
    valid_runs = first_month[first_month > 0]
    months = valid_runs.tolist()
    steps_ok = sum(1 for a, b in zip(months, months[1:]) if (b - a) % 12 == 1)
    period_of_run = {r: i + 1 for i, r in enumerate(valid_runs.index)}
    out["period"] = run.map(period_of_run).astype("Int64")
    # every run must hold exactly one calendar month, and each workload value must be a distinct run
    one_month_per_run = bool((out.groupby(run)[config.MONTH].nunique() == 1).all())
    consistency = {
        "runs_total": int(run.nunique()),
        "runs_with_month": int(len(months)),
        "consecutive_month_steps": int(steps_ok),
        "steps_checked": int(max(len(months) - 1, 0)),
        "one_month_per_run": one_month_per_run,
        "distinct_workload_values": int(out[config.WORKLOAD].nunique()),
        "rows_without_period": int(out["period"].isna().sum()),
        "ok": bool(one_month_per_run and steps_ok == max(len(months) - 1, 0)
                   and out[config.WORKLOAD].nunique() == run.nunique()),
        "assumed_start": f"{config.TIMELINE_START_YEAR}-{config.TIMELINE_START_MONTH:02d}",
        "note": ("Reconstructed from row order and the monthly workload figure; the file has no date column. "
                 "The start month is taken from the public dataset documentation."),
    }
    return out, consistency
