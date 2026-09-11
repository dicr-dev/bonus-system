import {
  BookOutlined,CheckCircleOutlined,CloudSyncOutlined,DashboardOutlined,DatabaseOutlined,DownloadOutlined,
  ExclamationCircleOutlined,FundOutlined,ReloadOutlined,SettingOutlined,TrophyOutlined
} from '@ant-design/icons'
import {
  Alert,Button,Card,Col,Collapse,Descriptions,Drawer,Empty,Form,Input,InputNumber,Layout,Menu,Popconfirm,
  Progress,Row,Select,Space,Statistic,Table,Tag,Typography,message
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query'
import { useEffect,useState } from 'react'
import SettingsPage from './SettingsPage'
import InstructionPage from './InstructionPage'
import OnboardingPage from './OnboardingPage'
import {BitrixLink,dealUrl,sourceUrl} from './BitrixLink'
import {
  createManualBonusAdjustment,deleteDealBonusOverride,deleteManualBonusAdjustment,excelUrl,getCalculation,
  getCalculations,getCurrentUser,getDashboard,getDealBonusOverrides,getDepartmentDeals,getDiagnostics,
  getEmployees,getKPI,getManualBonusAdjustments,getRules,getSyncJob,getSyncStatus,login,logout,runCalculation,
  runDiagnostics,saveDealBonusOverride,savePlan,startDealsSync,updateManualBonusAdjustment
} from './api'
import type {
  Calculation,CalculationDetail,Deal,DealBonusOverride,DealBonusOverrideInput,FunnelSummary,Issue,KPIDeal,
  KPIPlannedDeal,ManualBonusAdjustment,ManualBonusAdjustmentInput,ResponsibleSummary,RuleVersion,SyncJob
} from './types'

const {Header,Content,Sider}=Layout
const {Title,Text}=Typography
const FUNNELS:Record<string,string>={tech_integration:'Тех интеграция',implementation:'Внедрение',cr_start:'CR Start',support:'Сопровождение'}
const BONUS:Record<string,string>={tech_integration:'Тех интеграция',implementation:'Внедрение',cr_start_implementation:'CR Start как внедрение',cr_start_fixed:'CR Start фикс.',deal_manual_adjustment:'Ручная корректировка сделки',manual_adjustment:'Ручной бонус / штраф',sale:'Продажа',support_hours:'Сопровождение по часам',task_hours_reference:'Справочные часы по задачам',current_client:'Текущий клиент',training:'Обучение'}
const funnel=(v:string)=>FUNNELS[v]??v
const rub=(v:string|number)=>new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB',maximumFractionDigits:0}).format(Number(v||0))
const num=(v:string|number)=>new Intl.NumberFormat('ru-RU').format(Number(v||0))
const dateTime=(v:string|null|undefined)=>v?new Date(v).toLocaleString('ru-RU'):'—'
const shortDate=(v:string)=>{const [y,m,d]=v.split('-').map(Number);return new Date(y,m-1,d).toLocaleDateString('ru-RU')}
const monthName=(v:string)=>new Date(`${v.slice(0,7)}-01T00:00:00Z`).toLocaleDateString('ru-RU',{month:'long',year:'numeric',timeZone:'UTC'})
const monthNow=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`}
const Month=({value,onChange}:{value:string;onChange:(v:string)=>void})=><Input type="month" value={value} onChange={e=>onChange(e.target.value)} style={{width:180}}/>

function Dashboard({isAdmin,userId}:{isAdmin:boolean;userId:string}){
 const [month,setMonth]=useState(monthNow())
 const q=useQuery({queryKey:['dashboard',userId,month],queryFn:()=>getDashboard(month),refetchInterval:60000})
 if(q.isLoading)return <Card loading/>
 if(!q.data)return <Alert type="error" message="Не удалось загрузить дашборд"/>
 const fcols:ColumnsType<FunnelSummary>=[
  {title:'Воронка',dataIndex:'funnel',render:funnel},{title:'В работе',dataIndex:'active_deals',align:'right'},
  {title:'Оплата в месяц',dataIndex:'monthly_amount',align:'right',render:rub},{title:'Машин',dataIndex:'machines_count',align:'right',render:num},
  {title:'Интеграция 1С',dataIndex:'integration_1c_deals',align:'right'}
 ]
 const rcols:ColumnsType<ResponsibleSummary>=[
  {title:'Ответственный за внедрение',dataIndex:'full_name'},{title:'Сделок',dataIndex:'active_deals',align:'right'},
  {title:'Оплата',dataIndex:'monthly_amount',align:'right',render:rub},{title:'Машин',dataIndex:'machines_count',align:'right',render:num}
 ]
 const d=q.data
 return <Space direction="vertical" size={24} style={{width:'100%'}}>
  <Row justify="space-between"><Title level={2}>Главная</Title><Month value={month} onChange={setMonth}/></Row>
  <Row gutter={[16,16]}>
   <Col xs={24} md={6}><Card><Statistic title="Сделок в работе" value={d.active_deals}/></Card></Col>
   <Col xs={24} md={6}><Card><Statistic title="Оплата в месяц" value={Number(d.monthly_amount)} formatter={v=>rub(Number(v))}/></Card></Col>
   <Col xs={24} md={6}><Card><Statistic title="Машин" value={d.machines_count}/></Card></Col>
   <Col xs={24} md={6}><Card><Statistic title="Интеграций 1С" value={d.integration_1c_deals}/></Card></Col>
  </Row>
  <Card title={`Сумма переданных на подписку сделок за ${month}`}>
   <Row gutter={[16,16]}>
    <Col xs={24} md={8}><Statistic title="Воронка «Внедрение»" value={Number(d.subscription_implementation_amount)} formatter={v=>rub(Number(v))}/></Col>
    <Col xs={24} md={8}><Statistic title="Воронка «CR Start»" value={Number(d.subscription_cr_start_amount)} formatter={v=>rub(Number(v))}/></Col>
    <Col xs={24} md={8}><Statistic title="Итого" value={Number(d.subscription_total_amount)} formatter={v=>rub(Number(v))}/></Col>
   </Row>
  </Card>
  <Card title="Воронки"><Table rowKey="funnel" columns={fcols} dataSource={d.funnels} pagination={false}/></Card>
  {isAdmin&&<Card title="Ответственные за внедрение"><Table rowKey="user_id" columns={rcols} dataSource={d.responsibles} pagination={{pageSize:20}}/></Card>}
 </Space>
}

function KPI(){
 const [month,setMonth]=useState(monthNow());const [plan,setPlan]=useState<number|null>(null);const qc=useQueryClient()
 const q=useQuery({queryKey:['kpi',month],queryFn:()=>getKPI(month)})
 useEffect(()=>{if(q.data)setPlan(Number(q.data.plan))},[q.data])
 const save=useMutation({mutationFn:()=>savePlan(month,plan??0),onSuccess:()=>{message.success('План сохранен');void qc.invalidateQueries({queryKey:['kpi',month]})}})
 const dc:ColumnsType<KPIDeal>=[
  {title:'Сделка',dataIndex:'title',render:(title,deal)=><BitrixLink href={dealUrl(deal.bitrix_id)}>№{deal.bitrix_id} — {title}</BitrixLink>},
  {title:'Сумма',dataIndex:'amount',render:rub,align:'right'}
 ]
 const plannedColumns:ColumnsType<KPIPlannedDeal>=[
  {title:'Сделка',dataIndex:'title',render:(title,deal)=><BitrixLink href={dealUrl(deal.bitrix_id)}>№{deal.bitrix_id} — {title}</BitrixLink>},
  {title:'Расчетная дата перевода на подписку',dataIndex:'planned_date',render:shortDate},
  {title:'Сумма сделки',dataIndex:'amount',render:rub,align:'right'},
  {title:'Кол-во машин',dataIndex:'machines_count',render:num,align:'right'}
 ]
 if(!q.data)return <Card loading/>
 const d=q.data
 return <Space direction="vertical" size={24} style={{width:'100%'}}>
  <Row justify="space-between"><Title level={2}>KPI отдела</Title><Month value={month} onChange={setMonth}/></Row>
  <Row gutter={[16,16]}>
   <Col xs={24} md={8}><Card><Statistic title="План" value={Number(d.plan)} formatter={v=>rub(Number(v))}/></Card></Col>
   <Col xs={24} md={8}><Card><Statistic title="Факт" value={Number(d.fact)} formatter={v=>rub(Number(v))}/></Card></Col>
   <Col xs={24} md={8}><Card><Statistic title="Процент выполнения плана" value={Number(d.plan_completion_percent)} precision={1} suffix="%"/></Card></Col>
  </Row>
  <Card title="План месяца"><Space><InputNumber min={0} value={plan} onChange={v=>setPlan(v)} addonAfter="₽"/><Button type="primary" loading={save.isPending} onClick={()=>save.mutate()}>Сохранить</Button></Space></Card>
  <Card title="Переданные на подписку сделки"><Collapse defaultActiveKey={[]} items={[
    {key:'implementation',label:<Space><Text strong>Внедрение</Text><Text type="secondary">{d.implementation_deals.length} сделок · {rub(d.implementation_total)}</Text></Space>,children:<Table rowKey="deal_id" columns={dc} dataSource={d.implementation_deals} pagination={false}/>},
    {key:'cr_start',label:<Space><Text strong>CR Start</Text><Text type="secondary">{d.cr_start_deals.length} сделок · {rub(d.cr_start_total)}</Text></Space>,children:<Table rowKey="deal_id" columns={dc} dataSource={d.cr_start_deals} pagination={false}/>}
  ]}/></Card>
  <Card title="Сделки, которые планируется передать в этом месяце"><Collapse defaultActiveKey={[]} items={[
   {key:'planned',label:<Space><Text strong>Список сделок</Text><Text type="secondary">{d.planned_deals.length}</Text></Space>,children:<Table rowKey="deal_id" columns={plannedColumns} dataSource={d.planned_deals} pagination={false} scroll={{x:850}}/>}
  ]}/></Card>
 </Space>
}

function Bonuses({isAdmin,userId}:{isAdmin:boolean;userId:string}){
 const [month,setMonth]=useState(monthNow());const [id,setId]=useState<string|null>(null);const [editingManualId,setEditingManualId]=useState<string|null>(null);const [overrideForm]=Form.useForm<DealBonusOverrideInput>();const [manualForm]=Form.useForm<ManualBonusAdjustmentInput>();const qc=useQueryClient()
 const q=useQuery({queryKey:['calc',userId,month],queryFn:()=>getCalculations(month)})
 const detail=useQuery({queryKey:['calc-detail',userId,id],queryFn:()=>getCalculation(id!),enabled:Boolean(id)})
 const overrides=useQuery({queryKey:['deal-bonus-overrides'],queryFn:getDealBonusOverrides,enabled:isAdmin})
 const manualAdjustments=useQuery({queryKey:['manual-bonus-adjustments'],queryFn:getManualBonusAdjustments,enabled:isAdmin})
 const employees=useQuery({queryKey:['employees'],queryFn:getEmployees,enabled:isAdmin})
 const run=useMutation({mutationFn:()=>runCalculation(month),onSuccess:()=>{message.success('Новая версия расчета создана');void qc.invalidateQueries({queryKey:['calc',userId,month]})},onError:(error:any)=>message.error(error.response?.data?.detail||'Не удалось выполнить расчёт')})
 const saveOverride=useMutation({
  mutationFn:saveDealBonusOverride,
  onSuccess:()=>{
   message.success('Корректировка сохранена. Пересчитайте нужные месяцы.')
   overrideForm.resetFields()
   void qc.invalidateQueries({queryKey:['deal-bonus-overrides']})
  },
  onError:(error:any)=>message.error(error.response?.data?.detail||'Не удалось сохранить корректировку')
 })
 const removeOverride=useMutation({
  mutationFn:deleteDealBonusOverride,
  onSuccess:()=>{message.success('Корректировка удалена');void qc.invalidateQueries({queryKey:['deal-bonus-overrides']})},
  onError:(error:any)=>message.error(error.response?.data?.detail||'Не удалось удалить корректировку')
 })
 const saveManualAdjustment=useMutation({
  mutationFn:(values:ManualBonusAdjustmentInput)=>editingManualId?updateManualBonusAdjustment(editingManualId,values):createManualBonusAdjustment(values),
  onSuccess:()=>{message.success('Ручной бонус или штраф сохранён. Пересчитайте нужные месяцы.');manualForm.resetFields();setEditingManualId(null);void qc.invalidateQueries({queryKey:['manual-bonus-adjustments']})},
  onError:(error:any)=>message.error(error.response?.data?.detail||'Не удалось сохранить ручную корректировку')
 })
 const removeManualAdjustment=useMutation({
  mutationFn:deleteManualBonusAdjustment,
  onSuccess:()=>{message.success('Ручной бонус или штраф удалён');void qc.invalidateQueries({queryKey:['manual-bonus-adjustments']})},
  onError:(error:any)=>message.error(error.response?.data?.detail||'Не удалось удалить ручную корректировку')
 })
 const overrideMode=Form.useWatch('calculation_mode',overrideForm)??'manual_amount'

 const cols:ColumnsType<Calculation>=[
  {title:'ФИО сотрудника',dataIndex:'employee_name',render:(v:string|null)=>v??'—'},
  {title:'Версия',dataIndex:'version'},
  {title:'За текущих клиентов',dataIndex:'current_client_total',render:rub},
  {title:'KPI',dataIndex:'kpi_total',render:rub},
  {title:'KPI/2,5',dataIndex:'kpi_divided_total',render:rub},
  {title:'CR Start',dataIndex:'cr_start_fixed_total',render:rub},
  {title:'Часы текущих клиентов',dataIndex:'support_hours'},
  {title:'Кол-во часов переработки',dataIndex:'overtime_hours'},
  {title:'Итого',dataIndex:'total_bonus',render:v=><b>{rub(v)}</b>},
  {title:'',render:(_,r)=><Button onClick={()=>setId(r.id)}>Детализация</Button>}
 ]

 const calculationDepartment=(calculation:Calculation)=>
  calculation.employee_department?.split(';').map(value=>value.trim()).includes('Разработка 1С')
   ?'Разработка 1С'
   :'Отдел внедрения'
 const departmentGroups=['Отдел внедрения','Разработка 1С'].map(department=>({
  department,
  calculations:(q.data??[]).filter(calculation=>calculationDepartment(calculation)===department)
 }))
 const employeeOptions=(employees.data??[]).filter(employee=>employee.is_active&&['Отдел внедрения','Разработка 1С'].some(department=>employee.department_name?.split(';').map(value=>value.trim()).includes(department))).map(employee=>({value:employee.id,label:`${employee.full_name} · ${employee.department_name}`}))

 const overrideColumns:ColumnsType<DealBonusOverride>=[
  {title:'Сделка',render:(_,item)=><BitrixLink href={dealUrl(item.deal_bitrix_id)}>№{item.deal_bitrix_id} — {item.deal_title}</BitrixLink>},
  {title:'Воронка',dataIndex:'funnel',render:funnel},
  {title:'Сотрудник',dataIndex:'employee_name'},
  {title:'Период',render:(_,item)=>`${monthName(item.start_month)} — ${monthName(item.end_month)}`},
  {title:'Месяцев',dataIndex:'months',align:'center'},
  {title:'Режим',dataIndex:'calculation_mode',render:mode=>mode==='formula'?'По формуле':'Ручная сумма'},
  {title:'Сумма за месяц',dataIndex:'amount',render:(value:string|null)=>value===null?'По формуле':rub(value),align:'right'},
  {title:'Комментарий',dataIndex:'comment',render:(value:string|null)=>value||'—'},
  {title:'',render:(_,item)=><Space><Button size="small" onClick={()=>overrideForm.setFieldsValue({deal_bitrix_id:item.deal_bitrix_id,employee_id:item.employee_id,start_month:item.start_month.slice(0,7),months:item.months,calculation_mode:item.calculation_mode,amount:item.amount===null?undefined:Number(item.amount),comment:item.comment??undefined})}>Изменить</Button><Popconfirm title="Удалить корректировку?" description="После удаления для сделки снова будет применяться период из Bitrix." okText="Удалить" cancelText="Отмена" onConfirm={()=>removeOverride.mutate(item.id)}><Button size="small" danger>Удалить</Button></Popconfirm></Space>}
 ]

 const manualAdjustmentColumns:ColumnsType<ManualBonusAdjustment>=[
  {title:'Сотрудник',dataIndex:'employee_name'},
  {title:'Название',dataIndex:'title'},
  {title:'Период',render:(_,item)=>`${monthName(item.start_month)} — ${monthName(item.end_month)}`},
  {title:'Месяцев',dataIndex:'months',align:'center'},
  {title:'Сумма за месяц',dataIndex:'amount',render:rub,align:'right'},
  {title:'Комментарий',dataIndex:'comment',render:(value:string|null)=>value||'—'},
  {title:'',render:(_,item)=><Space><Button size="small" onClick={()=>{setEditingManualId(item.id);manualForm.setFieldsValue({employee_id:item.employee_id,title:item.title,start_month:item.start_month.slice(0,7),months:item.months,amount:Number(item.amount),comment:item.comment??undefined})}}>Изменить</Button><Popconfirm title="Удалить ручную корректировку?" okText="Удалить" cancelText="Отмена" onConfirm={()=>removeManualAdjustment.mutate(item.id)}><Button size="small" danger>Удалить</Button></Popconfirm></Space>}
 ]

 type Item = CalculationDetail['items'][number]

 const groups=[
  ['tech_integration','Технические интеграции'],
  ['implementation','Внедрение'],
  ['cr_start_fixed','CR Start фиксированный'],
  ['cr_start_implementation','CR Start как внедрение'],
  ['deal_manual_adjustment','Ручные корректировки сделок'],
  ['manual_adjustment','Ручные бонусы и штрафы'],
  ['current_client','Текущие клиенты'],
  ['training','Обучение'],
  ['overtime_hours','Переработки — учёт часов'],
  ['sale','Продажи']
 ] as const

 const baseValue=(item:Item)=>{
  if(item.bonus_type==='current_client')return `${num(item.base_amount)} машин`
  if(['support_hours','task_hours_reference','overtime_hours'].includes(item.bonus_type))return `${num(item.quantity)} ч`
  if(item.bonus_type==='training')return `${num(item.quantity)} шт.`
  return rub(item.base_amount)
 }

 const rateValue=(item:Item)=>{
  if(item.bonus_type==='overtime_hours')return 'Только часы'
  if(item.bonus_type==='task_hours_reference')return 'Справочно'
  if(item.bonus_type==='current_client')return rub(item.rate)
  if(item.bonus_type==='support_hours')return `${rub(item.rate)}/ч`
  if(item.bonus_type==='training')return rub(item.rate)
  if(['deal_manual_adjustment','manual_adjustment'].includes(item.bonus_type))return 'Ручная сумма'
  return `${num(Number(item.rate)*100)}%`
 }

 const sourceValue=(item:Item)=>{
  if(item.source_type==='task'){
   try{
    const task=JSON.parse(item.details_json||'{}').task
    if(task?.title)return task.title
    if(task?.TITLE)return task.TITLE
   }catch{/* Older snapshots may have no task data. */}
  }
  if(item.deal_title)return item.deal_title
  if(item.description)return item.description
  return '—'
 }

 const itemColumns:ColumnsType<Item>=[
  {title:'Сделка / источник',render:(_,item)=><div><div><BitrixLink href={sourceUrl(item)}>{sourceValue(item)}</BitrixLink></div>{item.source_type==='task'&&item.source_external_id&&<div><BitrixLink href={sourceUrl(item)}>Задача #{item.source_external_id}</BitrixLink></div>}{item.deal_bitrix_id&&item.source_type==='task'&&<div><BitrixLink href={dealUrl(item.deal_bitrix_id)}>Сделка #{item.deal_bitrix_id}: {item.deal_title}</BitrixLink></div>}{item.deal_bitrix_id&&item.source_type!=='task'&&<BitrixLink href={dealUrl(item.deal_bitrix_id)}>ID {item.deal_bitrix_id}</BitrixLink>}</div>},
  {title:'Месяц',render:(_,item)=>{try{const json=JSON.parse(item.details_json||'{}');const month=json.bonus_month_number;return month?`${month}-й месяц`:'—'}catch{return '—'}},align:'center'},
  {title:'База',render:(_,item)=>baseValue(item),align:'right'},
  {title:'Ставка',render:(_,item)=>rateValue(item),align:'right'},
  {title:'Начислено',dataIndex:'amount_before_divider',render:rub,align:'right'},
  {title:'Делится на 2,5',dataIndex:'divider_applied',render:(v:boolean)=>v?'Да':'Нет',align:'center'},
  {title:'К выплате',dataIndex:'amount_final',render:(v:string)=><b>{rub(v)}</b>,align:'right'}
 ]

 const detailsValue=(item:Item):Record<string,any>=>{
  try{return JSON.parse(item.details_json||'{}')}catch{return {}}
 }

 const taskHourFunnel=(item:Item)=>{
  const group=detailsValue(item).task_hours_group
  if(group)return String(group)
  const value=detailsValue(item).client_deal_funnel
  if(value)return String(value)
  return item.bonus_type==='support_hours'?'support':''
 }

 const taskHourColumns:ColumnsType<Item>=[
  {title:'Задача',render:(_,item)=><BitrixLink href={sourceUrl(item)}>{item.source_external_id?`№${item.source_external_id} — `:''}{sourceValue(item)}</BitrixLink>},
  {title:'Сделка',render:(_,item)=>item.deal_bitrix_id?<BitrixLink href={dealUrl(item.deal_bitrix_id)}>{item.deal_title||`Сделка №${item.deal_bitrix_id}`}</BitrixLink>:'—'},
  {title:'Часы',dataIndex:'quantity',render:num,align:'right'},
  {title:'В KPI',render:(_,item)=>item.bonus_type==='support_hours'?<Tag color="green">Да</Tag>:<Tag>Нет</Tag>,align:'center'},
  {title:'Ставка',render:(_,item)=>item.bonus_type==='support_hours'?`${rub(item.rate)}/ч`:'—',align:'right'},
  {title:'К выплате',render:(_,item)=>item.bonus_type==='support_hours'?<b>{rub(item.amount_final)}</b>:'—',align:'right'}
 ]

 const renderDetail=()=>{
  if(!detail.data)return null
  const data=detail.data

  const totalBy=(type:string)=>data.items.filter(item=>item.bonus_type===type).reduce((sum,item)=>sum+Number(item.amount_before_divider||0),0)
  const hoursBy=(type:string)=>data.items.filter(item=>item.bonus_type===type).reduce((sum,item)=>sum+Number(item.quantity||0),0)
  const sectionRows=(type:string, labelFactory?:(item:Item)=>string)=>{
    const items=data.items.filter(item=>item.bonus_type===type)
    return items.map(item=>({
      id:item.id,
      href:sourceUrl(item),
      label: labelFactory?labelFactory(item):sourceValue(item),
      value: rub(item.amount_before_divider)
    }))
  }

  const summarySections=[
   {label:'Интеграции', total:totalBy('tech_integration'), rows:sectionRows('tech_integration',item=>sourceValue(item))},
   {label:'Внедрение', total:totalBy('implementation'), rows:sectionRows('implementation',item=>sourceValue(item))},
   {label:'CR Start как внедрение', total:totalBy('cr_start_implementation'), rows:sectionRows('cr_start_implementation',item=>sourceValue(item))},
   {label:'Обучения', total:totalBy('training'), rows:sectionRows('training',item=>item.description||sourceValue(item))},
   {label:'Оплата за часы текущих клиентов', total:totalBy('support_hours'), rows:[]},
   {label:'Часы текущих клиентов', total:hoursBy('support_hours'), rows:[], suffix:' ч'},
   {label:'Переработка', total:hoursBy('overtime_hours'), rows:[], suffix:' ч'},
   {label:'CR Start', total:totalBy('cr_start_fixed'), rows:sectionRows('cr_start_fixed',item=>sourceValue(item))},
   {label:'Корректировки сделок', total:totalBy('deal_manual_adjustment'), rows:sectionRows('deal_manual_adjustment',item=>sourceValue(item))},
   {label:'Ручные бонусы и штрафы', total:totalBy('manual_adjustment'), rows:sectionRows('manual_adjustment',item=>item.description)},
   {label:'Текущие', total:totalBy('current_client'), rows:[]}
  ]

  const taskHourItems=data.items.filter(item=>['support_hours','task_hours_reference'].includes(item.bonus_type))
  const taskHourFunnels=[
   ['tech_integration','Тех интеграция'],
   ['implementation','Внедрение'],
   ['support','Сопровождение'],
   ['cr_start_before_commercial','CR Start до комм. использования'],
   ['cr_start_commercial','CR Start при комм. использовании']
  ] as const

  return <>
   <Card size="small" title="Общая информация" style={{marginBottom:20}}>
    <Space direction="vertical" size={12} style={{width:'100%'}}>
     {summarySections.map(section=>{
      if(section.rows.length===0 && section.total===0 && !['Переработка','Оплата за часы текущих клиентов','Часы текущих клиентов','Текущие'].includes(section.label)) return null
      return <div key={section.label}>
       <Text strong>{section.label} — {section.suffix?`${num(section.total)}${section.suffix}`:rub(section.total)}</Text>
       {section.rows.length>0&&<div style={{marginTop:8, paddingLeft:16}}>
        {section.rows.map(row=><div key={row.id} style={{display:'flex',justifyContent:'space-between',gap:12,marginBottom:4}}><BitrixLink href={row.href}>{row.label}</BitrixLink><span>{row.value}</span></div>)}
       </div>}
      </div>
     })}
    </Space>
   </Card>

   <Descriptions bordered size="small" column={3}>
    <Descriptions.Item label="Итого">{rub(data.total_bonus)}</Descriptions.Item>
    <Descriptions.Item label="Версия">{data.version}</Descriptions.Item>
    <Descriptions.Item label="Делимая часть">{rub(data.subtotal_dividable)}</Descriptions.Item>
   </Descriptions>

   <Space direction="vertical" size={16} style={{width:'100%',marginTop:20}}>
    <Card size="small" title="Расшифровка по часам задач">
     <Collapse
      defaultActiveKey={[]}
      items={taskHourFunnels.map(([funnelKey,title])=>{
       const items=taskHourItems.filter(item=>taskHourFunnel(item)===funnelKey)
       const hours=items.reduce((sum,item)=>sum+Number(item.quantity||0),0)
       return {
        key:funnelKey,
        label:<Space><Text strong>{title}</Text><Text type="secondary">{items.length} задач · {num(hours)} ч</Text></Space>,
        children:items.length>0?<Table rowKey="id" columns={taskHourColumns} dataSource={items} pagination={false} size="small" scroll={{x:800}}/>:<Text type="secondary">Нет записей времени за выбранный месяц</Text>
       }
      })}
     />
    </Card>

    {groups.map(([type,title])=>{
      const items=data.items.filter(item=>item.bonus_type===type)
      if(items.length===0)return null
      const total=items.reduce((sum,item)=>sum+Number(item.amount_final||0),0)

      return <Card
       key={type}
       size="small"
       title={title}
       extra={<Text strong>Итого: {rub(total)}</Text>}
      >
       <Table
        rowKey="id"
        columns={itemColumns}
        dataSource={items}
        pagination={false}
        size="small"
        scroll={{x:900}}
       />
      </Card>
    })}

    {data.items.length===0&&<Alert type="warning" showIcon message="В расчете нет детализации начислений."/>}

    {!data.items.some(item=>item.bonus_type==='support_hours')&&
     <Alert
      type="warning"
      showIcon
      message="Часы по задачам текущих клиентов отсутствуют в расчете"
      description="Это не проблема отображения: backend не вернул ни одного начисления support_hours для этого сотрудника и месяца."
     />}
   </Space>
  </>
 }

 return <Space direction="vertical" size={24} style={{width:'100%'}}>
  <Row justify="space-between">
   <Title level={2}>{isAdmin?'Расчет премий':'Моя премия'}</Title>
   <Space>
    <Month value={month} onChange={setMonth}/>
    {isAdmin&&<Button type="primary" loading={run.isPending} onClick={()=>run.mutate()}>Пересчитать</Button>}
    {isAdmin&&<Button icon={<DownloadOutlined/>} href={excelUrl(month)}>Excel</Button>}
   </Space>
  </Row>
  {isAdmin&&<Alert type="info" showIcon message="Каждый перерасчет создает новую версию; история не перезаписывается."/>}

  {isAdmin&&<Card title="Корректировки начислений сделок">
   <Alert type="info" showIcon message="Доступны сделки CR Start и Внедрения. Режим «По формуле» сохраняет правила сделки, «Ручная сумма» начисляет указанную сумму без деления на 2,5. После сохранения пересчитайте каждый нужный месяц." style={{marginBottom:20}}/>
   <Form form={overrideForm} layout="vertical" initialValues={{months:3,calculation_mode:'manual_amount',amount:10000}} onFinish={values=>saveOverride.mutate(values)}>
    <Row gutter={[16,0]} align="bottom">
     <Col xs={24} md={4}><Form.Item name="deal_bitrix_id" label="Номер сделки" rules={[{required:true,message:'Укажите номер сделки'}]}><InputNumber min={1} precision={0} style={{width:'100%'}} placeholder="51524"/></Form.Item></Col>
     <Col xs={24} md={6}><Form.Item name="employee_id" label="Сотрудник" rules={[{required:true,message:'Выберите сотрудника'}]}><Select showSearch optionFilterProp="label" loading={employees.isLoading} options={employeeOptions}/></Form.Item></Col>
     <Col xs={24} md={3}><Form.Item name="start_month" label="Первый месяц" rules={[{required:true,message:'Выберите месяц'}]}><Input type="month"/></Form.Item></Col>
     <Col xs={24} md={2}><Form.Item name="months" label="Месяцев" rules={[{required:true}]}><InputNumber min={1} max={12} precision={0} style={{width:'100%'}}/></Form.Item></Col>
     <Col xs={24} md={3}><Form.Item name="calculation_mode" label="Режим"><Select options={[{value:'formula',label:'По формуле'},{value:'manual_amount',label:'Ручная сумма'}]}/></Form.Item></Col>
     <Col xs={24} md={3}><Form.Item name="amount" label="Сумма, ₽" rules={overrideMode==='manual_amount'?[{required:true,message:'Укажите сумму'}]:[]}><InputNumber disabled={overrideMode==='formula'} precision={2} style={{width:'100%'}}/></Form.Item></Col>
     <Col xs={24} md={3}><Form.Item name="comment" label="Комментарий"><Input placeholder="Причина"/></Form.Item></Col>
    </Row>
    <Button type="primary" htmlType="submit" loading={saveOverride.isPending}>Сохранить корректировку</Button>
   </Form>
   <div style={{marginTop:24}}>
    {overrides.data?.length?<Table rowKey="id" columns={overrideColumns} dataSource={overrides.data} pagination={false}/>:<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Корректировок пока нет"/>}
   </div>
  </Card>}

  {isAdmin&&<Card title="Ручные бонусы и штрафы">
   <Alert type="info" showIcon message="Сумма начисляется каждый месяц выбранного периода, не делится на 2,5. Для штрафа укажите отрицательное значение." style={{marginBottom:20}}/>
   <Form form={manualForm} layout="vertical" initialValues={{months:1}} onFinish={values=>saveManualAdjustment.mutate(values)}>
    <Row gutter={[16,0]} align="bottom">
     <Col xs={24} md={6}><Form.Item name="employee_id" label="Сотрудник" rules={[{required:true,message:'Выберите сотрудника'}]}><Select showSearch optionFilterProp="label" loading={employees.isLoading} options={employeeOptions}/></Form.Item></Col>
     <Col xs={24} md={6}><Form.Item name="title" label="Название" rules={[{required:true,message:'Укажите название'}]}><Input placeholder="Фиксированный KPI на период адаптации"/></Form.Item></Col>
     <Col xs={24} md={3}><Form.Item name="start_month" label="Первый месяц" rules={[{required:true,message:'Выберите месяц'}]}><Input type="month"/></Form.Item></Col>
     <Col xs={24} md={2}><Form.Item name="months" label="Месяцев" rules={[{required:true}]}><InputNumber min={1} max={12} precision={0} style={{width:'100%'}}/></Form.Item></Col>
     <Col xs={24} md={3}><Form.Item name="amount" label="Сумма, ₽" rules={[{required:true,message:'Укажите сумму'}]}><InputNumber precision={2} style={{width:'100%'}}/></Form.Item></Col>
     <Col xs={24} md={4}><Form.Item name="comment" label="Комментарий"><Input placeholder="Основание"/></Form.Item></Col>
    </Row>
    <Space><Button type="primary" htmlType="submit" loading={saveManualAdjustment.isPending}>{editingManualId?'Сохранить изменения':'Добавить бонус или штраф'}</Button>{editingManualId&&<Button onClick={()=>{manualForm.resetFields();setEditingManualId(null)}}>Отмена</Button>}</Space>
   </Form>
   <div style={{marginTop:24}}>
    {manualAdjustments.data?.length?<Table rowKey="id" columns={manualAdjustmentColumns} dataSource={manualAdjustments.data} pagination={false}/>:<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description="Ручных бонусов и штрафов пока нет"/>}
   </div>
  </Card>}

  {isAdmin?departmentGroups.map(group=><Card
   key={group.department}
   title={group.department}
   extra={<Text type="secondary">{group.calculations.length} сотрудников</Text>}
   loading={q.isLoading}
  >
   {group.calculations.length?<Table rowKey="id" columns={cols} dataSource={group.calculations} scroll={{x:1100}}/>:<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`Нет расчетов за ${month}`}/>}
  </Card>):<Card>
   {(q.data??[]).length?<Table rowKey="id" columns={cols} dataSource={q.data??[]} loading={q.isLoading} scroll={{x:1100}}/>:<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={`Нет расчета за ${month}`}/>}
  </Card>}

  <Drawer
   open={Boolean(id)}
   onClose={()=>setId(null)}
   width={1200}
   title={detail.data?.employee_name??'Детализация'}
  >
   {renderDetail()}
  </Drawer>
 </Space>
}

function Deals({isAdmin,userId}:{isAdmin:boolean;userId:string}){
 const q=useQuery({queryKey:['deals',userId],queryFn:getDepartmentDeals})
 const cols:ColumnsType<Deal>=[{title:'ID',dataIndex:'bitrix_id',render:id=><BitrixLink href={dealUrl(id)}>{id}</BitrixLink>},{title:'Сделка',dataIndex:'title',render:(title,deal)=><BitrixLink href={dealUrl(deal.bitrix_id)}>{title}</BitrixLink>},{title:'Воронка',dataIndex:'funnel',render:funnel},{title:'Оплата/мес.',dataIndex:'monthly_amount',render:rub},{title:'Машин',dataIndex:'machines_count'},{title:'1С',dataIndex:'integration_1c',render:v=>v?<Tag color="green">Да</Tag>:<Tag>Нет</Tag>}]
 return <Space direction="vertical" size={24} style={{width:'100%'}}><Title level={2}>{isAdmin?'Сделки':'Мои сделки'}</Title><Card><Table rowKey="id" columns={cols} dataSource={q.data??[]} loading={q.isLoading} pagination={{pageSize:25}}/></Card></Space>
}

function Diagnostics(){
 const [month,setMonth]=useState(monthNow());const qc=useQueryClient()
 const q=useQuery({queryKey:['issues',month],queryFn:()=>getDiagnostics(month)})
 const run=useMutation({mutationFn:()=>runDiagnostics(month),onSuccess:()=>void qc.invalidateQueries({queryKey:['issues',month]})})
 const cols:ColumnsType<Issue>=[{title:'Уровень',dataIndex:'severity',render:v=><Tag color={v==='critical'?'red':'orange'}>{v}</Tag>},{title:'Код',dataIndex:'code'},{title:'Причина',dataIndex:'message'},{title:'Сделка',dataIndex:'deal_bitrix_id',render:(id:number|null)=>id?<BitrixLink href={dealUrl(id)}>Открыть сделку #{id}</BitrixLink>:'—'}]
 return <Space direction="vertical" size={24} style={{width:'100%'}}><Row justify="space-between"><Title level={2}>Диагностика</Title><Space><Month value={month} onChange={setMonth}/><Button icon={<ReloadOutlined/>} onClick={()=>run.mutate()}>Проверить</Button></Space></Row><Card><Table rowKey="id" columns={cols} dataSource={q.data??[]} pagination={{pageSize:30}}/></Card></Space>
}

function Rules(){
 const q=useQuery({queryKey:['rules'],queryFn:getRules})
 const cols:ColumnsType<RuleVersion>=[{title:'Версия',dataIndex:'version'},{title:'С',dataIndex:'effective_from'},{title:'До',dataIndex:'effective_to',render:v=>v??'текущая'},{title:'Комментарий',dataIndex:'comment'},{title:'JSON правил',dataIndex:'config_json',ellipsis:true}]
 return <Space direction="vertical" size={24} style={{width:'100%'}}><Title level={2}>Правила расчета</Title><Alert type="info" showIcon message="Правила версионируются по датам действия."/><Card><Table rowKey="id" columns={cols} dataSource={q.data??[]} pagination={false}/></Card></Space>
}

function Sync(){
 const [jobId,setJobId]=useState<string|null>(null);const qc=useQueryClient()
 const status=useQuery({queryKey:['sync-status'],queryFn:getSyncStatus,refetchInterval:30000})
 const job=useQuery({queryKey:['sync-job',jobId],queryFn:()=>getSyncJob(jobId!),enabled:Boolean(jobId),refetchInterval:q=>{const d=q.state.data as SyncJob|undefined;return d?.status==='completed'||d?.status==='failed'?false:1500}})
 const start=useMutation({mutationFn:(full:boolean)=>startDealsSync(full),onSuccess:j=>setJobId(j.job_id)})
 useEffect(()=>{if(job.data?.status==='completed')void qc.invalidateQueries()},[job.data?.status,qc])
 const nightly=status.data?.nightly_last_result
 return <Space direction="vertical" size={24} style={{width:'100%'}}><Title level={2}>Синхронизация</Title><Card title="Автоматическая ночная синхронизация"><Space direction="vertical"><Text>Запуск ежедневно в {String(status.data?.nightly_hour??2).padStart(2,'0')}:00 ({status.data?.nightly_timezone??'Europe/Moscow'})</Text><Text>Последняя успешная: {dateTime(status.data?.nightly_last_success)}</Text><Text type="secondary">Последняя попытка: {dateTime(status.data?.nightly_last_attempt)}</Text>{nightly&&<Text>Сотрудников: {nightly.users}; сделок: {nightly.deals}; задач: {nightly.tasks}; записей времени: {nightly.elapsed_items}. Период задач: {nightly.period_from} — {nightly.period_to}</Text>}{status.data?.nightly_last_error&&<Alert type="error" showIcon message="Ошибка ночной синхронизации" description={status.data.nightly_last_error}/>}</Space></Card><Card title="Ручная синхронизация сделок"><Space direction="vertical"><Text>Последняя успешная: {dateTime(status.data?.last_success)}</Text><Space><Button type="primary" icon={<CloudSyncOutlined/>} onClick={()=>start.mutate(false)}>Инкрементальная</Button><Button icon={<ReloadOutlined/>} onClick={()=>start.mutate(true)}>Полная</Button></Space></Space></Card>{job.data&&<Card title={`Job ${job.data.job_id}`}><Progress percent={job.data.progress}/><Text>{job.data.status}; обработано {job.data.processed}</Text>{job.data.error&&<Alert type="error" message={job.data.error}/>}</Card>}</Space>
}

function Login({onSuccess}:{onSuccess:()=>void}){
 const [form]=Form.useForm<{login:string;password:string}>()
 const mutation=useMutation({mutationFn:(v:{login:string;password:string})=>login(v.login,v.password),onSuccess})
 return <Layout style={{minHeight:'100vh',alignItems:'center',justifyContent:'center'}}><Card title="Вход администратора" style={{width:380}}>
  <Form form={form} layout="vertical" onFinish={v=>mutation.mutate(v)}>
   <Form.Item name="login" label="Логин" rules={[{required:true}]}><Input autoComplete="username"/></Form.Item>
   <Form.Item name="password" label="Пароль" rules={[{required:true}]}><Input.Password autoComplete="current-password"/></Form.Item>
   {mutation.isError&&<Alert type="error" message="Неверный логин или пароль" showIcon/>}
  <Button type="primary" htmlType="submit" loading={mutation.isPending} block>Войти</Button>
  <Button href="/api/v1/auth/bitrix/login" block style={{marginTop:12}}>Войти через Bitrix24</Button>
  </Form>
 </Card></Layout>
}

export default function App(){
 const [page,setPage]=useState('dashboard')
 const [authVersion,setAuthVersion]=useState(0)
 const user=useQuery({queryKey:['current-user',authVersion],queryFn:getCurrentUser,retry:false})
 if(user.isLoading)return <Card loading/>
 if(user.isError||!user.data)return <Login onSuccess={()=>setAuthVersion(v=>v+1)}/>
 const isAdmin=user.data.is_admin
 const effectivePage=!isAdmin&&!['dashboard','bonus','deals','instruction','onboarding'].includes(page)?'dashboard':page
 const content=({dashboard:<Dashboard isAdmin={isAdmin} userId={user.data.id}/>,kpi:<KPI/>,bonus:<Bonuses isAdmin={isAdmin} userId={user.data.id}/>,deals:<Deals isAdmin={isAdmin} userId={user.data.id}/>,instruction:<InstructionPage/>,onboarding:<OnboardingPage isAdmin={isAdmin}/>,diagnostics:<Diagnostics/>,rules:<Rules/>,settings:<SettingsPage/>,sync:<Sync/>}[effectivePage]??<Dashboard isAdmin={isAdmin} userId={user.data.id}/>)
 const employeeMenu=[
  {key:'dashboard',icon:<DashboardOutlined/>,label:'Главная'},
  {key:'bonus',icon:<FundOutlined/>,label:'Моя премия'},
  {key:'deals',icon:<DatabaseOutlined/>,label:'Мои сделки'},
  {key:'instruction',icon:<BookOutlined/>,label:'Инструкция'},
  {key:'onboarding',icon:<CheckCircleOutlined/>,label:'Адаптация'}
 ]
 const adminMenu=[
  {key:'dashboard',icon:<DashboardOutlined/>,label:'Главная'},{key:'kpi',icon:<TrophyOutlined/>,label:'KPI отдела'},
  {key:'bonus',icon:<FundOutlined/>,label:'Расчет премий'},{key:'deals',icon:<DatabaseOutlined/>,label:'Сделки'},
  {key:'instruction',icon:<BookOutlined/>,label:'Инструкция'},{key:'onboarding',icon:<CheckCircleOutlined/>,label:'Адаптация'},
  {key:'diagnostics',icon:<ExclamationCircleOutlined/>,label:'Диагностика'},{key:'rules',icon:<SettingOutlined/>,label:'Правила'},
  {key:'settings',icon:<SettingOutlined/>,label:'\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438'},
  {key:'sync',icon:<CloudSyncOutlined/>,label:'Синхронизация'}
 ]
 return <Layout className="app-layout">
  <Sider breakpoint="lg" collapsedWidth={0} width={240} className="app-sider">
   <div className="app-logo"><div className="logo-mark">CR</div><div><div className="logo-title">CR Portal</div><div className="logo-subtitle">KPI & Bonus</div></div></div>
   <Menu theme="dark" mode="inline" selectedKeys={[effectivePage]} onClick={({key})=>setPage(key)} items={isAdmin?adminMenu:employeeMenu}/>
  </Sider>
  <Layout><Header className="app-header"><Text strong>CR Integration Portal</Text><Space><Tag color="green" icon={<CheckCircleOutlined/>}>{user.data.full_name}</Tag><Button size="small" onClick={async()=>{await logout();setAuthVersion(v=>v+1)}}>Выйти</Button></Space></Header><Content className="app-content"><div className="content-container">{content}</div></Content></Layout>
 </Layout>
}
