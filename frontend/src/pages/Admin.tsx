// Модератор: вход, список карточек, приглашения, выгрузка для КПЭ.
import { Button, Card, Form, Input, Segmented, Space, Table, Tag, Typography } from 'antd'
import { DownloadOutlined, LogoutOutlined, ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError, hasAdminAuth, MODE, setAdminAuth, STATUS, type CardShort, type Mode, type Status } from '../api'

const { Title, Text } = Typography

export function AdminLogin({ onOk }: { onOk: () => void }) {
  const [err, setErr] = useState<string | null>(null)
  const [busy, setBusy] = useState(false)
  return (
    <Card className="login" title="Вход модератора">
      <Form layout="vertical" onFinish={async ({ user, password }) => {
        setBusy(true)
        setAdminAuth(user, password)
        try {
          await api.admin.cards()
          onOk()
        } catch (e) {
          setAdminAuth('', null)
          setErr((e as ApiError).message)
        } finally {
          setBusy(false)
        }
      }}>
        <Form.Item name="user" label="Логин" initialValue="admin" rules={[{ required: true }]}><Input autoComplete="username" /></Form.Item>
        <Form.Item name="password" label="Пароль" rules={[{ required: true }]} validateStatus={err ? 'error' : undefined} help={err}>
          <Input.Password autoComplete="current-password" />
        </Form.Item>
        <Button type="primary" htmlType="submit" loading={busy} block>Войти</Button>
      </Form>
    </Card>
  )
}

export function useAdminGate() {
  const [ok, setOk] = useState(hasAdminAuth())
  return { ok, setOk }
}

export default function Admin() {
  const { ok, setOk } = useAdminGate()
  if (!ok) return <AdminLogin onOk={() => setOk(true)} />
  return (
    <div>
      <div className="admin-head">
        <Title level={3} style={{ margin: 0 }}>Модерация</Title>
        <Space>
          <Button icon={<DownloadOutlined />} onClick={() => api.admin.download('/admin/export.xlsx', 'tehnoteka_export.xlsx')}>Выгрузка для КПЭ (Excel)</Button>
          <Button icon={<LogoutOutlined />} onClick={() => { setAdminAuth('', null); setOk(false) }}>Выйти</Button>
        </Space>
      </div>
      <CardsTab />
    </div>
  )
}

function CardsTab() {
  const nav = useNavigate()
  const [status, setStatus] = useState<Status | 'all'>('submitted')
  const [data, setData] = useState<CardShort[]>([])
  const [loading, setLoading] = useState(true)
  const load = useCallback(() => {
    setLoading(true)
    api.admin.cards(status === 'all' ? undefined : status).then(setData).finally(() => setLoading(false))
  }, [status])
  useEffect(load, [load])
  return (
    <>
      <Space className="mb" wrap>
        <Segmented value={status} onChange={(v) => setStatus(v as Status | 'all')} options={[
          { value: 'submitted', label: 'Ждут модерации' }, { value: 'returned', label: 'Возвращены' },
          { value: 'accepted', label: 'Приняты' }, { value: 'all', label: 'Все' }]} />
        <Button icon={<ReloadOutlined />} onClick={load}>Обновить</Button>
      </Space>
      <Table rowKey="id" loading={loading} dataSource={data} size="middle" pagination={{ pageSize: 20 }}
        onRow={(r) => ({ onClick: () => nav(`/admin/cards/${r.id}`), style: { cursor: 'pointer' } })}
        locale={{ emptyText: 'Нет карточек' }}
        columns={[
          { title: '№', dataIndex: 'id', width: 60 },
          { title: 'Организация', dataIndex: 'org_label' },
          { title: 'Разработка', dataIndex: 'title', render: (t) => t || <Text type="secondary">без названия</Text> },
          { title: 'Режим', dataIndex: 'mode', render: (m: Mode) => MODE[m], width: 160 },
          { title: 'Статус', dataIndex: 'status', width: 200, render: (s: Status) => <Tag color={STATUS[s].color}>{STATUS[s].label}</Tag> },
          { title: 'Изменена', dataIndex: 'updated_at', width: 150, render: (d: string) => new Date(d).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) },
        ]} />
    </>
  )
}
