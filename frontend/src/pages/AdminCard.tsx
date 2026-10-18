// Модератор: карточка + материалы + ответ ИИ, решение по чек-листу.
import { Alert, App, Button, Card, Checkbox, Col, Descriptions, Input, List, Result, Row, Space, Spin, Tag, Typography } from 'antd'
import { ArrowLeftOutlined, CheckOutlined, FileTextOutlined, RollbackOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, MODE, STATUS, type AdminCard as AdminCardT } from '../api'
import { CardForm, isEmpty } from '../CardForm'
import { AdminLogin, useAdminGate } from './Admin'

const { Title, Text } = Typography

// Чек-лист модерации (уточнить по F01)
export const CHECKLIST = [
  'Наименование и краткое описание понятны и соответствуют материалам',
  'Отрасль, статус и TRL соответствуют материалам',
  'Сведения об организации верны (юрлицо, ИНН, регион)',
  'Технические характеристики указаны с единицами измерения',
  'Нет сведений, которых нет в материалах',
  'Нет грамматических ошибок и рекламных преувеличений',
]

export default function AdminCard() {
  const { ok, setOk } = useAdminGate()
  if (!ok) return <AdminLogin onOk={() => setOk(true)} />
  return <AdminCardInner />
}

function AdminCardInner() {
  const id = Number(useParams().id)
  const { message } = App.useApp()
  const [schema, setSchema] = useState<any>(null)
  const [card, setCard] = useState<AdminCardT | null>(null)
  const [error, setError] = useState<string | null>(null)
  const [check, setCheck] = useState<Record<string, boolean>>({})
  const [comment, setComment] = useState('')
  const [busy, setBusy] = useState(false)

  const load = useCallback(() => api.admin.card(id).then(setCard), [id])
  useEffect(() => {
    Promise.all([api.schema(), load()]).then(([s]) => setSchema(s)).catch((e: ApiError) => setError(e.message))
  }, [id, load])

  if (error) return <Result status="warning" title={error} extra={<Link to="/admin">К списку</Link>} />
  if (!card || !schema) return <div className="center"><Spin size="large" /></div>

  const decide = async (verdict: 'accepted' | 'returned') => {
    setBusy(true)
    try {
      const checklist = Object.fromEntries(CHECKLIST.map((c) => [c, !!check[c]]))
      await api.admin.moderate(id, { verdict, checklist, comment: comment || null })
      message.success(verdict === 'accepted' ? 'Карточка принята' : 'Карточка возвращена организации')
      setCheck({}); setComment('')
      load()
    } catch (e) { message.error((e as Error).message) } finally { setBusy(false) }
  }

  const ai = card.ai
  const aiFields = ai ? Object.entries(ai.card).filter(([, f]) => !isEmpty(f.value)) : []
  const edited = aiFields.filter(([k, f]) => JSON.stringify(f.value) !== JSON.stringify(card.values[k] ?? null)).length
  const allChecked = CHECKLIST.every((c) => check[c])

  return (
    <div>
      <Link to="/admin" className="back"><ArrowLeftOutlined /> Все карточки</Link>
      <div className="card-title">
        <Title level={3} style={{ margin: 0 }}>{card.title || 'Без названия'}</Title>
        <Space><Tag>{MODE[card.mode]}</Tag><Tag color={STATUS[card.status].color}>{STATUS[card.status].label}</Tag></Space>
      </div>
      <Row gutter={20}>
        <Col xs={24} lg={16}>
          <CardForm schema={schema} values={card.values} ai={card.mode === 'ai' ? ai : null} problems={{}} readonly />
        </Col>
        <Col xs={24} lg={8}>
          <div className="side">
            <Card size="small" title="Сведения" className="mb">
              <Descriptions size="small" column={1} items={[
                { label: 'Организация', children: card.org_label },
                { label: 'Время заполнения', children: card.minutes != null ? `${card.minutes} мин` : '—' },
                ...(card.moderation.length ? [{ label: 'Модерация', children: card.moderation.map((m) =>
                  m.verdict === 'accepted' ? 'принята' : 'возвращена').join(' → ') }] : []),
                ...(ai ? [
                  { label: 'Модель', children: `${ai.provider} · ${ai.model}` },
                  { label: 'Извлечение', children: `${ai.latency_s} с · ${ai.tokens_in}/${ai.tokens_out} ток.` },
                  { label: 'Поля ИИ', children: `${aiFields.length} заполнено, ${edited} исправлено пользователем` },
                ] : []),
              ]} />
              {ai?.warnings?.length ? <Alert type="warning" className="mt" message="Замечания извлечения"
                description={<ul className="warn">{ai.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul>} /> : null}
            </Card>
            <Card size="small" title="Материалы" className="mb">
              <List size="small" dataSource={card.files} locale={{ emptyText: 'Файлов нет' }} renderItem={(f) => (
                <List.Item><a onClick={() => api.admin.download(`/admin/cards/${id}/files/${f.id}`, f.name)}>
                  <FileTextOutlined /> {f.name}</a></List.Item>)} />
            </Card>
            {card.status === 'submitted' && (
              <Card size="small" title="Решение" className="mb">
                <Space direction="vertical" style={{ width: '100%' }}>
                  {CHECKLIST.map((c) => (
                    <Checkbox key={c} checked={!!check[c]} onChange={(e) => setCheck({ ...check, [c]: e.target.checked })}>{c}</Checkbox>
                  ))}
                  <Input.TextArea rows={3} placeholder="Комментарий для организации (обязателен при возврате)"
                    value={comment} onChange={(e) => setComment(e.target.value)} />
                  <Space wrap>
                    <Button type="primary" icon={<CheckOutlined />} loading={busy} disabled={!allChecked} onClick={() => decide('accepted')}>Принять</Button>
                    <Button danger icon={<RollbackOutlined />} loading={busy} disabled={!comment.trim()} onClick={() => decide('returned')}>Вернуть на доработку</Button>
                  </Space>
                  {!allChecked && <Text type="secondary">Чтобы принять, отметьте все пункты чек-листа.</Text>}
                </Space>
              </Card>
            )}
          </div>
        </Col>
      </Row>
    </div>
  )
}
