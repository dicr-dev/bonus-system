import {Alert,Button,Card,Input,Space,Table,Typography} from 'antd'
import type {ColumnsType} from 'antd/es/table'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {useState} from 'react'
import {api} from './api'
import {BitrixLink,dealUrl,taskUrl} from './BitrixLink'

type RatingDeal={bitrix_id:number;title:string;amount:string}
type ImplementationEmployee={id:string;name:string;deal_count:number;deal_amount:string;deals:RatingDeal[]}
type Developer={id:string;name:string;task_count:number;integration_count:number|null;hours:string}
type IntegrationTask={bitrix_id:number;title:string;responsible_bitrix_id:number|null;responsible_name:string;group_id:number|null}
type IntegrationIssue=RatingDeal&{reason:string;tasks:IntegrationTask[]}
type MonthlyRating={month:string;implementation:ImplementationEmployee[];development:Developer[];integration_issues:IntegrationIssue[];warnings:string[];integration_count_reliable:boolean;type_metadata_loaded_at:string|null}

const money=(value:string)=>new Intl.NumberFormat('ru-RU',{style:'currency',currency:'RUB'}).format(Number(value))
const currentMonth=()=>new Intl.DateTimeFormat('sv-SE',{timeZone:'Europe/Moscow',year:'numeric',month:'2-digit'}).format(new Date()).slice(0,7)
const dealColumns:ColumnsType<RatingDeal>=[
 {title:'Название сделки',dataIndex:'title',render:(title,row)=><BitrixLink href={dealUrl(row.bitrix_id)}>{title}</BitrixLink>},
 {title:'Сумма сделки',dataIndex:'amount',align:'right',render:money},
]
const implementationColumns:ColumnsType<ImplementationEmployee>=[
 {title:'ФИО',dataIndex:'name',sorter:(a,b)=>a.name.localeCompare(b.name,'ru')},
 {title:'Кол-во сделок, переведённых на подписку',dataIndex:'deal_count',align:'right',sorter:(a,b)=>a.deal_count-b.deal_count},
 {title:'Сумма сделок, переведённых на подписку',dataIndex:'deal_amount',align:'right',sorter:(a,b)=>Number(a.deal_amount)-Number(b.deal_amount),defaultSortOrder:'descend',render:money},
]
const developerColumns:ColumnsType<Developer>=[
 {title:'ФИО',dataIndex:'name',sorter:(a,b)=>a.name.localeCompare(b.name,'ru')},
 {title:'Выполнено задач',dataIndex:'task_count',align:'right',sorter:(a,b)=>a.task_count-b.task_count},
 {title:'Выполнено интеграций',dataIndex:'integration_count',align:'right',sorter:(a,b)=>(a.integration_count??-1)-(b.integration_count??-1),defaultSortOrder:'descend',render:value=>value??'Не определено'},
 {title:'Часы за месяц',dataIndex:'hours',align:'right',sorter:(a,b)=>Number(a.hours)-Number(b.hours),render:value=>new Intl.NumberFormat('ru-RU',{maximumFractionDigits:2}).format(Number(value))},
]
const taskColumns:ColumnsType<IntegrationTask>=[
 {title:'Задача',dataIndex:'title',render:(title,row)=><BitrixLink href={taskUrl(row.bitrix_id,row.group_id,row.responsible_bitrix_id)}>{title}</BitrixLink>},
 {title:'Исполнитель',dataIndex:'responsible_name'},
]
const issueColumns:ColumnsType<IntegrationIssue>=[
 {title:'Название сделки',dataIndex:'title',render:(title,row)=><BitrixLink href={dealUrl(row.bitrix_id)}>{title}</BitrixLink>},
 {title:'Причина',dataIndex:'reason'},
 {title:'Связанные задачи',render:(_,row)=><Table size="small" rowKey="bitrix_id" columns={taskColumns} dataSource={row.tasks} pagination={false} locale={{emptyText:'Подходящие задачи не найдены'}}/>},
]

export default function MonthlyRatingPage(){
 const [month,setMonth]=useState(currentMonth)
 const queryClient=useQueryClient()
 const report=useQuery({queryKey:['monthly-rating',month],queryFn:async()=> (await api.get<MonthlyRating>('/analytics/monthly-rating',{params:{month}})).data,enabled:/^\d{4}-\d{2}$/.test(month)})
 const metadata=useMutation({mutationFn:()=>api.post('/analytics/monthly-rating/type-metadata'),onSuccess:()=>queryClient.invalidateQueries({queryKey:['monthly-rating']})})
 const data=report.data
 return <Space direction="vertical" size={20} style={{width:'100%'}}>
  <Typography.Title level={2}>Рейтинг за месяц</Typography.Title>
  <Card><Space wrap><Typography.Text>Отчётный месяц:</Typography.Text><Input aria-label="Отчётный месяц" type="month" value={month} onChange={event=>{if(event.target.value)setMonth(event.target.value)}} style={{width:190}}/><Button onClick={()=>report.refetch()} loading={report.isFetching}>Обновить отчёт</Button><Button onClick={()=>metadata.mutate()} loading={metadata.isPending}>Обновить справочник типов задач 1С</Button></Space></Card>
  {report.isError&&<Alert type="error" showIcon message="Не удалось загрузить рейтинг" description="Проверьте выбранный месяц и повторите запрос."/>}
  {metadata.isError&&<Alert type="error" showIcon message="Не удалось загрузить справочник 1С" description="Проверьте постоянное подключение Битрикса на странице синхронизации и повторите загрузку."/>}
  {metadata.isSuccess&&<Alert type="success" showIcon message="Справочник типов задач 1С обновлён"/>}
  {data?.warnings.map(warning=><Alert key={warning} type={data.integration_count_reliable?'info':'warning'} showIcon message={warning}/>)}
  <Card title="Отдел внедрения">
   <Typography.Paragraph type="secondary">Успешно закрытые сделки воронки «Внедрение» за выбранный месяц, по текущему ответственному за внедрение. Сумма — поле «Сумма сделки».</Typography.Paragraph>
   <Table rowKey="id" columns={implementationColumns} dataSource={data?.implementation??[]} loading={report.isFetching} pagination={false} scroll={{x:800}} expandable={{rowExpandable:row=>row.deals.length>0,expandedRowRender:row=><Table size="small" rowKey="bitrix_id" columns={dealColumns} dataSource={row.deals} pagination={false}/>}}/>
  </Card>
  <Card title="Разработка 1С">
   <Typography.Paragraph type="secondary">Задачи — по исполнителю и дате завершения. Интеграции — по дате успешного закрытия Техинтеграции с признаком 1С, исполнитель — из задачи «Реализация интеграции». Часы — по автору и дате записи времени, независимо от завершения задачи. Даты — по Москве. Нажмите заголовок столбца для изменения сортировки.</Typography.Paragraph>
   <Table rowKey="id" columns={developerColumns} dataSource={data?.development??[]} loading={report.isFetching} pagination={false} scroll={{x:750}}/>
   {!!data?.integration_issues.length&&<Space direction="vertical" style={{width:'100%',marginTop:24}}><Alert type="warning" showIcon message="Интеграции, которые не удалось однозначно засчитать" description="При разных исполнителях интеграция не засчитывается никому. Несколько задач одного разработчика в одной сделке считаются одной интеграцией."/><Table rowKey="bitrix_id" columns={issueColumns} dataSource={data.integration_issues} pagination={false} scroll={{x:950}}/></Space>}
  </Card>
 </Space>
}
