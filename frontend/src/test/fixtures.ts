// Small hand-written fixtures that mirror the API response shapes. Used only by tests.
export const meta = {
  model: { name: 'Random Forest', version: '1.0.0', created_utc: '2026-01-01', threshold: 0.34, task: 'binary', limitations: ['Small data.'],
    training: { rows_used_for_deployed_model: 697, employees: 33 }, revision: 2 },
  inputs: {
    reasons: [{ code: 23, label: 'Medical consultation', n: 149, tier: 'mostly short' }, { code: 13, label: 'Musculoskeletal diseases', n: 55, tier: 'mostly long' }],
    months: [{ code: 7, label: 'July' }, { code: 8, label: 'August' }], weekdays: [{ code: 3, label: 'Tuesday' }, { code: 4, label: 'Wednesday' }],
  },
  simulation: { reason_keys: [{ key: '23', label: 'Medical consultation', tier: 'mostly short', events: 149, historical_share: 0.5, mean_hours: 2 },
    { key: '13', label: 'Musculoskeletal diseases', tier: 'mostly long', events: 55, historical_share: 0.5, mean_hours: 14 }], working_days_per_month: 21, limits: {} },
  dataset: { modelled_rows: 697, employees: 33, long_share: 0.389 },
}
export const overview = { raw_rows: 740, raw_columns: 21, raw_employees: 36, missing_values: 0, exact_duplicate_rows: 34, rule_rows: 43, rule_rows_all_zero_hours: true,
  modelled_rows: 697, modelled_employees: 33, long_n: 271, long_share: 0.389, long_threshold_hours: 8, months_covered: 37, duplicate_note: 'Kept.' }
export const durations = { histogram: [{ hours: 8, events: 208, long: true }], mean: 7.35, median: 3, p90: 8, max: 120, events_between_5_and_7_hours: 8,
  events_exactly_8_hours: 208, long_events_that_are_whole_days: 1, long_share_of_events: 0.389, long_share_of_lost_hours: 0.801, total_lost_hours: 5124 }
export const predictOk = {
  reason: 23, month: 7, weekday: 3, reason_label: 'Medical consultation', month_label: 'July', weekday_label: 'Tuesday', probability_long: 0.074, predicted_long: false,
  threshold: 0.34, label: 'short (<8 hours)', reason_only_probability: 0.1, historical: { n: 149, long_rate: 0.087, ci_low: 0.05, ci_high: 0.14, low_n: false, tier: 'mostly short' },
  sensitivity: { min_probability: 0.04, max_probability: 0.28, share_of_month_weekday_combinations_flagged: 0, flag_depends_on_month_or_weekday: false },
  model_name: 'Random Forest', model_version: '1.0.0',
}
const det = (gap: number) => ({ scheduled_hours: 50400, required_hours: 45360, reserve_hours: 1512, expected_events: 150, mean_hours_per_event: 7.35, assumed_absence_hours_pct_of_scheduled: 2.2,
  expected_lost_hours: 1102, available_hours: 50809, gap_hours: gap, shortfall: gap > 0, gap_fte: gap / 504, long_event_share_in_mix: 0.39 })
export const simulateOk = {
  scenarios: [{ name: 'Baseline', deterministic: det(-5449), warnings: [], monte_carlo: { n_sims: 2000, seed: 42, lost_hours: { p10: 870, p50: 1088, p90: 1340 }, gap_hours: { p10: 0, p50: 0, p90: 0 }, probability_of_shortfall: 0, assumptions: ['Events are independent.'] } },
    { name: 'Higher absence', deterministic: det(1200), warnings: ['Example warning.'], monte_carlo: { n_sims: 2000, seed: 42, lost_hours: { p10: 3000, p50: 3300, p90: 3700 }, gap_hours: { p10: 0, p50: 0, p90: 0 }, probability_of_shortfall: 0.62, assumptions: [] } }],
  comparison: [{ name: 'Baseline', gap_hours: -5449, gap_vs_first_hours: 0, expected_lost_hours: 1102, shortfall: false }, { name: 'Higher absence', gap_hours: 1200, gap_vs_first_hours: 6649, expected_lost_hours: 3300, shortfall: true }],
  disclaimer: 'Scenario outputs follow from the assumptions you entered.',
}

type Handler = (url: string, init?: RequestInit) => { status?: number; body: unknown }
/** Install a fake fetch that routes by path (without the /api prefix). */
export function mockFetch(routes: Record<string, Handler | unknown>) {
  const fn = vi.fn(async (input: RequestInfo | URL, init?: RequestInit) => {
    const url = String(input).replace(/^.*\/api/, '')
    const route = routes[url]
    if (route === undefined) return new Response(JSON.stringify({ error: { code: 'not_found', message: 'Not found', details: [] } }), { status: 404 })
    const out = typeof route === 'function' ? (route as Handler)(url, init)
      : (route && typeof route === 'object' && 'body' in route) ? (route as { status?: number; body: unknown }) : { body: route }
    return new Response(JSON.stringify(out.body), { status: out.status ?? 200, headers: { 'Content-Type': 'application/json' } })
  })
  vi.stubGlobal('fetch', fn)
  return fn
}
