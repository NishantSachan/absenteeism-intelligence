import { request } from './client'
import type { Association, Calendar, Durations, Employees, Health, Meta, ModelMetrics, Overview, PredictRequest, PredictResponse,
  Reasons, ScenarioInput, SimulateResponse, Timeline } from './types'

export const api = {
  health: () => request<Health>('/health'),
  meta: () => request<Meta>('/meta'),
  predict: (body: PredictRequest) => request<PredictResponse>('/predict', { method: 'POST', body }),
  overview: () => request<Overview>('/analytics/overview'),
  durations: () => request<Durations>('/analytics/durations'),
  reasons: () => request<Reasons>('/analytics/reasons'),
  calendar: () => request<Calendar>('/analytics/calendar'),
  timeline: () => request<Timeline>('/analytics/timeline'),
  employees: () => request<Employees>('/analytics/employees'),
  association: () => request<Association>('/analytics/association'),
  modelMetrics: () => request<ModelMetrics>('/model/metrics'),
  simulate: (scenarios: ScenarioInput[], monteCarlo: boolean, nSims = 2000) =>
    request<SimulateResponse>('/simulate', { method: 'POST', body: { scenarios, monte_carlo: monteCarlo, n_sims: nSims } }),
}
