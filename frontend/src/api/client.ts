import type { ErrorDetail } from './types'

/** Base URL comes from the environment (default: same-origin "/api"). No secrets or keys are ever used. */
export const API_BASE: string = ((import.meta.env.VITE_API_BASE_URL as string | undefined) ?? '/api').replace(/\/$/, '')

export class ApiRequestError extends Error {
  status: number
  code: string
  details: ErrorDetail[]
  constructor(status: number, code: string, message: string, details: ErrorDetail[] = []) {
    super(message)
    this.name = 'ApiRequestError'
    this.status = status
    this.code = code
    this.details = details
  }
}

export async function request<T>(path: string, init?: { method?: string; body?: unknown }): Promise<T> {
  let response: Response
  try {
    response = await fetch(`${API_BASE}${path}`, {
      method: init?.method ?? 'GET',
      headers: init?.body !== undefined ? { 'Content-Type': 'application/json' } : undefined,
      body: init?.body !== undefined ? JSON.stringify(init.body) : undefined,
    })
  } catch {
    throw new ApiRequestError(0, 'network_error', 'Could not reach the server. Please check your connection and try again.')
  }
  let payload: any = null
  try { payload = await response.json() } catch { /* non-JSON body */ }
  if (!response.ok) {
    const err = payload?.error
    throw new ApiRequestError(response.status, err?.code ?? 'http_error', err?.message ?? `Request failed (${response.status}).`, err?.details ?? [])
  }
  return payload as T
}
