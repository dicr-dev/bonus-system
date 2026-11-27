import {useMemo,useState} from 'react'
import {useQuery} from '@tanstack/react-query'
import {QuestionCircleOutlined} from '@ant-design/icons'
import {Alert,Button,Card,Input,Modal,Radio,Select,Space,Table,Tooltip,Typography} from 'antd'
import type {ColumnsType} from 'antd/es/table'
import {api} from './api'
import {BitrixLink,dealUrl} from './BitrixLink'
import {startModules,otherModules,matchesModule} from './metricsModules'

type SpeedDeal={id:string;bitrix_id:number;title:string;employee_id:string;employee:string;module:string;funnel:string;start:string|null;end:string|null;days:number|null;reason:string;is_error:boolean;logistics_type:string|null;logistics_warning:string;links:{bitrix_id:number;title:string}[]}
type Report={employees:{id:string;name:string;hire_date:string|null}[];deals:SpeedDeal[]}
type Row={key:string;name:string;hireDate:string|null;deals:SpeedDeal[];children?:Row[]}
const label=(date:string|null,period:string)=>!date?'Дата не определена':period==='all'?'Весь период':period==='year'?date.slice(0,4):period==='quarter'?`${date.slice(0,4)} Q${Math.ceil(Number(date.slice(5,7))/3)}`:date.slice(0,7)
function prior(c:string,period:string,date:string|null){
 if(!date||period==='all'||c==='Дата не определена')return false
 const end=period==='month'?`${c}-31`:period==='quarter'?`${c.slice(0,4)}-${String(Number(c.slice(-1))*3).padStart(2,'0')}-31`:`${c}-12-31`
 return end<date
}
export default function ImplementationSpeed(){
 const [period,setPeriod]=useState('month'),[group,setGroup]=useState<'all'|'start'|'other'>('all')
 const [employee,setEmployee]=useState<string>(),[modules,setModules]=useState<string[]>([]),[from,setFrom]=useState(''),[to,setTo]=useState('')
 const [details,setDetails]=useState<{title:string;deals:SpeedDeal[]}|null>(null)
 const q=useQuery({queryKey:['implementation-speed'],queryFn:async()=>(await api.get<Report>('/analytics/implementation-speed')).data})
 const all=q.data?.deals??[],people=q.data?.employees??[],hire=new Map(people.map(p=>[p.id,p.hire_date]))
 const selected=all.filter(d=>(group==='all'||(group==='start'?d.funnel==='cr_start':d.funnel!=='cr_start'))&&(!employee||employee===d.employee_id)&&matchesModule(d,modules)&&(!from||!d.start||d.start>=from)&&(!to||!d.start||d.start<=to))
 const filtered=selected.filter(d=>!hire.get(d.employee_id)||!d.start||d.start>=hire.get(d.employee_id)!)
 const completed=filtered.filter(d=>d.days!==null),errors=filtered.filter(d=>d.is_error).length
 const average=completed.length?Math.round(completed.reduce((sum,d)=>sum+d.days!,0)/completed.length):null
 const {rows,cohorts,maxDays}=useMemo(()=>{
  const byUser=new Map<string,Row>(), dates=new Set(selected.map(d=>label(d.start,period)))
  for(const p of people)if(!employee||employee===p.id)byUser.set(p.id,{key:p.id,name:p.name,hireDate:p.hire_date,deals:[],children:[]})
  for(const d of filtered){
   let row=byUser.get(d.employee_id)
   if(!row){row={key:d.employee_id,name:d.employee,hireDate:hire.get(d.employee_id)??null,deals:[],children:[]};byUser.set(d.employee_id,row)}
   row.deals.push(d)
   const name=d.funnel==='cr_start'?'CR Start':'Другие'
   let section=row.children!.find(x=>x.name===name)
   if(!section){section={key:JSON.stringify([d.employee_id,name]),name,hireDate:row.hireDate,deals:[],children:[]};row.children!.push(section)}
   section.deals.push(d)
   let child=section.children!.find(x=>x.name===d.module)
   if(!child){child={key:JSON.stringify([d.employee_id,name,d.module]),name:d.module,hireDate:row.hireDate,deals:[]};section.children!.push(child)}
   child.deals.push(d)
  }
  return {rows:[...byUser.values()].sort((a,b)=>a.name.localeCompare(b.name,'ru')),cohorts:[...dates].sort((a,b)=>a==='Дата не определена'?-1:b==='Дата не определена'?1:a.localeCompare(b)),maxDays:Math.max(1,...filtered.map(d=>d.days??0))}
 },[filtered,selected,people,employee,period])
 const columns:ColumnsType<Row>=[{title:'Сотрудник / модуль',dataIndex:'name',fixed:'left',width:260},...cohorts.map((c,index)=>({key:c,title:period==='month'&&/^\d{4}-\d{2}$/.test(c)?<span>{c.slice(0,4)}<br/>{c.slice(5)}</span>:period==='quarter'&&/^\d{4} Q[1-4]$/.test(c)?<span>{c.slice(0,4)}<br/>{c.slice(5)}</span>:c,width:80,
  onCell:(row:Row)=>({className:'implementation-speed-td',style:prior(c,period,row.hireDate)?{backgroundColor:'#e5e7eb'}:row.deals.some(d=>label(d.start,period)===c&&d.is_error)?{backgroundColor:'#fff1f0'}:undefined}),
  render:(_:unknown,row:Row)=>{
   if(prior(c,period,row.hireDate))return <Tooltip title={`Дата устройства на работу ${row.hireDate!.split('-').reverse().join('.')}, данных до этого нет`}><div style={{height:40}}/></Tooltip>
   const deals=row.deals.filter(d=>label(d.start,period)===c)
   if(!deals.length)return '—'
   const valid=deals.filter(d=>d.days!==null),bad=deals.filter(d=>d.is_error).length
   const avg=valid.length?valid.reduce((sum,d)=>sum+d.days!,0)/valid.length:null
   const mean=(column:string)=>{const ds=row.deals.filter(d=>label(d.start,period)===column&&d.days!==null);return ds.length?ds.reduce((sum,d)=>sum+d.days!,0)/ds.length:null}
   const prev=index?mean(cohorts[index-1]):null,next=index+1<cohorts.length?mean(cohorts[index+1]):null
   const y=(n:number)=>40-30*n/maxDays
   return <button type="button" className="implementation-speed-cell" onClick={()=>setDetails({title:`${row.name} — ${c}`,deals})}>
    {avg!==null?<svg viewBox="0 0 100 44" preserveAspectRatio="none" aria-hidden="true">{prev!==null&&<line x1="0" y1={(y(prev)+y(avg))/2} x2="50" y2={y(avg)}/>} {next!==null&&<line x1="50" y1={y(avg)} x2="100" y2={(y(avg)+y(next))/2}/>} {prev===null&&next===null&&<line x1="0" y1={y(avg)} x2="100" y2={y(avg)}/>}<circle cx="50" cy={y(avg)} r="3"/></svg>:<div style={{height:44}}/>}
    <span>{avg===null?'—':`${Math.round(avg)}д.`} ({valid.length}{bad?`/${bad}`:''})</span>
   </button>
  }}))]
 const options=Array.from(new Set([...(group==='other'?[]:startModules),...(group==='start'?[]:otherModules),...all.filter(d=>group==='all'||(group==='start'?d.funnel==='cr_start':d.funnel!=='cr_start')).map(d=>d.module).filter(m=>m!=='Логистика')])).sort((a,b)=>a.localeCompare(b,'ru')).map(value=>({label:value,value}))
 return <Space direction="vertical" size={12} style={{width:'100%'}}>
  <div><Typography.Text strong>Итого по выбранным сделкам: </Typography.Text>{average===null?'Нет данных':`${average} д. (${completed.length}${errors?`/${errors}`:''})`} <Tooltip title="Среднее число календарных дней, включая день начала и день завершения. В скобках: успешные сделки / ошибки."><Button type="text" size="small" shape="circle" icon={<QuestionCircleOutlined/>} aria-label="Как рассчитывается скорость запуска"/></Tooltip></div>
  {q.isError&&<Alert type="error" message="Не удалось загрузить скорость запуска"/>}
  <Card size="small"><Space wrap><Radio.Group value={group} onChange={e=>{setGroup(e.target.value);setModules([])}} optionType="button" buttonStyle="solid" options={[{label:'Все',value:'all'},{label:'CR Start',value:'start'},{label:'Другие',value:'other'}]}/>
   <Select value={period} onChange={setPeriod} style={{width:150}} options={[{value:'month',label:'Месяцы'},{value:'quarter',label:'Кварталы'},{value:'year',label:'Годы'},{value:'all',label:'Весь период'}]}/>
   <Select allowClear showSearch optionFilterProp="label" value={employee} onChange={setEmployee} placeholder="Сотрудник" style={{width:230}} options={people.map(p=>({value:p.id,label:p.name}))}/>
   <Select mode="multiple" allowClear maxTagCount="responsive" value={modules} onChange={setModules} placeholder="Все модули" options={options} style={{width:260}}/>
   <Input type="date" aria-label="Скорость: дата от" value={from} onChange={e=>setFrom(e.target.value)}/><Input type="date" aria-label="Скорость: дата до" value={to} onChange={e=>setTo(e.target.value)}/>
  </Space></Card>
  <Card size="small"><Table<Row> className="implementation-metrics-matrix" rowKey="key" size="small" dataSource={rows} columns={columns} loading={q.isLoading} scroll={{x:260+80*cohorts.length}} pagination={{pageSize:25}}/></Card>
  <Modal title={details?.title} open={!!details} onCancel={()=>setDetails(null)} footer={null} width="calc(100vw - 32px)" style={{top:16}}>
   <Table<SpeedDeal> rowKey="id" size="small" pagination={false} scroll={{x:1050,y:'calc(100vh - 160px)'}} dataSource={details?.deals??[]} columns={[
    {title:'Сделки',render:(_,d)=><Space direction="vertical" size={0}>{d.links.map(link=><BitrixLink key={link.bitrix_id} href={dealUrl(link.bitrix_id)}>{link.bitrix_id} — {link.title}</BitrixLink>)}</Space>},
    {title:'Модуль',dataIndex:'module'},{title:'Начало',dataIndex:'start'},{title:'Завершение',dataIndex:'end'},
    {title:'Дней',render:(_,d)=>d.days??'—'},{title:'Примечание',render:(_,d)=>[d.reason,d.logistics_warning].filter(Boolean).join('; ')||'—'}
   ]}/>
  </Modal>
 </Space>
}
