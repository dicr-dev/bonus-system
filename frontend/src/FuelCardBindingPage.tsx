import { Alert, Button, Card, Descriptions, Input, Space, Table, Tag, Typography, message } from 'antd'
import { useMutation } from '@tanstack/react-query'
import { useState } from 'react'
import { applyFuelCardBindings, previewFuelCardBindings } from './api'

type Item = { row: number; number: string; brand: string; plate: string; car_id: number | null; error: string | null }
type Preview = { total: number; ready: number; errors: number; items: Item[] }
const errorText = (error: any) => error?.response?.data?.detail || 'Операция не выполнена.'
const keyOf = (item: Pick<Item, 'row' | 'brand' | 'number'>) => `${item.row}:${item.brand}:${item.number}`

export default function FuelCardBindingPage() {
  const [importFile, setImportFile] = useState<File | null>(null)
  const [token, setToken] = useState('')
  const [preview, setPreview] = useState<Preview | null>(null)
  const [selectedKeys, setSelectedKeys] = useState<string[]>([])
  const [appliedKeys, setAppliedKeys] = useState<string[]>([])
  const previewRequest = useMutation({
    mutationFn: previewFuelCardBindings,
    onSuccess: data => { setPreview(data); setAppliedKeys([]); setSelectedKeys(data.items.filter((item: Item) => !item.error).slice(0, 10).map(keyOf)) },
    onError: error => message.error(errorText(error)),
  })
  const applyRequest = useMutation({
    mutationFn: ({ file, token, selected }: { file: File; token: string; selected: string[] }) => applyFuelCardBindings(file, token, selected, true),
    onSuccess: data => { const completed = data.items.filter((item: any) => item.status === 'applied').map((item: any) => keyOf(item)); setAppliedKeys(keys => [...keys, ...completed]); setSelectedKeys([]); setToken(''); message.success(`Привязано карт: ${data.applied}. Ошибок: ${data.failed}.`) },
    onError: error => message.error(errorText(error)),
  })
  const validate = () => {
    if (!importFile) { message.warning('Загрузите Excel-файл.'); return }
    previewRequest.mutate(importFile)
  }
  const apply = () => {
    if (!importFile || !preview) return
    if (!token.trim()) { message.warning('Укажите временный токен CargoRun.'); return }
    if (!selectedKeys.length) { message.warning('Выберите карты для привязки.'); return }
    applyRequest.mutate({ file: importFile, token, selected: selectedKeys })
  }
  return <Space direction="vertical" size={24} style={{ width: '100%' }}>
    <Typography.Title level={2}>Привязка топливных карт</Typography.Title>
    <Alert type="warning" showIcon message="Временный токен не сохраняется" description="Токен передаётся только в CargoRun при применении и не записывается в базу, логи или историю операций." />
    <Card title="Единый Excel-файл">
      <Typography.Paragraph>Одна строка — одно ТС. Нужны колонки <Typography.Text code>госномер</Typography.Text> и <Typography.Text code>id</Typography.Text>, а также брендовые колонки карт: <Typography.Text code>ТАИФ</Typography.Text>, <Typography.Text code>Делкойл</Typography.Text>, <Typography.Text code>Газпромнефть</Typography.Text>, <Typography.Text code>Роснефть</Typography.Text>. Пустые брендовые ячейки пропускаются.</Typography.Paragraph>
      <input type="file" accept=".xlsx" onChange={event => { setImportFile(event.target.files?.[0] ?? null); setPreview(null); setSelectedKeys([]); setAppliedKeys([]) }} />
      <div style={{ marginTop: 16 }}><Button type="primary" onClick={validate} loading={previewRequest.isPending}>Проверить сопоставление</Button></div>
    </Card>
    {preview && <Card title="Проверка перед применением" extra={<Tag color={preview.errors ? 'orange' : 'green'}>{preview.ready} готово из {preview.total}</Tag>}>
      <Descriptions size="small" column={3} items={[{ key: 'total', label: 'Найдено карт', children: preview.total }, { key: 'ready', label: 'Будет применено', children: preview.ready }, { key: 'errors', label: 'Исключено', children: preview.errors }]} />
      <Typography.Paragraph type="secondary" style={{ marginTop: 16 }}>Для первого запуска уже выбраны первые 10 корректных карт. Отметьте нужные строки вручную; успешно применённые карты останутся в таблице и не будут доступны для повторного выбора.</Typography.Paragraph>
      <Table size="small" rowKey={keyOf} rowSelection={{ selectedRowKeys: selectedKeys, onChange: keys => setSelectedKeys(keys.map(String)), getCheckboxProps: item => ({ disabled: Boolean(item.error) || appliedKeys.includes(keyOf(item)) }) }} dataSource={preview.items} pagination={false} style={{ marginTop: 16 }} columns={[{ title: 'Строка', dataIndex: 'row', width: 80 }, { title: 'Карта', dataIndex: 'number' }, { title: 'Бренд', dataIndex: 'brand' }, { title: 'Госномер', dataIndex: 'plate' }, { title: 'ID ТС', dataIndex: 'car_id' }, { title: 'Статус', render: (_, item: Item) => item.error ? <Tag color="red">{item.error}</Tag> : appliedKeys.includes(keyOf(item)) ? <Tag color="blue">Привязана</Tag> : <Tag color="green">Готово</Tag> }]} scroll={{ x: 800 }} />
      {preview.ready > 0 && <Space direction="vertical" style={{ marginTop: 20, width: '100%' }}><Input.Password value={token} onChange={event => setToken(event.target.value)} autoComplete="off" placeholder="Временный токен CargoRun" aria-label="Временный токен CargoRun" /><Button danger type="primary" loading={applyRequest.isPending} disabled={!selectedKeys.length} onClick={apply}>Подтверждаю: привязать {selectedKeys.length} карт</Button></Space>}
    </Card>}
  </Space>
}
