"""
analytics.py - aggregate-only pattern discovery for the app (no employee IDs, no row-level records).

Every number is computed from the data by build_analytics(); nothing is typed in by hand.
Statistics used (kept deliberately simple for n = 697 events / 33 employees):
  * Wilson 95% intervals for proportions,
  * chi-square tests + Cramer's V as an effect size for association with the long/short outcome,
  * shares and concentration measures (top-N share, Gini) for employee repetition.
"""
import math
from datetime import datetime, timezone
from typing import Dict, List

import numpy as np
import pandas as pd
from scipy.stats import chi2_contingency

from src import config
from src.data_loader import add_target, flag_rule_rows, load_raw_data
from src.reason_codes import DAY_LABELS, MONTH_LABELS, REASON_LABELS
from src.timeline import add_period, month_label

T = config.TARGET_COLUMN
H = config.RAW_TARGET_COLUMN


def wilson(k: int, n: int, z: float = 1.96):
    """95% Wilson score interval for a proportion k/n."""
    if n == 0:
        return 0.0, 1.0
    p = k / n
    denom = 1 + z * z / n
    centre = p + z * z / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z * z / (4 * n * n))
    return max(0.0, (centre - margin) / denom), min(1.0, (centre + margin) / denom)


def _rate_row(sub: pd.DataFrame) -> Dict:
    n, k = int(len(sub)), int(sub[T].sum())
    lo, hi = wilson(k, n)
    return {"n": n, "long_n": k, "long_rate": k / n if n else 0.0, "ci_low": lo, "ci_high": hi,
            "mean_hours": float(sub[H].mean()) if n else 0.0, "lost_hours": int(sub[H].sum())}


def _cramers_v(table: pd.DataFrame):
    chi2, p, dof, expected = chi2_contingency(table, correction=False)
    n = table.to_numpy().sum()
    k = min(table.shape) - 1
    v = math.sqrt(chi2 / (n * k)) if k > 0 and n > 0 else 0.0
    return float(chi2), float(p), int(dof), float(v), float((expected < 5).mean())


def _association(df: pd.DataFrame) -> Dict:
    out = {}
    pooled = df[config.REASON].map(df[config.REASON].value_counts()).lt(config.LOW_N_THRESHOLD)
    reason_pooled = df[config.REASON].where(~pooled, other=-1)       # rare reasons pooled so the test is valid-ish
    for name, col in [("Reason for absence", reason_pooled), ("Month of absence", df[config.MONTH]),
                      ("Day of the week", df[config.DAY_OF_WEEK])]:
        chi2, p, dof, v, low_expected = _cramers_v(pd.crosstab(col, df[T]))
        out[name] = {"chi2": chi2, "p_value": p, "dof": dof, "cramers_v": v, "share_cells_expected_lt5": low_expected}
    out["note"] = ("Chi-square tests treat the 697 events as independent, but events from the same employee are "
                   "correlated, so p-values are optimistic. Cramer's V (0 to 1) is the more useful effect size.")
    return out


def _tier(row: Dict) -> str:
    if row["n"] < config.LOW_N_THRESHOLD:
        return "insufficient data"
    if row["ci_high"] < 0.5:
        return "mostly short"
    if row["ci_low"] > 0.5:
        return "mostly long"
    return "mixed / uncertain"


def _gini(values: List[int]) -> float:
    v = np.sort(np.asarray(values, dtype=float))
    n = len(v)
    return float((2 * np.arange(1, n + 1) - n - 1).dot(v) / (n * v.sum())) if n and v.sum() else 0.0


def build_analytics(raw: pd.DataFrame = None) -> Dict:
    raw = load_raw_data() if raw is None else raw
    with_period, consistency = add_period(raw)
    rule = flag_rule_rows(raw)
    df = add_target(with_period.loc[~rule]).reset_index(drop=True)
    hours = raw[H]
    long_mask = df[T] == 1
    total_hours = int(df[H].sum())

    # ---------------- overview
    overview = {
        "raw_rows": int(len(raw)), "raw_columns": int(raw.shape[1]), "raw_employees": int(raw[config.GROUP_COLUMN].nunique()),
        "missing_values": int(raw.isna().sum().sum()), "exact_duplicate_rows": int(raw.duplicated().sum()),
        "rule_rows": int(rule.sum()), "rule_rows_all_zero_hours": bool((hours[rule] == 0).all()),
        "modelled_rows": int(len(df)), "modelled_employees": int(df[config.GROUP_COLUMN].nunique()),
        "long_n": int(df[T].sum()), "long_share": float(df[T].mean()),
        "long_threshold_hours": config.LONG_ABSENCE_THRESHOLD_HOURS,
        "months_covered": int(df["period"].nunique()),
        "duplicate_note": "Kept: with no date column, identical rows can be different events.",
    }

    # ---------------- durations
    vc = df[H].value_counts().sort_index()
    long_hours = df.loc[long_mask, H]
    durations = {
        "histogram": [{"hours": int(h), "events": int(c), "long": bool(h >= config.LONG_ABSENCE_THRESHOLD_HOURS)} for h, c in vc.items()],
        "mean": float(df[H].mean()), "median": float(df[H].median()), "p90": float(df[H].quantile(0.9)), "max": int(df[H].max()),
        "events_between_5_and_7_hours": int(df[H].between(5, 7).sum()), "events_exactly_8_hours": int((df[H] == 8).sum()),
        "long_events_that_are_whole_days": float((long_hours % 8 == 0).mean()),
        "long_share_of_events": float(long_mask.mean()),
        "long_share_of_lost_hours": float(df.loc[long_mask, H].sum() / total_hours),
        "total_lost_hours": total_hours,
    }

    # ---------------- reasons
    reasons, by_reason_hours = [], {}
    counts = df[config.REASON].value_counts()
    for code in sorted(df[config.REASON].unique()):
        sub = df[df[config.REASON] == code]
        row = {"code": int(code), "label": REASON_LABELS.get(int(code), str(code)), **_rate_row(sub)}
        row["event_share"] = row["n"] / len(df)
        row["hours_share"] = row["lost_hours"] / total_hours
        row["low_n"] = row["n"] < config.LOW_N_THRESHOLD
        row["tier"] = _tier(row)
        reasons.append(row)
        key = str(int(code)) if counts[code] >= config.HOURS_BY_REASON_MIN_N else "other"
        h = by_reason_hours.setdefault(key, {})
        for hv, c in sub[H].value_counts().items():
            h[str(int(hv))] = h.get(str(int(hv)), 0) + int(c)
    hours_by_reason = {k: {"events": int(sum(v.values())), "histogram": dict(sorted(v.items(), key=lambda kv: int(kv[0])))}
                       for k, v in by_reason_hours.items()}

    # ---------------- calendar
    calendar = {
        "by_month": [{"code": int(m), "label": MONTH_LABELS[int(m)], **_rate_row(df[df[config.MONTH] == m])}
                     for m in sorted(df[config.MONTH].unique())],
        "by_weekday": [{"code": int(d), "label": DAY_LABELS[int(d)], **_rate_row(df[df[config.DAY_OF_WEEK] == d])}
                       for d in sorted(df[config.DAY_OF_WEEK].unique())],
        "note": "Each bar rests on roughly 50-90 events; differences between months or weekdays are mostly within noise.",
    }

    # ---------------- timeline (inferred)
    per = []
    for p, sub in df.groupby("period"):
        per.append({"period": int(p), "label": month_label(int(p)), **_rate_row(sub)})
    ev = [r["n"] for r in per]
    third = max(len(per) // 3, 1)
    segs = {"first_third": per[:third], "middle_third": per[third:2 * third], "last_third": per[2 * third:]}
    seg_stats = {}
    for name, rows in segs.items():
        n, k = sum(r["n"] for r in rows), sum(r["long_n"] for r in rows)
        seg_stats[name] = {"months": len(rows), "events": n, "long_rate": k / n if n else 0.0,
                           "events_per_month": n / len(rows) if rows else 0.0}
    timeline = {
        "periods": per, "segments": seg_stats, "consistency": consistency,
        "events_per_month": {"mean": float(np.mean(ev)), "min": int(min(ev)), "max": int(max(ev)), "months": len(ev)},
        "caveat": ("Monthly counts are recorded absence EVENTS, not an absence rate: the file has no headcount per month "
                   "and no record of days without absence."),
    }

    # ---------------- employees (anonymous aggregates only)
    per_emp = df.groupby(config.GROUP_COLUMN).agg(n=(T, "size"), long_rate=(T, "mean")).sort_values("n", ascending=False)
    n_emp = len(per_emp)
    top10 = max(int(math.ceil(0.1 * n_emp)), 1)
    bins = [0, 0.2, 0.4, 0.6, 0.8, 1.0000001]
    labels = ["0-20%", "20-40%", "40-60%", "60-80%", "80-100%"]
    eligible = per_emp[per_emp["n"] >= config.HOURS_BY_REASON_MIN_N]
    hist = pd.cut(eligible["long_rate"], bins=bins, labels=labels, right=False).value_counts().reindex(labels)
    employees = {
        "employees": n_emp,
        "records_per_employee_sorted": [int(v) for v in per_emp["n"]],
        "top_3_share": float(per_emp["n"].head(3).sum() / len(df)),
        "top_10pct_employees": top10, "top_10pct_share": float(per_emp["n"].head(top10).sum() / len(df)),
        "gini": _gini(per_emp["n"].tolist()), "median_records": float(per_emp["n"].median()),
        "long_share_distribution": [{"bin": b, "employees": int(c)} for b, c in hist.items()],
        "long_share_distribution_note": f"Employees with at least {config.HOURS_BY_REASON_MIN_N} records only.",
        "ethics_note": "Aggregates only. The app never ranks, scores or identifies individual employees.",
    }

    return {
        "generated_utc": datetime.now(timezone.utc).isoformat(timespec="seconds"),
        "overview": overview, "durations": durations,
        "reasons": {"rows": reasons, "hours_by_reason": hours_by_reason,
                    "hours_by_reason_note": f"Reasons with fewer than {config.HOURS_BY_REASON_MIN_N} records are pooled as 'other'."},
        "calendar": calendar, "timeline": timeline, "employees": employees,
        "association": _association(df),
        "labels": {"reason": {str(k): v for k, v in REASON_LABELS.items()},
                   "month": {str(k): v for k, v in MONTH_LABELS.items()},
                   "weekday": {str(k): v for k, v in DAY_LABELS.items()}},
    }
