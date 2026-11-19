/**
 * Live integration test: renders the real React app against a RUNNING FastAPI server (no mocks).
 * Skipped unless LIVE_API is set:   LIVE_API=http://127.0.0.1:8000 npx vitest run src/test/live.integration.test.tsx
 */
import { render, screen, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterAll, beforeAll, describe, expect, it, vi } from 'vitest'
import App from '../App'

const LIVE = process.env.LIVE_API
const realFetch = globalThis.fetch

describe.skipIf(!LIVE)('live API integration (real backend, real model)', () => {
  beforeAll(() => {
    vi.stubGlobal('fetch', (input: RequestInfo | URL, init?: RequestInit) => realFetch(String(input).startsWith('/api') ? `${LIVE}${input}` : input, init))
  })
  afterAll(() => vi.unstubAllGlobals())

  const open = (path: string) => render(<MemoryRouter initialEntries={[path]}><App /></MemoryRouter>)

  it('Home shows real project figures', async () => {
    open('/')
    expect(await screen.findByText('Absence events analysed', {}, { timeout: 8000 })).toBeInTheDocument()
    expect(screen.getByText('697')).toBeInTheDocument()
    expect(screen.getByText('v1.0.0')).toBeInTheDocument()
  })

  it('Predict: a medical-consultation absence is short and a long-illness absence is long', async () => {
    open('/predict')
    const user = userEvent.setup()
    await user.selectOptions(await screen.findByLabelText(/Reason for absence/, {}, { timeout: 8000 }), '23')
    await user.selectOptions(screen.getByLabelText(/^Month/), '7')
    await user.selectOptions(screen.getByLabelText(/Day of the week/), '3')
    await user.click(screen.getByRole('button', { name: /Estimate duration/ }))
    expect(await screen.findByText(/Likely a short absence/, {}, { timeout: 8000 })).toBeInTheDocument()
    await user.selectOptions(screen.getByLabelText(/Reason for absence/), '22')
    await user.click(screen.getByRole('button', { name: /Estimate duration/ }))
    expect(await screen.findByText(/Likely a long absence/, {}, { timeout: 8000 })).toBeInTheDocument()
  })

  it.each(['/data-explorer', '/model-performance', '/insights', '/about'])('%s loads real data without an error banner', async path => {
    open(path)
    await screen.findByRole('heading', { level: 1 }, { timeout: 8000 })
    await new Promise(r => setTimeout(r, 1500))
    expect(screen.queryByText(/Could not load this section/)).toBeNull()
  })

  it('Planning: runs two real scenarios and shows the disclaimer and a shortfall comparison', async () => {
    open('/planning')
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /Run scenarios/ }, { timeout: 8000 }))
    expect(await screen.findByText(/follow from the assumptions you entered/, {}, { timeout: 8000 })).toBeInTheDocument()
    const table = screen.getAllByRole('table').at(-1)!
    expect(within(table).getByText('Expected lost hours')).toBeInTheDocument()
    expect(within(table).getByText(/Chance of a shortfall/)).toBeInTheDocument()
  })
})
