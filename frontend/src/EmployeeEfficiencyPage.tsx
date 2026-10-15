import {DownloadOutlined} from '@ant-design/icons'
import {Alert,Button,Card,Col,Input,Row,Select,Space,Statistic,Table,Tabs,Tag,Tooltip,Typography} from 'antd'
import type {ColumnsType,ColumnType} from 'antd/es/table'
import {useQuery} from '@tanstack/react-query'
import {useState} from 'react'
import {employeeEfficiencyExcelUrl,getEmployeeEfficiency} from './api'
import {BitrixLink,dealUrl} from './BitrixLink'
import type {EfficiencyDeal,EfficiencyEmployee,EfficiencyFilters,EfficiencyFunnel,EfficiencyMetrics} from './efficiencyTypes'

const {Title,Text}=Typography
const funnelNames={tech_integration:'Техинтеграция',implementation:'Внедрение'}
const statusNames:Record<string,string>={in_progress:'В работе',won:'Успешно',lost:'Неуспешно',unknown:'Нет даты закрытия'}
const money=(value:string|number)=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2}).format(Number(value))+' ₽'
const displayDate=(value:string|null|undefined)=>value?new Intl.DateTimeFormat('ru-RU',{timeZone:'Europe/Moscow'}).format(new Date(value)):'—'
const moscowToday=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Moscow',year:'numeric',month:'2-digit',day:'2-digit'}).format(new Date())

function periodDates(value:string){
 const today=moscowToday()
 if(value==='all')return {from:'',to:''}
 if(value==='week'){
  const monday=new Date(today+'T12:00:00Z');monday.setUTCDate(monday.getUTCDate()-((monday.getUTCDay()+6)%7))
  return {from:monday.toISOString().slice(0,10),to:today}
 }
 if(value==='year')return {from:today.slice(0,4)+'-01-01',to:today}
 if(value==='previous_month'){
  const date=new Date(today.slice(0,7)+'-01T12:00:00Z');date.setUTCDate(0)
  return {from:date.toISOString().slice(0,7)+'-01',to:date.toISOString().slice(0,10)}
 }
 return {from:today.slice(0,7)+'-01',to:today}
}

function metricColumn(title:string,funnel:EfficiencyFunnel,key:keyof EfficiencyMetrics,format?:(value:number|string|null)=>string):ColumnType<EfficiencyEmployee>{
 return {title,dataIndex:['metrics',funnel,key],width:125,align:'right',
  sorter:(a,b)=>Number(a.metrics[funnel][key]??-1)-Number(b.metrics[funnel][key]??-1),
  render:value=>value==null?'—':format?format(value):value}
}

function employeeColumns(firstTitle='Сотрудник'):ColumnsType<EfficiencyEmployee>{
 return [
  {title:firstTitle,dataIndex:'name',fixed:'left',width:240,sorter:(a,b)=>a.name.localeCompare(b.name),render:(value,row)=><Space direction="vertical" size={0}><Text strong>{value}</Text>{row.department&&<Text type="secondary" style={{fontSize:12}}>{row.department}</Text>}{row.is_active===false&&<Tag>Неактивен</Tag>}</Space>},
  {title:'Техинтеграция',children:[metricColumn('Новые','tech_integration','new_count'),metricColumn('Были в работе','tech_integration','work_count'),metricColumn('Открыты на конец','tech_integration','active_end_count'),metricColumn('Успешно','tech_integration','won_count'),metricColumn('Неуспешно','tech_integration','lost_count'),metricColumn('Сумма успешных','tech_integration','won_amount',value=>money(value??0)),metricColumn('Срок с 1С, дни','tech_integration','avg_days_with_1c'),metricColumn('Срок без 1С, дни','tech_integration','avg_days_without_1c')]},
  {title:'Внедрение',children:[metricColumn('Новые','implementation','new_count'),metricColumn('Были в работе','implementation','work_count'),metricColumn('Открыты на конец','implementation','active_end_count'),metricColumn('Завершено','implementation','won_count'),metricColumn('Неуспешно','implementation','lost_count'),metricColumn('Сумма успешных','implementation','won_amount',value=>money(value??0)),metricColumn('Доля успешных, %','implementation','success_rate',value=>`${value}%`),metricColumn('Полный срок, дни','implementation','avg_completion_days')]},
  {title:'Обучения в периоде',children:[metricColumn('Первое','implementation','first_training_count'),metricColumn('Второе','implementation','second_training_count'),metricColumn('Отчётам','implementation','reports_training_count'),metricColumn('Всего','implementation','training_count'),metricColumn('Все пройдены к концу','implementation','fully_trained_count'),metricColumn('Создано Сопровождений','implementation','support_created_count')]},
 ]
}

function DealsTable({deals}:{deals:EfficiencyDeal[]}){
 const [search,setSearch]=useState('')
 const query=search.trim().toLocaleLowerCase('ru-RU')
 const rows=deals.filter(row=>!query||`${row.bitrix_id} ${row.title} ${row.employee_name} ${row.module_name}`.toLocaleLowerCase('ru-RU').includes(query))
 const columns:ColumnsType<EfficiencyDeal>=[
  {title:'Сотрудник',dataIndex:'employee_name',width:190,sorter:(a,b)=>a.employee_name.localeCompare(b.employee_name)},
  {title:'Сделка',dataIndex:'title',width:300,render:(value,row)=><BitrixLink href={dealUrl(row.bitrix_id)}>{row.bitrix_id} — {value}</BitrixLink>},
  {title:'Воронка',dataIndex:'funnel',width:150,filters:Object.entries(funnelNames).map(([value,text])=>({value,text})),onFilter:(value,row)=>row.funnel===value,render:value=>funnelNames[value as EfficiencyFunnel]},
  {title:'Модуль',dataIndex:'module_name',width:180,sorter:(a,b)=>a.module_name.localeCompare(b.module_name)},
  {title:'Интеграция 1С',dataIndex:'integration_1c',width:120,render:value=>value?'Да':'Нет'},
  {title:'События периода',width:260,render:(_,row)=><Space wrap>{row.new_in_period&&<Tag color="blue">Новая</Tag>}{row.won_in_period&&<Tag color="green">Завершена</Tag>}{row.lost_in_period&&<Tag color="red">Отказ</Tag>}{row.trainings_in_period.length>0&&<Tag>Обучений: {row.trainings_in_period.length}</Tag>}</Space>},
  {title:'На конец периода',dataIndex:'status_at_end',width:160,filters:Object.entries(statusNames).map(([value,text])=>({value,text})),onFilter:(value,row)=>row.status_at_end===value,render:value=>statusNames[value]??value},
  {title:'Текущая стадия',dataIndex:'current_stage_title',width:220,render:value=>value??'—'},
  {title:'Сумма',dataIndex:'amount',width:135,align:'right',sorter:(a,b)=>Number(a.amount)-Number(b.amount),render:money},
  {title:'Создана',dataIndex:'created_at',width:130,render:displayDate},
  {title:'Завершена на конец периода',dataIndex:'closed_at',width:165,render:displayDate},
  {title:'Полный срок, дни',dataIndex:'duration_days',width:130,sorter:(a,b)=>(a.duration_days??-1)-(b.duration_days??-1),render:value=>value??'—'},
  {title:'Дней на стадии к концу периода',dataIndex:'days_in_stage',width:170,render:value=>value??'Нет истории'},
  {title:'Причина отказа',dataIndex:'loss_reason',width:240,render:value=>value??'—'},
  {title:'Первое обучение',dataIndex:['training_dates','first'],width:150,render:displayDate},
  {title:'Второе обучение',dataIndex:['training_dates','second'],width:150,render:displayDate},
  {title:'Обучение отчётам',dataIndex:['training_dates','reports'],width:155,render:displayDate},
  {title:'Обучения к концу периода',width:165,render:(_,row)=>row.funnel==='implementation'?`${row.training_done} / ${row.training_target??'норматив не задан'}`:'—'},
  {title:'Новое Сопровождение',width:180,render:(_,row)=><Space direction="vertical">{row.supports_created_in_period.map(id=><BitrixLink key={id} href={dealUrl(id)}>#{id}</BitrixLink>)}</Space>},
 ]
 return <Space direction="vertical" style={{width:'100%'}}><Input.Search allowClear value={search} onChange={event=>setSearch(event.target.value)} placeholder="Найти сделку, сотрудника или модуль" style={{maxWidth:440}}/><Table rowKey="id" size="small" dataSource={rows} columns={columns} pagination={{pageSize:25,showSizeChanger:true,pageSizeOptions:[25,50,100]}} scroll={{x:3400}} expandable={{rowExpandable:row=>row.history.length>0,expandedRowRender:row=><Card size="small" title="История стадий за весь срок сделки"><Table rowKey={(item,index)=>`${item.at}-${index}`} size="small" pagination={{pageSize:10}} dataSource={row.history} columns={[{title:'Дата',dataIndex:'at',render:displayDate},{title:'Стадия',dataIndex:'stage'},{title:'Статус',dataIndex:'status',render:value=>statusNames[value]??value}]}/></Card>}}/></Space>
}

export default function EmployeeEfficiencyPage(){
 const initial=periodDates('month')
 const [period,setPeriod]=useState('month');const [dateFrom,setDateFrom]=useState(initial.from);const [dateTo,setDateTo]=useState(initial.to)
 const [employee,setEmployee]=useState<string>();const [module,setModule]=useState<string>();const [integration,setIntegration]=useState<string>()
 const filters:EfficiencyFilters={date_from:dateFrom||undefined,date_to:dateTo||undefined,employee_id:employee,module,integration_1c:integration===undefined?undefined:integration==='yes'}
 const valid=!dateFrom||dateFrom<=(dateTo||moscowToday())
 const report=useQuery({queryKey:['employee-efficiency',filters],queryFn:()=>getEmployeeEfficiency(filters),enabled:valid})
 const data=report.data
 const allDeals=data?.employees.flatMap(person=>person.deals)??[]
 const modules=data?.employees.flatMap(person=>person.modules.map(item=>({id:`${person.id}:${item.module_name}`,name:`${person.name} — ${item.module_name}`,department:null,is_active:person.is_active,metrics:item.metrics,deals:[],modules:[]})))??[]
 const selectPeriod=(value:string)=>{setPeriod(value);if(value==='custom')return;const dates=periodDates(value);setDateFrom(dates.from);setDateTo(dates.to)}
 return <Space direction="vertical" size={20} style={{width:'100%'}}>
  <Title level={2}>Эффективность сотрудников</Title>
  <Card><Space wrap>
   <Select value={period} onChange={selectPeriod} style={{width:200}} options={[{value:'week',label:'Текущая неделя'},{value:'month',label:'Текущий месяц'},{value:'previous_month',label:'Предыдущий месяц'},{value:'year',label:'Текущий год'},{value:'all',label:'За весь срок'},{value:'custom',label:'Произвольный период'}]}/>
   <span>С</span><Input aria-label="Начало периода" type="date" max={dateTo||moscowToday()} value={dateFrom} onChange={e=>{setPeriod('custom');setDateFrom(e.target.value)}} style={{width:160}}/>
   <span>По</span><Input aria-label="Конец периода" type="date" max={moscowToday()} value={dateTo} onChange={e=>{setPeriod('custom');setDateTo(e.target.value)}} style={{width:160}}/>
   <Select allowClear showSearch optionFilterProp="label" value={employee} onChange={setEmployee} placeholder="Все сотрудники" style={{width:260}} options={[...(data?.options.employees??[]).map(person=>({value:person.id,label:person.name})),{value:'unassigned',label:'Без ответственного'}]}/>
   <Select allowClear value={module} onChange={setModule} placeholder="Все модули" style={{width:230}} options={(data?.options.modules??[]).map(value=>({value,label:value}))}/>
   <Select allowClear value={integration} onChange={setIntegration} placeholder="С 1С и без 1С" style={{width:200}} options={[{value:'yes',label:'С интеграцией 1С'},{value:'no',label:'Без интеграции 1С'}]}/>
   <Button icon={<DownloadOutlined/>} disabled={!valid||!data} href={employeeEfficiencyExcelUrl(filters)}>Выгрузить в Excel</Button>
  </Space></Card>
  {!valid&&<Alert type="error" showIcon message="Дата начала не может быть позже даты окончания"/>}
  {report.isError&&<Alert type="error" showIcon message="Не удалось загрузить отчёт" description="Проверьте период и подключение к локальному приложению."/>}
  <Alert type="info" showIcon message="Фактические показатели по текущему ответственному за внедрение" description="Новые сделки учитываются по дате создания, завершения — по дате закрытия. Доля успешных — среди закрытий выбранного периода. Средний срок — весь срок успешной сделки. Логистика и Эксплуатация: 3 обучения; Топливный модуль и Загрузки: 1. Планы и оценочные баллы пока не применяются."/>
  {data?.warnings.map((warning,index)=><Alert key={index} type="warning" showIcon message={warning}/>)}
  <Row gutter={[16,16]}>
   <Col xs={24} md={6}><Card loading={report.isLoading}><Statistic title="Успешных техинтеграций" value={data?.summary.tech_integration.won_count??0}/></Card></Col>
   <Col xs={24} md={6}><Card loading={report.isLoading}><Statistic title="Завершённых внедрений" value={data?.summary.implementation.won_count??0}/></Card></Col>
   <Col xs={24} md={6}><Card loading={report.isLoading}><Statistic title="Обучений в периоде" value={data?.summary.implementation.training_count??0}/></Card></Col>
   <Col xs={24} md={6}><Card loading={report.isLoading}><Statistic title="Неуспешных закрытий" value={(data?.summary.tech_integration.lost_count??0)+(data?.summary.implementation.lost_count??0)}/></Card></Col>
  </Row>
  <Card><Tabs items={[
   {key:'employees',label:'По сотрудникам',children:<><Text type="secondary">Разверните сотрудника, чтобы увидеть его сделки. Сортировка доступна в заголовках.</Text><Table style={{marginTop:16}} rowKey="id" dataSource={data?.employees??[]} loading={report.isLoading} columns={employeeColumns()} scroll={{x:3100}} pagination={{pageSize:20,showSizeChanger:true}} expandable={{rowExpandable:person=>person.deals.length>0,expandedRowRender:person=><DealsTable deals={person.deals}/>}}/></>},
   {key:'modules',label:'По модулям',children:<Table rowKey="id" dataSource={modules} loading={report.isLoading} columns={employeeColumns('Сотрудник / модуль')} scroll={{x:3100}} pagination={{pageSize:25}}/>},
   {key:'losses',label:'Причины отказов',children:<Table rowKey={row=>`${row.funnel}:${row.reason}`} dataSource={data?.losses??[]} loading={report.isLoading} pagination={{pageSize:25}} columns={[{title:'Воронка',dataIndex:'funnel',render:value=>funnelNames[value as EfficiencyFunnel]},{title:'Причина',dataIndex:'reason'},{title:'Количество',dataIndex:'count',sorter:(a,b)=>a.count-b.count},{title:'Сумма',dataIndex:'amount',render:money,sorter:(a,b)=>Number(a.amount)-Number(b.amount)}]}/>},
   {key:'details',label:`Все сделки (${data?.total_deals??0})`,children:<DealsTable deals={allDeals}/>},
  ]}/></Card>
  {data&&<Tooltip title="Сделки относятся к сотрудникам по текущему ответственному, включая неактивных сотрудников. Состояние на конец периода использует историю стадий, если она загружена."><Text type="secondary">Период: {data.date_from?displayDate(data.date_from):'весь срок'} — {displayDate(data.date_to)}. С историей стадий: {data.history_deals} из {data.total_deals} сделок.</Text></Tooltip>}
 </Space>
}
