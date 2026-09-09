import axios from 'axios'
import type { AppSettings,Calculation,CalculationDetail,CurrentUser,DashboardSummary,Deal,DealBonusOverride,DealBonusOverrideInput,Employee,Issue,KPISummary,ManualBonusAdjustment,ManualBonusAdjustmentInput,RuleConfig,RuleVersion,SyncJob,SyncStatus } from './types'

export const api=axios.create({baseURL:'/api/v1',withCredentials:true,timeout:30000})
export async function login(login:string,password:string){return (await api.post('/auth/login',{login,password})).data}
export async function getCurrentUser():Promise<CurrentUser>{return (await api.get('/auth/me')).data}
export async function logout(){return (await api.post('/auth/logout')).data}
export async function getDashboard(month?:string):Promise<DashboardSummary>{return (await api.get('/reports/dashboard',{params:month?{month}:undefined})).data}
export async function getDepartmentDeals():Promise<Deal[]>{return (await api.get('/reports/department-deals')).data}
export async function getSyncStatus():Promise<SyncStatus>{return (await api.get('/sync/deals/status')).data}
export async function startDealsSync(full=false):Promise<SyncJob>{return (await api.post('/sync/deals',null,{params:{full}})).data}
export async function getSyncJob(id:string):Promise<SyncJob>{return (await api.get(`/sync/jobs/${id}`)).data}
export async function getKPI(month:string):Promise<KPISummary>{return (await api.get('/kpi/summary',{params:{month}})).data}
export async function savePlan(month:string,plan_value:number){return (await api.put('/kpi/plan',{plan_value,comment:''},{params:{month}})).data}
export async function runCalculation(month:string):Promise<Calculation[]>{return (await api.post('/calculations/run',null,{params:{month},timeout:120000})).data}
export async function getCalculations(month:string):Promise<Calculation[]>{return (await api.get('/calculations',{params:{month}})).data}
export async function getCalculation(id:string):Promise<CalculationDetail>{return (await api.get(`/calculations/${id}`)).data}
export async function getDealBonusOverrides():Promise<DealBonusOverride[]>{return (await api.get('/calculations/deal-overrides')).data}
export async function saveDealBonusOverride(data:DealBonusOverrideInput):Promise<DealBonusOverride>{return (await api.post('/calculations/deal-overrides',{...data,start_month:`${data.start_month}-01`})).data}
export async function deleteDealBonusOverride(id:string){return api.delete(`/calculations/deal-overrides/${id}`)}
export async function getManualBonusAdjustments():Promise<ManualBonusAdjustment[]>{return (await api.get('/calculations/manual-adjustments')).data}
export async function createManualBonusAdjustment(data:ManualBonusAdjustmentInput):Promise<ManualBonusAdjustment>{return (await api.post('/calculations/manual-adjustments',{...data,start_month:`${data.start_month}-01`})).data}
export async function updateManualBonusAdjustment(id:string,data:ManualBonusAdjustmentInput):Promise<ManualBonusAdjustment>{return (await api.put(`/calculations/manual-adjustments/${id}`,{...data,start_month:`${data.start_month}-01`})).data}
export async function deleteManualBonusAdjustment(id:string){return api.delete(`/calculations/manual-adjustments/${id}`)}
export async function getEmployees():Promise<Employee[]>{return (await api.get('/users/')).data}
export async function runDiagnostics(month:string):Promise<Issue[]>{return (await api.post('/diagnostics/run',null,{params:{month}})).data}
export async function getDiagnostics(month:string):Promise<Issue[]>{return (await api.get('/diagnostics',{params:{month}})).data}
export async function getRules():Promise<RuleVersion[]>{return (await api.get('/settings/rules')).data}
export async function createRule(effective_from:string,config:RuleConfig,comment=''){return (await api.post('/settings/rules',{effective_from,config,comment})).data}
export async function getAppSettings():Promise<AppSettings>{return (await api.get('/settings/app')).data}
export async function saveAppSettings(data:AppSettings):Promise<AppSettings>{return (await api.put('/settings/app',data)).data}
export function excelUrl(month:string){return `/api/v1/reports/export/excel?month=${encodeURIComponent(month)}`}
