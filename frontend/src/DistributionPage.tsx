import {Alert, Button, Card, Collapse, Empty, Space, Table, Tag, Typography, message} from 'antd'
import type {ColumnsType} from 'antd/es/table'
import {useMutation, useQuery, useQueryClient} from '@tanstack/react-query'
import {assignDistribution, getDistributionPending} from './api'
import {BitrixLink, dealUrl} from './BitrixLink'
import type {DistributionDeal, DistributionCandidate, DistributionWorkDeal} from './types'

const {Title, Text} = Typography
const funnelName: Record<string, string> = {tech_integration: 'Техинтеграция', implementation: 'Внедрение'}
const money = (value:number|string) => new Intl.NumberFormat('ru-RU', {style:'currency',currency:'RUB'}).format(Number(value))

function WorkDeals({rows}:{rows:DistributionWorkDeal[]}) {
 const columns:ColumnsType<DistributionWorkDeal> = [
  {title:'Сделка',render:(_, row)=><BitrixLink href={dealUrl(row.bitrix_id)}>{row.bitrix_id} — {row.title}</BitrixLink>},
  {title:'Воронка',dataIndex:'funnel',render:value=>funnelName[value]??value},
  {title:'Сумма сделки',dataIndex:'amount',align:'right',render:money},
  {title:'Машин',dataIndex:'machines_count',align:'right'},
 ]
 return <Table rowKey="bitrix_id" size="small" columns={columns} dataSource={rows} pagination={false} summary={()=> <Table.Summary.Row><Table.Summary.Cell index={0} colSpan={2}>Итого: {rows.length} сделок</Table.Summary.Cell><Table.Summary.Cell index={2} align="right">{money(rows.reduce((sum,row)=>sum+Number(row.amount),0))}</Table.Summary.Cell><Table.Summary.Cell index={3} align="right">{rows.reduce((sum,row)=>sum+row.machines_count,0)}</Table.Summary.Cell></Table.Summary.Row>}/>
}

function Candidates({deal}: {deal: DistributionDeal}) {
 const queryClient = useQueryClient()
 const assign = useMutation({mutationFn: (userId: string) => assignDistribution(deal.id, userId), onSuccess: () => { message.success('Сотрудник назначен в Bitrix'); queryClient.invalidateQueries({queryKey: ['distribution-pending']}) }, onError: () => message.error('Не удалось назначить сотрудника. Проверьте подключение к Bitrix.')})
 const columns: ColumnsType<DistributionCandidate> = [
  {title: 'Сотрудник', dataIndex: 'full_name'}, {title: 'Активных этой компании', dataIndex: 'company_active_deals', align: 'right'}, {title: 'Все активные', dataIndex: 'active_deals', align: 'right'}, {title: 'Активные с интеграцией', dataIndex: 'active_integration_deals', align: 'right'}, {title: 'Причина рекомендации', dataIndex: 'reason'},
  {title: '', width: 120, render: (_, row) => <Button type="primary" size="small" loading={assign.isPending} onClick={() => assign.mutate(row.user_id)}>Назначить</Button>},
 ]
 return <Table rowKey="user_id" size="small" columns={columns} dataSource={deal.candidates} pagination={false} expandable={{expandedRowRender:row=><Collapse items={[{key:'active',label:`Активные сделки (${row.deals.length})`,children:<WorkDeals rows={row.deals}/>},{key:'integration',label:`Активные с интеграцией (${row.active_integration_deals})`,children:<WorkDeals rows={row.deals.filter(item=>item.integration_1c)}/>} ]}/>}}/>
}

export default function DistributionPage() {
 const pending = useQuery({queryKey: ['distribution-pending'], queryFn: getDistributionPending})
 const columns: ColumnsType<DistributionDeal> = [
  {title: 'Сделка', dataIndex: 'title', render: (value, row) => <BitrixLink href={dealUrl(row.bitrix_id)}>{row.bitrix_id} — {value}</BitrixLink>}, {title: 'Воронка', dataIndex: 'funnel', render: value => funnelName[value] ?? value}, {title: 'Компания', dataIndex: 'company_name', render: value => value || 'Не указана'}, {title: 'Интеграция', dataIndex: 'integration_1c', render: value => value ? <Tag color="blue">Да</Tag> : 'Нет'},
 ]
 return <Space direction="vertical" size={20} style={{width: '100%'}}><Title level={2}>Помощник назначения новых сделок на сотрудника</Title><Alert type="info" showIcon message="CR Start распределяется автоматически и в помощнике не показывается." description="Сначала сотрудник с активными сделками этой компании; затем минимум активных интеграций для сделки с интеграцией или минимум всех активных сделок."/>{pending.isError && <Alert type="error" showIcon message="Не удалось загрузить сделки для назначения"/>}{!pending.isLoading && !pending.data?.items.length && <Card><Empty description="Нет активных сделок без ответственного за внедрение"/></Card>}{pending.data?.items.map(deal => <Card key={deal.id} title={<Text strong>{deal.bitrix_id} — {deal.title}</Text>}><Table rowKey="id" size="small" columns={columns} dataSource={[deal]} pagination={false}/><div style={{marginTop: 16}}><Candidates deal={deal}/></div></Card>)}</Space>
}
