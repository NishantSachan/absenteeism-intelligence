import { Bar, BarChart, CartesianGrid, Cell, ComposedChart, ErrorBar, Legend, Line, LineChart, ReferenceLine, ResponsiveContainer, Tooltip, XAxis, YAxis } from 'recharts'
import { COLORS } from '../lib/format'

const axis = { stroke: COLORS.muted, fontSize: 12 }
const pctTick = (v: number) => `${Math.round(v * 100)}%`

export function Chart({ children, tall, label }: { children: React.ReactElement; tall?: boolean; label: string }) {
  return <div className={`chart${tall ? ' tall' : ''}`} role="img" aria-label={label}><ResponsiveContainer width="100%" height="100%">{children}</ResponsiveContainer></div>
}

/** Long-rate bars with 95% Wilson interval whiskers and an overall-rate reference line. */
export function RateBars({ rows, overall, label, angle = 0 }: { rows: { label: string; long_rate: number; ci_low: number; ci_high: number; n: number }[]; overall: number; label: string; angle?: number }) {
  const data = rows.map(r => ({ ...r, err: [r.long_rate - r.ci_low, r.ci_high - r.long_rate] }))
  return (
    <Chart label={label} tall>
      <ComposedChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: angle ? 60 : 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e8edf6" vertical={false} />
        <XAxis dataKey="label" {...axis} interval={0} angle={angle} textAnchor={angle ? 'end' : 'middle'} />
        <YAxis {...axis} tickFormatter={pctTick} domain={[0, 1]} />
        <Tooltip formatter={(v: number, _n, p) => [`${(v * 100).toFixed(0)}% (n=${p.payload.n})`, 'Long-absence rate']} />
        <ReferenceLine y={overall} stroke={COLORS.muted} strokeDasharray="5 4" label={{ value: `overall ${(overall * 100).toFixed(0)}%`, fill: COLORS.muted, fontSize: 11, position: 'insideTopRight' }} />
        <Bar dataKey="long_rate" fill={COLORS.neutral} radius={[6, 6, 0, 0]}><ErrorBar dataKey="err" stroke={COLORS.ink} width={4} /></Bar>
      </ComposedChart>
    </Chart>
  )
}

export function SimpleBars({ data, x, y, label, color = COLORS.neutral, fmt, angle = 0, tall }: { data: Record<string, any>[]; x: string; y: string; label: string; color?: string; fmt?: (v: number) => string; angle?: number; tall?: boolean }) {
  return (
    <Chart label={label} tall={tall}>
      <BarChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: angle ? 60 : 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e8edf6" vertical={false} />
        <XAxis dataKey={x} {...axis} interval={0} angle={angle} textAnchor={angle ? 'end' : 'middle'} />
        <YAxis {...axis} tickFormatter={fmt} />
        <Tooltip formatter={(v: number) => (fmt ? fmt(v) : v)} />
        <Bar dataKey={y} fill={color} radius={[6, 6, 0, 0]} />
      </BarChart>
    </Chart>
  )
}

export function HistogramLongShort({ data }: { data: { hours: number; events: number; long: boolean }[] }) {
  return (
    <Chart label="Histogram of absence durations in hours, coloured by long or short" tall>
      <BarChart data={data} margin={{ top: 10, right: 12, left: 0, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e8edf6" vertical={false} />
        <XAxis dataKey="hours" {...axis} label={{ value: 'Hours absent', position: 'insideBottom', offset: -2, fill: COLORS.muted, fontSize: 12 }} />
        <YAxis {...axis} />
        <Tooltip formatter={(v: number) => [v, 'Events']} labelFormatter={h => `${h} hours`} />
        <Bar dataKey="events" radius={[5, 5, 0, 0]}>{data.map(d => <Cell key={d.hours} fill={d.long ? COLORS.long : COLORS.short} />)}</Bar>
      </BarChart>
    </Chart>
  )
}

export function MultiLine({ data, x, lines, label, percent }: { data: Record<string, any>[]; x: string; lines: { key: string; name: string; color: string; dashed?: boolean }[]; label: string; percent?: boolean }) {
  return (
    <Chart label={label} tall>
      <LineChart data={data} margin={{ top: 10, right: 16, left: 0, bottom: 10 }}>
        <CartesianGrid strokeDasharray="3 3" stroke="#e8edf6" />
        <XAxis dataKey={x} {...axis} />
        <YAxis {...axis} tickFormatter={percent ? pctTick : undefined} domain={percent ? [0, 1] : undefined} />
        <Tooltip formatter={(v: number) => (percent ? `${(v * 100).toFixed(0)}%` : v)} />
        <Legend />
        {lines.map(l => <Line key={l.key} type="monotone" dataKey={l.key} name={l.name} stroke={l.color} strokeWidth={2} dot={false} strokeDasharray={l.dashed ? '5 4' : undefined} />)}
      </LineChart>
    </Chart>
  )
}
