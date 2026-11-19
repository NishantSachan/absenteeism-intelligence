export const pct = (x: number, digits = 0): string => `${(x * 100).toFixed(digits)}%`

/** Probability wording rounded to 5% steps to avoid false precision (as in the original app). */
export function describeProbability(p: number): string {
  if (p < 0.025) return 'under 5%'
  if (p > 0.975) return 'over 95%'
  return `about ${Math.round(p * 20) * 5}%`
}

export const num = (x: number, digits = 0): string =>
  x.toLocaleString('en-US', { minimumFractionDigits: digits, maximumFractionDigits: digits })

export const hours = (x: number): string => `${num(x, Math.abs(x) < 100 ? 1 : 0)} h`

export const fmt = (x: number | undefined | null, digits = 2): string => (x === undefined || x === null || Number.isNaN(x) ? '–' : x.toFixed(digits))

export const COLORS = { long: '#D65367', short: '#159A83', neutral: '#5273D8', ink: '#14213D', muted: '#66738B', amber: '#E0A43A' }
