import {
  CheckCircleOutlined,
  CloudSyncOutlined,
  DashboardOutlined,
  DatabaseOutlined,
  DollarOutlined,
  ReloadOutlined,
  TeamOutlined,
  TruckOutlined,
} from '@ant-design/icons'
import {
  Alert,
  Button,
  Card,
  Col,
  Layout,
  Menu,
  Progress,
  Row,
  Space,
  Statistic,
  Table,
  Tag,
  Typography,
  message,
} from 'antd'
import type { ColumnsType } from 'antd/es/table'
import {
  useMutation,
  useQuery,
  useQueryClient,
} from '@tanstack/react-query'
import { useEffect, useMemo, useState } from 'react'

import {
  getDashboard,
  getDepartmentDeals,
  getSyncJob,
  getSyncStatus,
  startDealsSync,
} from './api'
import type {
  Deal,
  FunnelSummary,
  ResponsibleSummary,
  SyncJob,
} from './types'

const { Header, Content, Sider } = Layout
const { Title, Text } = Typography

const FUNNEL_NAMES: Record<string, string> = {
  tech_integration: 'Тех интеграция',
  implementation: 'Внедрение',
  cr_start: 'CR Start',
  support: 'Сопровождение',
}

function funnelName(value: string): string {
  return FUNNEL_NAMES[value] ?? value
}

function formatMoney(value: string | number): string {
  const number = Number(value || 0)
  return new Intl.NumberFormat('ru-RU', {
    style: 'currency',
    currency: 'RUB',
    maximumFractionDigits: 0,
  }).format(number)
}

function formatNumber(value: number): string {
  return new Intl.NumberFormat('ru-RU').format(value)
}

function formatDate(value: string | null | undefined): string {
  if (!value) return '—'
  const date = new Date(value)
  if (Number.isNaN(date.getTime())) return value

  return new Intl.DateTimeFormat('ru-RU', {
    dateStyle: 'medium',
    timeStyle: 'short',
  }).format(date)
}

function DashboardPage() {
  const dashboard = useQuery({
    queryKey: ['dashboard'],
    queryFn: getDashboard,
    refetchInterval: 60000,
  })

  if (dashboard.isLoading) {
    return <Card loading />
  }

  if (dashboard.isError || !dashboard.data) {
    return (
      <Alert
        type="error"
        showIcon
        message="Не удалось загрузить дашборд"
        description="Проверьте доступность backend API."
      />
    )
  }

  const data = dashboard.data

  const funnelColumns: ColumnsType<FunnelSummary> = [
    {
      title: 'Воронка',
      dataIndex: 'funnel',
      render: (value: string) => <strong>{funnelName(value)}</strong>,
    },
    {
      title: 'В работе',
      dataIndex: 'active_deals',
      align: 'right',
      render: formatNumber,
      sorter: (a, b) => a.active_deals - b.active_deals,
    },
    {
      title: 'Оплата в месяц',
      dataIndex: 'monthly_amount',
      align: 'right',
      render: formatMoney,
      sorter: (a, b) => Number(a.monthly_amount) - Number(b.monthly_amount),
    },
    {
      title: 'Машин',
      dataIndex: 'machines_count',
      align: 'right',
      render: formatNumber,
      sorter: (a, b) => a.machines_count - b.machines_count,
    },
    {
      title: 'Интеграция 1С',
      dataIndex: 'integration_1c_deals',
      align: 'right',
      render: (value: number) => (
        <Tag color="green">{formatNumber(value)}</Tag>
      ),
    },
  ]

  const responsibleColumns: ColumnsType<ResponsibleSummary> = [
    {
      title: 'Ответственный',
      dataIndex: 'full_name',
      render: (value: string) => <strong>{value}</strong>,
    },
    {
      title: 'Сделок в работе',
      dataIndex: 'active_deals',
      align: 'right',
      sorter: (a, b) => a.active_deals - b.active_deals,
    },
    {
      title: 'Оплата в месяц',
      dataIndex: 'monthly_amount',
      align: 'right',
      render: formatMoney,
      sorter: (a, b) => Number(a.monthly_amount) - Number(b.monthly_amount),
    },
    {
      title: 'Машин',
      dataIndex: 'machines_count',
      align: 'right',
      render: formatNumber,
      sorter: (a, b) => a.machines_count - b.machines_count,
    },
  ]

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div>
        <Title level={2} style={{ marginBottom: 4 }}>Дашборд</Title>
        <Text type="secondary">Текущие показатели по активным сделкам Bitrix24</Text>
      </div>

      <Row gutter={[16, 16]}>
        <Col xs={24} sm={12} xl={6}>
          <Card className="metric-card">
            <Statistic
              title="Сделок в работе"
              value={data.active_deals}
              prefix={<DatabaseOutlined />}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} xl={6}>
          <Card className="metric-card">
            <Statistic
              title="Оплата в месяц"
              value={Number(data.monthly_amount)}
              prefix={<DollarOutlined />}
              formatter={(value) => formatMoney(Number(value))}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} xl={6}>
          <Card className="metric-card">
            <Statistic
              title="Количество машин"
              value={data.machines_count}
              prefix={<TruckOutlined />}
            />
          </Card>
        </Col>

        <Col xs={24} sm={12} xl={6}>
          <Card className="metric-card">
            <Statistic
              title="С интеграцией 1С"
              value={data.integration_1c_deals}
              prefix={<CheckCircleOutlined />}
            />
          </Card>
        </Col>
      </Row>

      <Card title="Воронки" className="dashboard-card">
        <Table
          rowKey="funnel"
          columns={funnelColumns}
          dataSource={data.funnels}
          pagination={false}
          scroll={{ x: 700 }}
        />
      </Card>

      <Card
        title={
          <Space>
            <TeamOutlined />
            <span>Ответственные</span>
          </Space>
        }
        className="dashboard-card"
      >
        <Table
          rowKey="user_id"
          columns={responsibleColumns}
          dataSource={data.responsibles}
          pagination={{ pageSize: 20, showSizeChanger: false }}
          scroll={{ x: 700 }}
        />
      </Card>
    </Space>
  )
}

function DealsPage() {
  const deals = useQuery({
    queryKey: ['department-deals'],
    queryFn: getDepartmentDeals,
    refetchInterval: 60000,
  })

  const columns: ColumnsType<Deal> = [
    {
      title: 'ID',
      dataIndex: 'bitrix_id',
      width: 90,
      sorter: (a, b) => a.bitrix_id - b.bitrix_id,
    },
    {
      title: 'Сделка',
      dataIndex: 'title',
      width: 320,
      render: (value: string) => (
        <Text strong>{value || 'Без названия'}</Text>
      ),
    },
    {
      title: 'Воронка',
      dataIndex: 'funnel',
      width: 170,
      filters: Object.entries(FUNNEL_NAMES).map(([value, text]) => ({
        text,
        value,
      })),
      onFilter: (value, record) => record.funnel === value,
      render: (value: string) => <Tag>{funnelName(value)}</Tag>,
    },
    {
      title: 'Сумма в месяц',
      dataIndex: 'monthly_amount',
      width: 170,
      align: 'right',
      render: formatMoney,
      sorter: (a, b) => Number(a.monthly_amount) - Number(b.monthly_amount),
    },
    {
      title: 'Машин',
      dataIndex: 'machines_count',
      width: 110,
      align: 'right',
      sorter: (a, b) => a.machines_count - b.machines_count,
    },
    {
      title: '1С',
      dataIndex: 'integration_1c',
      width: 100,
      align: 'center',
      filters: [
        { text: 'Да', value: true },
        { text: 'Нет', value: false },
      ],
      onFilter: (value, record) => record.integration_1c === value,
      render: (value: boolean) =>
        value ? <Tag color="green">Да</Tag> : <Tag>Нет</Tag>,
    },
    {
      title: 'Создана',
      dataIndex: 'created_time',
      width: 180,
      render: formatDate,
      sorter: (a, b) =>
        new Date(a.created_time ?? 0).getTime()
        - new Date(b.created_time ?? 0).getTime(),
    },
  ]

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div>
        <Title level={2} style={{ marginBottom: 4 }}>Сделки в работе</Title>
        <Text type="secondary">Все активные сделки четырёх рабочих воронок</Text>
      </div>

      {deals.isError ? (
        <Alert type="error" showIcon message="Не удалось получить сделки" />
      ) : (
        <Card>
          <Table
            loading={deals.isLoading}
            rowKey="id"
            columns={columns}
            dataSource={deals.data ?? []}
            pagination={{
              defaultPageSize: 25,
              showSizeChanger: true,
              pageSizeOptions: [25, 50, 100],
              showTotal: (total) => `Всего: ${total}`,
            }}
            scroll={{ x: 1200 }}
          />
        </Card>
      )}
    </Space>
  )
}

function SyncPage() {
  const queryClient = useQueryClient()
  const [jobId, setJobId] = useState<string | null>(null)

  const syncStatus = useQuery({
    queryKey: ['sync-status'],
    queryFn: getSyncStatus,
    refetchInterval: 30000,
  })

  const syncJob = useQuery({
    queryKey: ['sync-job', jobId],
    queryFn: () => getSyncJob(jobId!),
    enabled: Boolean(jobId),
    refetchInterval: (query) => {
      const data = query.state.data as SyncJob | undefined
      if (data?.status === 'completed' || data?.status === 'failed') {
        return false
      }
      return 1500
    },
  })

  const startSync = useMutation({
    mutationFn: (full: boolean) => startDealsSync(full),

    onSuccess: (job) => {
      setJobId(job.job_id)
      message.success(
        job.full
          ? 'Полная синхронизация поставлена в очередь'
          : 'Синхронизация поставлена в очередь',
      )
    },

    onError: () => {
      message.error('Не удалось запустить синхронизацию')
    },
  })

  useEffect(() => {
    if (syncJob.data?.status === 'completed') {
      void queryClient.invalidateQueries({ queryKey: ['dashboard'] })
      void queryClient.invalidateQueries({ queryKey: ['department-deals'] })
      void queryClient.invalidateQueries({ queryKey: ['sync-status'] })
    }
  }, [syncJob.data?.status, queryClient])

  const job = syncJob.data

  const jobStatus = useMemo(() => {
    if (!job) return null

    switch (job.status) {
      case 'queued':
        return { text: 'В очереди', color: 'default' }
      case 'running':
        return { text: 'Выполняется', color: 'processing' }
      case 'completed':
        return { text: 'Завершено', color: 'success' }
      case 'failed':
        return { text: 'Ошибка', color: 'error' }
    }
  }, [job])

  return (
    <Space direction="vertical" size={24} style={{ width: '100%' }}>
      <div>
        <Title level={2} style={{ marginBottom: 4 }}>Синхронизация</Title>
        <Text type="secondary">Обновление данных из Bitrix24</Text>
      </div>

      <Card title="Состояние данных" className="dashboard-card">
        <Row gutter={[24, 20]}>
          <Col xs={24} md={12}>
            <Text type="secondary">Последняя успешная синхронизация</Text>
            <div className="sync-date">
              {formatDate(syncStatus.data?.last_success)}
            </div>
          </Col>

          <Col xs={24} md={12}>
            <Space wrap>
              <Button
                type="primary"
                size="large"
                icon={<CloudSyncOutlined />}
                loading={startSync.isPending}
                disabled={job?.status === 'running' || job?.status === 'queued'}
                onClick={() => startSync.mutate(false)}
              >
                Синхронизировать
              </Button>

              <Button
                size="large"
                icon={<ReloadOutlined />}
                loading={startSync.isPending}
                disabled={job?.status === 'running' || job?.status === 'queued'}
                onClick={() => startSync.mutate(true)}
              >
                Полная синхронизация
              </Button>
            </Space>
          </Col>
        </Row>
      </Card>

      {job && (
        <Card
          title={
            <Space>
              <span>Задание</span>
              {jobStatus && <Tag color={jobStatus.color}>{jobStatus.text}</Tag>}
            </Space>
          }
        >
          <Space direction="vertical" size={16} style={{ width: '100%' }}>
            <Progress
              percent={job.progress ?? 0}
              status={
                job.status === 'failed'
                  ? 'exception'
                  : job.status === 'completed'
                    ? 'success'
                    : 'active'
              }
            />

            <Row gutter={[16, 16]}>
              <Col xs={24} md={8}>
                <Text type="secondary">Обработано</Text>
                <div className="sync-value">{formatNumber(job.processed)}</div>
              </Col>

              <Col xs={24} md={8}>
                <Text type="secondary">Текущая воронка</Text>
                <div className="sync-value">
                  {job.current_funnel ? funnelName(job.current_funnel) : '—'}
                </div>
              </Col>

              <Col xs={24} md={8}>
                <Text type="secondary">Тип</Text>
                <div className="sync-value">
                  {job.full ? 'Полная' : 'Инкрементальная'}
                </div>
              </Col>
            </Row>

            {job.error && (
              <Alert
                type="error"
                showIcon
                message="Ошибка синхронизации"
                description={job.error}
              />
            )}
          </Space>
        </Card>
      )}
    </Space>
  )
}

function App() {
  const [page, setPage] = useState('dashboard')

  return (
    <Layout className="app-layout">
      <Sider
        breakpoint="lg"
        collapsedWidth={0}
        className="app-sider"
      >
        <div className="app-logo">
          <div className="logo-mark">CR</div>

          <div>
            <div className="logo-title">CR Portal</div>
            <div className="logo-subtitle">Bonus System</div>
          </div>
        </div>

        <Menu
          theme="dark"
          mode="inline"
          selectedKeys={[page]}
          onClick={({ key }) => setPage(key)}
          items={[
            {
              key: 'dashboard',
              icon: <DashboardOutlined />,
              label: 'Дашборд',
            },
            {
              key: 'deals',
              icon: <DatabaseOutlined />,
              label: 'Сделки',
            },
            {
              key: 'sync',
              icon: <CloudSyncOutlined />,
              label: 'Синхронизация',
            },
          ]}
        />
      </Sider>

      <Layout>
        <Header className="app-header">
          <div>
            <Text strong className="header-title">
              CR Integration Portal
            </Text>
          </div>

          <Tag color="green" icon={<CheckCircleOutlined />}>
            Bitrix24 подключён
          </Tag>
        </Header>

        <Content className="app-content">
          <div className="content-container">
            {page === 'dashboard'
              ? <DashboardPage />
              : page === 'deals'
                ? <DealsPage />
                : <SyncPage />
            }
          </div>
        </Content>
      </Layout>
    </Layout>
  )
}

export default App
