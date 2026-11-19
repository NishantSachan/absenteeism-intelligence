import { FormEvent, useState } from 'react'
import { Link } from 'react-router-dom'
import { ApiRequestError } from '../api/client'
import { api } from '../api/endpoints'
import type { PredictResponse } from '../api/types'
import { Details, Footer, Hero, Info, Kicker, Load, Metric, Warn } from '../components/ui'
import { COLORS, describeProbability, pct } from '../lib/format'
import { useApi } from '../lib/useApi'

type Errors = Partial<Record<'reason' | 'month' | 'weekday', string>>

export default function Predict() {
  const meta = useApi(api.meta)
  const [form, setForm] = useState({ reason: '', month: '', weekday: '' })
  const [errors, setErrors] = useState<Errors>({})
  const [busy, setBusy] = useState(false)
  const [apiError, setApiError] = useState<ApiRequestError | null>(null)
  const [result, setResult] = useState<PredictResponse | null>(null)

  async function submit(e: FormEvent) {
    e.preventDefault()
    const next: Errors = {}
    if (!form.reason) next.reason = 'Please choose a reason.'
    if (!form.month) next.month = 'Please choose a month.'
    if (!form.weekday) next.weekday = 'Please choose a weekday.'
    setErrors(next)
    if (Object.keys(next).length) return
    setBusy(true); setApiError(null)
    try {
      setResult(await api.predict({ reason: Number(form.reason), month: Number(form.month), weekday: Number(form.weekday) }))
    } catch (err) {
      setResult(null)
      setApiError(err instanceof ApiRequestError ? err : new ApiRequestError(0, 'unknown', 'Something went wrong.'))
    } finally { setBusy(false) }
  }

  return (
    <>
      <Hero eyebrow="Predict" title="Will a reported absence be long?">
        Pick the recorded reason and the day of an absence that has <em>already been reported</em>. The model estimates the chance that it lasts 8 hours or more.
      </Hero>
      <Load state={meta}>
        {m => (
          <>
            <form onSubmit={submit} noValidate aria-label="Prediction form" className="card">
              <div className="form-row">
                <label className="field">Reason for absence
                  <select aria-invalid={!!errors.reason} value={form.reason} onChange={e => setForm({ ...form, reason: e.target.value })}>
                    <option value="">Select a reason…</option>
                    {m.inputs.reasons.map(r => <option key={r.code} value={r.code}>{r.code} – {r.label}</option>)}
                  </select>
                  {errors.reason && <span className="field-error" role="alert">{errors.reason}</span>}
                </label>
                <label className="field">Month
                  <select aria-invalid={!!errors.month} value={form.month} onChange={e => setForm({ ...form, month: e.target.value })}>
                    <option value="">Select…</option>
                    {m.inputs.months.map(o => <option key={o.code} value={o.code}>{o.label}</option>)}
                  </select>
                  {errors.month && <span className="field-error" role="alert">{errors.month}</span>}
                </label>
                <label className="field">Day of the week
                  <select aria-invalid={!!errors.weekday} value={form.weekday} onChange={e => setForm({ ...form, weekday: e.target.value })}>
                    <option value="">Select…</option>
                    {m.inputs.weekdays.map(o => <option key={o.code} value={o.code}>{o.label}</option>)}
                  </select>
                  {errors.weekday && <span className="field-error" role="alert">{errors.weekday}</span>}
                </label>
              </div>
              <button className="primary wide" type="submit" disabled={busy}>{busy ? 'Estimating…' : 'Estimate duration'}</button>
            </form>

            {apiError && (
              <div className="error-strip" role="alert">
                <strong>{apiError.message}</strong>
                {apiError.details.length > 0 && <ul>{apiError.details.map((d, i) => <li key={i}>{d.field ? `${d.field}: ` : ''}{d.message}</li>)}</ul>}
              </div>
            )}

            {result && <Result r={result} />}

            <Details title="How to read this">
              <p>The percentage is the model’s estimate for absences <em>like this one in the historical data</em>. It is not a certainty and not a statement about any person.
                The recorded reason does most of the work; month and weekday move the estimate only slightly.</p>
            </Details>
            <Footer>The model was trained on {m.model.training.rows_used_for_deployed_model} events from {m.model.training.employees} employees at one company. See <Link to="/model-performance">Model Performance</Link> for how well it does and where it does not beat simple baselines.</Footer>
          </>
        )}
      </Load>
    </>
  )
}

function Result({ r }: { r: PredictResponse }) {
  const accent = r.predicted_long ? COLORS.long : COLORS.short
  const h = r.historical
  return (
    <section aria-label="Prediction result">
      <Kicker>Result</Kicker>
      <div className="result-card" style={{ ['--accent' as string]: accent }}>
        <h3>{r.predicted_long ? 'Likely a long absence (8 hours or more)' : 'Likely a short absence (under 8 hours)'}</h3>
        <p>Estimated chance of a long absence: <strong>{describeProbability(r.probability_long)}</strong>. The alert level is {pct(r.threshold)}, chosen to catch most long absences at the cost of some false alarms.</p>
        <div className="bar" aria-hidden="true"><span style={{ width: `${Math.round(r.probability_long * 100)}%` }} /></div>
        <p className="small-note" style={{ marginTop: 8 }}>{r.reason_label} · {r.month_label} · {r.weekday_label}</p>
      </div>
      <div className="grid g3">
        <Metric label="Model estimate" value={pct(r.probability_long)} sub={`${r.model_name} v${r.model_version}`} />
        {r.reason_only_probability !== null && <Metric label="Reason-only comparison" value={pct(r.reason_only_probability)} sub="simple model using the reason alone" />}
        {h && <Metric label="Historical rate for this reason" value={pct(h.long_rate)} sub={`95% interval ${pct(h.ci_low)}–${pct(h.ci_high)} · ${h.n} events`} />}
      </div>
      {h?.low_n && <Warn>Only {h.n} historical events have this reason, so the historical rate and the estimate are unreliable.</Warn>}
      <Info>
        If only the month and weekday were different, the estimate for this reason would range from {pct(r.sensitivity.min_probability)} to {pct(r.sensitivity.max_probability)}.{' '}
        {r.sensitivity.flag_depends_on_month_or_weekday
          ? 'For this reason the long/short call itself depends on the month or weekday, so treat it as borderline.'
          : 'The long/short call stays the same for every month and weekday.'}
      </Info>
    </section>
  )
}
