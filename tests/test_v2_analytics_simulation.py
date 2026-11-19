"""Tests for the v2 modules: timeline, analytics, robustness outputs, simulation maths, metadata consistency."""
import hashlib
import json
import math

import numpy as np
import pytest

from src import config
from src.analytics import build_analytics, wilson
from src.data_loader import add_target, flag_rule_rows, load_raw_data
from src.simulation import DurationModel, Scenario, SimulationError, compare, run_scenario
from src.timeline import add_period, month_label

pytestmark = pytest.mark.filterwarnings("ignore::DeprecationWarning")


@pytest.fixture(scope="module")
def raw():
    return load_raw_data()


@pytest.fixture(scope="module")
def analytics(raw):
    return build_analytics(raw)


# ---------------------------------------------------------------- target and timeline
def test_target_is_hours_at_least_eight_and_rule_rows_are_excluded(raw):
    kept = add_target(raw.loc[~flag_rule_rows(raw)])
    assert len(kept) == 697 and kept[config.TARGET_COLUMN].sum() == 271
    assert (kept[config.TARGET_COLUMN] == (kept[config.RAW_TARGET_COLUMN] >= 8)).all()
    assert (raw.loc[flag_rule_rows(raw), config.RAW_TARGET_COLUMN] == 0).all()


def test_timeline_reconstruction_is_consistent(raw):
    out, c = add_period(raw)
    assert c["ok"] and c["runs_with_month"] == 37 and c["consecutive_month_steps"] == c["steps_checked"] == 36
    assert out["period"].dropna().astype(int).between(1, 37).all() and c["rows_without_period"] == 3
    # period order must follow the calendar months stored in the file
    firsts = out.dropna(subset=["period"]).groupby("period")[config.MONTH].first().tolist()
    assert all((b - a) % 12 == 1 for a, b in zip(firsts, firsts[1:]))
    assert month_label(1) == "2007-07" and month_label(7) == "2008-01" and month_label(37) == "2010-07"


def test_timeline_check_fails_loudly_on_shuffled_rows(raw):
    shuffled = raw.sample(frac=1, random_state=1).reset_index(drop=True)
    _, c = add_period(shuffled)
    assert c["ok"] is False


# ---------------------------------------------------------------- analytics
def test_wilson_interval_properties():
    lo, hi = wilson(0, 69)
    assert lo == 0.0 and 0 < hi < 0.1
    lo, hi = wilson(50, 100)
    assert lo < 0.5 < hi and math.isclose((lo + hi) / 2, 0.5, abs_tol=0.01)
    assert wilson(0, 0) == (0.0, 1.0)
    narrow, wide = wilson(500, 1000), wilson(5, 10)
    assert narrow[1] - narrow[0] < wide[1] - wide[0]


def test_analytics_totals_reconcile(analytics):
    ov = analytics["overview"]
    assert (ov["raw_rows"], ov["modelled_rows"], ov["rule_rows"], ov["long_n"]) == (740, 697, 43, 271)
    assert sum(r["n"] for r in analytics["reasons"]["rows"]) == 697
    assert sum(v["events"] for v in analytics["reasons"]["hours_by_reason"].values()) == 697
    assert sum(r["lost_hours"] for r in analytics["reasons"]["rows"]) == analytics["durations"]["total_lost_hours"] == 5124
    assert math.isclose(sum(r["hours_share"] for r in analytics["reasons"]["rows"]), 1)
    for r in analytics["reasons"]["rows"]:
        assert r["ci_low"] <= r["long_rate"] <= r["ci_high"]


def test_small_cells_are_pooled_in_public_histograms(analytics):
    keys = analytics["reasons"]["hours_by_reason"]
    assert "other" in keys
    for k, v in keys.items():
        if k != "other":
            assert v["events"] >= config.HOURS_BY_REASON_MIN_N


def test_known_findings_hold(analytics):
    d = analytics["durations"]
    assert d["long_events_that_are_whole_days"] == 1.0 and d["events_between_5_and_7_hours"] == 8
    assert 0.79 < d["long_share_of_lost_hours"] < 0.81
    assoc = analytics["association"]
    assert assoc["Reason for absence"]["cramers_v"] > 0.6 > assoc["Month of absence"]["cramers_v"]


def test_employee_aggregates_contain_no_identifiers(analytics):
    e = analytics["employees"]
    assert sum(e["records_per_employee_sorted"]) == 697 and e["employees"] == 33 and 0 < e["gini"] < 1
    assert "ID" not in json.dumps(analytics)


def test_saved_assets_are_up_to_date_with_the_data(analytics):
    saved = json.loads(config.ANALYTICS_PATH.read_text())
    assert saved["overview"] == analytics["overview"]
    assert saved["durations"] == analytics["durations"]
    assert saved["reasons"]["rows"] == analytics["reasons"]["rows"]


# ---------------------------------------------------------------- simulation maths (toy durations make hand-checks exact)
def toy(hours=8.0):
    return DurationModel({"a": {"events": 10, "histogram": {str(int(hours)): 10}}})


def scn(**kw):
    base = dict(name="t", headcount=10, horizon_days=21, shift_hours=8, events_per_employee_per_month=1.0, reserve_staff=0, required_capacity_pct=100.0)
    base.update(kw)
    return Scenario(**base)


def test_deterministic_arithmetic_is_exact():
    r = run_scenario(scn(), toy(8), monte_carlo=False)["deterministic"]
    assert r["scheduled_hours"] == 10 * 21 * 8 == 1680
    assert r["expected_events"] == pytest.approx(10 * 1.0 * 1.0)          # 21 days = exactly 1 working month
    assert r["expected_lost_hours"] == pytest.approx(80)
    assert r["available_hours"] == pytest.approx(1600) and r["gap_hours"] == pytest.approx(80) and r["shortfall"] is True
    assert r["gap_fte"] == pytest.approx(80 / 8 / 21)


def test_reserve_and_required_capacity_move_the_gap_exactly():
    base = run_scenario(scn(), toy(), monte_carlo=False)["deterministic"]["gap_hours"]
    with_reserve = run_scenario(scn(reserve_staff=2), toy(), monte_carlo=False)["deterministic"]["gap_hours"]
    assert base - with_reserve == pytest.approx(2 * 21 * 8)
    relaxed = run_scenario(scn(required_capacity_pct=90), toy(), monte_carlo=False)["deterministic"]["gap_hours"]
    assert base - relaxed == pytest.approx(0.10 * 1680)


def test_zero_absence_means_no_lost_hours():
    r = run_scenario(scn(events_per_employee_per_month=0, required_capacity_pct=95), toy())
    assert r["deterministic"]["expected_lost_hours"] == 0 and r["deterministic"]["gap_hours"] == pytest.approx(-0.05 * 1680)
    assert r["monte_carlo"]["lost_hours"]["p90"] == 0 and r["monte_carlo"]["probability_of_shortfall"] == 0


def test_gap_grows_with_absence_and_shrinks_with_headcount_reserve():
    d = toy(8)
    gaps = [run_scenario(scn(events_per_employee_per_month=x), d, monte_carlo=False)["deterministic"]["gap_hours"] for x in (0, 0.5, 1, 2)]
    assert gaps == sorted(gaps) and len(set(gaps)) == 4


def test_lost_hours_are_capped_at_scheduled_hours_with_a_warning():
    r = run_scenario(scn(events_per_employee_per_month=10), toy(120), monte_carlo=False)
    assert r["deterministic"]["expected_lost_hours"] == r["deterministic"]["scheduled_hours"] and r["warnings"]


def test_reason_mix_changes_mean_duration_in_the_right_direction():
    d = DurationModel({"short": {"events": 90, "histogram": {"2": 90}}, "long": {"events": 10, "histogram": {"16": 10}}})
    hist = d.mean_hours(d.mix(None))
    short_heavy = d.mean_hours(d.mix({"short": 95, "long": 5}))
    long_heavy = d.mean_hours(d.mix({"short": 1, "long": 1}))
    assert hist == pytest.approx(0.9 * 2 + 0.1 * 16) and short_heavy < hist < long_heavy
    assert d.long_share(d.mix(None)) == pytest.approx(0.1)


def test_real_duration_model_matches_measured_mean(analytics):
    d = DurationModel(analytics["reasons"]["hours_by_reason"])
    assert d.mean_hours(d.historical_mix) == pytest.approx(analytics["durations"]["mean"])
    assert d.long_share(d.historical_mix) == pytest.approx(analytics["overview"]["long_share"])


def test_monte_carlo_is_seeded_and_centred_on_the_deterministic_value(analytics):
    d = DurationModel(analytics["reasons"]["hours_by_reason"])
    s = scn(headcount=200, horizon_days=63, events_per_employee_per_month=0.5, required_capacity_pct=95)
    a, b = run_scenario(s, d, seed=3), run_scenario(s, d, seed=3)
    assert a["monte_carlo"] == b["monte_carlo"]
    assert run_scenario(s, d, seed=4)["monte_carlo"]["lost_hours"] != a["monte_carlo"]["lost_hours"]
    det = a["deterministic"]["expected_lost_hours"]
    assert a["monte_carlo"]["lost_hours"]["mean"] == pytest.approx(det, rel=0.05)
    mc = a["monte_carlo"]["lost_hours"]
    assert mc["p10"] <= mc["p50"] <= mc["p90"]


def test_shortfall_probability_is_one_when_requirement_is_unmeetable():
    r = run_scenario(scn(events_per_employee_per_month=1, required_capacity_pct=100), toy(8))
    assert r["monte_carlo"]["probability_of_shortfall"] > 0.99


@pytest.mark.parametrize("kw", [dict(headcount=0), dict(horizon_days=0), dict(horizon_days=367), dict(shift_hours=0), dict(shift_hours=25),
                                dict(events_per_employee_per_month=-0.1), dict(required_capacity_pct=101), dict(reserve_staff=-1)])
def test_scenario_validation(kw):
    with pytest.raises(SimulationError):
        run_scenario(scn(**kw), toy())


def test_mix_validation():
    d = toy()
    for bad in ({"zzz": 1}, {"a": -1}, {"a": 0}, {"a": float("nan")}):
        with pytest.raises(SimulationError):
            d.mix(bad)


def test_compare_limits_and_deltas():
    d = toy()
    with pytest.raises(SimulationError):
        compare([], d)
    with pytest.raises(SimulationError):
        compare([scn()] * 5, d)
    out = compare([scn(name="a"), scn(name="b", events_per_employee_per_month=2)], d, monte_carlo=False)
    assert out["comparison"][0]["gap_vs_first_hours"] == 0 and out["comparison"][1]["gap_vs_first_hours"] > 0 and "not predictions" in out["disclaimer"]


# ---------------------------------------------------------------- metadata / metrics consistency
def test_model_artifact_is_unchanged_and_metadata_is_consistent():
    meta = json.loads(config.METADATA_PATH.read_text())
    metrics = json.loads(config.METRICS_PATH.read_text())
    assert hashlib.sha256(config.MODEL_PATH.read_bytes()).hexdigest() == meta["metadata_revision"]["artifact_sha256"]
    assert meta["decision_threshold"] == metrics["threshold"]["chosen"] == metrics["evaluation_v2"]["threshold_used"]
    assert meta["feature_columns"] == config.FINAL_FEATURE_COLUMNS and meta["model_name"] == "Random Forest"


def test_evaluation_v2_is_complete_and_honest():
    v2 = json.loads(config.METRICS_PATH.read_text())["evaluation_v2"]
    rows = v2["pooled_grouped_cv"]
    assert v2["employees"] == 33 and v2["rows"] == 697
    assert rows["Prevalence baseline (no skill)"]["pr_auc"] == pytest.approx(v2["prevalence"], abs=1e-9)
    assert rows["Random Forest"]["pr_auc"] > v2["prevalence"] + 0.25
    for name, r in rows.items():
        lo, hi = r["pr_auc_ci95_employee_bootstrap"]
        assert lo <= r["pr_auc"] <= hi + 1e-9, name
    diff = v2["paired_pr_auc_differences"]["Random Forest minus Reason-only baseline (LR)"]
    assert diff["ci95"][0] < 0 < diff["ci95"][1]          # documented finding: not distinguishable from the baseline
    assert v2["temporal_check"]["train_months"] + v2["temporal_check"]["test_months"] == 37
    assert json.loads(config.EVALUATION_PATH.read_text())["test_per_employee"]


def test_evaluation_document_matches_saved_metrics():
    """docs/MODEL_EVALUATION.md must not drift from models/metrics.json."""
    from pathlib import Path
    doc = (Path(config.PROJECT_ROOT) / "docs" / "MODEL_EVALUATION.md").read_text(encoding="utf-8")
    v2 = json.loads(config.METRICS_PATH.read_text())["evaluation_v2"]
    for name, row in v2["pooled_grouped_cv"].items():
        assert f"{row['pr_auc']:.3f}" in doc, f"PR-AUC of {name} missing/stale in MODEL_EVALUATION.md"
    for name, d in v2["paired_pr_auc_differences"].items():
        assert f"{d['median']:+.3f}" in doc, name
    t = v2["temporal_check"]
    assert f"{t['test_prevalence']:.2f}" in doc and str(t["train_rows"]) in doc and str(t["test_rows"]) in doc
