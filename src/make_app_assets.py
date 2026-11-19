"""
make_app_assets.py - build every aggregate JSON the deployed API serves.

Run from the project root (needs data/raw/Absenteeism_at_work.csv and the trained model):
    python -m src.make_app_assets
Output (reports/app_assets/):  analytics.json, model_grid.json, evaluation.json
The deployed server never needs the raw CSV: it reads only these aggregate files. They contain
counts, rates and intervals; no employee ID and no row-level record.
"""
import json

import joblib
import numpy as np
import pandas as pd

from src import config
from src.analytics import build_analytics
from src.data_loader import build_modelling_dataset, load_raw_data
from src.models import get_final_shortlist

TABLES = config.PROJECT_ROOT / "reports" / "tables"


def _records(name: str, rename: dict = None) -> list:
    df = pd.read_csv(TABLES / name)
    if "Unnamed: 0" in df.columns:
        df = df.rename(columns={"Unnamed: 0": "model"})
    if rename:
        df = df.rename(columns=rename)
    return json.loads(df.to_json(orient="records"))


def build_model_grid(analytics: dict) -> dict:
    """Model-implied probabilities summarised over the full input grid, plus the reason-only comparator."""
    pipe = joblib.load(config.MODEL_PATH)
    meta = json.loads(config.METADATA_PATH.read_text())
    sch = meta["input_schema"]
    reasons, months, days = sch[config.REASON]["allowed"], sch[config.MONTH]["allowed"], sch[config.DAY_OF_WEEK]["allowed"]
    grid = pd.DataFrame([(r, m, d) for r in reasons for m in months for d in days], columns=config.FINAL_FEATURE_COLUMNS)
    grid["p"] = pipe.predict_proba(grid)[:, 1]
    # reason-only logistic regression fitted on all modelled rows (a comparator shown next to the deployed model)
    model_df = build_modelling_dataset(load_raw_data())
    ro = get_final_shortlist()["Reason-only baseline (LR)"].fit(model_df[config.FINAL_FEATURE_COLUMNS], model_df[config.TARGET_COLUMN])
    ro_p = ro.predict_proba(pd.DataFrame({config.REASON: reasons, config.MONTH: 1, config.DAY_OF_WEEK: 2})[config.FINAL_FEATURE_COLUMNS])[:, 1]
    mix = {r["code"]: r["event_share"] for r in analytics["reasons"]["rows"]}
    w = grid[config.REASON].map(mix)
    by = lambda col: [{"code": int(k), "weighted_probability": float(np.average(g["p"], weights=w[g.index]))} for k, g in grid.groupby(col)]
    thr = float(meta["decision_threshold"])
    per_reason = grid.groupby(config.REASON)["p"].agg(["mean", "min", "max"])
    iqr = grid.groupby(config.REASON)["p"].apply(lambda v: float(np.percentile(v, 75) - np.percentile(v, 25)))
    flag_share = grid.groupby(config.REASON)["p"].apply(lambda v: float((v >= thr).mean()))
    flips = [int(r) for r, f in flag_share.items() if 0 < f < 1]      # reasons whose flag depends on month/weekday
    return {
        "reasons": {str(int(r)): {"model_mean": float(per_reason.loc[r, "mean"]), "model_min": float(per_reason.loc[r, "min"]),
                                  "model_max": float(per_reason.loc[r, "max"]), "reason_only": float(ro_p[i])}
                    for i, r in enumerate(reasons)},
        "month_marginal": by(config.MONTH), "weekday_marginal": by(config.DAY_OF_WEEK),
        "month_day_spread_within_reason": {"median_iqr": float(iqr.median()), "max_iqr": float(iqr.max()),
                                           "reasons_whose_flag_depends_on_month_or_weekday": flips,
                                           "threshold": thr},
        "note": "Computed from the saved model over all 1,620 supported input combinations; reason-only is a comparator fitted on the same data.",
    }


def build_evaluation() -> dict:
    per_emp = pd.read_csv(TABLES / "final_test_per_employee.csv")
    per_emp.insert(0, "label", [f"Employee {chr(65 + i)}" for i in range(len(per_emp))])
    return {
        "model_comparison": {
            "all_13_features": _records("exp1_full_features_grouped_cv.csv"),
            "three_inputs": _records("exp5_reduced_features_grouped_cv.csv"),
            "confirmation_fresh_seeds": _records("exp7_confirmation_fresh_seeds.csv"),
        },
        "random_vs_grouped": _records("exp2_random_vs_grouped.csv"),
        "feature_ablation": _records("exp3_feature_set_ablation.csv"),
        "tuning": _records("exp6_tuning_nested_cv.csv"),
        "threshold_curve": _records("final_threshold_curve.csv"),
        "test_per_employee": json.loads(per_emp.drop(columns=["employee"]).to_json(orient="records")),
        "note": "Tables are copied from reports/tables (real runs). Test employees are anonymised.",
    }


def main():
    config.APP_ASSETS_DIR.mkdir(parents=True, exist_ok=True)
    analytics = build_analytics()
    for path, data in [(config.ANALYTICS_PATH, analytics), (config.MODEL_GRID_PATH, build_model_grid(analytics)),
                       (config.EVALUATION_PATH, build_evaluation())]:
        path.write_text(json.dumps(data, indent=1))
        print("wrote", path.relative_to(config.PROJECT_ROOT), f"({path.stat().st_size / 1024:.0f} KB)")


if __name__ == "__main__":
    main()
