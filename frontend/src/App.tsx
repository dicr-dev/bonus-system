import {
  CheckCircleOutlined,CloudSyncOutlined,DashboardOutlined,DatabaseOutlined,DownloadOutlined,
  ExclamationCircleOutlined,FundOutlined,ReloadOutlined,SettingOutlined,TrophyOutlined
} from '@ant-design/icons'
import {
  Alert,Button,Card,Col,Descriptions,Drawer,Input,InputNumber,Layout,Menu,Progress,Row,Space,
  Statistic,Table,Tag,Typography,message
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import { useMutation,useQuery,useQueryClient } from '@tanstack/react-query'
import { useEffect,useMemo,useState } from 'react'
import SettingsPage from './SettingsPage'
import {
  excelUrl,getCalculation,getCalculations,getDashboard,getDepartmentDeals,getDiagnostics,getKPI,getRules,
  getSyncJob,getSyncStatus,runCalculation,runDiagnostics,savePlan,startDealsSync
} from './api'
import type {
  Calculation,CalculationDetail,Deal,FunnelSummary,Issue,KPIDeal,KPIEmployee,ResponsibleSummary,RuleVersion,SyncJob
} from './types'

const {Header,Content,Sider}=Layout
const {Title,Text}=Typography
const FUNNELS:Record<string,string>={tech_integration:'Тех интеграция',implementation:'Внедрение',cr_start:'CR Start',support:'Сопровождение'}
const BONUS:Record<string,string>={tech_integration:'Тех интеграция',implementation:'Внедрение',cr_start_implementation:'CR Start как внедрение',cr_start_fixed:'CR Start фикс.',sale:'Продажа',support_hours:'Сопровождение по часам',current_client:'Текущий клиент',training:'Обучение'}
const funnel=(v:string)=>FUNNELS[v]??v
const rub=(v:string|number)=>new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB',maximumFractionDigits:0}).format(Number(v||0))
const num=(v:string|number)=>new Intl.NumberFormat('ru-RU').format(Number(v||0))
const monthNow=()=>{const d=new Date();return `${d.getFullYear()}-${String(d.getMonth()+1).padStart(2,'0')}`}
const Month=({value,onChange}:{value:string;onChange:(v:string)=>void})=><Input type="month" value={value} onChange={e=>onChange(e.target.value)} style={{width:180}}/>

function Dashboard(){
 const [month,setMonth]=useState(monthNow())
 const q=useQuery({queryKey:['dashboard',month],queryFn:()=>getDashboard(month),refetchInterval:60000})
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
  <Card title="Ответственные за внедрение"><Table rowKey="user_id" columns={rcols} dataSource={d.responsibles} pagination={{pageSize:20}}/></Card>
 </Space>
}

function KPI(){
 const [month,setMonth]=useState(monthNow());const [plan,setPlan]=useState<number|null>(null);const qc=useQueryClient()
 const q=useQuery({queryKey:['kpi',month],queryFn:()=>getKPI(month)})
 useEffect(()=>{if(q.data)setPlan(Number(q.data.plan))},[q.data])
 const save=useMutation({mutationFn:()=>savePlan(month,plan??0),onSuccess:()=>{message.success('План сохранен');void qc.invalidateQueries({queryKey:['kpi',month]})}})
 const ec:ColumnsType<KPIEmployee>=[{title:'Сотрудник',dataIndex:'employee_name'},{title:'Внедрение',dataIndex:'implementation'},{title:'CR Start',dataIndex:'cr_start'},{title:'Факт',dataIndex:'fact'}]
 const dc:ColumnsType<KPIDeal>=[{title:'ID',dataIndex:'bitrix_id'},{title:'Сделка',dataIndex:'title'},{title:'Воронка',dataIndex:'funnel',render:funnel},{title:'Сотрудник',dataIndex:'employee_name',render:v=>v??'Без ответственного'}]
 if(!q.data)return <Card loading/>
 const d=q.data
 return <Space direction="vertical" size={24} style={{width:'100%'}}>
  <Row justify="space-between"><Title level={2}>KPI отдела</Title><Month value={month} onChange={setMonth}/></Row>
  <Row gutter={[12,12]}>
   {[
    ['План',d.plan],['Факт',d.fact],['Выполнение, %',d.completion_percent],['Осталось',d.remaining],['Потенциально',d.potential],['Прогноз',d.forecast]
   ].map(([t,v])=><Col xs={12} md={4} key={String(t)}><Card><Statistic title={String(t)} value={Number(v)}/></Card></Col>)}
  </Row>
  <Card title="План месяца"><Space><InputNumber min={0} value={plan} onChange={v=>setPlan(v)}/><Button type="primary" loading={save.isPending} onClick={()=>save.mutate()}>Сохранить</Button></Space></Card>
  <Card title={`Факт = Внедрение ${d.implementation_fact} + CR Start ${d.cr_start_fact}`}><Table rowKey={r=>r.employee_id??r.employee_name} columns={ec} dataSource={d.employees} pagination={false}/></Card>
  <Card title="Сделки результата"><Table rowKey="deal_id" columns={dc} dataSource={d.result_deals} pagination={{pageSize:20}}/></Card>
  <Card title="Потенциальные сделки"><Table rowKey="deal_id" columns={dc} dataSource={d.potential_deals} pagination={{pageSize:20}}/></Card>
 </Space>
}

function Bonuses(){
 const [month,setMonth]=useState(monthNow());const [id,setId]=useState<string|null>(null);const qc=useQueryClient()
 const q=useQuery({queryKey:['calc',month],queryFn:()=>getCalculations(month)})
 const detail=useQuery({queryKey:['calc-detail',id],queryFn:()=>getCalculation(id!),enabled:Boolean(id)})
 const run=useMutation({mutationFn:()=>runCalculation(month),onSuccess:()=>{message.success('Новая версия расчета создана');void qc.invalidateQueries({queryKey:['calc',month]})}})

 const cols:ColumnsType<Calculation>=[
  {title:'ФИО сотрудника',dataIndex:'employee_name',render:(v:string|null)=>v??'—'},
  {title:'Версия',dataIndex:'version'},
  {title:'За текущих клиентов',dataIndex:'current_client_total',render:rub},
  {title:'KPI',dataIndex:'kpi_total',render:rub},
  {title:'KPI/2,5',dataIndex:'kpi_divided_total',render:rub},
  {title:'CR Start',dataIndex:'cr_start_fixed_total',render:rub},
  {title:'Кол-во часов переработки',dataIndex:'support_hours'},
  {title:'Итого',dataIndex:'total_bonus',render:v=><b>{rub(v)}</b>},
  {title:'',render:(_,r)=><Button onClick={()=>setId(r.id)}>Детализация</Button>}
 ]

 type Item = CalculationDetail['items'][number]

 const groups=[
  ['tech_integration','Технические интеграции'],
  ['implementation','Внедрение'],
  ['cr_start_fixed','CR Start фиксированный'],
  ['cr_start_implementation','CR Start как внедрение'],
  ['current_client','Текущие клиенты'],
  ['support_hours','Часы по задачам текущих клиентов'],
  ['training','Обучение'],
  ['sale','Продажи']
 ] as const

 const baseValue=(item:Item)=>{
  if(item.bonus_type==='current_client')return `${num(item.base_amount)} машин`
  if(item.bonus_type==='support_hours')return `${num(item.quantity)} ч`
  if(item.bonus_type==='training')return `${num(item.quantity)} шт.`
  return rub(item.base_amount)
 }

 const rateValue=(item:Item)=>{
  if(item.bonus_type==='current_client')return rub(item.rate)
  if(item.bonus_type==='support_hours')return `${rub(item.rate)}/ч`
  if(item.bonus_type==='training')return rub(item.rate)
  return `${num(Number(item.rate)*100)}%`
 }

 const sourceValue=(item:Item)=>{
  if(item.deal_title)return item.deal_title
  if(item.description)return item.description
  return '—'
 }

 const itemColumns:ColumnsType<Item>=[
  {title:'Сделка / источник',render:(_,item)=><div><div>{sourceValue(item)}</div>{(item.deal_bitrix_id??item.source_external_id)&&<Text type="secondary">ID {item.deal_bitrix_id??item.source_external_id}</Text>}</div>},
  {title:'Месяц',render:(_,item)=>{try{const json=JSON.parse(item.details_json||'{}');const month=json.bonus_month_number;return month?`${month}-й месяц`:'—'}catch{return '—'}},align:'center'},
  {title:'База',render:(_,item)=>baseValue(item),align:'right'},
  {title:'Ставка',render:(_,item)=>rateValue(item),align:'right'},
  {title:'Начислено',dataIndex:'amount_before_divider',render:rub,align:'right'},
  {title:'Делится на 2,5',dataIndex:'divider_applied',render:(v:boolean)=>v?'Да':'Нет',align:'center'},
  {title:'К выплате',dataIndex:'amount_final',render:(v:string)=><b>{rub(v)}</b>,align:'right'}
 ]

 const renderDetail=()=>{
  if(!detail.data)return null
  const data=detail.data

  const totalBy=(type:string)=>data.items.filter(item=>item.bonus_type===type).reduce((sum,item)=>sum+Number(item.amount_before_divider||0),0)
  const hoursBy=(type:string)=>data.items.filter(item=>item.bonus_type===type).reduce((sum,item)=>sum+Number(item.quantity||0),0)
  const sectionRows=(type:string, labelFactory?:(item:Item)=>string)=>{
    const items=data.items.filter(item=>item.bonus_type===type)
    return items.map(item=>({
      label: labelFactory?labelFactory(item):sourceValue(item),
      value: rub(item.amount_before_divider)
    }))
  }

  const summarySections=[
   {label:'Интеграции', total:totalBy('tech_integration'), rows:sectionRows('tech_integration',item=>sourceValue(item))},
   {label:'Внедрение', total:totalBy('implementation'), rows:sectionRows('implementation',item=>sourceValue(item))},
   {label:'CR Start как внедрение', total:totalBy('cr_start_implementation'), rows:sectionRows('cr_start_implementation',item=>sourceValue(item))},
   {label:'Обучения', total:totalBy('training'), rows:sectionRows('training',item=>item.description||sourceValue(item))},
   {label:'Оплата за часы', total:totalBy('support_hours'), rows:[]},
   {label:'Переработка', total:hoursBy('support_hours'), rows:[], suffix:' ч'},
   {label:'CR Start', total:totalBy('cr_start_fixed'), rows:sectionRows('cr_start_fixed',item=>sourceValue(item))},
   {label:'Текущие', total:totalBy('current_client'), rows:[]}
  ]

  return <>
   <Card size="small" title="Общая информация" style={{marginBottom:20}}>
    <Space direction="vertical" size={12} style={{width:'100%'}}>
     {summarySections.map(section=>{
      if(section.rows.length===0 && section.total===0 && section.label!=='Переработка' && section.label!=='Оплата за часы' && section.label!=='Текущие') return null
      return <div key={section.label}>
       <Text strong>{section.label} — {section.label==='Переработка'?`${num(section.total)}${section.suffix ?? ''}`:rub(section.total)}</Text>
       {section.rows.length>0&&<div style={{marginTop:8, paddingLeft:16}}>
        {section.rows.map(row=><div key={`${section.label}-${row.label}`} style={{display:'flex',justifyContent:'space-between',gap:12,marginBottom:4}}><span>{row.label}</span><span>{row.value}</span></div>)}
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
   <Title level={2}>Расчет премий</Title>
   <Space>
    <Month value={month} onChange={setMonth}/>
    <Button type="primary" loading={run.isPending} onClick={()=>run.mutate()}>Пересчитать</Button>
    <Button icon={<DownloadOutlined/>} href={excelUrl(month)}>Excel</Button>
   </Space>
  </Row>
  <Alert type="info" showIcon message="Каждый перерасчет создает новую версию; история не перезаписывается."/>

  <Card>
   <Table
    rowKey="id"
    columns={cols}
    dataSource={q.data??[]}
    loading={q.isLoading}
    scroll={{x:1100}}
   />
  </Card>

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

function Deals(){
 const q=useQuery({queryKey:['deals'],queryFn:getDepartmentDeals})
 const cols:ColumnsType<Deal>=[{title:'ID',dataIndex:'bitrix_id'},{title:'Сделка',dataIndex:'title'},{title:'Воронка',dataIndex:'funnel',render:funnel},{title:'Оплата/мес.',dataIndex:'monthly_amount',render:rub},{title:'Машин',dataIndex:'machines_count'},{title:'1С',dataIndex:'integration_1c',render:v=>v?<Tag color="green">Да</Tag>:<Tag>Нет</Tag>}]
 return <Space direction="vertical" size={24} style={{width:'100%'}}><Title level={2}>Сделки</Title><Card><Table rowKey="id" columns={cols} dataSource={q.data??[]} loading={q.isLoading} pagination={{pageSize:25}}/></Card></Space>
}

function Diagnostics(){
 const [month,setMonth]=useState(monthNow());const qc=useQueryClient()
 const q=useQuery({queryKey:['issues',month],queryFn:()=>getDiagnostics(month)})
 const run=useMutation({mutationFn:()=>runDiagnostics(month),onSuccess:()=>void qc.invalidateQueries({queryKey:['issues',month]})})
 const cols:ColumnsType<Issue>=[{title:'Уровень',dataIndex:'severity',render:v=><Tag color={v==='critical'?'red':'orange'}>{v}</Tag>},{title:'Код',dataIndex:'code'},{title:'Причина',dataIndex:'message'},{title:'Сделка',dataIndex:'deal_id',ellipsis:true}]
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
 return <Space direction="vertical" size={24} style={{width:'100%'}}><Title level={2}>Синхронизация</Title><Card><Space direction="vertical"><Text>Последняя успешная: {status.data?.last_success??'—'}</Text><Space><Button type="primary" icon={<CloudSyncOutlined/>} onClick={()=>start.mutate(false)}>Инкрементальная</Button><Button icon={<ReloadOutlined/>} onClick={()=>start.mutate(true)}>Полная</Button></Space></Space></Card>{job.data&&<Card title={`Job ${job.data.job_id}`}><Progress percent={job.data.progress}/><Text>{job.data.status}; обработано {job.data.processed}</Text>{job.data.error&&<Alert type="error" message={job.data.error}/>}</Card>}</Space>
}

export default function App(){
 const [page,setPage]=useState('dashboard')
 const content=useMemo(()=>({dashboard:<Dashboard/>,kpi:<KPI/>,bonus:<Bonuses/>,deals:<Deals/>,diagnostics:<Diagnostics/>,rules:<Rules/>,settings:<SettingsPage/>,sync:<Sync/>}[page]??<Dashboard/>),[page])
 return <Layout className="app-layout">
  <Sider breakpoint="lg" collapsedWidth={0} width={240} className="app-sider">
   <div className="app-logo"><div className="logo-mark">CR</div><div><div className="logo-title">CR Portal</div><div className="logo-subtitle">KPI & Bonus</div></div></div>
   <Menu theme="dark" mode="inline" selectedKeys={[page]} onClick={({key})=>setPage(key)} items={[
    {key:'dashboard',icon:<DashboardOutlined/>,label:'Главная'},{key:'kpi',icon:<TrophyOutlined/>,label:'KPI отдела'},
    {key:'bonus',icon:<FundOutlined/>,label:'Расчет премий'},{key:'deals',icon:<DatabaseOutlined/>,label:'Сделки'},
    {key:'diagnostics',icon:<ExclamationCircleOutlined/>,label:'Диагностика'},{key:'rules',icon:<SettingOutlined/>,label:'Правила'},
    {key:'settings',icon:<SettingOutlined/>,label:'\u041d\u0430\u0441\u0442\u0440\u043e\u0439\u043a\u0438'},
    {key:'sync',icon:<CloudSyncOutlined/>,label:'Синхронизация'}
   ]}/>
  </Sider>
  <Layout><Header className="app-header"><Text strong>CR Integration Portal</Text><Tag color="green" icon={<CheckCircleOutlined/>}>Bitrix24 подключён</Tag></Header><Content className="app-content"><div className="content-container">{content}</div></Content></Layout>
 </Layout>
}


