import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { MemoryRouter } from 'react-router-dom'
import { afterEach, describe, expect, it, vi } from 'vitest'
import Predict from '../pages/Predict'
import { meta, mockFetch, predictOk } from './fixtures'

afterEach(() => vi.unstubAllGlobals())
const setup = () => render(<MemoryRouter><Predict /></MemoryRouter>)

async function fill() {
  const user = userEvent.setup()
  await user.selectOptions(await screen.findByLabelText(/Reason for absence/), '23')
  await user.selectOptions(screen.getByLabelText(/^Month/), '7')
  await user.selectOptions(screen.getByLabelText(/Day of the week/), '3')
  return user
}

describe('Predict page', () => {
  it('shows validation errors and does not call the API when the form is empty', async () => {
    const f = mockFetch({ '/meta': meta, '/predict': { body: predictOk } })
    setup()
    const user = userEvent.setup()
    await user.click(await screen.findByRole('button', { name: /Estimate duration/ }))
    expect(screen.getByText('Please choose a reason.')).toBeInTheDocument()
    expect(screen.getByText('Please choose a month.')).toBeInTheDocument()
    expect(f.mock.calls.filter(c => String(c[0]).endsWith('/predict'))).toHaveLength(0)
  })

  it('sends numeric inputs and renders the result with comparisons', async () => {
    const f = mockFetch({ '/meta': meta, '/predict': (_u: string, init?: RequestInit) => ({ body: { ...predictOk, echoed: JSON.parse(String(init?.body)) } }) })
    setup()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: /Estimate duration/ }))
    expect(await screen.findByText(/Likely a short absence/)).toBeInTheDocument()
    expect(screen.getByText('Reason-only comparison')).toBeInTheDocument()
    expect(screen.getByText(/Historical rate for this reason/)).toBeInTheDocument()
    const call = f.mock.calls.find(c => String(c[0]).endsWith('/predict'))!
    expect(JSON.parse(String((call[1] as RequestInit).body))).toEqual({ reason: 23, month: 7, weekday: 3 })
  })

  it('displays server-side validation errors clearly', async () => {
    mockFetch({ '/meta': meta, '/predict': { status: 422, body: { error: { code: 'invalid_input', message: 'The input is not supported by the model.', details: [{ field: null, message: 'Reason code 0 is outside the model scope.' }] } } } })
    setup()
    const user = await fill()
    await user.click(screen.getByRole('button', { name: /Estimate duration/ }))
    const alert = await screen.findByRole('alert')
    expect(alert).toHaveTextContent('not supported by the model')
    expect(alert).toHaveTextContent('outside the model scope')
  })

  it('shows a retry option if the form options cannot be loaded', async () => {
    mockFetch({})
    setup()
    expect(await screen.findByText(/Could not load this section/)).toBeInTheDocument()
    await waitFor(() => expect(screen.getByRole('button', { name: /Try again/ })).toBeInTheDocument())
  })
})
