import { CheckCircleOutlined, DeleteOutlined, PlusOutlined } from '@ant-design/icons'
import { Alert, Button, Card, Empty, Form, Input, Modal, Progress, Select, Space, Tag, Typography, message } from 'antd'
import { useMutation, useQuery, useQueryClient } from '@tanstack/react-query'
import { useEffect, useState } from 'react'
import { assignOnboarding, getEmployees, getMyOnboarding, getOnboardings, getOnboardingTemplate, saveOnboardingTemplate, updateOnboardingTask } from './api'
import type { OnboardingAssignment, OnboardingPlanSection, OnboardingTask } from './types'

const { Title, Text } = Typography

function progress(assignment: OnboardingAssignment) {
  const done = assignment.tasks.filter(task => task.is_completed).length
  return { done, total: assignment.tasks.length, percent: assignment.tasks.length ? Math.round(done / assignment.tasks.length * 100) : 0 }
}

function Plan({ assignment, editable }: { assignment: OnboardingAssignment, editable: boolean }) {
  const queryClient = useQueryClient()
  const [task, setTask] = useState<OnboardingTask | null>(null)
  const [form] = Form.useForm<{ comment: string }>()
  const save = useMutation({
    mutationFn: ({ id, comment }: { id: string, comment: string }) => updateOnboardingTask(id, true, comment),
    onSuccess: () => {
      message.success('Отметка о выполнении сохранена')
      form.resetFields(); setTask(null)
      void queryClient.invalidateQueries({ queryKey: ['my-onboarding'] })
      void queryClient.invalidateQueries({ queryKey: ['onboardings'] })
    },
    onError: (error: any) => message.error(error.response?.data?.detail ?? 'Не удалось сохранить отметку'),
  })
  const grouped = assignment.tasks.reduce<Record<string, OnboardingTask[]>>((result, item) => {
    (result[item.section] ??= []).push(item); return result
  }, {})
  const current = progress(assignment)
  return <Card title={editable ? 'Мой план адаптации' : assignment.employee_name} extra={<Space><Text type="secondary">Назначил: {assignment.assigned_by_name}</Text><Tag color="blue">{current.done}/{current.total}</Tag></Space>}>
    <Progress percent={current.percent} status={current.percent === 100 ? 'success' : 'active'} style={{ marginBottom: 20 }} />
    {Object.entries(grouped).map(([section, tasks]) => <div key={section} style={{ marginBottom: 22 }}>
      <Title level={4}>{section}</Title>
      {tasks[0]?.section_details && <Text type="secondary" style={{ whiteSpace: 'pre-wrap', display: 'block', marginBottom: 12 }}>{tasks[0].section_details}</Text>}
      <Space direction="vertical" size={12} style={{ width: '100%' }}>
        {tasks.map(item => <Card key={item.id} size="small" style={{ background: item.is_completed ? '#f6ffed' : undefined }}>
          <Space align="start" style={{ width: '100%', justifyContent: 'space-between' }}>
            <div><Text strong={item.is_completed}>{item.title}</Text>{item.details && <><br /><Text type="secondary" style={{ whiteSpace: 'pre-wrap' }}>{item.details}</Text></>}{item.is_completed && <><br /><Text type="secondary">Итог: {item.comment}</Text></>}</div>
            {item.is_completed ? <Tag color="green" icon={<CheckCircleOutlined />}>Выполнено</Tag> : editable ? <Button type="primary" size="small" onClick={() => { form.resetFields(); setTask(item) }}>Отметить</Button> : <Tag>В плане</Tag>}
          </Space>
        </Card>)}
      </Space>
    </div>)}
    <Modal open={Boolean(task)} title={task?.title} okText="Сохранить отметку" confirmLoading={save.isPending} onCancel={() => setTask(null)} onOk={() => form.validateFields().then(values => task && save.mutate({ id: task.id, comment: values.comment }))}>
      <Form form={form} layout="vertical"><Form.Item name="comment" label="Итог выполнения" rules={[{ required: true, whitespace: true, message: 'Укажите, что сделано' }]}><Input.TextArea rows={4} placeholder="Опишите результат работы" /></Form.Item></Form>
    </Modal>
  </Card>
}

export default function OnboardingPage({ isAdmin }: { isAdmin: boolean }) {
  const queryClient = useQueryClient()
  const mine = useQuery({ queryKey: ['my-onboarding'], queryFn: getMyOnboarding, enabled: !isAdmin })
  const all = useQuery({ queryKey: ['onboardings'], queryFn: getOnboardings, enabled: isAdmin })
  const employees = useQuery({ queryKey: ['employees'], queryFn: getEmployees, enabled: isAdmin })
  const template = useQuery({ queryKey: ['onboarding-template'], queryFn: getOnboardingTemplate, enabled: isAdmin })
  const [employeeId, setEmployeeId] = useState<string>()
  const [templateForm] = Form.useForm<{ sections: OnboardingPlanSection[] }>()
  useEffect(() => { if (template.data) templateForm.setFieldsValue({ sections: template.data }) }, [template.data, templateForm])
  const assign = useMutation({
    mutationFn: assignOnboarding,
    onSuccess: () => { message.success('Адаптация назначена'); setEmployeeId(undefined); void queryClient.invalidateQueries({ queryKey: ['onboardings'] }) },
    onError: (error: any) => message.error(error.response?.data?.detail ?? 'Не удалось назначить адаптацию'),
  })
  const saveTemplate = useMutation({
    mutationFn: (values: { sections: OnboardingPlanSection[] }) => saveOnboardingTemplate(values.sections),
    onSuccess: () => { message.success('Структура адаптации сохранена'); void queryClient.invalidateQueries({ queryKey: ['onboarding-template'] }) },
    onError: (error: any) => message.error(error.response?.data?.detail ?? 'Не удалось сохранить структуру'),
  })
  if (!isAdmin) {
    if (mine.isLoading) return <Card loading />
    return <Space direction="vertical" size={24} style={{ width: '100%' }}><Title level={2}>Адаптация</Title>{mine.data ? <Plan assignment={mine.data} editable /> : <Empty description="Адаптация пока не назначена" />}</Space>
  }
  const assigned = new Set((all.data ?? []).map(item => item.employee_id))
  const options = (employees.data ?? []).filter(employee => employee.is_active && !employee.is_admin && !assigned.has(employee.id)).map(employee => ({ value: employee.id, label: employee.full_name }))
  return <Space direction="vertical" size={24} style={{ width: '100%' }}>
    <Title level={2}>Адаптация сотрудников</Title>
    <Card title="Структура и инструкции" loading={template.isLoading}>
      <Text type="secondary">Этот шаблон применяется к новым назначениям. Уже назначенные планы не меняются.</Text>
      <Form form={templateForm} layout="vertical" style={{ marginTop: 16 }} onFinish={values => saveTemplate.mutate(values)}>
        <Form.List name="sections">{(sectionFields, { add: addSection, remove: removeSection }) => <Space direction="vertical" size={16} style={{ width: '100%' }}>
          {sectionFields.map(section => <Card key={section.key} size="small" title={`Раздел ${section.name + 1}`} extra={<Button danger type="text" icon={<DeleteOutlined />} onClick={() => removeSection(section.name)}>Удалить раздел</Button>}>
            <Form.Item name={[section.name, 'title']} label="Название раздела" rules={[{ required: true, whitespace: true, message: 'Укажите название раздела' }]}><Input /></Form.Item>
            <Form.Item name={[section.name, 'details']} label="Инструкция к разделу"><Input.TextArea rows={3} placeholder="Что сотрудник должен изучить или подготовить в этом модуле" /></Form.Item>
            <Form.List name={[section.name, 'tasks']}>{(taskFields, { add: addTask, remove: removeTask }) => <Space direction="vertical" size={8} style={{ width: '100%' }}>
              <Text strong>Пункты раздела</Text>
              {taskFields.map(task => <Card key={task.key} size="small"><Form.Item name={[task.name, 'title']} label="Название пункта" rules={[{ required: true, whitespace: true, message: 'Укажите название пункта' }]}><Input /></Form.Item><Form.Item name={[task.name, 'details']} label="Подробная инструкция"><Input.TextArea rows={2} placeholder="Конкретные действия, ссылки, ожидаемый результат" /></Form.Item><Button danger type="link" icon={<DeleteOutlined />} onClick={() => removeTask(task.name)}>Удалить пункт</Button></Card>)}
              <Button icon={<PlusOutlined />} onClick={() => addTask({ title: '', details: null })}>Добавить пункт</Button>
            </Space>}</Form.List>
          </Card>)}
          <Button icon={<PlusOutlined />} onClick={() => addSection({ title: '', details: null, tasks: [{ title: '', details: null }] })}>Добавить раздел</Button>
        </Space>}</Form.List>
        <Button type="primary" htmlType="submit" loading={saveTemplate.isPending} style={{ marginTop: 16 }}>Сохранить структуру</Button>
      </Form>
    </Card>
    <Card title="Назначить адаптацию"><Space wrap><Select placeholder="Выберите сотрудника" value={employeeId} onChange={setEmployeeId} options={options} loading={employees.isLoading} style={{ minWidth: 300 }} /><Button type="primary" disabled={!employeeId} loading={assign.isPending} onClick={() => employeeId && assign.mutate(employeeId)}>Назначить</Button></Space></Card>
    {all.isLoading ? <Card loading /> : all.data?.length ? all.data.map(item => <Plan key={item.id} assignment={item} editable={false} />) : <Alert type="info" message="Адаптация пока никому не назначена" />}
  </Space>
}
