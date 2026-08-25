import axios from 'axios'

import type {
  DashboardSummary,
  Deal,
  SyncJob,
  SyncStatus,
} from './types'

export const api = axios.create({
  baseURL: '/api/v1',
  withCredentials: true,
  timeout: 30000,
})

export async function getDashboard(): Promise<DashboardSummary> {
  const response = await api.get<DashboardSummary>('/reports/dashboard')
  return response.data
}

export async function getDepartmentDeals(): Promise<Deal[]> {
  const response = await api.get<Deal[]>('/reports/department-deals')
  return response.data
}

export async function getSyncStatus(): Promise<SyncStatus> {
  const response = await api.get<SyncStatus>('/sync/deals/status')
  return response.data
}

export async function startDealsSync(full = false): Promise<SyncJob> {
  const response = await api.post<SyncJob>(
    '/sync/deals',
    null,
    { params: { full } },
  )
  return response.data
}

export async function getSyncJob(jobId: string): Promise<SyncJob> {
  const response = await api.get<SyncJob>(`/sync/jobs/${jobId}`)
  return response.data
}
