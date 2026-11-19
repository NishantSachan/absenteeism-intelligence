import { useCallback, useEffect, useRef, useState } from 'react'
import { ApiRequestError } from '../api/client'

export interface Loadable<T> { data: T | null; error: ApiRequestError | null; loading: boolean; reload: () => void }

/** Fetch on mount (and on reload). Handles loading, error and unmount cleanly. */
export function useApi<T>(fn: () => Promise<T>): Loadable<T> {
  const [data, setData] = useState<T | null>(null)
  const [error, setError] = useState<ApiRequestError | null>(null)
  const [loading, setLoading] = useState(true)
  const [tick, setTick] = useState(0)
  const fnRef = useRef(fn)
  fnRef.current = fn
  const reload = useCallback(() => setTick(t => t + 1), [])

  useEffect(() => {
    let cancelled = false
    setLoading(true); setError(null)
    fnRef.current().then(d => { if (!cancelled) { setData(d); setLoading(false) } })
      .catch(e => { if (!cancelled) { setError(e instanceof ApiRequestError ? e : new ApiRequestError(0, 'unknown', 'Something went wrong.')); setLoading(false) } })
    return () => { cancelled = true }
  }, [tick])
  return { data, error, loading, reload }
}
