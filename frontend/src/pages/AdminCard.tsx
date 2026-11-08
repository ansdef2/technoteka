// Модератор: карточка + материалы + ответ ИИ, решение по чек-листу (принять / на доработку с комментарием).
import { Alert, App, Button, Card, Checkbox, Col, Descriptions, Input, List, Result, Row, Space, Spin, Tag, Typography } from 'antd'
import { ArrowLeftOutlined, CheckOutlined, FileTextOutlined, RollbackOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, MODE, STATUS, type AdminCard as AdminCardT, type Status } from '../api'
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

  const allChecked = CHECKLIST.every((c) => check[c])
  const decide = async (verdict: 'accepted' | 'returned') => {
    // кнопки не блокируем — объясняем, чего не хватает: серые кнопки внизу выглядели как «кнопок нет»
    if (verdict === 'accepted' && !allChecked) {
      message.warning('Чтобы принять, отметьте все пункты чек-листа — или отправьте карточку на доработку')
      return
    }
    if (verdict === 'returned' && !comment.trim()) {
      message.warning('Напишите в комментарии, что организации исправить')
      return
    }
    setBusy(true)
    try {
      const checklist = Object.fromEntries(CHECKLIST.map((c) => [c, !!check[c]]))
      await api.admin.moderate(id, { verdict, checklist, comment: comment || null })
      message.success(verdict === 'accepted' ? 'Карточка принята' : 'Карточка отправлена организации на доработку')
      setCheck({}); setComment('')
      load()
    } catch (e) { message.error((e as Error).message) } finally { setBusy(false) }
  }

  const ai = card.ai
  const aiFields = ai ? Object.entries(ai.card).filter(([, f]) => !isEmpty(f.value)) : []
  const edited = aiFields.filter(([k, f]) => JSON.stringify(f.value) !== JSON.stringify(card.values[k] ?? null)).length
  const waiting: Partial<Record<Status, string>> = {
    draft: 'Организация ещё не отправила карточку — решение станет доступно после отправки.',
    processing: 'Организация ещё не отправила карточку — решение станет доступно после отправки.',
    ready: 'Организация ещё не отправила карточку — решение станет доступно после отправки.',
    returned: 'Карточка на доработке у организации — после исправления она снова придёт сюда.',
    accepted: 'Карточка принята.',
  }

  return (
    <div>
      <Link to="/admin" className="back"><ArrowLeftOutlined /> Все карточки</Link>
      <div className="card-title">
        <Title level={3} style={{ margin: 0 }}>{card.title || 'Без названия'}</Title>
        <Space><Tag>{MODE[card.mode]}</Tag><Tag color={STATUS[card.status].color}>{STATUS[card.status].label}</Tag></Space>
      </div>
      <Row gutter={20}>
        {/* на узком экране решение — над формой, а не после неё */}
        <Col xs={{ span: 24, order: 2 }} lg={{ span: 16, order: 1 }}>
          <CardForm schema={schema} values={card.values} ai={card.mode === 'ai' ? ai : null} problems={{}} readonly />
        </Col>
        <Col xs={{ span: 24, order: 1 }} lg={{ span: 8, order: 2 }}>
          <div className="side">
            <Card size="small" title="Решение" className="mb decision">
              {card.status === 'submitted' ? (
                <Space direction="vertical" style={{ width: '100%' }}>
                  {CHECKLIST.map((c) => (
                    <Checkbox key={c} checked={!!check[c]} onChange={(e) => setCheck({ ...check, [c]: e.target.checked })}>{c}</Checkbox>
                  ))}
                  <div>
                    <Text strong>Комментарий для организации</Text>
                    <Input.TextArea rows={3} className="mt-xs" value={comment} onChange={(e) => setComment(e.target.value)}
                      placeholder="Что исправить — обязателен при отправке на доработку; при приёмке — по желанию" />
                  </div>
                  <Space wrap>
                    <Button type="primary" icon={<CheckOutlined />} loading={busy} onClick={() => decide('accepted')}>Принять</Button>
                    <Button danger icon={<RollbackOutlined />} loading={busy} onClick={() => decide('returned')}>Отправить на доработку</Button>
                  </Space>
                  <Text type="secondary">Принять — когда отмечены все пункты; на доработку — с комментарием.
                    Организация увидит комментарий в своей карточке.</Text>
                </Space>
              ) : <Text type="secondary">{waiting[card.status]}</Text>}
            </Card>
            {card.moderation.length > 0 && (
              <Card size="small" title="История решений" className="mb">
                <List size="small" dataSource={[...card.moderation].reverse()} renderItem={(m) => (
                  <List.Item>
                    <div>
                      <Space wrap size={6}>
                        <Tag color={m.verdict === 'accepted' ? 'green' : 'red'}>{m.verdict === 'accepted' ? 'принята' : 'на доработку'}</Tag>
                        <Text type="secondary">{m.created_at ? new Date(m.created_at).toLocaleString('ru-RU', { dateStyle: 'short', timeStyle: 'short' }) : ''}
                          {m.moderator ? ` · ${m.moderator}` : ''}</Text>
                      </Space>
                      {m.comment && <div className="mt-xs">{m.comment}</div>}
                    </div>
                  </List.Item>
                )} />
              </Card>
            )}
            <Card size="small" title="Сведения" className="mb">
              <Descriptions size="small" column={1} items={[
                { label: 'Организация', children: card.org_label },
                { label: 'Время заполнения', children: card.minutes != null ? `${card.minutes} мин` : '—' },
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
          </div>
        </Col>
      </Row>
    </div>
  )
}
