import { render, screen, within } from '@testing-library/react'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import App from '../App'
import { describeProbability, pct } from '../lib/format'
import { durations, meta, mockFetch, overview } from './fixtures'

afterEach(() => vi.unstubAllGlobals())

describe('navigation and Home', () => {
  it('offers the six original screens plus Workforce Planning', async () => {
    mockFetch({ '/meta': meta, '/analytics/overview': overview, '/analytics/durations': durations })
    render(<MemoryRouter><App /></MemoryRouter>)
    const nav = within(screen.getByRole('navigation', { name: 'Main' }))
    for (const name of ['Home', 'Predict', 'Data Explorer', 'Model Performance', 'Insights', 'About', 'Workforce Planning']) {
      expect(nav.getByRole('link', { name: new RegExp(name) })).toBeInTheDocument()
    }
  })

  it('renders live project figures on Home from the API', async () => {
    mockFetch({ '/meta': meta, '/analytics/overview': overview, '/analytics/durations': durations })
    render(<MemoryRouter><App /></MemoryRouter>)
    expect(await screen.findByText('Absence events analysed')).toBeInTheDocument()
    expect(screen.getByText('697')).toBeInTheDocument()
    expect(screen.getByText('v1.0.0')).toBeInTheDocument()
    expect(screen.getByText(/80%/)).toBeInTheDocument()
  })

  it('shows an error with retry when the API is unavailable', async () => {
    mockFetch({})
    render(<MemoryRouter><App /></MemoryRouter>)
    expect(await screen.findByText(/Could not load this section/)).toBeInTheDocument()
  })

  it('shows a not-found page for unknown routes', () => {
    mockFetch({})
    render(<MemoryRouter initialEntries={['/nope']}><App /></MemoryRouter>)
    expect(screen.getByText('Page not found')).toBeInTheDocument()
  })
})

describe('format helpers', () => {
  it('rounds probabilities to 5% steps with bounded wording', () => {
    expect(describeProbability(0.01)).toBe('under 5%')
    expect(describeProbability(0.074)).toBe('about 5%')
    expect(describeProbability(0.62)).toBe('about 60%')
    expect(describeProbability(0.99)).toBe('over 95%')
  })
  it('formats percentages', () => { expect(pct(0.389)).toBe('39%'); expect(pct(0.389, 1)).toBe('38.9%') })
})
