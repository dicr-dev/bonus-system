import axios from 'axios'
import type { Calculation,CalculationDetail,DashboardSummary,Deal,Issue,KPISummary,RuleVersion,SyncJob,SyncStatus } from './types'
export const api=axios.create({baseURL:'/api/v1',withCredentials:true,timeout:30000})
export async function getDashboard():Promise<DashboardSummary>{return (await api.get('/reports/dashboard')).data}
export async function getDepartmentDeals():Promise<Deal[]>{return (await api.get('/reports/department-deals')).data}
export async function getSyncStatus():Promise<SyncStatus>{return (await api.get('/sync/deals/status')).data}
export async function startDealsSync(full=false):Promise<SyncJob>{return (await api.post('/sync/deals',null,{params:{full}})).data}
export async function getSyncJob(id:string):Promise<SyncJob>{return (await api.get(`/sync/jobs/${id}`)).data}
export async function getKPI(month:string):Promise<KPISummary>{return (await api.get('/kpi/summary',{params:{month}})).data}
export async function savePlan(month:string,plan_value:number){return (await api.put('/kpi/plan',{plan_value,comment:''},{params:{month}})).data}
export async function runCalculation(month:string):Promise<Calculation[]>{return (await api.post('/calculations/run',null,{params:{month}})).data}
export async function getCalculations(month:string):Promise<Calculation[]>{return (await api.get('/calculations',{params:{month}})).data}
export async function getCalculation(id:string):Promise<CalculationDetail>{return (await api.get(`/calculations/${id}`)).data}
export async function runDiagnostics(month:string):Promise<Issue[]>{return (await api.post('/diagnostics/run',null,{params:{month}})).data}
export async function getDiagnostics(month:string):Promise<Issue[]>{return (await api.get('/diagnostics',{params:{month}})).data}
export async function getRules():Promise<RuleVersion[]>{return (await api.get('/settings/rules')).data}
export function excelUrl(month:string){return `/api/v1/reports/export/excel?month=${encodeURIComponent(month)}`}
