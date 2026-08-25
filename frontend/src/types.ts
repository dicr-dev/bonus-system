export interface FunnelSummary {
  funnel: string
  active_deals: number
  monthly_amount: string
  machines_count: number
  integration_1c_deals: number
}

export interface ResponsibleSummary {
  user_id: string
  full_name: string
  active_deals: number
  monthly_amount: string
  machines_count: number
}

export interface DashboardSummary {
  active_deals: number
  monthly_amount: string
  machines_count: number
  integration_1c_deals: number
  funnels: FunnelSummary[]
  responsibles: ResponsibleSummary[]
}

export interface Deal {
  id: string
  bitrix_id: number
  category_id: number
  funnel: string
  stage_id: string
  status: string
  title: string
  opportunity: string
  monthly_amount: string
  machines_count: number
  integration_1c: boolean
  bitrix_assigned_by_id: number | null
  responsible_user_id: string | null
  created_time: string | null
  closed_time: string | null
}

export type SyncJobStatus = 'queued' | 'running' | 'completed' | 'failed'

export interface SyncJob {
  job_id: string
  type: string
  full: boolean
  status: SyncJobStatus
  progress: number
  processed: number
  current_funnel: string | null
  created_at: string
  started_at: string | null
  finished_at: string | null
  error: string | null
}

export interface SyncStatus {
  last_success: string | null
}
