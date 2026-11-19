import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Planning, { validateDraft } from '../pages/Planning'
import { meta, mockFetch, simulateOk } from './fixtures'

afterEach(() => vi.unstubAllGlobals())
const base = { name: 'A', headcount: '100', horizon_days: '63', shift_hours: '8', events: '0.5', reserve: '3', required: '90', preset: 'historical' as const }

describe('validateDraft', () => {
  it('accepts sensible inputs', () => { expect(validateDraft(base)).toEqual({}) })
  it('rejects out-of-range, non-numeric and fractional-people inputs', () => {
    const e = validateDraft({ ...base, headcount: '0', horizon_days: '400', shift_hours: 'abc', required: '120', reserve: '2.5', name: ' ' })
    expect(Object.keys(e).sort()).toEqual(['headcount', 'horizon_days', 'name', 'required', 'reserve', 'shift_hours'])
  })
})

describe('Planning page', () => {
  const setup = () => render(<MemoryRouter><Planning /></MemoryRouter>)

  it('labels assumptions separately from measured data', async () => {
    mockFetch({ '/meta': meta })
    setup()
    expect(await screen.findByText(/You assume:/)).toBeInTheDocument()
    expect(screen.getByText(/The data supplies:/)).toBeInTheDocument()
  })

  it('blocks submission when an input is invalid', async () => {
    const f = mockFetch({ '/meta': meta, '/simulate': { body: simulateOk } })
    setup()
    const user = userEvent.setup()
    const inputs = await screen.findAllByLabelText(/Scheduled employees/)
    await user.clear(inputs[0]); await user.type(inputs[0], '0')
    await user.click(screen.getByRole('button', { name: /Run scenarios/ }))
    expect(await screen.findByText(/Please fix the highlighted fields/)).toBeInTheDocument()
    expect(f.mock.calls.filter(c => String(c[0]).endsWith('/simulate'))).toHaveLength(0)
  })

  it('runs scenarios and shows the comparison, shortfall labels and disclaimer', async () => {
    const f = mockFetch({ '/meta': meta, '/simulate': (_u: string, init?: RequestInit) => ({ body: { ...simulateOk, sent: JSON.parse(String(init?.body)) } }) })
    setup()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /Run scenarios/ }))
    expect(await screen.findByText(/follow from the assumptions you entered/)).toBeInTheDocument()
    expect(screen.getByText(/\(shortfall\)/)).toBeInTheDocument()
    expect(screen.getByText(/\(spare\)/)).toBeInTheDocument()
    expect(screen.getByText(/Example warning/)).toBeInTheDocument()
    const sent = JSON.parse(String((f.mock.calls.find(c => String(c[0]).endsWith('/simulate'))![1] as RequestInit).body))
    expect(sent.scenarios).toHaveLength(2)
    expect(sent.scenarios[0]).toMatchObject({ headcount: 100, horizon_days: 63, events_per_employee_per_month: 0.5, reason_weights: null })
    expect(sent.monte_carlo).toBe(true)
  })

  it('shows server errors', async () => {
    mockFetch({ '/meta': meta, '/simulate': { status: 422, body: { error: { code: 'invalid_scenario', message: 'headcount must be between 1 and 100000', details: [] } } } })
    setup()
    await userEvent.setup().click(await screen.findByRole('button', { name: /Run scenarios/ }))
    expect(await screen.findByText(/headcount must be between/)).toBeInTheDocument()
  })

  it('applies the reason-mix preset by up-weighting the matching tier', async () => {
    const f = mockFetch({ '/meta': meta, '/simulate': { body: simulateOk } })
    setup()
    const user = userEvent.setup()
    const selects = await screen.findAllByLabelText(/Reason mix/)
    await user.selectOptions(selects[0], 'long')
    await user.click(screen.getByRole('button', { name: /Run scenarios/ }))
    await screen.findByText(/follow from the assumptions/)
    const sent = JSON.parse(String((f.mock.calls.find(c => String(c[0]).endsWith('/simulate'))![1] as RequestInit).body))
    expect(sent.scenarios[0].reason_weights).toEqual({ '23': 0.5, '13': 1 })
  })
})
