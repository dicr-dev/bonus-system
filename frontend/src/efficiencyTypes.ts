export type EfficiencyFunnel='tech_integration'|'implementation'
export interface EfficiencyMetrics {
 deal_count:number;new_count:number;work_count:number;active_end_count:number;won_count:number;lost_count:number
 won_amount:string;lost_amount:string;success_rate:number|null;avg_completion_days:number|null
 with_1c_count:number;won_with_1c_count:number;avg_days_with_1c:number|null;avg_days_without_1c:number|null
 training_count:number;first_training_count:number;second_training_count:number;reports_training_count:number
 fully_trained_count:number;unknown_training_target_count:number;support_created_count:number
}
export interface EfficiencyDeal {
 id:string;bitrix_id:number;title:string;employee_id:string;employee_name:string;funnel:EfficiencyFunnel;module_name:string
 integration_1c:boolean;amount:string;created_at:string|null;closed_at:string|null
 status_at_end:string;current_status:string;stage_title:string|null;current_stage_title:string|null
 new_in_period:boolean;worked_in_period:boolean;won_in_period:boolean;lost_in_period:boolean;loss_reason:string|null
 duration_days:number|null;days_in_stage:number|null;training_dates:Record<string,string|null>
 training_target:number|null;training_done:number;trainings_in_period:string[];supports_created_in_period:number[]
 history_available:boolean;history:{at:string;stage:string;status:string}[]
}
export interface EfficiencyEmployee {
 id:string;name:string;department:string|null;is_active:boolean|null
 metrics:Record<EfficiencyFunnel,EfficiencyMetrics>;deals:EfficiencyDeal[]
 modules:{module_name:string;metrics:Record<EfficiencyFunnel,EfficiencyMetrics>}[]
}
export interface EmployeeEfficiencyReport {
 date_from:string|null;date_to:string;generated_at:string;summary:Record<EfficiencyFunnel,EfficiencyMetrics>
 employees:EfficiencyEmployee[];losses:{funnel:EfficiencyFunnel;reason:string;count:number;amount:string}[]
 warnings:string[];history_deals:number;total_deals:number
 options:{modules:string[];employees:{id:string;name:string}[]}
}
export interface EfficiencyFilters {
 date_from?:string;date_to?:string;employee_id?:string;module?:string;integration_1c?:boolean
}
