import type { ReactNode } from 'react'
import { useState } from 'react'
import type { Loadable } from '../lib/useApi'

export function Hero({ eyebrow, title, children, image }: { eyebrow: string; title: string; children?: ReactNode; image?: string }) {
  return (
    <section className="hero">
      <div className={image ? 'hero-split' : undefined}>
        <div>
          <span className="hero-eyebrow">{eyebrow}</span>
          <h1>{title}</h1>
          {children && <p>{children}</p>}
        </div>
        {image && <img src={image} alt="Illustration of an analytics dashboard" />}
      </div>
    </section>
  )
}

export const Kicker = ({ children }: { children: ReactNode }) => <div className="kicker">{children}</div>

export function Metric({ label, value, sub }: { label: string; value: ReactNode; sub?: ReactNode }) {
  return (
    <div className="metric">
      <div className="label">{label}</div>
      <div className="value">{value}</div>
      {sub && <div className="sub">{sub}</div>}
    </div>
  )
}

export const Info = ({ children }: { children: ReactNode }) => <div className="info-strip">{children}</div>
export const Warn = ({ children }: { children: ReactNode }) => <div className="warn-strip" role="note">{children}</div>
export const Footer = ({ children }: { children?: ReactNode }) => (
  <div className="footer-note">{children ?? 'Educational analytics project. Not for hiring, firing, discipline or any individual decision. Associations are not causes.'}</div>
)

export function Tabs({ tabs, children }: { tabs: string[]; children: (active: string) => ReactNode }) {
  const [active, setActive] = useState(tabs[0])
  return (
    <>
      <div className="tabs" role="tablist">
        {tabs.map(t => (
          <button key={t} role="tab" aria-selected={active === t} onClick={() => setActive(t)}>{t}</button>
        ))}
      </div>
      <div role="tabpanel">{children(active)}</div>
    </>
  )
}

/** Shows a skeleton while loading and a clear error with retry; renders children only when data is ready. */
export function Load<T>({ state, children }: { state: Loadable<T>; children: (data: T) => ReactNode }) {
  if (state.loading) return <div aria-busy="true" aria-label="Loading"><div className="skeleton" /><div className="skeleton" style={{ marginTop: 12 }} /></div>
  if (state.error || !state.data) {
    return (
      <div className="error-strip" role="alert">
        <strong>Could not load this section.</strong> {state.error?.message ?? 'No data returned.'}{' '}
        <button onClick={state.reload}>Try again</button>
      </div>
    )
  }
  return <>{children(state.data)}</>
}

export function Table({ head, rows, numeric = [] }: { head: string[]; rows: ReactNode[][]; numeric?: number[] }) {
  return (
    <div className="table-wrap">
      <table>
        <thead><tr>{head.map((h, i) => <th key={h + i} className={numeric.includes(i) ? 'num' : undefined}>{h}</th>)}</tr></thead>
        <tbody>{rows.map((r, i) => <tr key={i}>{r.map((c, j) => <td key={j} className={numeric.includes(j) ? 'num' : undefined}>{c}</td>)}</tr>)}</tbody>
      </table>
    </div>
  )
}

export const Details = ({ title, children }: { title: string; children: ReactNode }) => <details><summary>{title}</summary>{children}</details>
