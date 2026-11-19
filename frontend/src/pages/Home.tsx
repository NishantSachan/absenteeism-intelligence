import { Link } from 'react-router-dom'
import { api } from '../api/endpoints'
import { Details, Footer, Hero, Info, Kicker, Load, Metric } from '../components/ui'
import { num, pct } from '../lib/format'
import { useApi } from '../lib/useApi'

export default function Home() {
  const state = useApi(async () => {
    const [meta, overview, durations] = await Promise.all([api.meta(), api.overview(), api.durations()])
    return { meta, overview, durations }
  })

  return (
    <>
      <Hero eyebrow="Absenteeism Intelligence & Workforce Planning" title="Understand absence patterns. Estimate duration. Plan cover." image="/hero_dashboard.png">
        A capstone analytics system that connects pattern discovery, an explainable absence-duration model and an assumption-driven staffing simulator,
        built on {` `}real absence events from the public “Absenteeism at work” dataset.
      </Hero>

      <Load state={state}>
        {({ meta, overview, durations }) => (
          <>
            <Kicker>Project snapshot</Kicker>
            <div className="grid g4">
              <Metric label="Absence events analysed" value={num(overview.modelled_rows)} sub={`of ${overview.raw_rows} records (${overview.rule_rows} rule rows excluded)`} />
              <Metric label="Employees" value={overview.modelled_employees} sub={`${overview.months_covered} months of records`} />
              <Metric label={`Long absences (≥ ${overview.long_threshold_hours} h)`} value={pct(overview.long_share)} sub="share of recorded events" />
              <Metric label="Deployed model" value={`v${meta.model.version}`} sub={meta.model.name} />
            </div>

            <Kicker>Three connected modules</Kicker>
            <div className="grid g3">
              <div className="card"><h3>1. Pattern discovery</h3><p>What the recorded absences look like: duration, reasons, calendar, timeline and repetition.</p><Link className="btn primary" to="/data-explorer">Explore the data</Link></div>
              <div className="card"><h3>2. Prediction &amp; explainability</h3><p>For an already-reported absence, estimate whether it will be long, and see how that compares with history.</p><Link className="btn primary" to="/predict">Try a prediction</Link></div>
              <div className="card"><h3>3. Workforce planning</h3><p>A what-if simulator that turns <em>your</em> assumptions into staffing gaps, using real absence durations.</p><Link className="btn primary" to="/planning">Plan scenarios</Link></div>
            </div>

            <Kicker>What the data says</Kicker>
            <Info>
              Long absences are only <strong>{pct(durations.long_share_of_events)}</strong> of events but account for <strong>{pct(durations.long_share_of_lost_hours)}</strong> of all
              lost hours. The recorded reason explains most of the difference between short and long absences; month and weekday add little.
              See <Link to="/insights">Insights</Link> for the evidence and its limits.
            </Info>

            <Details title="What this system does not do">
              <p>It does not predict whether a person will be absent, and it does not measure any organisation’s absence rate. The dataset contains absence <em>events</em> only.
                Planning outputs follow from the assumptions you enter. Model outputs describe historical association, not cause.</p>
            </Details>
            <Details title="How it works"><p>Data are cleaned and split by employee, models are compared against simple baselines, and only aggregate results are served by the API. See <Link to="/about">About</Link>.</p></Details>
            <Footer />
          </>
        )}
      </Load>
    </>
  )
}
