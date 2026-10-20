import {useEffect,useState} from 'react'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {Alert,Button,Card,Collapse,Descriptions,Drawer,Empty,Form,Input,Modal,Popconfirm,Select,Space,Table,Tabs,Tag,Typography,message} from 'antd'
import type {ColumnsType} from 'antd/es/table'
import {BitrixLink,dealUrl} from './BitrixLink'
import {
 confirmTrainingReview,createTrainingRubric,inspectTraining,parseTrainingAssessment,saveTrainingReview,
 searchTrainingDeals,trainingDetails,trainingFileUrl,trainingOptions,trainingPromptUrl,trainingRating,
 trainingSessions,uploadTraining,
} from './trainingApi'
import type {ExtractionInfo,Training,TrainingCriterion,TrainingOptions,TrainingReview} from './trainingApi'

const {Title,Text,Paragraph}=Typography
const score=(value:string|number|null)=>value===null?'Недостаточно данных':`${Number(value).toFixed(2)} / 100`
const dateText=(value:string)=>new Date(`${value}T00:00:00`).toLocaleDateString('ru-RU')
const versionLabel=(r:{title:string; id:string; created_at:string})=>`${r.title} · ${r.id.slice(0,8)}`
function errorText(error:unknown){
 const data=error as {response?:{data?:{detail?:unknown}};message?:string}
 const detail=data.response?.data?.detail
 if(typeof detail==='string')return detail
 if(Array.isArray(detail))return detail.map(x=>`${(x.loc??[]).slice(1).join('.')}: ${x.msg}`).join('; ')
 return data.message||'Не удалось выполнить действие'
}

function AddTraining({deal,options,onAdded,onCancel}:{deal?:{id:string; title:string; bitrix_id:number}; options:TrainingOptions; onAdded:(item:Training)=>void; onCancel:()=>void}){
 const [form]=Form.useForm()
 const [file,setFile]=useState<File|null>(null)
 const [info,setInfo]=useState<ExtractionInfo|null>(null)
 const [search,setSearch]=useState('')
 const [query,setQuery]=useState('')
 const [error,setError]=useState('')
 useEffect(()=>{const timer=setTimeout(()=>setQuery(search),250);return()=>clearTimeout(timer)},[search])
 const deals=useQuery({queryKey:['training-deals',query],queryFn:()=>searchTrainingDeals(query),enabled:!deal})
 const inspect=useMutation({mutationFn:inspectTraining,onSuccess:data=>setInfo(data),onError:e=>setError(errorText(e))})
 const upload=useMutation({mutationFn:(values:unknown)=>uploadTraining(file!,values),onSuccess:onAdded,onError:e=>setError(errorText(e))})
 const chooseFile=(next:File|null)=>{
  setFile(null);setInfo(null);setError('');form.setFieldValue('speaker_label',undefined)
  if(!next)return
  if(!next.name.toLowerCase().endsWith('.docx')||next.size>options.max_file_bytes){setError('Нужен DOCX не больше 10 МБ');return}
  setFile(next);inspect.mutate(next)
 }
 return <Modal open title="Добавить обучение и транскрибацию" onCancel={onCancel} footer={null} width={720} maskClosable={false}>
  <Form form={form} layout="vertical" initialValues={{deal_id:deal?.id,training_number:1}} onFinish={values=>{setError('');upload.mutate(values)}}>
   <Alert type="info" showIcon message="Файл сохраняется только в приложении. Отправка в ChatGPT выполняется вами вручную." style={{marginBottom:16}}/>
   <Form.Item name="deal_id" label="Сделка" rules={[{required:true}]}>
    <Select disabled={Boolean(deal)} showSearch filterOption={false} onSearch={setSearch} loading={deals.isFetching} placeholder="Начните вводить название или ID сделки"
     options={deal?[{value:deal.id,label:`№${deal.bitrix_id} — ${deal.title}`}]:deals.data?.map(d=>({value:d.id,label:`№${d.bitrix_id} — ${d.title}`}))}
     onChange={id=>{const d=deals.data?.find(x=>x.id===id);if(d?.module_name)form.setFieldValue('module',d.module_name)}}/>
   </Form.Item>
   <Form.Item name="trainer_id" label="Кто проводил обучение" rules={[{required:true}]}>
    <Select showSearch optionFilterProp="label" options={options.trainers.map(u=>({value:u.id,label:`${u.full_name}${u.is_active?'':' (неактивен)'}`}))}/>
   </Form.Item>
   <Space align="start" wrap>
    <Form.Item name="training_date" label="Фактическая дата обучения" rules={[{required:true}]}><Input type="date"/></Form.Item>
    <Form.Item name="training_number" label="Номер обучения" rules={[{required:true}]}><Select style={{width:160}} options={[1,2,3].map(value=>({value,label:`Обучение ${value}`}))}/></Form.Item>
   </Space>
   <Form.Item name="module" label="Модуль (единое название для сравнения в рейтинге)" rules={[{required:true,max:255}]}>
    <Select showSearch options={['Логистика','Эксплуатация','Топливный модуль','Загрузки','КР Старт ТМ','КР Старт Эксплуатация'].map(value=>({value,label:value}))}/>
   </Form.Item>
   <Form.Item label="Транскрибация DOCX, до 10 МБ" required>
    <input type="file" accept=".docx,application/vnd.openxmlformats-officedocument.wordprocessingml.document" disabled={inspect.isPending||upload.isPending} onChange={e=>chooseFile(e.target.files?.[0]??null)}/>
   </Form.Item>
   {inspect.isPending&&<Paragraph>Чтение структуры DOCX…</Paragraph>}
   {info&&<>
    <Alert type="warning" showIcon message="Проверьте дату и участника" description={info.warnings.join(' ')} style={{marginBottom:16}}/>
    <Paragraph type="secondary">{info.characters.toLocaleString('ru-RU')} символов · последняя метка: {info.last_timecode||'нет'} · {info.summary_excluded?'резюме исключено':'раздел диалога не выделен'}</Paragraph>
   </>}
   <Form.Item name="speaker_label" label="Как сотрудник обозначен в транскрипте" rules={[{required:true,max:200}]}>
    {info?.speakers.length?<Select options={info.speakers.map(value=>({value,label:value}))}/>:<Input placeholder="Например: Максим (Speaker A)"/>}
   </Form.Item>
   {error&&<Alert type="error" showIcon message={error} style={{marginBottom:16}}/>}
   <Button type="primary" htmlType="submit" loading={upload.isPending} disabled={!file||!info||inspect.isPending}>Сохранить обучение</Button>
  </Form>
 </Modal>
}

function TrainingDetail({id,options,onClose}:{id:string; options:TrainingOptions; onClose:()=>void}){
 const qc=useQueryClient()
 const q=useQuery({queryKey:['training-detail',id],queryFn:()=>trainingDetails(id)})
 const [rubricId,setRubricId]=useState(options.rubrics[0]?.id)
 const [json,setJson]=useState('')
 const [error,setError]=useState('')
 const changed=()=>{void qc.invalidateQueries({queryKey:['training-detail',id]});void qc.invalidateQueries({queryKey:['training-rating']})}
 const save=useMutation({mutationFn:()=>saveTrainingReview(id,parseTrainingAssessment(json)),onSuccess:()=>{message.success('Черновик сохранён. Проверьте оценку и подтвердите её.');setError('');changed()},onError:e=>setError(errorText(e))})
 const confirm=useMutation({mutationFn:(reviewId:string)=>confirmTrainingReview(id,reviewId),onSuccess:()=>{message.success('Оценка подтверждена');changed()},onError:e=>setError(errorText(e))})
 const data=q.data
 const reviewContent=(review:TrainingReview)=>{
  const rubric=options.rubrics.find(x=>x.id===review.rubric_id)
  const columns:ColumnsType<TrainingReview['assessment']['criteria'][number]>=[
   {title:'Критерий',dataIndex:'id',render:value=>{const c=rubric?.criteria.find(x=>x.id===value);return c?`${c.title} (${c.weight}%)`:value}},
   {title:'Балл / 10',dataIndex:'score',render:value=>value===null?'Нет данных':Number(value)},
   {title:'Обоснование и цитаты',render:(_,row)=><><Paragraph style={{whiteSpace:'pre-wrap'}}>{row.explanation}</Paragraph>{row.evidence.map((e,i)=><Paragraph key={i} style={{whiteSpace:'pre-wrap'}}><Text type="secondary">{e.timecode} </Text>«{e.quote}»</Paragraph>)}</>},
  ]
  return <Space direction="vertical" style={{width:'100%'}}>
   <Text>Версия: {rubric?versionLabel(rubric):review.rubric_id}</Text>
   <Table rowKey="id" columns={columns} dataSource={review.assessment.criteria} pagination={false} scroll={{x:650}}/>
   <Paragraph style={{whiteSpace:'pre-wrap'}}><Text strong>Сильные стороны: </Text>{review.assessment.strengths||'—'}</Paragraph>
   <Paragraph style={{whiteSpace:'pre-wrap'}}><Text strong>Рекомендации: </Text>{review.assessment.recommendations||'—'}</Paragraph>
   <Paragraph style={{whiteSpace:'pre-wrap'}}><Text strong>Ограничения: </Text>{review.assessment.limitations||'—'}</Paragraph>
   <Space wrap>
    <Button onClick={()=>{setJson(JSON.stringify(review.assessment,null,2));setError('')}}>Взять за основу новой оценки</Button>
    {review.status==='draft'&&<Popconfirm title="Подтвердить проверенную оценку?" description="В рейтинге используется последняя подтверждённая оценка этой версии критериев." onConfirm={()=>confirm.mutate(review.id)}><Button type="primary" loading={confirm.isPending}>Подтвердить оценку</Button></Popconfirm>}
   </Space>
  </Space>
 }
 return <Drawer open onClose={onClose} width={1000} title="Обучение — транскрибация и оценки">
  {q.isLoading&&<Card loading/>}{q.isError&&<Alert type="error" message={errorText(q.error)}/>}
  {data&&<Space direction="vertical" size={20} style={{width:'100%'}}>
   <Descriptions bordered column={2} items={[
    {key:'deal',label:'Сделка',children:<BitrixLink href={dealUrl(data.deal_bitrix_id)}>{data.deal_title}</BitrixLink>},
    {key:'trainer',label:'Сотрудник',children:data.trainer_name},
    {key:'date',label:'Дата',children:dateText(data.training_date)},
    {key:'module',label:'Обучение',children:`${data.module} · №${data.training_number}`},
    {key:'speaker',label:'Участник',children:data.speaker_label},
    {key:'file',label:'Исходный файл',children:<a href={trainingFileUrl(id)}>{data.filename}</a>},
   ]}/>
   <Alert type="info" showIcon message="Ручной анализ через ChatGPT" description="Скачайте задание с транскриптом, вручную передайте его ChatGPT и перенесите JSON-ответ ниже. Перед передачей проверьте допустимость раскрытия клиентских данных. Приложение ничего не отправляет во внешние сервисы."/>
   <Space wrap><Select style={{minWidth:300}} value={rubricId} onChange={setRubricId} options={options.rubrics.map(r=>({value:r.id,label:versionLabel(r)}))}/><Button href={rubricId?trainingPromptUrl(id,rubricId):undefined} disabled={!rubricId}>Скачать задание для ChatGPT</Button></Space>
   <Collapse items={[{key:'transcript',label:'Исходный диалог (без резюме при наличии раздела «Транскрипт»)',children:<pre style={{whiteSpace:'pre-wrap',maxHeight:400,overflow:'auto'}}>{data.transcript}</pre>}]}/>
   <Card size="small" title="Перенести результат из ChatGPT">
    <Input.TextArea rows={9} value={json} onChange={e=>setJson(e.target.value)} placeholder="Вставьте JSON из ответа ChatGPT. При необходимости исправьте баллы, цитаты и пояснения перед сохранением."/>
    <Button type="primary" style={{marginTop:12}} loading={save.isPending} disabled={!json.trim()} onClick={()=>{setError('');save.mutate()}}>Проверить и сохранить черновик</Button>
   </Card>
   {error&&<Alert type="error" showIcon message={error}/>}
   <Title level={4}>История оценок</Title>
   {!data.reviews.length?<Empty description="Оценок пока нет"/>:<Collapse items={data.reviews.map(r=>({key:r.id,label:<Space wrap><Tag color={r.status==='confirmed'?'green':'orange'}>{r.status==='confirmed'?'Подтверждена':'Черновик'}</Tag><Text>{score(r.total)}</Text><Text type="secondary">{new Date(r.created_at).toLocaleString('ru-RU')}</Text></Space>,children:reviewContent(r)}))}/>}
  </Space>}
 </Drawer>
}

export function DealTrainingPanel({deal}:{deal:{id:string; title:string; bitrix_id:number}}){
 return <TrainingWorkspace deal={deal}/>
}

function TrainingWorkspace({deal}:{deal?:{id:string; title:string; bitrix_id:number}}){
 const qc=useQueryClient()
 const options=useQuery({queryKey:['training-options'],queryFn:trainingOptions})
 const [adding,setAdding]=useState(false)
 const [selected,setSelected]=useState<string|null>(null)
 const [page,setPage]=useState(1)
 const [trainer,setTrainer]=useState<string>()
 const q=useQuery({queryKey:['training-sessions',deal?.id,trainer,page],queryFn:()=>trainingSessions({deal_id:deal?.id,trainer_id:trainer,offset:(page-1)*25,limit:25})})
 const columns:ColumnsType<Training>=[
  {title:'Дата',dataIndex:'training_date',render:dateText},
  {title:'Сделка',dataIndex:'deal_title',render:(value,row)=><BitrixLink href={dealUrl(row.deal_bitrix_id)}>{value}</BitrixLink>},
  {title:'Сотрудник',dataIndex:'trainer_name'},
  {title:'Модуль',dataIndex:'module'},
  {title:'Обучение',dataIndex:'training_number'},
  {title:'',render:(_,row)=><Button onClick={()=>setSelected(row.id)}>Открыть</Button>},
 ]
 return <Space direction="vertical" style={{width:'100%'}} size={16}>
  {(q.isError||options.isError)&&<Alert type="error" message={errorText(q.error||options.error)}/>}
  <Space wrap>
   <Button type="primary" disabled={!options.data} onClick={()=>setAdding(true)}>Добавить обучение</Button>
   <Select allowClear showSearch optionFilterProp="label" placeholder="Все сотрудники" style={{width:280}} value={trainer} onChange={v=>{setTrainer(v);setPage(1)}} options={options.data?.trainers.map(u=>({value:u.id,label:u.full_name}))}/>
  </Space>
  <Table rowKey="id" columns={columns} dataSource={q.data?.items??[]} loading={q.isLoading} scroll={{x:800}} pagination={{current:page,pageSize:25,total:q.data?.total??0,onChange:setPage,showSizeChanger:false}}/>
  {adding&&options.data&&<AddTraining deal={deal} options={options.data} onCancel={()=>setAdding(false)} onAdded={item=>{setAdding(false);setSelected(item.id);void qc.invalidateQueries({queryKey:['training-sessions']})}}/>}
  {selected&&options.data&&<TrainingDetail key={selected} id={selected} options={options.data} onClose={()=>setSelected(null)}/>}
 </Space>
}

function RubricEditor({options}:{options:TrainingOptions}){
 const qc=useQueryClient()
 const [title,setTitle]=useState('')
 const [criteria,setCriteria]=useState(JSON.stringify(options.rubrics[0]?.criteria??[],null,2))
 const [error,setError]=useState('')
 const save=useMutation({mutationFn:()=>createTrainingRubric({title,criteria:JSON.parse(criteria) as TrainingCriterion[]}),onSuccess:()=>{setTitle('');setError('');message.success('Создана новая версия; прежние критерии и оценки сохранены');void qc.invalidateQueries({queryKey:['training-options']})},onError:e=>setError(errorText(e))})
 return <Space direction="vertical" style={{width:'100%'}}>
  <Alert type="info" message="Версии неизменяемые" description="Изменение критериев создаёт новую версию. Старые оценки не пересчитываются. Веса — целые проценты с суммой 100; коды id должны быть уникальными."/>
  <Table rowKey="id" dataSource={options.rubrics} columns={[{title:'Версия',render:(_,r)=>versionLabel(r)},{title:'Создана',dataIndex:'created_at',render:v=>new Date(v).toLocaleString('ru-RU')},{title:'',render:(_,r)=><Button onClick={()=>{setCriteria(JSON.stringify(r.criteria,null,2));setTitle(`${r.title} — новая версия`)}}>Взять за основу</Button>}]} pagination={false}/>
  <Input value={title} onChange={e=>setTitle(e.target.value)} maxLength={200} placeholder="Название новой версии"/>
  <Input.TextArea rows={18} value={criteria} onChange={e=>setCriteria(e.target.value)}/>
  {error&&<Alert type="error" message={error}/>}
  <Button type="primary" loading={save.isPending} disabled={!title.trim()} onClick={()=>save.mutate()}>Создать новую версию критериев</Button>
 </Space>
}

function Rating({options}:{options:TrainingOptions}){
 const [rubricId,setRubricId]=useState(options.rubrics[0]?.id)
 const [from,setFrom]=useState('')
 const [to,setTo]=useState('')
 const query={rubric_id:rubricId,date_from:from||undefined,date_to:to||undefined}
 const q=useQuery({queryKey:['training-rating',query],queryFn:()=>trainingRating(query),enabled:Boolean(rubricId)})
 return <Space direction="vertical" style={{width:'100%'}}>
  <Alert type="info" showIcon message="Только подтверждённые оценки" description="Период — по фактической дате обучения. Сравнение внутри одного модуля, номера обучения и версии критериев; средний балл по полным оценкам. Для каждого обучения используется последняя подтверждённая оценка выбранной версии. Не является автоматическим основанием для премии."/>
  <Space wrap><Select value={rubricId} style={{minWidth:300}} onChange={setRubricId} options={options.rubrics.map(r=>({value:r.id,label:versionLabel(r)}))}/><Text>С</Text><Input type="date" value={from} onChange={e=>setFrom(e.target.value)}/><Text>По</Text><Input type="date" value={to} onChange={e=>setTo(e.target.value)}/><Button onClick={()=>{setFrom('');setTo('')}}>Весь период</Button></Space>
  {q.isError&&<Alert type="error" message={errorText(q.error)}/>}
  {q.data&&<Paragraph type="secondary">{q.data.rubric.criteria.map(c=>`${c.title}: ${c.weight}%`).join(' · ')}</Paragraph>}
  <Table rowKey={r=>`${r.trainer_id}-${r.module}-${r.training_number}`} dataSource={q.data?.items??[]} loading={q.isLoading} pagination={false} scroll={{x:850}} columns={[
   {title:'Модуль',dataIndex:'module'},{title:'Обучение',dataIndex:'training_number'},
   {title:'Сотрудник',dataIndex:'trainer_name'},{title:'Полных оценок',dataIndex:'count'},
   {title:'Средний балл',dataIndex:'average',render:score},{title:'Неполных оценок (вне среднего)',dataIndex:'unscored'},
  ]}/>
 </Space>
}

export default function TrainingQualityPage(){
 const options=useQuery({queryKey:['training-options'],queryFn:trainingOptions})
 return <Space direction="vertical" size={20} style={{width:'100%'}}>
  <Title level={2}>Качество обучений</Title>
  <Text type="secondary">Только для администратора. DOCX хранится в приложении; работа с ChatGPT — вручную.</Text>
  {options.isError&&<Alert type="error" message={errorText(options.error)}/>}
  <Tabs items={[
   {key:'trainings',label:'Обучения и транскрибации',children:<TrainingWorkspace/>},
   {key:'rating',label:'Рейтинг сотрудников',children:options.data?<Rating options={options.data}/>:<Card loading/>},
   {key:'rubrics',label:'Критерии оценки',children:options.data?<RubricEditor options={options.data}/>:<Card loading/>},
  ]}/>
 </Space>
}
