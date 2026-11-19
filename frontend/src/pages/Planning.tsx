import { useMemo, useState } from 'react'
import { ApiRequestError } from '../api/client'
import { api } from '../api/endpoints'
import type { Meta, ScenarioInput, SimulateResponse } from '../api/types'
import { Chart } from '../components/charts'
import { Footer, Hero, Info, Kicker, Load, Table, Warn } from '../components/ui'
import { Bar, BarChart, CartesianGrid, Cell, ReferenceLine, Tooltip, XAxis, YAxis } from 'recharts'
import { COLORS, hours, num, pct } from '../lib/format'
import { useApi } from '../lib/useApi'

type Preset = 'historical' | 'short' | 'long'
interface Draft { name: string; headcount: string; horizon_days: string; shift_hours: string; events: string; reserve: string; required: string; preset: Preset }

const DEFAULTS: Draft[] = [
  { name: 'Baseline', headcount: '100', horizon_days: '63', shift_hours: '8', events: '0.5', reserve: '3', required: '90', preset: 'historical' },
  { name: 'Higher absence', headcount: '100', horizon_days: '63', shift_hours: '8', events: '1.5', reserve: '3', required: '90', preset: 'historical' },
]

const FIELDS: { key: keyof Omit<Draft, 'name' | 'preset'>; label: string; hint: string; min: number; max: number; integer?: boolean; step: string }[] = [
  { key: 'headcount', label: 'Scheduled employees', hint: 'people', min: 1, max: 100000, integer: true, step: '1' },
  { key: 'horizon_days', label: 'Planning window', hint: 'working days', min: 1, max: 366, integer: true, step: '1' },
  { key: 'shift_hours', label: 'Shift length', hint: 'hours per day', min: 0.5, max: 24, step: '0.5' },
  { key: 'events', label: 'Assumed absence events', hint: 'per employee per month (your assumption)', min: 0, max: 10, step: '0.1' },
  { key: 'reserve', label: 'Reserve staff', hint: 'extra people available', min: 0, max: 100000, integer: true, step: '1' },
  { key: 'required', label: 'Required capacity', hint: '% of scheduled hours that must be worked', min: 0, max: 100, step: '1' },
]

export function validateDraft(d: Draft): Record<string, string> {
  const errs: Record<string, string> = {}
  if (!d.name.trim()) errs.name = 'Name is required.'
  for (const f of FIELDS) {
    const raw = d[f.key]
    const v = Number(raw)
    if (raw.trim() === '' || Number.isNaN(v)) errs[f.key] = 'Enter a number.'
    else if (v < f.min || v > f.max) errs[f.key] = `Must be between ${f.min} and ${f.max}.`
    else if (f.integer && !Number.isInteger(v)) errs[f.key] = 'Use a whole number.'
  }
  return errs
}

function weightsFor(preset: Preset, meta: Meta): Record<string, number> | null {
  if (preset === 'historical') return null
  const want = preset === 'short' ? 'mostly short' : 'mostly long'
  return Object.fromEntries(meta.simulation.reason_keys.map(k => [k.key, k.historical_share * (k.tier === want ? 2 : 1)]))
}

export default function Planning() {
  const meta = useApi(api.meta)
  return (
    <>
      <Hero eyebrow="Workforce Planning" title="What-if staffing scenarios">
        Enter your own assumptions and compare scenarios. The only measured ingredient is how long absence events lasted historically.
      </Hero>
      <Load state={meta}>{m => <Simulator meta={m} />}</Load>
      <Footer />
    </>
  )
}

function Simulator({ meta }: { meta: Meta }) {
  const [drafts, setDrafts] = useState<Draft[]>(DEFAULTS)
  const [mc, setMc] = useState(true)
  const [busy, setBusy] = useState(false)
  const [apiError, setApiError] = useState<ApiRequestError | null>(null)
  const [result, setResult] = useState<SimulateResponse | null>(null)
  const [showErrors, setShowErrors] = useState(false)
  const errors = useMemo(() => drafts.map(validateDraft), [drafts])
  const valid = errors.every(e => Object.keys(e).length === 0)

  const update = (i: number, patch: Partial<Draft>) => setDrafts(ds => ds.map((d, j) => (j === i ? { ...d, ...patch } : d)))

  async function run() {
    setShowErrors(true)
    if (!valid) return
    const body: ScenarioInput[] = drafts.map(d => ({
      name: d.name.trim(), headcount: Number(d.headcount), horizon_days: Number(d.horizon_days), shift_hours: Number(d.shift_hours),
      events_per_employee_per_month: Number(d.events), reserve_staff: Number(d.reserve), required_capacity_pct: Number(d.required),
      reason_weights: weightsFor(d.preset, meta),
    }))
    setBusy(true); setApiError(null)
    try { setResult(await api.simulate(body, mc)) }
    catch (e) { setResult(null); setApiError(e instanceof ApiRequestError ? e : new ApiRequestError(0, 'unknown', 'Something went wrong.')) }
    finally { setBusy(false) }
  }

  return (
    <>
      <div className="grid g2">
        <div className="assump"><strong>You assume:</strong> headcount, window, shift length, how often absence events happen, reserve staff, required capacity and (optionally) the reason mix. These are inputs, not measurements or model predictions.</div>
        <div className="measured"><strong>The data supplies:</strong> how long an absence event lasts, by reason, from {meta.dataset.modelled_rows} events at one company. The dataset cannot tell you any organisation’s absence rate.</div>
      </div>

      <Kicker>Scenarios</Kicker>
      <div className="grid g2">
        {drafts.map((d, i) => (
          <fieldset key={i} className="card scenario" style={{ border: undefined }} aria-label={`Scenario ${i + 1}`}>
            <label className="field">Scenario name
              <input type="text" value={d.name} maxLength={60} aria-invalid={showErrors && !!errors[i].name} onChange={e => update(i, { name: e.target.value })} />
            </label>
            <div className="grid g2" style={{ marginTop: 10 }}>
              {FIELDS.map(f => (
                <label className="field" key={f.key}>{f.label}
                  <input type="number" inputMode="decimal" step={f.step} min={f.min} max={f.max} value={d[f.key]} aria-invalid={showErrors && !!errors[i][f.key]}
                    onChange={e => update(i, { [f.key]: e.target.value } as Partial<Draft>)} />
                  <span className="hint">{f.hint}</span>
                  {showErrors && errors[i][f.key] && <span className="field-error" role="alert">{errors[i][f.key]}</span>}
                </label>
              ))}
            </div>
            <label className="field" style={{ marginTop: 10 }}>Reason mix
              <select value={d.preset} onChange={e => update(i, { preset: e.target.value as Preset })}>
                <option value="historical">Historical mix</option>
                <option value="short">More short appointment-type reasons (×2)</option>
                <option value="long">More long illness-type reasons (×2)</option>
              </select>
            </label>
            {drafts.length > 1 && <button style={{ marginTop: 10 }} onClick={() => setDrafts(ds => ds.filter((_, j) => j !== i))}>Remove scenario</button>}
          </fieldset>
        ))}
      </div>
      <div style={{ display: 'flex', gap: 12, flexWrap: 'wrap', alignItems: 'center', margin: '14px 0' }}>
        {drafts.length < 4 && <button onClick={() => setDrafts(ds => [...ds, { ...ds[ds.length - 1], name: `Scenario ${ds.length + 1}` }])}>Add scenario</button>}
        <label style={{ display: 'flex', gap: 8, alignItems: 'center' }}><input type="checkbox" checked={mc} onChange={e => setMc(e.target.checked)} /> Include Monte Carlo spread</label>
        <button className="primary" onClick={run} disabled={busy}>{busy ? 'Calculating…' : 'Run scenarios'}</button>
      </div>
      {showErrors && !valid && <div className="error-strip" role="alert">Please fix the highlighted fields before running.</div>}
      {apiError && <div className="error-strip" role="alert"><strong>{apiError.message}</strong>{apiError.details.map((d, i) => <div key={i}>{d.field ? `${d.field}: ` : ''}{d.message}</div>)}</div>}
      {result && <Results r={result} />}
    </>
  )
}

function Results({ r }: { r: SimulateResponse }) {
  const chart = r.comparison.map(c => ({ name: c.name, gap: Math.round(c.gap_hours), shortfall: c.shortfall }))
  return (
    <section aria-label="Scenario results">
      <Kicker>Comparison</Kicker>
      <Warn>{r.disclaimer}</Warn>
      <h3>Staffing gap in hours (above zero = shortfall; below zero = spare capacity)</h3>
      <Chart label="Staffing gap in hours for each scenario" tall>
        <BarChart data={chart} margin={{ top: 10, right: 16, left: 10, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e8edf6" vertical={false} />
          <XAxis dataKey="name" stroke={COLORS.muted} fontSize={12} /><YAxis stroke={COLORS.muted} fontSize={12} />
          <Tooltip formatter={(v: number) => `${num(v)} h`} /><ReferenceLine y={0} stroke={COLORS.ink} />
          <Bar dataKey="gap" radius={[6, 6, 0, 0]}>{chart.map((c, i) => <Cell key={i} fill={c.shortfall ? COLORS.long : COLORS.short} />)}</Bar>
        </BarChart>
      </Chart>
      <h3>Details</h3>
      <Table head={['', ...r.scenarios.map(s => s.name)]} numeric={r.scenarios.map((_, i) => i + 1)} rows={[
        ['Scheduled hours', ...r.scenarios.map(s => hours(s.deterministic.scheduled_hours))],
        ['Required hours', ...r.scenarios.map(s => hours(s.deterministic.required_hours))],
        ['Expected absence events', ...r.scenarios.map(s => num(s.deterministic.expected_events, 1))],
        ['Mean hours per event (mix-weighted)', ...r.scenarios.map(s => num(s.deterministic.mean_hours_per_event, 1))],
        ['Long events in the mix', ...r.scenarios.map(s => pct(s.deterministic.long_event_share_in_mix))],
        ['Expected lost hours', ...r.scenarios.map(s => hours(s.deterministic.expected_lost_hours))],
        ['Lost hours as % of scheduled', ...r.scenarios.map(s => `${num(s.deterministic.assumed_absence_hours_pct_of_scheduled, 1)}%`)],
        ['Reserve hours', ...r.scenarios.map(s => hours(s.deterministic.reserve_hours))],
        ['Available hours', ...r.scenarios.map(s => hours(s.deterministic.available_hours))],
        ['Gap (hours)', ...r.scenarios.map(s => `${hours(s.deterministic.gap_hours)} ${s.deterministic.shortfall ? '(shortfall)' : '(spare)'}`)],
        ['Gap (average full-time staff)', ...r.scenarios.map(s => num(s.deterministic.gap_fte, 1))],
        ...(r.scenarios[0].monte_carlo ? [
          ['Lost hours, 10th–90th percentile', ...r.scenarios.map(s => s.monte_carlo ? `${num(s.monte_carlo.lost_hours.p10)}–${num(s.monte_carlo.lost_hours.p90)} h` : '–')],
          ['Chance of a shortfall (simulated)', ...r.scenarios.map(s => s.monte_carlo ? pct(s.monte_carlo.probability_of_shortfall) : '–')],
        ] : []),
      ]} />
      {r.scenarios.flatMap(s => s.warnings.map(w => <Warn key={s.name + w}><strong>{s.name}:</strong> {w}</Warn>))}
      {r.scenarios[0].monte_carlo && <Info>Monte Carlo: {r.scenarios[0].monte_carlo.n_sims} simulations with a fixed seed. {r.scenarios[0].monte_carlo.assumptions.join(' ')}</Info>}
    </section>
  )
}
