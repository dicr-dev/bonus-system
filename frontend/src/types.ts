export interface FunnelSummary { funnel:string; active_deals:number; monthly_amount:string; machines_count:number; integration_1c_deals:number }
export interface CurrentUser { id:string; bitrix_id:number; full_name:string; department_name:string|null; is_admin:boolean; is_active:boolean }
export interface ResponsibleSummary { user_id:string; full_name:string; active_deals:number; monthly_amount:string; machines_count:number }
export interface DashboardSummary { active_deals:number; monthly_amount:string; machines_count:number; integration_1c_deals:number; subscription_implementation_amount:string; subscription_cr_start_amount:string; subscription_total_amount:string; funnels:FunnelSummary[]; responsibles:ResponsibleSummary[] }
export interface Deal { id:string; bitrix_id:number; category_id:number; funnel:string; stage_id:string; status:string; title:string; opportunity:string; monthly_amount:string; machines_count:number; integration_1c:boolean; bitrix_assigned_by_id:number|null; responsible_user_id:string|null; created_time:string|null; closed_time:string|null }
export interface SyncJob { job_id:string; type:string; full:boolean; status:'queued'|'running'|'completed'|'failed'; progress:number; processed:number; current_funnel:string|null; created_at:string; started_at:string|null; finished_at:string|null; error:string|null }
export interface NightlySyncResult { users:number; deals:number; tasks:number; elapsed_items:number; period_from:string; period_to:string; finished_at:string }
export interface SyncStatus { last_success:string|null; nightly_last_attempt:string|null; nightly_last_success:string|null; nightly_last_error:string|null; nightly_last_result:NightlySyncResult|null; nightly_hour:number; nightly_timezone:string; nightly_task_months:number }
export interface KPIDeal { deal_id:string; bitrix_id:number; title:string; amount:string }
export interface KPIPlannedDeal { deal_id:string; bitrix_id:number; title:string; planned_date:string; amount:string; machines_count:number }
export interface KPIPartialSubscriptionDeal { deal_id:string; bitrix_id:number; title:string; billing_start_date:string; amount:string; support_deal_created:boolean }
export interface KPISummary { month:string; plan:string; fact:string; plan_completion_percent:string; implementation_total:string; cr_start_total:string; implementation_deals:KPIDeal[]; cr_start_deals:KPIDeal[]; partial_subscription_total:string; partial_subscription_deals:KPIPartialSubscriptionDeal[]; planned_deals:KPIPlannedDeal[] }
export interface BitrixDealField { code:string; title:string; field_type:string }
export interface TimeReportTask { task_bitrix_id:number; title:string; seconds:number; group_id:number|null; responsible_bitrix_id:number|null }
export interface TimeReportDay { date:string; seconds:number; tasks:TimeReportTask[] }
export interface TimeReportEmployee { employee_id:string; full_name:string; department_name:string|null; total_seconds:number; days:TimeReportDay[] }
export interface TimeReport { date_from:string; date_to:string; days:string[]; employees:TimeReportEmployee[] }
export interface Task1CError { task_bitrix_id:number; title:string; group_id:number|null; responsible_bitrix_id:number|null; creator_id:string; creator_name:string; start_time:string; status:number|null }
export interface Task1CErrorReport { tasks:Task1CError[] }
export interface Task1CCheckItem { task_bitrix_id:number; title:string; group_id:number|null; responsible_bitrix_id:number|null; deal_bitrix_id:number|null; deal_title:string|null; deal_funnel:string|null; creator_name:string|null; responsible_name:string|null; created_time:string|null; in_1c_project:boolean; has_1c_type:boolean; status:number|null }
export interface Task1CCheckReport { tasks:Task1CCheckItem[] }
export interface AnalyticsDeal { id:string; bitrix_id:number; title:string; funnel:string; status:string; stage_title:string|null; created_time:string|null; closed_time:string|null; manager_name:string|null }
export interface DealGroup { key:string; company_id:number|null; company_name:string; module_name:string|null; client_status:string; tech:AnalyticsDeal|null; implementation:AnalyticsDeal|null; support:AnalyticsDeal|null; tech_months:number|null; implementation_months:number|null; subscription_months:number|null }
export interface DealGroupIssue { type:string; title:string; child_deals:AnalyticsDeal[]; parent:AnalyticsDeal|null; candidates:AnalyticsDeal[] }
export interface DealGroupsReport { groups:DealGroup[]; issues:DealGroupIssue[] }
export interface SupportAutoMatchPreview { child:AnalyticsDeal; parent:AnalyticsDeal; relation:string }
export interface DealInWork { id:string; bitrix_id:number; title:string; implementation_responsible_name:string|null; funnel:string; first_training_delay_days:number|null; implementation_completion_delay_days:number|null; implementation_planned_billing_start:string|null; implementation_planned_subscription:string|null; planned_subscription_date:string|null }
export interface DealsInWorkReport { tech_integration:DealInWork[]; implementation:DealInWork[] }
export interface WeeklyOvDeal { id:string; bitrix_id:number; funnel:string; movement_status:string; module_name:string|null; implementation_responsible_name:string|null; title:string; salesperson_name:string|null; opportunity:string; machines_count:number; stage_title:string|null; days_in_current_status:number|null; days_in_funnel:number|null; deal_current_status:string|null }
export interface SupportAnalysisDeal { id:string; bitrix_id:number; title:string; opportunity:string; machines_count:number }
export interface SupportAnalysisRow { manager_id:string; manager_name:string; funnel:string; deals_count:number; opportunity:string; machines_count:number; deals:SupportAnalysisDeal[] }
export interface GiftInfoDeal { id:string; bitrix_id:number; title:string; module_name:string|null; decision_maker:string|null; company_name:string|null; responsible_name:string|null; machines_count:number; location:string|null; courier_contact:string|null }
export interface EmployeeMonthPlanDeal { id:string; bitrix_id:number; title:string; module:string|null; machines_count:number; integration_1c:boolean; opportunity:string; monthly_amount:string }
export interface EmployeeMonthPlan { month:string; available_deals:EmployeeMonthPlanDeal[]; planned_deals:EmployeeMonthPlanDeal[] }
export interface AdminEmployeeMonthPlanDeal extends EmployeeMonthPlanDeal {
  employee_id:string; employee_name:string; funnel:string; deal_current_status:string|null; stage_title:string|null
  timely_request_percent:string|null; planned_subscription_date:string|null; implementation_planned_billing_start:string|null
  implementation_planned_subscription:string|null; billing_start_date:string|null; salesperson_name:string|null
  implementation_responsible_name:string|null; integration_amount:string|null; first_training_date:string|null
  second_training_date:string|null; reports_training_date:string|null; cr_company_id:string|null
}
export interface AdminEmployeeMonthPlan { month:string; planned_deals:AdminEmployeeMonthPlanDeal[] }

export interface Calculation {
  id:string
  employee_id:string
  employee_name:string|null
  employee_department:string|null
  period_from:string
  period_to:string
  month:string
  version:number
  status:string
  rules_version:number|null
  implementation_total:string
  tech_integration_total:string
  support_hours:string
  overtime_hours:string
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

export interface Employee {
  id:string
  bitrix_id:number
  email:string|null
  full_name:string
  department_name:string|null
  position:string|null
  is_active:boolean
  is_admin:boolean
}

export interface DealBonusOverrideInput {
  deal_bitrix_id:number
  employee_id:string
  start_month:string
  months:number
  calculation_mode:'formula'|'manual_amount'
  amount?:number|null
  comment?:string
}

export interface DealBonusOverride {
  id:string
  deal_id:string
  deal_bitrix_id:number
  deal_title:string
  funnel:string
  employee_id:string
  employee_name:string
  start_month:string
  end_month:string
  months:number
  calculation_mode:'formula'|'manual_amount'
  amount:string|null
  comment:string|null
  created_at:string
}

export interface ManualBonusAdjustmentInput {
  employee_id:string
  title:string
  start_month:string
  months:number
  amount:number
  comment?:string
}

export interface ManualBonusAdjustment {
  id:string
  employee_id:string
  employee_name:string
  title:string
  start_month:string
  end_month:string
  months:number
  amount:string
  comment:string|null
  created_at:string
}

export interface Issue { id:string; calculation_id:string|null; month:string; severity:string; code:string; message:string; employee_id:string|null; deal_id:string|null; deal_bitrix_id:number|null; details_json:string; created_at:string }
export interface OnboardingTask { id:string; section:string; section_details:string|null; title:string; details:string|null; position:number; is_completed:boolean; comment:string|null; completed_at:string|null }
export interface OnboardingAssignment { id:string; employee_id:string; employee_name:string; assigned_by_name:string; created_at:string; tasks:OnboardingTask[] }
export interface OnboardingPlanTask { id?:string; title:string; details:string|null }
export interface OnboardingPlanSection { id?:string; title:string; details:string|null; tasks:OnboardingPlanTask[] }
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
  cr_start_implementation_modules:string[]
  field_client_works:string
  task_training_bonus_field:string
  task_1c_type_field:string
  task_1c_errors_project_id:number|null
  task_training_yes_value:string
  task_training_date_field:'CLOSED_DATE'|'DEADLINE'
  overtime_project_id:number|null
  overtime_department_ids:string
  task_overtime_hours_field:string
  overtime_time_priority:'manual'|'tracker'
  field_module:string
  field_integration_amount:string
  field_planned_subscription_date:string
  field_billing_start_date:string
  field_deal_current_status:string
  field_timely_request_percent:string
  field_implementation_planned_billing_start:string
  field_implementation_planned_subscription:string
  field_salesperson:string
  field_first_training_date:string
  field_second_training_date:string
  field_reports_training_date:string
  field_cr_company_id:string
  field_gift_decision_maker:string
  field_gift_location:string
  field_gift_courier_contact:string
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
