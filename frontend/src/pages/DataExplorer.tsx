import { Link } from 'react-router-dom'
import { api } from '../api/endpoints'
import { HistogramLongShort, MultiLine, RateBars, SimpleBars } from '../components/charts'
import { Footer, Hero, Info, Load, Metric, Table, Tabs, Warn } from '../components/ui'
import { COLORS, fmt, num, pct } from '../lib/format'
import { useApi } from '../lib/useApi'
import { useState } from 'react'

const TABS = ['Absence length', 'Reasons', 'Calendar', 'Timeline', 'Repetition', 'Data quality']

export default function DataExplorer() {
  return (
    <>
      <Hero eyebrow="Data Explorer" title="What the recorded absences look like">
        Every figure is computed from the dataset and served as aggregates only. No employee IDs or individual records leave the server.
      </Hero>
      <Tabs tabs={TABS}>
        {tab => tab === 'Absence length' ? <Lengths /> : tab === 'Reasons' ? <Reasons /> : tab === 'Calendar' ? <CalendarTab />
          : tab === 'Timeline' ? <TimelineTab /> : tab === 'Repetition' ? <Repetition /> : <Quality />}
      </Tabs>
      <Footer />
    </>
  )
}

function Lengths() {
  const s = useApi(() => Promise.all([api.durations(), api.overview()]).then(([d, o]) => ({ d, o })))
  return (
    <Load state={s}>{({ d, o }) => (
      <>
        <div className="grid g4">
          <Metric label="Median absence" value={`${d.median} h`} sub={`mean ${fmt(d.mean, 1)} h`} />
          <Metric label="90th percentile" value={`${d.p90} h`} sub={`longest ${d.max} h`} />
          <Metric label="Long (≥ 8 h) share of events" value={pct(d.long_share_of_events)} sub={`${o.long_n} events`} />
          <Metric label="Long share of lost hours" value={pct(d.long_share_of_lost_hours)} sub={`of ${num(d.total_lost_hours)} h`} />
        </div>
        <h2>Distribution of absence length</h2>
        <HistogramLongShort data={d.histogram} />
        <Info>
          Durations cluster at a few values: {d.events_exactly_8_hours} events last exactly 8 hours (one working day), while only {d.events_between_5_and_7_hours} fall between 5 and 7 hours.
          That gap is why “8 hours or more” is a natural line between short and long. Every long absence is a whole number of working days ({pct(d.long_events_that_are_whole_days)}).
        </Info>
      </>
    )}</Load>
  )
}

function Reasons() {
  const s = useApi(() => Promise.all([api.reasons(), api.overview()]).then(([r, o]) => ({ r, o })))
  const [minN, setMinN] = useState(10)
  return (
    <Load state={s}>{({ r, o }) => {
      const rows = r.rows.filter(x => x.n >= minN).map(x => ({ ...x, short: `${x.code}` }))
      return (
        <>
          <label className="field" style={{ maxWidth: 360 }}>Show reasons with at least {minN} events
            <input type="range" min={1} max={50} value={minN} onChange={e => setMinN(Number(e.target.value))} aria-label="Minimum events per reason" />
          </label>
          <h2>Long-absence rate by reason</h2>
          <p className="small-note">Bars show the share of events that were long; whiskers are 95% Wilson intervals. Reasons with few events have very wide intervals.</p>
          <RateBars rows={rows.map(x => ({ ...x, label: x.short }))} overall={o.long_share} label="Long-absence rate by reason code" />
          <h2>Event share vs lost-hours share</h2>
          <SimpleBars data={rows.map(x => ({ label: x.short, 'Share of events': x.event_share, 'Share of lost hours': x.hours_share }))} x="label" y="Share of lost hours" label="Share of lost hours by reason" fmt={v => pct(v)} color={COLORS.long} />
          <div style={{ height: 12 }} />
          <Table head={['Code', 'Reason', 'Events', 'Long rate', '95% interval', 'Events %', 'Lost hours %', 'Pattern']}
            numeric={[0, 2, 3, 5, 6]}
            rows={rows.map(x => [x.code, x.label, x.n, pct(x.long_rate), `${pct(x.ci_low)}–${pct(x.ci_high)}`, pct(x.event_share, 1), pct(x.hours_share, 1),
              <span key={x.code} className={`pill ${x.tier === 'mostly long' ? 'long' : x.tier === 'mostly short' ? 'short' : ''}`}>{x.tier}</span>])} />
          <Info>“Pattern” is only assigned when a reason has at least 10 events and its whole 95% interval is on one side of 50%. {r.hours_by_reason_note}</Info>
        </>
      )
    }}</Load>
  )
}

function CalendarTab() {
  const s = useApi(() => Promise.all([api.calendar(), api.overview()]).then(([c, o]) => ({ c, o })))
  return (
    <Load state={s}>{({ c, o }) => (
      <>
        <h2>By month of absence</h2>
        <RateBars rows={c.by_month.map(x => ({ ...x, label: x.label.slice(0, 3) }))} overall={o.long_share} label="Long-absence rate by month" />
        <h2>By day of the week</h2>
        <RateBars rows={c.by_weekday} overall={o.long_share} label="Long-absence rate by weekday" />
        <Info>{c.note} Note that long absences are recorded on the day they start, so the weekday describes the first day only.</Info>
      </>
    )}</Load>
  )
}

function TimelineTab() {
  const s = useApi(api.timeline)
  return (
    <Load state={s}>{t => (
      <>
        <Warn><strong>Reconstructed timeline.</strong> The file has no date column. Months were inferred from row order and the monthly workload figure
          ({t.consistency.consecutive_month_steps} of {t.consistency.steps_checked} month-to-month steps are consecutive; start month {t.consistency.assumed_start} taken from the public dataset documentation). {t.caveat}</Warn>
        <h2>Recorded absence events per month</h2>
        <MultiLine data={t.periods} x="label" label="Absence events per month over 37 months" lines={[{ key: 'n', name: 'Events', color: COLORS.neutral }, { key: 'long_n', name: 'Long events', color: COLORS.long }]} />
        <div className="grid g3" style={{ marginTop: 12 }}>
          {Object.entries(t.segments).map(([k, v]) => (
            <Metric key={k} label={k.replace('_', ' ')} value={pct(v.long_rate)} sub={`long-absence rate · ${v.events} events · ${fmt(v.events_per_month, 1)} per month`} />
          ))}
        </div>
        <Info>Events per month ranged from {t.events_per_month.min} to {t.events_per_month.max} (mean {fmt(t.events_per_month.mean, 1)}). The long-absence rate was lower in the most recent third of the period, a sign the mix of absences can shift over time.
          Treat it as a descriptive observation, not a trend forecast.</Info>
      </>
    )}</Load>
  )
}

function Repetition() {
  const s = useApi(api.employees)
  return (
    <Load state={s}>{e => (
      <>
        <div className="grid g4">
          <Metric label="Employees" value={e.employees} sub={`median ${e.median_records} events each`} />
          <Metric label="Top 3 employees" value={pct(e.top_3_share)} sub="share of all events" />
          <Metric label={`Top ${e.top_10pct_employees} employees (10%)`} value={pct(e.top_10pct_share)} sub="share of all events" />
          <Metric label="Gini of events" value={fmt(e.gini)} sub="0 = equal, 1 = concentrated" />
        </div>
        <h2>Events per employee (anonymous, sorted)</h2>
        <SimpleBars data={e.records_per_employee_sorted.map((v, i) => ({ rank: i + 1, events: v }))} x="rank" y="events" label="Number of events per employee, sorted" />
        <h2>How employees differ in long-absence share</h2>
        <SimpleBars data={e.long_share_distribution} x="bin" y="employees" label="Number of employees by long-absence share" color={COLORS.short} />
        <Info>{e.long_share_distribution_note} Repetition matters for method: because the same people appear many times, the model is validated on whole employees held out, not random rows. {e.ethics_note}</Info>
      </>
    )}</Load>
  )
}

function Quality() {
  const s = useApi(api.overview)
  return (
    <Load state={s}>{o => (
      <>
        <Table head={['Check', 'Result']} rows={[
          ['Raw records', `${o.raw_rows} rows × ${o.raw_columns} columns, ${o.raw_employees} employees`],
          ['Missing values', String(o.missing_values)],
          ['Exact duplicate rows', `${o.exact_duplicate_rows} (kept) – ${o.duplicate_note}`],
          ['Rule rows excluded', `${o.rule_rows} rows with reason code 0 (includes all disciplinary-failure rows); all have 0 hours: ${o.rule_rows_all_zero_hours ? 'yes' : 'no'}`],
          ['Rows used for modelling', `${o.modelled_rows} events, ${o.modelled_employees} employees`],
          ['Months covered', `${o.months_covered} (reconstructed, see Timeline)`],
        ]} />
        <Info>Codes with no records in the data (such as reason 20) are not accepted by the prediction form. See <Link to="/about">About</Link> for the full method.</Info>
      </>
    )}</Load>
  )
}
