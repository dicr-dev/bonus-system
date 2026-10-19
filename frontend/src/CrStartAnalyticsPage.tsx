import {Alert,Button,Card,Collapse,Descriptions,Drawer,Input,Select,Space,Table as AntTable,Tabs,Tag,Typography} from 'antd'
import type {TableProps} from 'antd'
import type {ColumnsType} from 'antd/es/table'
import {useQuery} from '@tanstack/react-query'
import {createContext,useContext,useState} from 'react'
import type {ReactNode} from 'react'
import {api} from './api'
import {BitrixLink,dealUrl,taskUrl} from './BitrixLink'
import {partitionEmployeeRows} from './crStartEmployeeVisibility'
import type {EmployeeVisibility} from './crStartEmployeeVisibility'
import {withColumnHelp} from './CrStartColumnHeaders'
import './crStartAnalytics.css'

const StickyOffset=createContext(48)
const InsideCollapsedEmployees=createContext(false)
function Table<T extends object>(props:TableProps<T>){
 const offsetHeader=useContext(StickyOffset)
 return <AntTable<T> sticky={{offsetHeader}} {...props} columns={withColumnHelp(props.columns)}/>
}
function EmployeeSections<T>({rows,employees,employeeId,employeeName,renderRows}:{
 rows:T[];employees:EmployeeVisibility[];employeeId:(row:T)=>string;
 employeeName?:(row:T)=>string;renderRows:(rows:T[])=>ReactNode
}){
 const alreadyExpanded=useContext(InsideCollapsedEmployees)
 const {visible,collapsed}=partitionEmployeeRows(rows,employees,employeeId,employeeName)
 if(alreadyExpanded)return <>{renderRows(rows)}</>
 return <Space direction="vertical" size={16} style={{width:'100%'}}>
  {renderRows(visible)}
  {collapsed.length>0&&<Collapse items={[{key:'collapsed-employees',label:`Неактивные и дополнительные сотрудники — строки: ${collapsed.length}`,
   children:<InsideCollapsedEmployees.Provider value>{renderRows(collapsed)}</InsideCollapsedEmployees.Provider>}]}/>}
 </Space>
}

type Metrics=Record<string,unknown>&{deals_count:number;companies_count:number;amount:string;commercial_count:number;ever_commercial_count:number;working_count:number;lost_before_count:number;lost_after_count:number;conversion:number|null;incomplete_history_count:number}
type Manager=Metrics&{id:string;name:string;active:boolean|null;modules:(Metrics&{module:string})[];deal_ids:string[]}
type Entry={id:number;author_id:string;author:string;at:string;seconds:number;hours:number;phase:string}
type Task={task_id:number;title:string;status:number|null;deadline:string|null;overdue:boolean;hours:number|null;entries:Entry[]}
type Deal={id:string;bitrix_id:number;title:string;company:string|null;module:string;owner_id:string;owner_name:string;stage:string;group:string;amount:string;created_at:string|null;first_commercial_at:string|null;loss_at:string|null;launch_days:number|null;usage_days:number|null;usage_months:number|null;current_period_days:number|null;reconnections:number|null;age_days:number|null;stage_days:number|null;hours:number|null;overdue_tasks:number;history_reliable:boolean;warnings:string[];periods:{start:string;end:string|null;reason:string|null;days:number|null}[];history:{at:string;stage:string}[];tasks:Task[];effort:{author_id:string;author:string;hours:number;before:number;commercial:number;break:number;unknown:number}[]}
type Report={as_of:string;managers:Manager[];deals:Deal[];totals:Metrics;modules:(Metrics&{module:string})[];monthly:{month:string;created:number;first_launch:number;lost_before:number;departures:number;reconnections:number}[];cohorts:(Metrics&{month:string})[];losses:{owner_id:string;owner_name:string;module:string;reason:string;after_commercial:boolean;count:number;amount:string}[];issues:{task_id:number;title:string;reason:string}[];warnings:string[]}
const modules=['Логистика','Топливный модуль','Эксплуатация']
const groups:Record<string,string>={working:'В работе',commercial:'Коммерческое использование',lost:'Отвал'}
const phases:Record<string,string>={before:'До первого запуска',commercial:'Использование',break:'Перерыв',unknown:'Этап неизвестен'}
const num=(value:unknown)=>value==null?'—':new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2}).format(Number(value))
const money=(value:unknown)=>value==null?'—':new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB',maximumFractionDigits:2}).format(Number(value))
const date=(value:string|null)=>value?new Intl.DateTimeFormat('ru-RU',{timeZone:'Europe/Moscow',dateStyle:'short',timeStyle:'short'}).format(new Date(value)):'—'
function numeric<T extends Record<string,unknown>>(key:string,title:string,render:(value:unknown)=>string=num):ColumnsType<T>[number]{
 return {title,dataIndex:key,align:'right',sorter:(a,b)=>Number(a[key]??-1)-Number(b[key]??-1),render}
}
function metricColumns<T extends Metrics>():ColumnsType<T>{return [
 numeric('deals_count','Всего сделок'),numeric('companies_count','Компаний с ID'),numeric('amount','Сумма',money),
 numeric('working_count','В работе'),numeric('working_amount','Сумма в работе',money),
 numeric('commercial_count','Пользуются сейчас'),numeric('commercial_amount','Сумма активных коммерческих',money),
 numeric('ever_commercial_count','Когда-либо запущены'),numeric('ever_commercial_amount','Сумма запущенных',money),
 numeric('lost_before_count','Отвал до запуска'),numeric('lost_before_amount','Сумма отказов до запуска',money),
 numeric('lost_after_count','Отвал после запуска'),numeric('lost_after_amount','Сумма отказов после запуска',money),
 numeric('conversion','Конверсия, %'),numeric('resolved_conversion','Конверсия среди результатов, %'),
 numeric('average_commercial_amount','Средняя сумма запуска',money),
 numeric('launch_mean_days','Среднее до запуска, дни'),numeric('launch_median_days','Медиана до запуска, дни'),numeric('launch_sample','Выборка запуска'),
 numeric('lost_usage_mean_days','Средний срок ушедших, дни'),numeric('lost_usage_median_days','Медиана ушедших, дни'),numeric('lost_usage_sample','Выборка ушедших'),
 numeric('active_usage_mean_days','Средний срок активных, дни'),numeric('active_usage_median_days','Медиана активных, дни'),numeric('active_usage_sample','Выборка активных'),
 ...([1,3,6] as const).flatMap(month=>[numeric<T>(`retention_${month}`,`Удержание ${month} мес., %`),numeric<T>(`retention_${month}_sample`,`Выборка ${month} мес.`),numeric<T>(`early_loss_${month}_count`,`Ранний отвал < ${month} мес.`)]),
 numeric('reconnections','Возвращений'),numeric('hours','Часы всех авторов по портфелю'),numeric('lost_before_hours','Часы отказов до запуска'),numeric('overdue_tasks','Просроченных задач'),numeric('incomplete_history_count','Замечаний к истории'),
]}
function laborColumns<T extends Metrics>():ColumnsType<T>{return [
 {title:'Сотрудник — автор списаний',dataIndex:'name',fixed:'left',width:240},
 numeric('author_hours','Личные часы'),numeric('before_hours','До запуска'),numeric('commercial_hours','Во время использования'),
 numeric('break_hours','В перерывах'),numeric('unknown_hours','Этап неизвестен'),numeric('lost_before_author_hours','Личные часы по отказам до запуска'),
 numeric('launch_effort_mean_hours','Средние личные часы до запуска'),numeric('launch_effort_sample','Сделок в выборке'),
]}

function DealDetails({deal,employees}:{deal:Deal;employees:EmployeeVisibility[]}){
 const taskColumns:ColumnsType<Task>=[
  {title:'Задача',dataIndex:'title',render:(v,r)=><BitrixLink href={taskUrl(r.task_id)}>{v}</BitrixLink>},
  {title:'Статус Bitrix',dataIndex:'status'}, {title:'Крайний срок',dataIndex:'deadline',render:date},
  {title:'Просрочена',dataIndex:'overdue',render:v=>v?<Tag color="error">Да</Tag>:'Нет'},
  {title:'Часы',dataIndex:'hours',render:num},
 ]
 return <Space direction="vertical" size={18} style={{width:'100%'}}>
  {deal.warnings.map(w=><Alert key={w} type="warning" showIcon message={w}/>)}
  <Descriptions bordered size="small" column={2} items={[
   {key:'company',label:'Компания',children:deal.company??'Нет данных'}, {key:'module',label:'Модуль',children:deal.module},
   {key:'owner',label:'Текущий ответственный',children:deal.owner_name},{key:'stage',label:'Стадия',children:deal.stage},
   {key:'created',label:'Создана',children:date(deal.created_at)}, {key:'first',label:'Первое использование',children:date(deal.first_commercial_at)},
   {key:'loss',label:'Последний отказ',children:date(deal.loss_at)}, {key:'usage',label:'Срок без перерывов',children:`${num(deal.usage_days)} дней / ${num(deal.usage_months)} усл. мес.`},
   {key:'current',label:'Текущий период',children:`${num(deal.current_period_days)} дней`}, {key:'returns',label:'Возвращений',children:num(deal.reconnections)},
  ]}/>
  <Card size="small" title="Периоды использования"><Typography.Paragraph type="secondary">{deal.history_reliable?'История согласуется с карточкой.':'Неполная или противоречивая история: ниже только известные границы, итоговый срок не рассчитывается.'}</Typography.Paragraph><Table rowKey={(_,i)=>String(i)} size="small" dataSource={deal.periods} pagination={false} columns={[{title:'Начало',dataIndex:'start',render:date},{title:'Конец',dataIndex:'end',render:v=>v?date(v):'Открытая граница'},{title:'Известная длительность, дни',dataIndex:'days',render:num},{title:'Причина',dataIndex:'reason'}]}/></Card>
  <Card size="small" title="Фактические часы по авторам"><EmployeeSections rows={deal.effort} employees={employees} employeeId={r=>r.author_id} employeeName={r=>r.author} renderRows={rows=><Table rowKey="author_id" dataSource={rows} pagination={false} size="small" columns={[{title:'Автор',dataIndex:'author'},{title:'Всего',dataIndex:'hours',render:num},{title:'До запуска',dataIndex:'before',render:num},{title:'Использование',dataIndex:'commercial',render:num},{title:'Перерывы',dataIndex:'break',render:num},{title:'Этап неизвестен',dataIndex:'unknown',render:num}]}/>}/></Card>
  <Card size="small" title="Задачи и списания"><Table rowKey="task_id" size="small" columns={taskColumns} dataSource={deal.tasks} pagination={{pageSize:10}} expandable={{rowExpandable:t=>t.entries.length>0,expandedRowRender:t=><EmployeeSections rows={t.entries} employees={employees} employeeId={r=>r.author_id} employeeName={r=>r.author} renderRows={rows=><Table rowKey="id" size="small" pagination={false} dataSource={rows} columns={[{title:'Автор',dataIndex:'author'},{title:'Дата МСК',dataIndex:'at',render:date},{title:'Часы',dataIndex:'hours',render:num},{title:'Этап',dataIndex:'phase',render:v=>phases[v]??v}]}/>}/>}}/></Card>
  <Card size="small" title="История стадий"><Table rowKey={(_,i)=>String(i)} size="small" dataSource={deal.history} columns={[{title:'Дата МСК',dataIndex:'at',render:date},{title:'Стадия',dataIndex:'stage'}]} pagination={{pageSize:15}}/></Card>
 </Space>
}

export default function CrStartAnalyticsPage(){
 const [employee,setEmployee]=useState<string>()
 const [module,setModule]=useState<string>()
 const [search,setSearch]=useState('')
 const [group,setGroup]=useState<string>()
 const [selected,setSelected]=useState<Deal>()
 // The unfiltered list keeps employee choices stable after selecting a manager.
 const directory=useQuery({queryKey:['cr-start-analytics-directory'],queryFn:async()=>(await api.get<Report>('/analytics/cr-start')).data,staleTime:60000})
 const report=useQuery({queryKey:['cr-start-analytics',employee,module],queryFn:async()=>(await api.get<Report>('/analytics/cr-start',{params:{employee_id:employee,module}})).data,enabled:!!employee||!!module})
 const active=employee||module?report:directory
 const data=active.data
 const employeeDirectory=directory.data?.managers??data?.managers??[]
 const employeeGroups=partitionEmployeeRows(directory.data?.managers??[],directory.data?.managers??[],m=>m.id)
 const params=new URLSearchParams()
 if(employee)params.set('employee_id',employee)
 if(module)params.set('module',module)
 const deals=(data?.deals??[]).filter(d=>(!group||d.group===group)&&`${d.title} ${d.company??''} ${d.bitrix_id} ${d.owner_name}`.toLocaleLowerCase('ru').includes(search.toLocaleLowerCase('ru')))
 const dealColumns:ColumnsType<Deal>=[
  {title:'Сделка',dataIndex:'title',fixed:'left',width:250,render:(v,d)=><BitrixLink href={dealUrl(d.bitrix_id)}>{v}</BitrixLink>},
  {title:'Компания',dataIndex:'company',width:200},{title:'Модуль',dataIndex:'module',width:160},
  {title:'Ответственный',dataIndex:'owner_name',width:220},{title:'Стадия',dataIndex:'stage',width:220},
  {title:'Сумма',dataIndex:'amount',render:money,sorter:(a,b)=>Number(a.amount)-Number(b.amount)},
  {title:'Первый запуск',dataIndex:'first_commercial_at',render:date},
  {title:'Срок использования, дни',dataIndex:'usage_days',render:num,sorter:(a,b)=>(a.usage_days??-1)-(b.usage_days??-1)},
  {title:'Усл. месяцев',dataIndex:'usage_months',render:num},
  {title:'Дней на стадии',dataIndex:'stage_days',render:num,sorter:(a,b)=>(a.stage_days??-1)-(b.stage_days??-1)},
  {title:'Возраст, дни',dataIndex:'age_days',render:num,sorter:(a,b)=>(a.age_days??-1)-(b.age_days??-1)},
  {title:'Часы всех авторов',dataIndex:'hours',render:num,sorter:(a,b)=>(a.hours??-1)-(b.hours??-1)},
  {title:'Просроченных задач',dataIndex:'overdue_tasks'},
  {title:'История',render:(_,d)=>d.warnings.length?<Tag color="warning">Есть замечания</Tag>:<Tag>Без замечаний</Tag>},
  {title:'',fixed:'right',width:110,render:(_,d)=><Button size="small" onClick={()=>setSelected(d)}>Подробнее</Button>},
 ]
 const renderDealRows=(items:Deal[])=><Table rowKey="id" size="small" dataSource={items} columns={dealColumns} scroll={{x:2400}} pagination={{defaultPageSize:20,showSizeChanger:true,pageSizeOptions:[20,50,100]}}/>
 const dealTable=(items:Deal[])=><EmployeeSections rows={items} employees={employeeDirectory} employeeId={d=>d.owner_id} employeeName={d=>d.owner_name} renderRows={renderDealRows}/>
 const managerColumns:ColumnsType<Manager>=[{title:'Менеджер (текущий портфель)',dataIndex:'name',fixed:'left',width:250,sorter:(a,b)=>a.name.localeCompare(b.name,'ru'),render:(v,r)=><>{v}{r.active===false&&<Tag>Неактивен</Tag>}</>},...metricColumns<Manager>(),numeric('author_hours','Личные часы автора')]
 const stageRows=Object.values((data?.deals??[]).filter(d=>d.group==='working').reduce<Record<string,{stage:string;count:number;amount:number;days:number[];unknown:number}>>((result,d)=>{const r=result[d.stage]??={stage:d.stage,count:0,amount:0,days:[],unknown:0};r.count++;r.amount+=Number(d.amount);if(d.stage_days==null)r.unknown++;else r.days.push(d.stage_days);return result},{})).map(r=>({...r,mean:r.days.length?r.days.reduce((a,b)=>a+b,0)/r.days.length:null,max:r.days.length?Math.max(...r.days):null}))
 return <Space className="cr-start-analytics" direction="vertical" size={20} style={{width:'100%'}}>
  <Typography.Title level={2}>CR Start — аналитика по менеджерам</Typography.Title>
  <Card><Space wrap><Typography.Text>За весь период</Typography.Text><Select allowClear showSearch optionFilterProp="label" placeholder="Текущий ответственный" value={employee} onChange={setEmployee} style={{width:280}} options={[{label:"Основной список",options:employeeGroups.visible.map(m=>({value:m.id,label:m.name}))},{label:"Неактивные и дополнительные",options:employeeGroups.collapsed.map(m=>({value:m.id,label:m.name}))}]}/><Select allowClear placeholder="Все модули" value={module} onChange={setModule} style={{width:210}} options={modules.map(value=>({value,label:value}))}/><Button onClick={()=>active.refetch()} loading={active.isFetching}>Обновить</Button><Button href={`/api/v1/analytics/cr-start/export?${params}`} disabled={!data}>Выгрузить в Excel</Button></Space><Typography.Paragraph type="secondary" style={{marginTop:12,marginBottom:0}}>Срез: {data?date(data.as_of):'—'} (МСК). Фильтры выше применяются к отчёту и Excel. Поиск в списке сделок — только к детализации.</Typography.Paragraph></Card>
  {active.isError&&<Alert type="error" showIcon message="Не удалось загрузить аналитику" description="Повторите запрос. Данные берутся из локальной базы, синхронизация автоматически не запускается."/>}
  {data&&<>
   {data.totals.incomplete_history_count>0&&<Alert type="warning" showIcon message={`Есть замечания к истории ${data.totals.incomplete_history_count} сделок`} description="Для таких сделок итоговый срок использования и удержание не оцениваются. Подробности — на вкладке «Качество данных» и в карточке сделки."/>}
   <Card title="Итого"><Descriptions column={4} items={[{key:'all',label:'Всего сделок',children:num(data.totals.deals_count)},{key:'work',label:'В работе',children:num(data.totals.working_count)},{key:'active',label:'Пользуются сейчас',children:num(data.totals.commercial_count)},{key:'ever',label:'Когда-либо запущены',children:num(data.totals.ever_commercial_count)},{key:'before',label:'Отвал до запуска',children:num(data.totals.lost_before_count)},{key:'after',label:'Отвал после запуска',children:num(data.totals.lost_after_count)},{key:'conversion',label:'Конверсия',children:`${num(data.totals.conversion)} %`},{key:'history',label:'Замечания к истории',children:num(data.totals.incomplete_history_count)}]}/></Card>
   <Tabs items={[
    {key:'managers',label:'Менеджеры',children:<><Typography.Paragraph type="secondary">Конверсия = когда-либо запущены / все сделки. Среди результатов = запущены / (запущены + отвал до запуска). Авторские часы могут принадлежать сотруднику без текущих сделок. Нажмите заголовок для сортировки.</Typography.Paragraph><EmployeeSections rows={data.managers} employees={employeeDirectory} employeeId={m=>m.id} renderRows={managerRows=><Table rowKey="id" columns={managerColumns} dataSource={managerRows} loading={active.isFetching} scroll={{x:6500}} pagination={false} expandable={{expandedRowRender:m=><Space direction="vertical" style={{width:'100%'}}><Table rowKey="module" dataSource={m.modules} columns={[{title:'Модуль',dataIndex:'module',fixed:'left',width:180},...metricColumns<Metrics&{module:string}>(),numeric<Metrics&{module:string}>('author_hours','Личные часы')]} pagination={false} size="small" scroll={{x:6000}}/>{dealTable(data.deals.filter(d=>m.deal_ids.includes(d.id)))}</Space>}}/>}/></>},
    {key:'modules',label:'Модули',children:<Table rowKey="module" dataSource={data.modules} columns={[{title:'Модуль',dataIndex:'module',fixed:'left',width:180},...metricColumns<Metrics&{module:string}>()]} pagination={false} scroll={{x:6000}}/>},
    {key:'labor',label:'Трудозатраты',children:<><Alert type="info" showIcon message="Часы не передаются новому менеджеру вместе со сделкой" description="Здесь только личные списания автора. Средние часы до запуска — по сделкам с известной датой первого запуска и личными списаниями до неё; размер выборки указан отдельно."/><EmployeeSections rows={data.managers} employees={employeeDirectory} employeeId={m=>m.id} renderRows={managerRows=><Table rowKey="id" columns={laborColumns<Manager>()} dataSource={managerRows} pagination={false} scroll={{x:1400}} expandable={{expandedRowRender:m=><Table rowKey="module" dataSource={m.modules} columns={[{title:'Модуль',dataIndex:'module'},...laborColumns<Metrics&{module:string}>().slice(1)]} pagination={false} size="small" scroll={{x:1300}}/>}}/>}/></>},
    {key:'portfolio',label:'Текущая работа',children:<><Typography.Paragraph type="secondary">Только сделки «В работе». Сроки фактические; нормативы зависания не заданы. Дата изменения карточки не заменяет вход на стадию.</Typography.Paragraph><Table rowKey="stage" dataSource={stageRows} pagination={false} columns={[{title:'Стадия',dataIndex:'stage'},{title:'Сделок',dataIndex:'count'},{title:'Сумма',dataIndex:'amount',render:money},{title:'Среднее на стадии, дни',dataIndex:'mean',render:num},{title:'Максимум на стадии, дни',dataIndex:'max',render:num},{title:'Нет даты входа',dataIndex:'unknown'}]}/>{dealTable(data.deals.filter(d=>d.group==='working'))}</>},
    {key:'dynamics',label:'Динамика и когорты',children:<Space direction="vertical" style={{width:'100%'}}><Typography.Paragraph type="secondary">Динамика — события по месяцам. Отказы и возвращения учитываются только при согласованной истории. Когорты — текущий результат сделок, созданных в одном месяце; свежие когорты ещё не завершили внедрение.</Typography.Paragraph><Table rowKey="month" dataSource={data.monthly} pagination={{pageSize:12}} columns={[{title:'Месяц',dataIndex:'month'},{title:'Создано',dataIndex:'created'},{title:'Первые запуски',dataIndex:'first_launch'},{title:'Отказы до запуска',dataIndex:'lost_before'},{title:'Отказы после запуска',dataIndex:'departures'},{title:'Возвращения',dataIndex:'reconnections'}]}/><Table rowKey="month" dataSource={data.cohorts} columns={[{title:'Месяц создания',dataIndex:'month',fixed:'left',width:150},...metricColumns<Metrics&{month:string}>()]} pagination={{pageSize:12}} scroll={{x:6000}}/></Space>},
    {key:'losses',label:'Отказы',children:<EmployeeSections rows={data.losses} employees={employeeDirectory} employeeId={r=>r.owner_id} employeeName={r=>r.owner_name} renderRows={lossRows=><Table rowKey={r=>`${r.owner_id}:${r.module}:${r.reason}:${r.after_commercial}`} dataSource={lossRows} columns={[{title:'Менеджер',dataIndex:'owner_name'},{title:'Модуль',dataIndex:'module'},{title:'Причина',dataIndex:'reason'},{title:'Когда',dataIndex:'after_commercial',render:v=>v?'После запуска':'До запуска'},{title:'Сделок',dataIndex:'count',sorter:(a,b)=>a.count-b.count},{title:'Сумма',dataIndex:'amount',render:money}]} pagination={{pageSize:20}}/>}/>},
    {key:'deals',label:`Сделки (${data.deals.length})`,children:<Space direction="vertical" style={{width:'100%'}}><Space wrap><Input.Search allowClear placeholder="Поиск в детализации (сводка не меняется)" value={search} onChange={e=>setSearch(e.target.value)} style={{width:390}}/><Select allowClear placeholder="Все группы стадий" value={group} onChange={setGroup} style={{width:260}} options={Object.entries(groups).map(([value,label])=>({value,label}))}/></Space>{dealTable(deals)}</Space>},
    {key:'quality',label:`Качество данных (${data.issues.length+data.totals.incomplete_history_count})`,children:<Space direction="vertical" style={{width:'100%'}}>{data.warnings.map(w=><Alert key={w} type="info" showIcon message={w}/>)}<Alert type="warning" showIcon message="Без полной истории итоговый срок и удержание не рассчитываются; отсутствие списаний показывается прочерком"/><Table rowKey="task_id" dataSource={data.issues} pagination={{pageSize:20}} columns={[{title:'Задача',dataIndex:'title',render:(v,r)=><BitrixLink href={taskUrl(r.task_id)}>{v}</BitrixLink>},{title:'Проблема',dataIndex:'reason'}]}/>{dealTable(data.deals.filter(d=>d.warnings.length>0))}</Space>},
   ]}/>
  </>}
  <Drawer title={selected?<BitrixLink href={dealUrl(selected.bitrix_id)}>{selected.title}</BitrixLink>:''} open={!!selected} onClose={()=>setSelected(undefined)} width="min(1200px, 95vw)">{selected&&<StickyOffset.Provider value={0}><DealDetails deal={selected} employees={employeeDirectory}/></StickyOffset.Provider>}</Drawer>
 </Space>
}
