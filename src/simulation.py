"""
simulation.py - assumption-driven workforce scenario simulator (numpy only, no model, no data files).

WHAT IS MEASURED AND WHAT IS ASSUMED
  Measured (from the dataset, passed in as `hours_by_reason`): how many hours an absence EVENT lasts,
      overall and by reason.  This is the only data-derived input.
  Assumed (chosen by the user): headcount, horizon, shift length, how often absence events occur,
      reserve staff, required capacity, and (optionally) the reason mix.
The dataset holds absence events only (no attendance calendar, no headcount per month), so it cannot
measure an organisation's absence rate. The events-per-employee-per-month input is therefore a pure
assumption, and every output is conditional on it. Nothing here is a forecast.

DETERMINISTIC MODE   expected lost hours = expected events x mean hours per event (mix-weighted)
MONTE CARLO MODE     events ~ Poisson(expected events), durations resampled from the empirical
                     distribution (events assumed independent). Seeded, so results are reproducible.
"""
from dataclasses import dataclass, field
from typing import Dict, List, Optional

import numpy as np

from src import config

OTHER = "other"


class SimulationError(ValueError):
    """Invalid scenario or duration data."""


@dataclass(frozen=True)
class Scenario:
    name: str
    headcount: int                       # scheduled employees
    horizon_days: int                    # working days in the planning window
    shift_hours: float                   # scheduled hours per employee per day
    events_per_employee_per_month: float  # ASSUMED absence-event frequency
    reserve_staff: int = 0               # extra people available to cover
    required_capacity_pct: float = 100.0  # share of scheduled hours that must be worked
    reason_weights: Optional[Dict[str, float]] = None   # None = historical event mix


class DurationModel:
    """Empirical hours-per-event distribution, by reason, built from aggregate histograms."""

    def __init__(self, hours_by_reason: Dict[str, Dict]):
        if not hours_by_reason:
            raise SimulationError("No duration data available.")
        self.keys: List[str] = list(hours_by_reason)
        self.values: Dict[str, np.ndarray] = {}
        self.probs: Dict[str, np.ndarray] = {}
        self.events: Dict[str, int] = {}
        for k, entry in hours_by_reason.items():
            hist = entry["histogram"]
            self.values[k] = np.array([float(h) for h in hist], dtype=float)
            counts = np.array([float(c) for c in hist.values()], dtype=float)
            self.probs[k] = counts / counts.sum()
            self.events[k] = int(counts.sum())
        total = sum(self.events.values())
        self.historical_mix = {k: self.events[k] / total for k in self.keys}
        self.means = {k: float(self.values[k] @ self.probs[k]) for k in self.keys}

    def mix(self, weights: Optional[Dict[str, float]]) -> Dict[str, float]:
        if weights is None:
            return dict(self.historical_mix)
        unknown = [k for k in weights if k not in self.values]
        if unknown:
            raise SimulationError(f"Unknown reason keys in reason_weights: {unknown}")
        if any((not np.isfinite(w)) or w < 0 for w in weights.values()):
            raise SimulationError("reason_weights must be finite and non-negative.")
        total = float(sum(weights.values()))
        if total <= 0:
            raise SimulationError("reason_weights must contain at least one positive weight.")
        return {k: weights.get(k, 0.0) / total for k in self.keys}

    def mean_hours(self, mix: Dict[str, float]) -> float:
        return float(sum(mix[k] * self.means[k] for k in self.keys))

    def long_share(self, mix: Dict[str, float]) -> float:
        thr = config.LONG_ABSENCE_THRESHOLD_HOURS
        return float(sum(mix[k] * self.probs[k][self.values[k] >= thr].sum() for k in self.keys))

    def sample(self, rng: np.random.Generator, mix: Dict[str, float], size: int) -> np.ndarray:
        reasons = rng.choice(len(self.keys), size=size, p=[mix[k] for k in self.keys])
        out = np.empty(size)
        for i, k in enumerate(self.keys):
            idx = np.where(reasons == i)[0]
            if idx.size:
                out[idx] = rng.choice(self.values[k], size=idx.size, p=self.probs[k])
        return out


def validate(s: Scenario) -> None:
    problems = []
    if not (1 <= s.headcount <= 100000): problems.append("headcount must be between 1 and 100000")
    if not (1 <= s.horizon_days <= 366): problems.append("horizon_days must be between 1 and 366")
    if not (0 < s.shift_hours <= 24): problems.append("shift_hours must be above 0 and at most 24")
    if not (0 <= s.events_per_employee_per_month <= 10): problems.append("events_per_employee_per_month must be between 0 and 10")
    if not (0 <= s.reserve_staff <= 100000): problems.append("reserve_staff must be between 0 and 100000")
    if not (0 <= s.required_capacity_pct <= 100): problems.append("required_capacity_pct must be between 0 and 100")
    if problems:
        raise SimulationError("; ".join(problems))


def _pct(a: np.ndarray, q: float) -> float:
    return float(np.percentile(a, q))


def run_scenario(s: Scenario, durations: DurationModel, monte_carlo: bool = True,
                 n_sims: int = config.SIM_DEFAULT_N, seed: int = config.SIM_DEFAULT_SEED) -> Dict:
    validate(s)
    mix = durations.mix(s.reason_weights)
    mean_h = durations.mean_hours(mix)
    months = s.horizon_days / config.WORKING_DAYS_PER_MONTH
    scheduled = s.headcount * s.horizon_days * s.shift_hours
    required = scheduled * s.required_capacity_pct / 100.0
    reserve = s.reserve_staff * s.horizon_days * s.shift_hours
    exp_events = s.events_per_employee_per_month * s.headcount * months
    lost = min(exp_events * mean_h, scheduled)
    available = scheduled - lost + reserve
    gap = required - available                         # > 0 means a shortfall (hours)
    fte_days = lambda hours: hours / s.shift_hours / s.horizon_days   # hours -> average full-time staff
    result: Dict = {
        "name": s.name,
        "inputs": {"headcount": s.headcount, "horizon_days": s.horizon_days, "shift_hours": s.shift_hours,
                   "events_per_employee_per_month": s.events_per_employee_per_month, "reserve_staff": s.reserve_staff,
                   "required_capacity_pct": s.required_capacity_pct,
                   "reason_mix": "custom" if s.reason_weights is not None else "historical"},
        "deterministic": {
            "scheduled_hours": scheduled, "required_hours": required, "reserve_hours": reserve,
            "expected_events": exp_events, "mean_hours_per_event": mean_h,
            "assumed_absence_hours_pct_of_scheduled": 100 * lost / scheduled if scheduled else 0.0,
            "expected_lost_hours": lost, "available_hours": available,
            "gap_hours": gap, "shortfall": gap > 0, "gap_fte": fte_days(gap),
            "long_event_share_in_mix": durations.long_share(mix),
        },
        "warnings": [],
    }
    if lost >= scheduled and scheduled > 0:
        result["warnings"].append("Expected lost hours exceed scheduled hours and were capped; check the assumptions.")
    if exp_events < 5 and s.events_per_employee_per_month > 0:
        result["warnings"].append("Fewer than 5 expected absence events: simulated spread will be very wide.")
    if monte_carlo and exp_events * 200 > 5_000_000:
        result["warnings"].append("Monte Carlo skipped: the scenario implies too many events to simulate safely; "
                                  "use the deterministic result.")
        monte_carlo = False
    if monte_carlo:
        n_sims = int(max(200, min(n_sims, 20000)))
        n_sims = int(max(200, min(n_sims, 5_000_000 // max(exp_events, 1))))     # bound memory
        rng = np.random.default_rng(seed)
        counts = rng.poisson(exp_events, size=n_sims)
        total = int(counts.sum())
        hours = durations.sample(rng, mix, total) if total else np.array([])
        sim_lost = np.bincount(np.repeat(np.arange(n_sims), counts), weights=hours, minlength=n_sims) if total else np.zeros(n_sims)
        sim_lost = np.minimum(sim_lost, scheduled)
        sim_gap = required - (scheduled - sim_lost + reserve)
        result["monte_carlo"] = {
            "n_sims": n_sims, "seed": seed,
            "lost_hours": {"p10": _pct(sim_lost, 10), "p50": _pct(sim_lost, 50), "p90": _pct(sim_lost, 90), "mean": float(sim_lost.mean())},
            "gap_hours": {"p10": _pct(sim_gap, 10), "p50": _pct(sim_gap, 50), "p90": _pct(sim_gap, 90)},
            "probability_of_shortfall": float((sim_gap > 0).mean()),
            "assumptions": ["Events are independent and Poisson-distributed.",
                            "Durations are resampled from 697 historical events from one company (33 employees).",
                            "Heavy-tailed durations (up to 120 h) make the upper percentiles noisy."],
        }
    return result


def compare(scenarios: List[Scenario], durations: DurationModel, monte_carlo: bool = True,
            n_sims: int = config.SIM_DEFAULT_N, seed: int = config.SIM_DEFAULT_SEED) -> Dict:
    if not (1 <= len(scenarios) <= 4):
        raise SimulationError("Provide between 1 and 4 scenarios.")
    results = [run_scenario(s, durations, monte_carlo, n_sims, seed) for s in scenarios]
    base = results[0]["deterministic"]
    comparison = [{"name": r["name"],
                   "gap_hours": r["deterministic"]["gap_hours"],
                   "gap_vs_first_hours": r["deterministic"]["gap_hours"] - base["gap_hours"],
                   "expected_lost_hours": r["deterministic"]["expected_lost_hours"],
                   "shortfall": r["deterministic"]["shortfall"]} for r in results]
    return {"scenarios": results, "comparison": comparison,
            "disclaimer": ("Scenario outputs follow from the assumptions you entered. They are not predictions of any "
                           "organisation's absence and not outputs of the machine-learning model.")}
