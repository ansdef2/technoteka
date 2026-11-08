// Модератор: вход, список карточек, приглашения, выгрузка для КПЭ.
import { App, Button, Card, Form, Input, Popconfirm, Segmented, Select, Space, Table, Tabs, Tag, Typography } from 'antd'
import { DeleteOutlined, DownloadOutlined, LogoutOutlined, PlusOutlined, ReloadOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import { useNavigate } from 'react-router-dom'
import { api, ApiError, hasAdminAuth, MODE, setAdminAuth, STATUS, type CardShort, type Invite, type Mode, type Status } from '../api'

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
      <Tabs items={[
        { key: 'cards', label: 'Карточки', children: <CardsTab /> },
        { key: 'invites', label: 'Приглашения', children: <InvitesTab /> },
      ]} />
    </div>
  )
}

const PLANS = [
  { value: 'ai,manual', label: 'ИИ → вручную' },
  { value: 'manual,ai', label: 'Вручную → ИИ' },
  { value: 'ai', label: 'Только ИИ' },
  { value: 'manual', label: 'Только вручную' },
]

function InvitesTab() {
  const { message } = App.useApp()
  const [form] = Form.useForm()
  const [data, setData] = useState<Invite[]>([])
  const [loading, setLoading] = useState(true)
  const [busy, setBusy] = useState(false)
  const load = useCallback(() => {
    setLoading(true)
    api.admin.invites().then((d) => {
      setData(d)
      // порядок карточек чередуем для контрбалансировки: новое приглашение — наоборот к последнему
      form.setFieldValue('plan', d[0]?.plan[0] === 'ai' ? 'manual,ai' : 'ai,manual')
    }).finally(() => setLoading(false))
  }, [form])
  useEffect(load, [load])
  return (
    <>
      <Form form={form} layout="inline" className="mb" onFinish={async ({ org_label, plan }) => {
        setBusy(true)
        try {
          const { url } = await api.admin.createInvite(org_label, plan.split(',') as Mode[])
          const copied = await navigator.clipboard?.writeText(url).then(() => true, () => false)
          message.success(copied ? 'Приглашение создано, ссылка скопирована' : 'Приглашение создано')
          form.resetFields(['org_label'])
          load()
        } catch (e) { message.error((e as Error).message) } finally { setBusy(false) }
      }}>
        <Form.Item name="org_label" rules={[{ required: true, whitespace: true, message: 'Название организации' }]}>
          <Input placeholder="Организация" style={{ width: 260 }} />
        </Form.Item>
        <Form.Item name="plan" initialValue="ai,manual"><Select options={PLANS} style={{ width: 170 }} /></Form.Item>
        <Button type="primary" htmlType="submit" icon={<PlusOutlined />} loading={busy}>Создать приглашение</Button>
      </Form>
      <Table rowKey="id" loading={loading} dataSource={data} size="middle" pagination={{ pageSize: 20 }}
        locale={{ emptyText: 'Приглашений пока нет' }}
        columns={[
          { title: 'Организация', dataIndex: 'org_label' },
          { title: 'Порядок карточек', dataIndex: 'plan', width: 200, render: (p: Mode[]) => p.map((m) => MODE[m]).join(' → ') },
          { title: 'Карточек', dataIndex: 'cards', width: 100 },
          { title: 'Создано', dataIndex: 'created_at', width: 150, render: (d: string) => new Date(d).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) },
          { title: 'Ссылка', dataIndex: 'url', render: (u: string) => <Text copyable style={{ wordBreak: 'break-all' }}>{u}</Text> },
          { key: 'delete', width: 56, render: (_: unknown, r: Invite) => (
            <Popconfirm title={`Удалить «${r.org_label}»?`} okText="Удалить" cancelText="Отмена" okButtonProps={{ danger: true }}
              description={<div style={{ maxWidth: 320 }}>
                {r.cards ? `Вместе с организацией удалятся её карточки (${r.cards}) — с файлами и историей модерации, `
                  + 'в том числе из выгрузки для КПЭ. ' : ''}Ссылка-приглашение перестанет работать. Отменить нельзя.
              </div>}
              onConfirm={async () => {
                try {
                  await api.admin.deleteInvite(r.id)
                  message.success(`«${r.org_label}» удалена`)
                  load()
                } catch (e) { message.error((e as Error).message) }
              }}>
              <Button type="text" danger icon={<DeleteOutlined />} aria-label={`Удалить ${r.org_label}`} title="Удалить организацию" />
            </Popconfirm>
          ) },
        ]} />
    </>
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
