import {useMemo, useState} from 'react'
import {useQuery} from '@tanstack/react-query'
import {QuestionCircleOutlined} from '@ant-design/icons'
import {Alert, Button, Card, Checkbox, Input, Modal, Radio, Select, Space, Table, Tooltip, Typography} from 'antd'
import type {ColumnsType} from 'antd/es/table'
import {api} from './api'
import {BitrixLink,dealUrl} from './BitrixLink'
import './implementationMetrics.css'

type Deal = {id:string; bitrix_id:number; title:string; company:string|null; funnel:string; module:string; opportunity:string; monthly_amount:string; employee_id:string; employee:string; implementation_employee:string; start:string|null; control_end:string|null; result:'retained'|'lost'|'pending'|'unknown'; reason:string}
type Report = {employees:{id:string; name:string; hire_date:string|null}[]; deals:Deal[]}
type MatrixRow = {key:string; name:string; deals:Deal[]; hireDate?:string|null; children?:MatrixRow[]}
const statuses:Record<string,string>={retained:'Удержана',lost:'Не удержана',pending:'Ожидает проверки',unknown:'Недостаточно данных'}
const resultOrder:Record<Deal['result'],number>={retained:0,lost:1,pending:2,unknown:2}
const startModules=['CR Start','CR Start Эксплуатация','CR Start ТМ']
const otherModules=['Логистика','Эксплуатация','Топливный модуль','Загрузки','Топливный планировщик','Дальнобой + ТМ','Маршрутизация','Каргоран Лайт + ТМ']
const sumAmount=(deals:Deal[],field:'opportunity'|'monthly_amount')=>deals.reduce((sum,d)=>sum+Math.round(Number(d[field]||0)*100),0)/100
const rub=(value:number)=>new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB',maximumFractionDigits:2}).format(value)
const wholeAmount=(value:number)=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:0}).format(value)
function cohort(date:string|null, period:string) {
 if(!date)return 'Дата не указана'
 if(period==='all')return 'Весь период'
 const year=date.slice(0,4), month=Number(date.slice(5,7))
 return period==='year'?year:period==='quarter'?`${year} Q${Math.ceil(month/3)}`:date.slice(0,7)
}
function beforeHire(value:string, period:string, hireDate?:string|null){
 if(!hireDate||period==='all'||value==='Дата не указана')return false
 const end=period==='month'?`${value}-31`:period==='quarter'?`${value.slice(0,4)}-${String(Number(value.slice(-1))*3).padStart(2,'0')}-31`:`${value}-12-31`
 return end<hireDate
}
function chartCohorts(values:string[], period:string):string[]{
 if(period==='all'||!values.length)return values
 const indexes=values.flatMap(value=>{
  const match=period==='month'?/^(\d{4})-(\d{2})$/.exec(value):period==='quarter'?/^(\d{4}) Q([1-4])$/.exec(value):/^(\d{4})$/.exec(value)
  if(!match)return []
  return [period==='month'?Number(match[1])*12+Number(match[2])-1:period==='quarter'?Number(match[1])*4+Number(match[2])-1:Number(match[1])]
 })
 if(!indexes.length)return values
 const result:string[]=[]
 for(let i=Math.min(...indexes);i<=Math.max(...indexes);i++){
  result.push(period==='month'?`${Math.floor(i/12)}-${String(i%12+1).padStart(2,'0')}`:period==='quarter'?`${Math.floor(i/4)} Q${i%4+1}`:String(i))
 }
 return values.includes('Дата не указана')?['Дата не указана',...result]:result
}
function retention(deals:Deal[]){
 const checked=deals.filter(d=>d.result==='retained'||d.result==='lost')
 return checked.length?{value:100*checked.filter(d=>d.result==='retained').length/checked.length,count:checked.length}:null
}
const chartColor=(value:number)=>value>70?'#389e0d':value>50?'#d4a000':'#cf1322'
function chartSegments(x1:number,value1:number,x2:number,value2:number){
 const cuts=[0,1,...[50,70].map(threshold=>(threshold-value1)/(value2-value1)).filter(t=>t>0&&t<1)].sort((a,b)=>a-b)
 const y=(value:number)=>45-value*0.35
 return cuts.slice(0,-1).map((from,index)=>{const to=cuts[index+1], v1=value1+(value2-value1)*from, v2=value1+(value2-value1)*to
  return <line key={index} x1={x1+(x2-x1)*from} y1={y(v1)} x2={x1+(x2-x1)*to} y2={y(v2)} style={{stroke:chartColor((v1+v2)/2)}}/>
 })
}
export default function ImplementationMetricsPage(){
 const [period,setPeriod]=useState('month')
 const [hidePending,setHidePending]=useState(false)
 const [displayMode,setDisplayMode]=useState<'percent'|'amount'|'graph'>('percent')
 const [funnelFilter,setFunnelFilter]=useState<'all'|'cr_start'|'other'>('all')
 const [employee,setEmployee]=useState<string>()
 const [selectedModules,setSelectedModules]=useState<string[]>([])
 const [from,setFrom]=useState('')
 const [to,setTo]=useState('')
 const [details,setDetails]=useState<{title:string; deals:Deal[]}|null>(null)
 const report=useQuery({queryKey:['implementation-metrics'],queryFn:async()=>(await api.get<Report>('/analytics/implementation-metrics')).data})
 const all=report.data?.deals??[]
 const employees=(report.data?.employees??[]).map(item=>({value:item.id,label:item.name}))
 const inFunnel=(d:Deal)=>funnelFilter==='all'||(funnelFilter==='cr_start'?d.funnel==='cr_start':d.funnel!=='cr_start')
 const modules=Array.from(new Set([...(funnelFilter==='other'?[]:startModules),...(funnelFilter==='cr_start'?[]:otherModules),...all.filter(inFunnel).map(d=>d.module)])).sort((a,b)=>a.localeCompare(b,'ru')).map(value=>({value,label:value}))
 const hireDates=new Map((report.data?.employees??[]).map(person=>[person.id,person.hire_date]))
 const baseFiltered=all.filter(d=>(!hidePending||d.result!=='pending')&&inFunnel(d)&&(!employee||d.employee_id===employee)&&(!selectedModules.length||selectedModules.includes(d.module))&&(!from||!!d.start&&d.start>=from)&&(!to||!!d.start&&d.start<=to))
 const filtered=baseFiltered.filter(d=>{const date=hireDates.get(d.employee_id);return !date||!!d.start&&d.start>=date})
 const {rows,cohorts}=useMemo(()=>{
  const result=new Map<string,MatrixRow>()
  const dates=new Set(baseFiltered.map(deal=>cohort(deal.start,period)))
  for(const person of report.data?.employees??[]){
   if(!employee||employee===person.id)result.set(person.id,{key:person.id,name:person.name,hireDate:person.hire_date,deals:[],children:[]})
  }
  for(const deal of filtered){
   dates.add(cohort(deal.start,period))
   if(!result.has(deal.employee_id))result.set(deal.employee_id,{key:deal.employee_id,name:deal.employee,hireDate:hireDates.get(deal.employee_id),deals:[],children:[]})
   const row=result.get(deal.employee_id)!
   row.deals.push(deal)
   const groupName=deal.funnel==='cr_start'?'CR Start':'Другие'
   let group=row.children!.find(item=>item.name===groupName)
   if(!group){group={key:JSON.stringify([deal.employee_id,'group',groupName]),name:groupName,hireDate:row.hireDate,deals:[],children:[]};row.children!.push(group)}
   group.deals.push(deal)
   let child=group.children!.find(item=>item.name===deal.module)
   if(!child){child={key:JSON.stringify([deal.employee_id,'module',groupName,deal.module]),name:deal.module,hireDate:row.hireDate,deals:[]};group.children!.push(child)}
   child.deals.push(deal)
  }
  const rows=[...result.values()].sort((a,b)=>a.name.localeCompare(b.name,'ru'))
  rows.forEach(row=>{row.children!.sort((a,b)=>a.name.localeCompare(b.name,'ru'));row.children!.forEach(group=>group.children!.sort((a,b)=>a.name.localeCompare(b.name,'ru')))})
  const sorted=[...dates].sort((a,b)=>a==='Дата не указана'?-1:b==='Дата не указана'?1:a.localeCompare(b))
  return {rows,cohorts:displayMode==='graph'?chartCohorts(sorted,period):sorted}
 },[filtered,baseFiltered,period,report.data,employee,displayMode])
 const cohortWidth=displayMode==='graph'?45:55
 const columns:ColumnsType<MatrixRow>=[
  {title:'Сотрудник / модуль',dataIndex:'name',fixed:'left',width:260},
  ...cohorts.map((c,index)=>({title:period==='month'&&/^\d{4}-\d{2}$/.test(c)?<span>{c.slice(0,4)}<br/>{c.slice(5)}</span>:period==='quarter'&&/^\d{4} Q[1-4]$/.test(c)?<span>{c.slice(0,4)}<br/>{c.slice(5)}</span>:c,key:c,width:cohortWidth,
   onCell:(row:MatrixRow)=>({className:displayMode==='graph'?'implementation-metrics-chart-cell':undefined,style:beforeHire(c,period,row.hireDate)?{backgroundColor:'#e5e7eb'}:row.deals.some(d=>cohort(d.start,period)===c&&d.result==='unknown')?{backgroundColor:'#fff1f0'}:undefined}),
   render:(_:unknown,row:MatrixRow)=>{
   if(beforeHire(c,period,row.hireDate))return <Tooltip title={`Дата устройства на работу ${row.hireDate!.split('-').reverse().join('.')}, данных до этого нет`}><div tabIndex={0} aria-label={`Дата устройства на работу ${row.hireDate!.split('-').reverse().join('.')}, данных до этого нет`} style={{minHeight:32,width:'100%'}}/></Tooltip>
   const deals=row.deals.filter(d=>cohort(d.start,period)===c)
   if(!deals.length)return '—'
   const retained=deals.filter(d=>d.result==='retained').length
   const checked=deals.filter(d=>d.result==='retained'||d.result==='lost').length
   const pending=deals.filter(d=>d.result==='pending').length
   const unknown=deals.filter(d=>d.result==='unknown').length
   if(displayMode==='graph'){
    const point=retention(deals)
    if(!point)return '—'
    const prev=index>0?retention(row.deals.filter(d=>cohort(d.start,period)===cohorts[index-1])):null
    const next=index+1<cohorts.length?retention(row.deals.filter(d=>cohort(d.start,period)===cohorts[index+1])):null
    const y=(value:number)=>45-value*0.35
    return <Tooltip title={`${row.name}: ${c} — ${Math.round(point.value)}% (${point.count} проверено)`}><button className="implementation-metrics-chart-point" aria-label={`${c}: ${Math.round(point.value)} процентов, проверено ${point.count}`} onClick={()=>setDetails({title:`${row.name} — ${c}`,deals})}><svg viewBox="0 0 100 54" preserveAspectRatio="none" aria-hidden="true">{!prev&&!next&&chartSegments(0,point.value,100,point.value)}{prev&&chartSegments(0,(prev.value+point.value)/2,50,point.value)}{next&&chartSegments(50,point.value,100,(next.value+point.value)/2)}<circle cx="50" cy={y(point.value)} r="3" style={{fill:chartColor(point.value)}}/></svg></button></Tooltip>
   }
   return <Button type="link" style={{height:'auto',padding:0,whiteSpace:'normal',textAlign:'left',color:'#1f1f1f',fontSize:displayMode==='amount'?10:undefined,overflowWrap:'anywhere'}} onClick={()=>setDetails({title:`${row.name} — ${c}`,deals})}>
    <span>{displayMode==='percent'?<>{checked?`${Math.round(100*retained/checked)}%`:'—'}<br/>({retained}/{checked}{unknown>0?`/${unknown}`:''})</>:<>{wholeAmount(sumAmount(deals.filter(d=>d.result==='retained'),'opportunity'))}<br/>/ {wholeAmount(sumAmount(deals,'opportunity'))}</>}{pending>0&&<><br/>Ожидают: {pending}</>}</span>
   </Button>
  }}))
 ]
 const retained=filtered.filter(d=>d.result==='retained').length,checked=filtered.filter(d=>d.result==='retained'||d.result==='lost').length
 return <Space className="implementation-metrics-page" direction="vertical" size={12} style={{width:'100%'}}>
  <Space align="center" size={8}><Typography.Title level={2} style={{margin:0}}>Ключевые метрики отдела внедрения</Typography.Title><Tooltip title="Результат определяется после окончания четвёртого календарного месяца. В процентах: удержаны / проверены / нет данных (если есть); ожидающие и сделки без данных не входят в процент. В рублях: сумма удержанных / сумма всех сделок, включая ожидающие и сделки без данных."><Button type="text" size="small" shape="circle" icon={<QuestionCircleOutlined/>} aria-label="Как рассчитываются показатели"/></Tooltip></Space>
  {report.isError&&<Alert type="error" message="Не удалось загрузить отчёт"/>}
  <Card size="small"><Space wrap>
   <Radio.Group aria-label="Фильтр по воронке" value={funnelFilter} onChange={e=>{setFunnelFilter(e.target.value);setSelectedModules([])}} optionType="button" buttonStyle="solid" options={[{label:'Все',value:'all'},{label:'CR Start',value:'cr_start'},{label:'Другие',value:'other'}]}/>
   <Radio.Group aria-label="Показатель" value={displayMode} onChange={e=>setDisplayMode(e.target.value)} optionType="button" buttonStyle="solid" options={[{label:'%',value:'percent'},{label:'₽',value:'amount'},{label:'Гр',value:'graph'}]}/>
   <Select value={period} onChange={setPeriod} style={{width:150}} options={[{value:'month',label:'Месяцы'},{value:'quarter',label:'Кварталы'},{value:'year',label:'Годы'},{value:'all',label:'Весь период'}]}/>
   <Select allowClear showSearch optionFilterProp="label" value={employee} onChange={setEmployee} placeholder="Сотрудник" options={employees} style={{width:240}}/>
   <Select mode="multiple" allowClear maxTagCount="responsive" value={selectedModules} onChange={setSelectedModules} placeholder="Все модули" options={modules} style={{width:260}}/>
   <Input aria-label="Дата начала периода" type="date" value={from} onChange={e=>setFrom(e.target.value)}/>
   <Input aria-label="Дата окончания периода" type="date" value={to} onChange={e=>setTo(e.target.value)}/>
   <Checkbox checked={hidePending} onChange={e=>setHidePending(e.target.checked)}>Убрать ожидающих</Checkbox>
  </Space></Card>
  <Card size="small"><Typography.Text strong>Итого по выбранным сделкам: </Typography.Text>{displayMode!=='amount'?(checked?`${Math.round(100*retained/checked)}% (${retained} из ${checked})`:'Нет проверенных сделок'):`${rub(sumAmount(filtered.filter(d=>d.result==='retained'),'opportunity'))} / ${rub(sumAmount(filtered,'opportunity'))}`}; ожидают: {filtered.filter(d=>d.result==='pending').length}; недостаточно данных: {filtered.filter(d=>d.result==='unknown').length}</Card>
  <Card size="small"><Table<MatrixRow> className="implementation-metrics-matrix" size="small" rowKey="key" dataSource={rows} loading={report.isLoading} pagination={{pageSize:25}} scroll={{x:260+cohortWidth*cohorts.length}} columns={columns}/></Card>
  <Modal title={details?.title} open={details!==null} onCancel={()=>setDetails(null)} footer={null} width="calc(100vw - 32px)" style={{top:16}}>
   <Space wrap style={{marginBottom:8}}>{([['Итого',details?.deals??[]],['Итого успешных',(details?.deals??[]).filter(d=>d.result==='retained')],['Итого неуспешных',(details?.deals??[]).filter(d=>d.result==='lost')]] as [string,Deal[]][]).map(([label,deals])=><span key={label}><strong>{label}:</strong> {rub(sumAmount(deals,'opportunity'))} / мес. {rub(sumAmount(deals,'monthly_amount'))}</span>)}</Space>
   <Table<Deal> className="implementation-metrics-deals" size="small" tableLayout="fixed" rowKey="id" rowClassName={d=>`implementation-metrics-deal-${d.result==='retained'?'retained':d.result==='lost'?'lost':'other'}`} pagination={false} scroll={{x:1300,y:'calc(100vh - 190px)'}} dataSource={[...(details?.deals??[])].sort((a,b)=>Number(a.funnel==='cr_start')-Number(b.funnel==='cr_start')||resultOrder[a.result]-resultOrder[b.result])} columns={[
   {title:'Сделка',width:'25%',ellipsis:true,render:(_,d)=><span title={`${d.bitrix_id} — ${d.title}`}><BitrixLink href={dealUrl(d.bitrix_id)}>{d.bitrix_id} — {d.title}</BitrixLink></span>},
   {title:'Модуль',dataIndex:'module',width:175,ellipsis:true},
   {title:'Сумма сделки',dataIndex:'opportunity',width:145,align:'right',render:(v:string)=>rub(Number(v||0))},
   {title:'Оплата в месяц',dataIndex:'monthly_amount',width:150,align:'right',render:(v:string)=>rub(Number(v||0))},
   {title:'Начало',dataIndex:'start',width:110},{title:'Проверка после',dataIndex:'control_end',width:145},
   {title:'Результат',width:155,render:(_,d)=>statuses[d.result]},{title:'Примечание',ellipsis:true,render:(_,d)=>{const text=[d.implementation_employee?`Внедрение: ${d.implementation_employee}`:'',d.reason].filter(Boolean).join('; ');return <span title={text}>{text}</span>}}
   ]}/>
  </Modal>
 </Space>
}
