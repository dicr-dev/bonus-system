export interface FunnelSummary { funnel:string; active_deals:number; monthly_amount:string; machines_count:number; integration_1c_deals:number }
export interface ResponsibleSummary { user_id:string; full_name:string; active_deals:number; monthly_amount:string; machines_count:number }
export interface DashboardSummary { active_deals:number; monthly_amount:string; machines_count:number; integration_1c_deals:number; subscription_implementation_amount:string; subscription_cr_start_amount:string; subscription_total_amount:string; funnels:FunnelSummary[]; responsibles:ResponsibleSummary[] }
export interface Deal { id:string; bitrix_id:number; category_id:number; funnel:string; stage_id:string; status:string; title:string; opportunity:string; monthly_amount:string; machines_count:number; integration_1c:boolean; bitrix_assigned_by_id:number|null; responsible_user_id:string|null; created_time:string|null; closed_time:string|null }
export interface SyncJob { job_id:string; type:string; full:boolean; status:'queued'|'running'|'completed'|'failed'; progress:number; processed:number; current_funnel:string|null; created_at:string; started_at:string|null; finished_at:string|null; error:string|null }
export interface SyncStatus { last_success:string|null }
export interface KPIEmployee { employee_id:string|null; employee_name:string; implementation:number; cr_start:number; fact:number }
export interface KPIDeal { deal_id:string; bitrix_id:number; title:string; funnel:string; employee_name:string|null; monthly_amount:string; machines_count:number }
export interface KPISummary { month:string; plan:string; fact:string; implementation_fact:number; cr_start_fact:number; remaining:string; completion_percent:string; potential:number; forecast:string; employees:KPIEmployee[]; result_deals:KPIDeal[]; potential_deals:KPIDeal[] }

export interface Calculation {
  id:string
  employee_id:string
  employee_name:string|null
  period_from:string
  period_to:string
  month:string
  version:number
  status:string
  rules_version:number|null
  implementation_total:string
  tech_integration_total:string
  support_hours:string
  sales_total:string
  training_count:number
  subtotal_dividable:string
  cr_start_fixed_total:string
  current_client_total:string
  kpi_total:string
  kpi_divided_total:string
  total_bonus:string
  issues_count:number
  created_at:string
}

export interface CalculationItem {
  id:string
  calculation_id:string
  employee_id:string
  deal_id:string|null
  deal_title:string|null
  deal_bitrix_id:number|null
  bonus_type:string
  source_type:string
  source_external_id:string|null
  base_amount:string
  rate:string
  quantity:string
  amount_before_divider:string
  divider_applied:boolean
  amount_final:string
  description:string
  details_json:string
}

export interface CalculationDetail extends Calculation {
  employee_name:string
  items:CalculationItem[]
}

export interface Issue { id:string; calculation_id:string|null; month:string; severity:string; code:string; message:string; employee_id:string|null; deal_id:string|null; details_json:string; created_at:string }
export interface RuleVersion { id:string; version:number; effective_from:string; effective_to:string|null; config_json:string; comment:string|null; created_at:string }

export interface AppSettings {
  tech_integration_category_id:number|null
  implementation_category_id:number|null
  cr_start_category_id:number|null
  support_category_id:number|null
  field_monthly_amount:string
  field_machines_count:string
  field_integration_1c:string
  field_implementation_responsible_id:string
  field_source_deal_id:string
  field_sales_bonus_user_id:string
  cr_start_boolean_fields:string[]
  field_client_works:string
  task_training_bonus_field:string
  field_module:string
  field_integration_amount:string
}

export interface RuleConfig {
  divider:number|string
  tech_integration_rate:number|string
  sales_rate:number|string
  support_hour_rate:number|string
  training_bonus:number|string
  cr_start_fixed:number|string
  implementation_thresholds:Array<{from:number|string;rate:number|string}>
  current_clients_tiers:Array<{from:number;to:number|null;bonus:number|string}>
}
