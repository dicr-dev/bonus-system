import {Button,Card,Col,Form,Input,InputNumber,Row,Space,Tabs,Typography,message} from 'antd'
import {useMutation,useQuery,useQueryClient} from '@tanstack/react-query'
import {useEffect,useMemo} from 'react'

import {createRule,getAppSettings,getRules,saveAppSettings} from './api'
import type {AppSettings,RuleConfig} from './types'

const {Title,Text}=Typography

const defaultRules:RuleConfig={
  divider:2.5,
  tech_integration_rate:0.5,
  sales_rate:0.1,
  support_hour_rate:200,
  training_bonus:2000,
  cr_start_fixed:10000,
  implementation_thresholds:[
    {from:0,rate:0.10},{from:100000,rate:0.11},{from:150000,rate:0.12},{from:175000,rate:0.13},{from:200000,rate:0.15}
  ],
  current_clients_tiers:[
    {from:1,to:99,bonus:1000},{from:100,to:299,bonus:2000},{from:300,to:499,bonus:3000},{from:500,to:null,bonus:4000}
  ]
}

function BitrixSettings(){
 const [form]=Form.useForm<any>()
 const qc=useQueryClient()
 const q=useQuery({queryKey:['app-settings'],queryFn:getAppSettings})
 useEffect(()=>{if(q.data)form.setFieldsValue({...q.data,cr_start_boolean_fields_text:q.data.cr_start_boolean_fields.join(', ')})},[q.data,form])
 const save=useMutation({
  mutationFn:(v:AppSettings)=>saveAppSettings(v),
  onSuccess:async()=>{message.success('Настройки Bitrix24 сохранены');await qc.invalidateQueries({queryKey:['app-settings']})}
 })
 if(q.isLoading)return <Card loading/>
 return <Form form={form} layout="vertical" onFinish={(v:any)=>{const {cr_start_boolean_fields_text,...rest}=v;save.mutate({...rest,cr_start_boolean_fields:String(cr_start_boolean_fields_text||'').split(',').map(x=>x.trim()).filter(Boolean)} as AppSettings)}}>
  <Card title="Воронки Bitrix24">
   <Row gutter={16}>
    <Col xs={24} md={6}><Form.Item name="tech_integration_category_id" label="Техинтеграция: ID воронки"><InputNumber style={{width:'100%'}}/></Form.Item></Col>
    <Col xs={24} md={6}><Form.Item name="implementation_category_id" label="Внедрение: ID воронки"><InputNumber style={{width:'100%'}}/></Form.Item></Col>
    <Col xs={24} md={6}><Form.Item name="cr_start_category_id" label="CR Start: ID воронки"><InputNumber style={{width:'100%'}}/></Form.Item></Col>
    <Col xs={24} md={6}><Form.Item name="support_category_id" label="Сопровождение: ID воронки"><InputNumber style={{width:'100%'}}/></Form.Item></Col>
   </Row>
  </Card>
  <Card title="Поля сделок" style={{marginTop:16}}>
   <Row gutter={16}>
    <Col xs={24} md={12}><Form.Item name="field_monthly_amount" label="Сумма оплаты в месяц"><Input/></Form.Item></Col>
    <Col xs={24} md={12}><Form.Item name="field_integration_amount" label="Сумма за интеграцию"><Input placeholder="ufCrm_..."/></Form.Item></Col>
    <Col xs={24} md={12}><Form.Item name="field_machines_count" label="Количество машин"><Input/></Form.Item></Col>
    <Col xs={24} md={12}><Form.Item name="field_integration_1c" label="Интеграция 1С"><Input/></Form.Item></Col>
    <Col xs={24} md={12}><Form.Item name="field_implementation_responsible_id" label="Ответственный за внедрение"><Input/></Form.Item></Col>
    <Col xs={24} md={12}><Form.Item name="field_sales_bonus_user_id" label="Сотрудник, получающий бонус за продажу"><Input/></Form.Item></Col>
    <Col xs={24} md={12}><Form.Item name="field_source_deal_id" label="ID сделки-источника"><Input/></Form.Item></Col>
    <Col xs={24} md={12}><Form.Item name="field_module" label="Направление (Модуль)"><Input/></Form.Item></Col>
    <Col xs={24} md={12}><Form.Item name="field_client_works" label="Клиент работает (если используется отдельное поле)"><Input/></Form.Item></Col>
    <Col xs={24} md={12}><Form.Item name="task_training_bonus_field" label="Поле задачи «Бонус за обучение»"><Input/></Form.Item></Col>
    <Col span={24}><Form.Item name="cr_start_boolean_fields_text" label="Поля CR Start"><Input.TextArea rows={3} placeholder="ufCrm_..., ufCrm_..."/></Form.Item></Col>
   </Row>
  </Card>
  <Button type="primary" htmlType="submit" loading={save.isPending} style={{marginTop:16}}>Сохранить настройки Bitrix24</Button>
 </Form>
}

function BonusRules(){
 const [form]=Form.useForm()
 const q=useQuery({queryKey:['rules'],queryFn:getRules})
 const latest=useMemo(()=>{
  const raw=q.data?.[0]?.config_json
  if(!raw)return defaultRules
  try{return {...defaultRules,...JSON.parse(raw)} as RuleConfig}catch{return defaultRules}
 },[q.data])
 useEffect(()=>{
  form.setFieldsValue({
   effective_from:new Date().toISOString().slice(0,10),comment:'',
   divider:Number(latest.divider),tech_integration_rate:Number(latest.tech_integration_rate)*100,
   sales_rate:Number(latest.sales_rate)*100,support_hour_rate:Number(latest.support_hour_rate),
   training_bonus:Number(latest.training_bonus),cr_start_fixed:Number(latest.cr_start_fixed)
  })
 },[latest,form])
 const save=useMutation({mutationFn:async(v:any)=>{
  const config:RuleConfig={
   ...latest,
   divider:v.divider,
   tech_integration_rate:Number(v.tech_integration_rate)/100,
   sales_rate:Number(v.sales_rate)/100,
   support_hour_rate:v.support_hour_rate,
   training_bonus:v.training_bonus,
   cr_start_fixed:v.cr_start_fixed,
   implementation_thresholds:JSON.parse(v.implementation_thresholds_json),
   current_clients_tiers:JSON.parse(v.current_clients_tiers_json)
  }
  return createRule(v.effective_from,config,v.comment||'')
 },onSuccess:()=>message.success('Создана новая версия правил')})
 return <Form form={form} layout="vertical" onFinish={(v:any)=>save.mutate(v)}>
  <Card title="Основные правила KPI">
   <Row gutter={16}>
    <Col xs={24} md={8}><Form.Item name="effective_from" label="Действует с" rules={[{required:true}]}><Input type="date"/></Form.Item></Col>
    <Col xs={24} md={8}><Form.Item name="divider" label="Делитель KPI"><InputNumber min={0.01} step={0.1} style={{width:'100%'}}/></Form.Item></Col>
    <Col xs={24} md={8}><Form.Item name="tech_integration_rate" label="Техинтеграция, %"><InputNumber min={0} max={100} style={{width:'100%'}}/></Form.Item></Col>
    <Col xs={24} md={8}><Form.Item name="sales_rate" label="Продажи, %"><InputNumber min={0} max={100} style={{width:'100%'}}/></Form.Item></Col>
    <Col xs={24} md={8}><Form.Item name="support_hour_rate" label="Стоимость часа, ₽"><InputNumber min={0} style={{width:'100%'}}/></Form.Item></Col>
    <Col xs={24} md={8}><Form.Item name="training_bonus" label="Обучение, ₽"><InputNumber min={0} style={{width:'100%'}}/></Form.Item></Col>
    <Col xs={24} md={8}><Form.Item name="cr_start_fixed" label="CR Start, ₽"><InputNumber min={0} style={{width:'100%'}}/></Form.Item></Col>
    <Col xs={24} md={16}><Form.Item name="comment" label="Комментарий к версии"><Input/></Form.Item></Col>
    <Col xs={24} md={12}><Form.Item name="implementation_thresholds_json" label="Шкала внедрения (JSON)" rules={[{required:true}]}><Input.TextArea rows={10}/></Form.Item></Col>
    <Col xs={24} md={12}><Form.Item name="current_clients_tiers_json" label="Шкала текущих клиентов (JSON)" rules={[{required:true}]}><Input.TextArea rows={10}/></Form.Item></Col>
   </Row>
   <Text type="secondary">Сохранение создаёт новую версию правил. Старые расчёты продолжают хранить снимок прежней версии.</Text>
  </Card>
  <Button type="primary" htmlType="submit" loading={save.isPending} style={{marginTop:16}}>Создать новую версию правил</Button>
 </Form>
}

export default function SettingsPage(){
 return <Space direction="vertical" size={20} style={{width:'100%'}}>
  <Title level={2}>Настройки</Title>
  <Tabs items={[
   {key:'bitrix',label:'Bitrix24',children:<BitrixSettings/>},
   {key:'bonus',label:'KPI и бонусы',children:<BonusRules/>}
  ]}/>
 </Space>
}
