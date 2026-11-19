import { afterEach, describe, expect, it, vi } from 'vitest'
import { API_BASE, ApiRequestError, request } from '../api/client'
import { mockFetch } from './fixtures'

afterEach(() => vi.unstubAllGlobals())

describe('api client', () => {
  it('uses the same-origin /api base by default (configurable via VITE_API_BASE_URL)', () => { expect(API_BASE).toBe('/api') })

  it('returns parsed JSON on success and sends JSON bodies', async () => {
    const f = mockFetch({ '/predict': (_u: string, init?: RequestInit) => ({ body: { echoed: JSON.parse(String(init?.body)) } }) })
    const out = await request<{ echoed: { a: number } }>('/predict', { method: 'POST', body: { a: 1 } })
    expect(out.echoed.a).toBe(1)
    expect(f.mock.calls[0][0]).toBe('/api/predict')
  })

  it('turns the consistent error shape into ApiRequestError', async () => {
    mockFetch({ '/predict': { status: 422, body: { error: { code: 'invalid_input', message: 'Bad input', details: [{ field: 'month', message: 'nope' }] } } } })
    await expect(request('/predict', { method: 'POST', body: {} })).rejects.toMatchObject({ status: 422, code: 'invalid_input', message: 'Bad input', details: [{ field: 'month', message: 'nope' }] })
  })

  it('reports network failures with a friendly message', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => { throw new TypeError('failed') }))
    const err = (await request('/health').catch((e: unknown) => e)) as ApiRequestError
    expect(err).toBeInstanceOf(ApiRequestError)
    expect(err.code).toBe('network_error')
  })

  it('handles non-JSON error bodies', async () => {
    vi.stubGlobal('fetch', vi.fn(async () => new Response('<html>bad gateway</html>', { status: 502 })))
    await expect(request('/health')).rejects.toMatchObject({ status: 502, code: 'http_error' })
  })
})
