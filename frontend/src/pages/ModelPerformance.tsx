import { ReferenceLine, LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ScatterChart, Scatter } from 'recharts'
import { api } from '../api/endpoints'
import type { ModelMetrics, Row } from '../api/types'
import { Chart, SimpleBars } from '../components/charts'
import { Footer, Hero, Info, Kicker, Load, Metric, Table, Tabs, Warn } from '../components/ui'
import { COLORS, fmt, pct } from '../lib/format'
import { useApi } from '../lib/useApi'

const TABS = ['Evidence summary', 'Held-out test', 'Model comparison', 'Validation design', 'Calibration & threshold', 'Time-ordered check']

export default function ModelPerformance() {
  const s = useApi(api.modelMetrics)
  return (
    <>
      <Hero eyebrow="Model Performance" title="How well does the model really do?">
        The deployed {` `}Random Forest is compared with simple baselines using every employee as validation, with uncertainty shown. The honest finding: the reason code does almost all the work.
      </Hero>
      <Load state={s}>{m => (
        <Tabs tabs={TABS}>
          {tab => tab === 'Evidence summary' ? <Evidence m={m} /> : tab === 'Held-out test' ? <Test m={m} /> : tab === 'Model comparison' ? <Comparison m={m} />
            : tab === 'Validation design' ? <Validation m={m} /> : tab === 'Calibration & threshold' ? <Calibration m={m} /> : <Temporal m={m} />}
        </Tabs>
      )}</Load>
      <Footer />
    </>
  )
}

function KeyTable({ rows }: { rows: Row[] }) {
  if (!rows.length) return null
  const keys = Object.keys(rows[0])
  return <Table head={keys} rows={rows.map(r => keys.map(k => String(r[k])))} numeric={keys.map((_, i) => i).slice(1)} />
}

function Evidence({ m }: { m: ModelMetrics }) {
  const v2 = m.metrics.evaluation_v2
  const names = Object.keys(v2.pooled_grouped_cv)
  return (
    <>
      <Info>{v2.conclusion}</Info>
      <h2>Pooled grouped cross-validation</h2>
      <p className="small-note">All {v2.employees} employees ({v2.rows} events) are held out exactly once per repeat, {v2.seeds} repeats. Alert level {pct(v2.threshold_used)} for recall/precision.
        “No-skill” PR-AUC equals the long share ({fmt(v2.prevalence, 3)}). Intervals come from resampling whole employees.</p>
      <Table head={['Model', 'PR-AUC', '95% interval', 'ROC-AUC', 'Brier', 'Recall', 'Precision', 'F1']} numeric={[1, 3, 4, 5, 6, 7]}
        rows={names.map(n => { const r = v2.pooled_grouped_cv[n]; return [n === m.model.name ? `${n} (deployed)` : n, fmt(r.pr_auc, 3), `${fmt(r.pr_auc_ci95_employee_bootstrap[0], 2)}–${fmt(r.pr_auc_ci95_employee_bootstrap[1], 2)}`, fmt(r.roc_auc, 3), fmt(r.brier, 3), fmt(r.recall, 2), fmt(r.precision, 2), fmt(r.f1, 2)] })} />
      <h2>Is the deployed model better than the baselines?</h2>
      <Table head={['Comparison', 'Median PR-AUC difference', '95% interval', 'Distinguishable from zero?']} numeric={[1]}
        rows={Object.entries(v2.paired_pr_auc_differences).map(([k, d]) => [k, fmt(d.median, 3), `${fmt(d.ci95[0], 3)} to ${fmt(d.ci95[1], 3)}`, d.ci95[0] > 0 || d.ci95[1] < 0 ? 'yes' : 'no'])} />
      <Warn>None of the model-versus-baseline differences can be told apart from zero with 33 employees. That is a limitation of the data, not a hidden success. The Random Forest is kept because nothing justifies replacing it.</Warn>
    </>
  )
}

function Test({ m }: { m: ModelMetrics }) {
  const t = m.metrics.test
  const c = t.chosen_model, ci = t.bootstrap_95ci
  const like = m.metrics.evaluation_v2.original_test_split_like_for_like
  const lk = (name: string, key: string) => like[name]?.[key]
  return (
    <>
      <Warn>This is the original single hold-out: {t.test_employees} employees and {t.test_rows} events, two of whom supply most rows. Intervals are wide, so use it as a sanity check, not as the headline result.</Warn>
      <div className="grid g4">
        <Metric label="PR-AUC" value={fmt(c.pr_auc, 2)} sub={`95% ${fmt(ci.pr_auc[0], 2)}–${fmt(ci.pr_auc[1], 2)}`} />
        <Metric label="Recall" value={pct(c.recall)} sub={`95% ${pct(ci.recall[0])}–${pct(ci.recall[1])}`} />
        <Metric label="Precision" value={pct(c.precision)} sub={`95% ${pct(ci.precision[0])}–${pct(ci.precision[1])}`} />
        <Metric label="F1" value={fmt(c.f1, 2)} sub={`95% ${fmt(ci.f1[0], 2)}–${fmt(ci.f1[1], 2)}`} />
      </div>
      <h2>Confusion matrix</h2>
      <Table head={['', 'Predicted short', 'Predicted long']} numeric={[1, 2]} rows={[['Actually short', c.tn, `${c.fp} (false alarms)`], ['Actually long', `${c.fn} (missed)`, c.tp]]} />
      <h2>Like-for-like against the reason-only baseline</h2>
      <Table head={['Model', 'PR-AUC', `Recall @ ${fmt(m.model.threshold, 2)}`, `Precision @ ${fmt(m.model.threshold, 2)}`]} numeric={[1, 2, 3]}
        rows={['Random Forest', 'Reason-only baseline (LR)'].map(n => [n, fmt(lk(n, 'pr_auc'), 3), fmt(lk(n, `at_${m.metrics.evaluation_v2.threshold_used}`)?.recall, 2), fmt(lk(n, `at_${m.metrics.evaluation_v2.threshold_used}`)?.precision, 2)])} />
      <p className="small-note">{like.note}</p>
      <h2>Accuracy by test employee (anonymised)</h2>
      <SimpleBars data={m.evaluation.test_per_employee} x="label" y="accuracy" label="Accuracy for each test employee" fmt={v => pct(v)} color={COLORS.short} />
    </>
  )
}

function Comparison({ m }: { m: ModelMetrics }) {
  const mc = m.evaluation.model_comparison
  return (
    <>
      <p>Grouped cross-validation on the 575-row training portion (mean ± standard deviation across folds and seeds).</p>
      <h2>All 13 features</h2><KeyTable rows={mc.all_13_features} />
      <h2>Only the three inputs the app uses</h2><KeyTable rows={mc.three_inputs} />
      <h2>Confirmation with fresh random seeds</h2><KeyTable rows={mc.confirmation_fresh_seeds} />
      <h2>Which inputs help?</h2><KeyTable rows={m.evaluation.feature_ablation} />
      <Info>The personal and workload columns did not improve grouped performance, so the deployed model uses only reason, month and weekday.</Info>
    </>
  )
}

function Validation({ m }: { m: ModelMetrics }) {
  return (
    <>
      <p>Random row-level splits let the same employee appear in training and validation, which flatters the score. The project therefore validates on whole employees held out.</p>
      <KeyTable rows={m.evaluation.random_vs_grouped} />
      <Info>The inflation is modest here because the signal is mostly the reason code, not who the employee is. Grouped validation is still the correct design for this repeated-measures data.</Info>
    </>
  )
}

function Calibration({ m }: { m: ModelMetrics }) {
  const cal = m.metrics.evaluation_v2.calibration_random_forest
  const th = m.evaluation.threshold_curve
  return (
    <>
      <h2>Calibration (pooled out-of-fold)</h2>
      <p className="small-note">Do predicted chances match observed rates? Points near the diagonal are well calibrated.</p>
      <Chart label="Calibration: predicted probability against observed long-absence rate" tall>
        <ScatterChart margin={{ top: 10, right: 16, left: 0, bottom: 20 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e8edf6" />
          <XAxis type="number" dataKey="mean_predicted" domain={[0, 1]} name="Predicted" tickFormatter={v => pct(v)} stroke={COLORS.muted} fontSize={12} />
          <YAxis type="number" dataKey="observed_rate" domain={[0, 1]} name="Observed" tickFormatter={v => pct(v)} stroke={COLORS.muted} fontSize={12} />
          <Tooltip formatter={(v: number) => pct(v)} />
          <ReferenceLine segment={[{ x: 0, y: 0 }, { x: 1, y: 1 }]} stroke={COLORS.muted} strokeDasharray="5 4" />
          <Scatter data={cal} fill={COLORS.neutral} />
        </ScatterChart>
      </Chart>
      <h2>Choosing the alert level</h2>
      <p className="small-note">The alert level {fmt(m.model.threshold, 2)} was set on training-only predictions, assuming a missed long absence costs {m.model.assumed_fn_to_fp_cost_ratio}× a false alarm. {m.model.threshold_rule}</p>
      <Chart label="Recall and precision across alert levels" tall>
        <LineChart data={th} margin={{ top: 10, right: 16, left: 0, bottom: 10 }}>
          <CartesianGrid strokeDasharray="3 3" stroke="#e8edf6" />
          <XAxis dataKey="threshold" stroke={COLORS.muted} fontSize={12} />
          <YAxis domain={[0, 1]} tickFormatter={v => pct(v)} stroke={COLORS.muted} fontSize={12} />
          <Tooltip formatter={(v: number) => pct(v)} /><Legend />
          <ReferenceLine x={m.model.threshold} stroke={COLORS.long} strokeDasharray="4 4" />
          <Line dataKey="recall" name="Recall" stroke={COLORS.short} dot={false} strokeWidth={2} />
          <Line dataKey="precision" name="Precision" stroke={COLORS.neutral} dot={false} strokeWidth={2} />
        </LineChart>
      </Chart>
    </>
  )
}

function Temporal({ m }: { m: ModelMetrics }) {
  const t = m.metrics.evaluation_v2.temporal_check
  return (
    <>
      <Warn>{t.note}</Warn>
      <div className="grid g4">
        <Metric label="Train months" value={t.train_months} sub={`${t.train_rows} events, long share ${pct(t.train_prevalence)}`} />
        <Metric label="Test months" value={t.test_months} sub={`${t.test_rows} events, long share ${pct(t.test_prevalence)}`} />
        <Metric label="Test employees" value={t.test_employees} sub={`${t.test_employees_also_in_train} also in training`} />
        <Metric label="Months are" value="inferred" sub="reconstructed from row order" />
      </div>
      <h2>Earlier months → later months</h2>
      <Table head={['Model', 'PR-AUC', 'ROC-AUC', 'Recall', 'Precision', 'F1']} numeric={[1, 2, 3, 4, 5]}
        rows={Object.entries(t.models).map(([n, r]) => [n, fmt(r.pr_auc, 3), fmt(r.roc_auc, 3), fmt(r.recall, 2), fmt(r.precision, 2), fmt(r.f1, 2)])} />
      <Kicker>Reading this</Kicker>
      <p>The ranking quality holds up on later months (ROC-AUC stays above 0.8 for every model), but precision falls because long absences became rarer in those months: when the alert fires, it is right less often than it was in the earlier period. All models, including the reason-only baseline, behave alike, which again points to the reason code as the driver. This is one split on inferred months, so treat it as a sanity check.</p>
      </>
  )
}
