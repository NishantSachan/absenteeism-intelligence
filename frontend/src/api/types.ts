export interface ErrorDetail { field: string | null; message: string }
export interface Health { status: string; model_loaded: boolean; model_name?: string; model_version?: string }

export interface ReasonOption { code: number; label: string; n: number; tier: string }
export interface Option { code: number; label: string }
export interface SimReasonKey { key: string; label: string; tier: string; events: number; historical_share: number; mean_hours: number }

export interface Meta {
  model: { name: string; version: string; created_utc: string; threshold: number; task: string; limitations: string[]
    training: { rows_used_for_deployed_model: number; employees: number }; revision: number }
  inputs: { reasons: ReasonOption[]; months: Option[]; weekdays: Option[] }
  simulation: { reason_keys: SimReasonKey[]; working_days_per_month: number; limits: Record<string, number[]> }
  dataset: { modelled_rows: number; employees: number; long_share: number }
}

export interface PredictRequest { reason: number; month: number; weekday: number }
export interface PredictResponse {
  reason: number; month: number; weekday: number; reason_label: string; month_label: string; weekday_label: string
  probability_long: number; predicted_long: boolean; threshold: number; label: string
  reason_only_probability: number | null
  historical: { n: number; long_rate: number; ci_low: number; ci_high: number; low_n: boolean; tier: string } | null
  sensitivity: { min_probability: number; max_probability: number; share_of_month_weekday_combinations_flagged: number; flag_depends_on_month_or_weekday: boolean }
  model_name: string; model_version: string
}

export interface RateRow { n: number; long_n: number; long_rate: number; ci_low: number; ci_high: number; mean_hours: number; lost_hours: number }
export interface ReasonRow extends RateRow { code: number; label: string; event_share: number; hours_share: number; low_n: boolean; tier: string }
export interface Overview {
  raw_rows: number; raw_columns: number; raw_employees: number; missing_values: number; exact_duplicate_rows: number
  rule_rows: number; rule_rows_all_zero_hours: boolean; modelled_rows: number; modelled_employees: number
  long_n: number; long_share: number; long_threshold_hours: number; months_covered: number; duplicate_note: string
}
export interface Durations {
  histogram: { hours: number; events: number; long: boolean }[]; mean: number; median: number; p90: number; max: number
  events_between_5_and_7_hours: number; events_exactly_8_hours: number; long_events_that_are_whole_days: number
  long_share_of_events: number; long_share_of_lost_hours: number; total_lost_hours: number
}
export interface Reasons { rows: ReasonRow[]; hours_by_reason_note: string }
export interface Calendar { by_month: (RateRow & { code: number; label: string })[]; by_weekday: (RateRow & { code: number; label: string })[]; note: string }
export interface Timeline {
  periods: (RateRow & { period: number; label: string })[]
  segments: Record<string, { months: number; events: number; long_rate: number; events_per_month: number }>
  consistency: { ok: boolean; consecutive_month_steps: number; steps_checked: number; runs_with_month: number; assumed_start: string; note: string; rows_without_period: number }
  events_per_month: { mean: number; min: number; max: number; months: number }; caveat: string
}
export interface Employees {
  employees: number; records_per_employee_sorted: number[]; top_3_share: number; top_10pct_employees: number; top_10pct_share: number
  gini: number; median_records: number; long_share_distribution: { bin: string; employees: number }[]; long_share_distribution_note: string; ethics_note: string
}
export interface AssociationEntry { chi2: number; p_value: number; dof: number; cramers_v: number }
export type Association = Record<string, AssociationEntry | string>

export interface PooledRow { pr_auc: number; pr_auc_sd_over_seeds: number; roc_auc: number; brier: number; recall: number; precision: number; f1: number; pr_auc_ci95_employee_bootstrap: [number, number] }
export interface EvaluationV2 {
  threshold_used: number; seeds: number; rows: number; employees: number; prevalence: number
  pooled_grouped_cv: Record<string, PooledRow>
  paired_pr_auc_differences: Record<string, { median: number; ci95: [number, number] }>
  calibration_random_forest: { mean_predicted: number; observed_rate: number; n: number }[]
  temporal_check: { train_months: number; test_months: number; train_rows: number; test_rows: number; train_prevalence: number; test_prevalence: number
    test_employees: number; test_employees_also_in_train: number; models: Record<string, { pr_auc: number; roc_auc: number; recall: number; precision: number; f1: number }>; note: string }
  original_test_split_like_for_like: Record<string, any>
  conclusion: string
}
export type Row = Record<string, string | number>
export interface ModelMetrics {
  model: { name: string; version: string; created_utc: string; threshold: number; threshold_rule: string; assumed_fn_to_fp_cost_ratio: number
    threshold_sensitivity: Record<string, number>; training: { rows_used_for_deployed_model: number; employees: number }
    library_versions: Record<string, string>; limitations: string[]; feature_columns: string[] }
  metrics: {
    test: Record<string, any>
    permutation_importance: Record<string, number>
    evaluation_v2: EvaluationV2
    [k: string]: any
  }
  evaluation: {
    model_comparison: Record<string, Row[]>; random_vs_grouped: Row[]; feature_ablation: Row[]
    threshold_curve: { threshold: number; recall: number; precision: number; cost_per_100?: number }[]
    test_per_employee: { label: string; rows: number; long_share: number; accuracy: number }[]
  }
  model_grid: { reasons: Record<string, { model_mean: number; reason_only: number }>
    month_day_spread_within_reason: { median_iqr: number; max_iqr: number; reasons_whose_flag_depends_on_month_or_weekday: number[]; threshold: number } }
}

export interface ScenarioInput {
  name: string; headcount: number; horizon_days: number; shift_hours: number; events_per_employee_per_month: number
  reserve_staff: number; required_capacity_pct: number; reason_weights: Record<string, number> | null
}
export interface ScenarioResult {
  name: string
  deterministic: { scheduled_hours: number; required_hours: number; reserve_hours: number; expected_events: number; mean_hours_per_event: number
    assumed_absence_hours_pct_of_scheduled: number; expected_lost_hours: number; available_hours: number; gap_hours: number; shortfall: boolean; gap_fte: number; long_event_share_in_mix: number }
  monte_carlo?: { n_sims: number; seed: number; lost_hours: Record<string, number>; gap_hours: Record<string, number>; probability_of_shortfall: number; assumptions: string[] }
  warnings: string[]
}
export interface SimulateResponse {
  scenarios: ScenarioResult[]
  comparison: { name: string; gap_hours: number; gap_vs_first_hours: number; expected_lost_hours: number; shortfall: boolean }[]
  disclaimer: string
}
