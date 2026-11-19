import { Link } from 'react-router-dom'
import { api } from '../api/endpoints'
import { SimpleBars } from '../components/charts'
import { Details, Footer, Hero, Info, Kicker, Load, Metric, Table, Warn } from '../components/ui'
import { COLORS, fmt, pct } from '../lib/format'
import { useApi } from '../lib/useApi'
import type { AssociationEntry } from '../api/types'

export default function Insights() {
  const s = useApi(() => Promise.all([api.modelMetrics(), api.association(), api.durations(), api.reasons(), api.meta()])
    .then(([m, a, d, r, meta]) => ({ m, a, d, r, meta })))
  return (
    <>
      <Hero eyebrow="Insights" title="What the analysis means, and what it does not">
        Three kinds of statement are kept apart on this page: what the data <em>shows</em>, what the model <em>predicts</em>, and what nobody can claim: <em>causes</em>.
      </Hero>
      <Load state={s}>{({ m, a, d, r, meta }) => {
        const imp = Object.entries(m.metrics.permutation_importance).map(([k, v]) => ({ feature: k, importance: v })).sort((x, y) => y.importance - x.importance)
        const assoc = Object.entries(a).filter((e): e is [string, AssociationEntry] => typeof e[1] !== 'string')
        const grid = m.model_grid
        const heavy = [...r.rows].sort((x, y) => y.hours_share - x.hours_share).slice(0, 3)
        return (
          <>
            <Kicker>1 · Historical association (what the data shows)</Kicker>
            <div className="grid g3">
              <Metric label="Long absences" value={pct(d.long_share_of_events)} sub="of events…" />
              <Metric label="…but" value={pct(d.long_share_of_lost_hours)} sub="of all lost hours" />
              <Metric label="Top 3 reasons by lost hours" value={heavy.map(h => h.code).join(', ')} sub={`${pct(heavy.reduce((s2, h) => s2 + h.hours_share, 0))} of lost hours together`} />
            </div>
            <h3 style={{ marginTop: 16 }}>Strength of association with long vs short (Cramér’s V)</h3>
            <SimpleBars data={assoc.map(([k, v]) => ({ feature: k, v: v.cramers_v }))} x="feature" y="v" label="Cramér's V by input" fmt={v => fmt(v, 2)} color={COLORS.neutral} />
            <p className="small-note">Reason shows a strong association; month and weekday are weak. {String(a.note)}</p>

            <Kicker>2 · Model prediction (what the model learned)</Kicker>
            <h3>Permutation importance: drop in PR-AUC when an input is shuffled</h3>
            <SimpleBars data={imp} x="feature" y="importance" label="Permutation importance by input" fmt={v => fmt(v, 2)} color={COLORS.short} />
            <Info>
              The reason code carries nearly all of the signal. Holding the reason fixed, changing only the month or weekday moves the model’s estimate by a median of about{' '}
              {pct(grid.month_day_spread_within_reason.median_iqr)} (interquartile range), and flips the long/short call only for reason code(s) {grid.month_day_spread_within_reason.reasons_whose_flag_depends_on_month_or_weekday.join(', ') || 'none'}.
            </Info>
            <h3>Model vs history, by reason</h3>
            <Table head={['Code', 'Reason', 'Events', 'Observed long rate', 'Model (avg)', 'Reason-only model']} numeric={[0, 2, 3, 4, 5]}
              rows={r.rows.filter(x => !x.low_n).map(x => [x.code, x.label, x.n, pct(x.long_rate), pct(grid.reasons[String(x.code)]?.model_mean ?? 0), pct(grid.reasons[String(x.code)]?.reason_only ?? 0)])} />
            <p className="small-note">Model values are fitted on the same data and so are in-sample; they show what the model learned, not how it generalises.</p>

            <Kicker>3 · What cannot be claimed</Kicker>
            <Warn>
              Nothing here shows that a reason, month or weekday <em>causes</em> a longer absence, and nothing predicts whether anyone will be absent.
              The data are {meta.dataset.modelled_rows} events from {meta.dataset.employees} employees at one company, so results may not transfer to other workplaces or future periods.
            </Warn>

            <Kicker>Planning implications</Kicker>
            <p>Because long absences drive most lost time, the <em>mix</em> of reasons matters more for cover planning than the raw count of events. The <Link to="/planning">Workforce Planning</Link> simulator
              lets you change that mix and the event frequency (which you must assume) and see the resulting gap.</p>
            <Details title="Why not SHAP or clustering?">
              <p>With only three categorical inputs, the model can be evaluated exactly on all 1,620 input combinations, which is what the “month and weekday spread” figure uses. SHAP would add a heavy dependency without new insight.
                Clustering 33 employees would amount to profiling individuals, so the app only reports anonymous aggregates.</p>
            </Details>
            <Footer />
          </>
        )
      }}</Load>
    </>
  )
}
