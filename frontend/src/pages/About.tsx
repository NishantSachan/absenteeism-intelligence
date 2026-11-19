import { api } from '../api/endpoints'
import { Details, Footer, Hero, Kicker, Load, Table } from '../components/ui'
import { useApi } from '../lib/useApi'

export default function About() {
  const s = useApi(() => Promise.all([api.meta(), api.modelMetrics()]).then(([meta, mm]) => ({ meta, mm })))
  return (
    <>
      <Hero eyebrow="About" title="Method, data and limits">
        A data science capstone built to be honest about what a small dataset can and cannot support.
      </Hero>
      <Kicker>Data</Kicker>
      <p>The public UCI “Absenteeism at work” dataset: absence events from a Brazilian courier company, 740 records and 36 employees. It contains absence <em>events</em> only (no attendance calendar and no headcount per month).
        Rows with reason code 0 (43 rows, no recorded absence) were excluded. The “long absence” target is a recorded duration of at least 8 hours (one working day).</p>
      <Kicker>Method</Kicker>
      <ol>
        <li>Audit the data: missing values, duplicates, repeated employees, leakage, class balance.</li>
        <li>Validate by whole employee (not random rows); compare the model with baselines using pooled grouped cross-validation, employee-level bootstrap intervals and a time-ordered check.</li>
        <li>Keep the deployed model unless evidence justifies a change. The saved artifact was verified to retrain identically.</li>
        <li>Serve only aggregates through a FastAPI backend; the React app never sees records or employee IDs.</li>
        <li>Provide a transparent, assumption-driven staffing simulator that is never presented as a forecast.</li>
      </ol>
      <Load state={s}>{({ meta, mm }) => (
        <>
          <Kicker>Deployed model</Kicker>
          <Table head={['Property', 'Value']} rows={[
            ['Model', `${meta.model.name} v${meta.model.version}`], ['Task', meta.model.task],
            ['Inputs', mm.model.feature_columns.join(', ')], ['Alert level', String(meta.model.threshold)],
            ['Trained on', `${meta.model.training.rows_used_for_deployed_model} events, ${meta.model.training.employees} employees`],
            ['Library versions', Object.entries(mm.model.library_versions).map(([k, v]) => `${k} ${v}`).join(', ')]]} />
          <Kicker>Limitations</Kicker>
          <ul>{meta.model.limitations.map(l => <li key={l}>{l}</li>)}</ul>
        </>
      )}</Load>
      <Details title="Privacy and responsible use"><p>No employee IDs, individual records or raw data files are exposed by the API or shipped to the browser. Reason categories can relate to health, so only grouped counts are shown, and small groups are flagged or pooled.
        The system must not be used to evaluate, rank, discipline or hire individuals.</p></Details>
      <Details title="Technology"><p>React + Vite + TypeScript frontend; FastAPI + Pydantic backend; pandas, NumPy and scikit-learn for data and modelling; deployed as a static site (S3 + CloudFront) with the API on EC2.</p></Details>
      <Details title="Possible future work"><p>Collect dates and headcount to enable genuine absence-rate forecasting; evaluate on a second organisation; add confidence intervals to individual predictions.</p></Details>
      <Footer />
    </>
  )
}
