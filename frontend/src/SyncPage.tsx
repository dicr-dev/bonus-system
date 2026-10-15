import {Alert,Button,Card,Empty,Progress,Space,Tag,Typography} from 'antd'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {getSyncConnection,getSyncJob,getSyncJobs,startAllSync,startDealsSync,startFullTasksSync,startRecentTasksSync} from './api'
import type {SyncJob} from './types'

const {Text,Title}=Typography
const typeNames:Record<string,string>={all:'Все объекты',reporting_resume:'Дозагрузка истории, задач и полей',deals:'Сделки',tasks_full:'Задачи за весь срок',tasks_recent:'Задачи за 3 месяца',task_metadata:'Восстановление карточек задач'}
const stageNames:Record<string,string>={users:'Пользователи',deals:'Сделки',stage_history:'История стадий сделок',tasks:'Задачи',task_1c_errors:'Проверка задач 1С',tech_integration:'Техинтеграция',implementation:'Внедрение',support:'Сопровождение',cr_start:'CR Start',report_fields:'Поля отчётов'}
const statusNames={queued:'В очереди',running:'Выполняется',completed:'Завершена',failed:'Ошибка'}
const dateTime=(value:string|null)=>value?new Intl.DateTimeFormat('ru-RU',{timeZone:'Europe/Moscow',dateStyle:'short',timeStyle:'medium'}).format(new Date(value)):'—'

function JobCard({job}:{job:SyncJob}){
 const queued=job.status==='queued'
 const title=typeNames[job.type]??job.type
 return <Card size="small" title={<Space wrap><Text strong>{title}{job.type==='deals'?(job.full?' — полная':' — инкрементальная'):''}</Text><Tag color={job.status==='failed'?'error':job.status==='completed'?'success':queued?'default':'processing'}>{statusNames[job.status]}</Tag></Space>}>
  <Space direction="vertical" style={{width:'100%'}}>
   {!queued&&<Progress percent={job.progress} status={job.status==='failed'?'exception':job.status==='completed'?'success':'active'}/>}
   {queued?<Text>Ожидает освобождения worker. Загрузка ещё не началась.</Text>:<Text>Обработано: {job.processed}. Этап: {job.current_funnel?(stageNames[job.current_funnel]??job.current_funnel):job.status==='running'?'Подготовка':'—'}.</Text>}
   <Text type="secondary">Создана: {dateTime(job.created_at)}; начало: {dateTime(job.started_at)}{job.finished_at?`; завершение: ${dateTime(job.finished_at)}`:''} (МСК)</Text>
   {job.error&&<Alert type="error" showIcon message={job.error}/>}
  </Space>
 </Card>
}

export default function SyncPage(){
 const qc=useQueryClient()
 const pinnedId=new URLSearchParams(window.location.search).get('metadata_job')
 const jobs=useQuery({queryKey:['sync-jobs'],queryFn:getSyncJobs,refetchInterval:2000})
 const connection=useQuery({queryKey:['sync-connection'],queryFn:getSyncConnection,refetchInterval:30000})
 const pinned=useQuery({queryKey:['sync-job',pinnedId],queryFn:()=>getSyncJob(pinnedId!),enabled:!!pinnedId,refetchInterval:query=>['completed','failed'].includes(query.state.data?.status??'')?false:2000})
 const refresh=()=>qc.invalidateQueries({queryKey:['sync-jobs']})
 const all=useMutation({mutationFn:startAllSync,onSuccess:refresh})
 const deals=useMutation({mutationFn:(full:boolean)=>startDealsSync(full),onSuccess:refresh})
 const fullTasks=useMutation({mutationFn:startFullTasksSync,onSuccess:refresh})
 const recentTasks=useMutation({mutationFn:startRecentTasksSync,onSuccess:refresh})
 const rows=new Map((jobs.data??[]).map(job=>[job.job_id,job]))
 if(pinned.data&&!rows.has(pinned.data.job_id))rows.set(pinned.data.job_id,pinned.data)
 const active=[...rows.values()].filter(job=>['queued','running'].includes(job.status))
 const recent=[...rows.values()].filter(job=>['completed','failed'].includes(job.status))
 const startError=all.isError||deals.isError||fullTasks.isError||recentTasks.isError
 return <Space direction="vertical" size={24} style={{width:'100%'}}>
  <Title level={2}>Синхронизация</Title>
  <Card title="Административное подключение Битрикса" loading={connection.isLoading}>
   {connection.isError?<Alert type="error" message="Не удалось проверить настройку подключения"/>:connection.data?.configured?<Space direction="vertical"><Text>Закреплённый администратор Битрикса: №{connection.data.admin_bitrix_user_id}. Проверен: {dateTime(connection.data.verified_at)} (МСК).</Text><Text type="secondary">Доступ сохранён при установке приложения в Битриксе и хранится отдельно от входов сотрудников. Права проверяются перед каждой синхронизацией и при обновлении токенов.</Text></Space>:<Alert type="warning" showIcon message="Требуется переустановка приложения в Битриксе" description="Администратору Битрикса нужно нажать «Переустановить» в настройках этого приложения. Административный доступ для синхронизации сохранится автоматически. Токены входящих сотрудников не используются."/>}
  </Card>
  <Card title="Все объекты"><Button type="primary" loading={all.isPending} onClick={()=>all.mutate()}>Синхронизировать все объекты</Button></Card>
  <Card title="Сделки"><Space wrap><Button type="primary" loading={deals.isPending} onClick={()=>deals.mutate(false)}>Инкрементальная</Button><Button loading={deals.isPending} onClick={()=>deals.mutate(true)}>Полная</Button></Space></Card>
  <Card title="Задачи"><Space wrap><Button loading={recentTasks.isPending} onClick={()=>recentTasks.mutate()}>За 3 месяца</Button><Button loading={fullTasks.isPending} onClick={()=>fullTasks.mutate()}>За весь срок</Button></Space></Card>
  {startError&&<Alert type="error" showIcon message="Не удалось запустить синхронизацию. Повторите попытку."/>}
  {jobs.isError&&<Alert type="error" showIcon message="Не удалось обновить статусы синхронизаций" description="Показаны последние полученные данные. Повторная проверка выполняется автоматически."/>}
  <Card title="Статус выполнения" loading={jobs.isLoading} extra={<Button onClick={()=>refresh()} loading={jobs.isFetching}>Обновить</Button>}>
   <Space direction="vertical" style={{width:'100%'}}>{active.length?active.map(job=><JobCard key={job.job_id} job={job}/>):<Empty image={Empty.PRESENTED_IMAGE_SIMPLE} description={jobs.isError?'Актуальный статус недоступен':'Нет выполняющихся или ожидающих синхронизаций'}/>}</Space>
  </Card>
  {!!recent.length&&<Card title="Последние завершённые синхронизации"><Space direction="vertical" style={{width:'100%'}}>{recent.map(job=><JobCard key={job.job_id} job={job}/>)}</Space></Card>}
 </Space>
}
