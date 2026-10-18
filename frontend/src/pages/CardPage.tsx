// Карточка: загрузка материалов → автозаполнение → проверка и правка → отправка на модерацию.
import { Alert, App, Button, Card, Collapse, List, Progress, Result, Space, Spin, Tag, Typography, Upload } from 'antd'
import { ArrowLeftOutlined, DeleteOutlined, FileTextOutlined, InboxOutlined, RobotOutlined, SendOutlined } from '@ant-design/icons'
import { useCallback, useEffect, useRef, useState } from 'react'
import { Link, useParams } from 'react-router-dom'
import { api, ApiError, MODE, STATUS, type Card as CardT, type Problems } from '../api'
import { CardForm, isEmpty, requiredProgress } from '../CardForm'
import { flush, track } from '../events'

const { Title, Text, Paragraph } = Typography

export default function CardPage() {
  const id = Number(useParams().id)
  const { message } = App.useApp()
  const [schema, setSchema] = useState<any>(null)
  const [card, setCard] = useState<CardT | null>(null)
  const [values, setValues] = useState<Record<string, unknown>>({})
  const [problems, setProblems] = useState<Problems>({})
  const [save, setSave] = useState<'idle' | 'saving' | 'saved' | 'error'>('idle')
  const [error, setError] = useState<string | null>(null)
  const [submitting, setSubmitting] = useState(false)
  const timer = useRef<number>()
  const pending = useRef<Record<string, unknown> | null>(null)

  const load = useCallback(async () => {
    const c = await api.card(id)
    setCard(c)
    setValues(c.values || {})
    return c
  }, [id])

  useEffect(() => {
    Promise.all([api.schema(), load()])
      .then(([s]) => { setSchema(s); track(id, 'card_opened') })
      .catch((e: ApiError) => setError(e.message))
  }, [id, load])

  // пока ИИ работает — опрашиваем раз в 2 с
  useEffect(() => {
    if (card?.status !== 'processing') return
    const t = setInterval(async () => {
      const c = await api.card(id)
      if (c.status !== 'processing') {
        track(id, 'extraction_done')
        setCard(c)
        setValues(c.values || {})
        if (c.ai?.errors?.length) message.error('Не удалось заполнить карточку автоматически')
        else message.success('Карточка заполнена — проверьте поля')
      }
    }, 2000)
    return () => clearInterval(t)
  }, [card?.status, id, message])

  const doSave = useCallback(async () => {
    if (!pending.current) return
    const v = pending.current
    pending.current = null
    setSave('saving')
    try {
      const r = await api.save(id, v)
      setProblems((prev) => {
        // ошибки формата — от сервера; «обязательное поле» оставляем, пока поле пустое
        const keep = Object.fromEntries(Object.entries(prev).filter(([k, m]) => m === 'обязательное поле' && isEmpty(v[k])))
        return { ...keep, ...r.problems }
      })
      setSave('saved')
    } catch {
      setSave('error')
      pending.current = pending.current ?? v
    }
  }, [id])

  const onChange = (next: Record<string, unknown>) => {
    for (const k of new Set([...Object.keys(next), ...Object.keys(values)])) {
      if (JSON.stringify(next[k] ?? null) !== JSON.stringify(values[k] ?? null)) track(id, 'field_changed', k)
    }
    setValues(next)
    pending.current = next
    clearTimeout(timer.current)
    timer.current = window.setTimeout(doSave, 800)
  }

  const submit = async () => {
    clearTimeout(timer.current)
    await doSave()
    setSubmitting(true)
    try {
      await api.submit(id)
      track(id, 'submitted')
      flush()
      await load()
      window.scrollTo({ top: 0, behavior: 'smooth' })
    } catch (e) {
      const err = e as ApiError
      if (err.status === 422 && err.body?.problems) {
        setProblems(err.body.problems)
        const n = Object.keys(err.body.problems).length
        message.warning(`Поправьте поля перед отправкой: ${n}`)
        const first = Object.keys(schema.properties).find((k) => err.body.problems[k])
        document.getElementById(`field-${first}`)?.scrollIntoView({ behavior: 'smooth', block: 'center' })
      } else message.error(err.message)
    } finally {
      setSubmitting(false)
    }
  }

  if (error) return <Result status="warning" title="Карточка недоступна" subTitle={error} extra={<Link to="/">К списку карточек</Link>} />
  if (!card || !schema) return <div className="center"><Spin size="large" /></div>

  const ai = card.mode === 'ai'
  const readonly = card.status === 'submitted' || card.status === 'accepted'
  const showForm = !(ai && (card.status === 'draft' || card.status === 'processing'))
  const prog = requiredProgress(schema, values)

  return (
    <div className="card-page">
      <Link to="/" className="back"><ArrowLeftOutlined /> Мои карточки</Link>
      <div className="card-title">
        <Title level={3} style={{ margin: 0 }}>{(values.product_short_name as string) || (values.product_name as string) || 'Новая карточка'}</Title>
        <Space>
          <Tag>{MODE[card.mode]}</Tag>
          <Tag color={STATUS[card.status].color}>{STATUS[card.status].label}</Tag>
        </Space>
      </div>

      {card.status === 'returned' && (
        <Alert type="warning" showIcon className="mb" message="Модератор вернул карточку на доработку"
          description={card.return_comment || 'Исправьте поля и отправьте снова.'} />
      )}
      {card.status === 'submitted' && <Alert type="success" showIcon className="mb" message="Карточка отправлена на модерацию"
        description="Спасибо! Если модератору понадобятся исправления, карточка вернётся к вам с комментарием." />}
      {card.status === 'accepted' && <Alert type="success" showIcon className="mb" message="Карточка принята модератором" />}

      {ai && card.status === 'draft' && <UploadStep card={card} onChange={setCard} />}
      {card.status === 'processing' && <Processing />}

      {!ai && card.status === 'draft' && (
        <Alert type="info" showIcon className="mb" message="Эта карточка заполняется вручную"
          description="Без автозаполнения — по вашим материалам. Так мы сравним время с карточкой, заполненной ИИ. Всё сохраняется автоматически." />
      )}
      {ai && card.ai && card.status === 'ready' && <AiSummary card={card} total={Object.keys(schema.properties).length} />}

      {showForm && (
        <>
          <CardForm schema={schema} values={values} ai={ai ? card.ai : null} problems={problems} readonly={readonly} onChange={onChange} />
          {!readonly && (
            <div className="bottom-bar">
              <div className="bottom-inner">
                <div className="bottom-progress">
                  <Text>Обязательные поля: {prog.done} из {prog.total}</Text>
                  <Progress percent={Math.round((prog.done / prog.total) * 100)} showInfo={false} size="small" />
                </div>
                <Text type="secondary" className="save-state">
                  {save === 'saving' ? 'Сохраняю…' : save === 'saved' ? 'Сохранено' : save === 'error' ? 'Нет связи — повторю' : 'Изменения сохраняются автоматически'}
                </Text>
                <Button type="primary" size="large" icon={<SendOutlined />} loading={submitting} onClick={submit}>Отправить на модерацию</Button>
              </div>
            </div>
          )}
        </>
      )}
    </div>
  )
}

function UploadStep({ card, onChange }: { card: CardT; onChange: (c: CardT) => void }) {
  const { message } = App.useApp()
  const [starting, setStarting] = useState(false)
  const refresh = async () => onChange(await api.card(card.id))

  const start = async () => {
    setStarting(true)
    try {
      await api.extract(card.id)
      track(card.id, 'extraction_started')
      await refresh()
    } catch (e) {
      message.error((e as Error).message)
    } finally {
      setStarting(false)
    }
  }

  return (
    <Card className="mb" title="Шаг 1. Загрузите материалы о разработке">
      {card.ai?.errors?.length ? (
        <Alert type="error" showIcon className="mb" message="Не получилось заполнить автоматически"
          description={<>{card.ai.errors.join('; ')}. Попробуйте другие файлы (с текстовым слоем, не сканы) или запустите ещё раз.</>} />
      ) : null}
      <Paragraph type="secondary">
        Подойдут презентация, описание продукта, техпаспорт, буклет. PDF, DOCX или PPTX, до 5 файлов, до 20 МБ каждый.
        Сканы без текстового слоя пока не читаются.
      </Paragraph>
      <Upload.Dragger multiple showUploadList={false} accept=".pdf,.docx,.pptx,.html,.htm,.txt"
        customRequest={async ({ file, onSuccess, onError }) => {
          try {
            await api.upload(card.id, [file as File])
            track(card.id, 'files_uploaded')
            await refresh()
            onSuccess?.({})
          } catch (e) {
            message.error((e as Error).message)
            onError?.(e as Error)
          }
        }}>
        <p className="ant-upload-drag-icon"><InboxOutlined /></p>
        <p className="ant-upload-text">Перетащите файлы сюда или нажмите, чтобы выбрать</p>
      </Upload.Dragger>
      {card.files.length > 0 && (
        <List className="files" size="small" dataSource={card.files} renderItem={(f) => (
          <List.Item actions={[<Button key="d" type="text" icon={<DeleteOutlined />} aria-label="Удалить"
            onClick={async () => { await api.deleteFile(card.id, f.id); refresh() }} />]}>
            <FileTextOutlined /> <span className="fname">{f.name}</span> <Text type="secondary">{(f.size / 1024 / 1024).toFixed(1)} МБ</Text>
          </List.Item>
        )} />
      )}
      <div className="step-actions">
        <Button type="primary" size="large" icon={<RobotOutlined />} disabled={!card.files.length} loading={starting} onClick={start}>
          Заполнить карточку автоматически
        </Button>
      </div>
    </Card>
  )
}

function Processing() {
  const [sec, setSec] = useState(0)
  useEffect(() => {
    const t = setInterval(() => setSec((s) => s + 1), 1000)
    return () => clearInterval(t)
  }, [])
  return (
    <Card className="mb processing">
      <Spin size="large" />
      <Title level={4}>Читаем материалы и заполняем карточку…</Title>
      <Text type="secondary">Обычно 30–90 секунд. Прошло: {sec} с. Страницу можно не обновлять.</Text>
    </Card>
  )
}

function AiSummary({ card, total }: { card: CardT; total: number }) {
  const fields = Object.values(card.ai!.card)
  const filled = fields.filter((f) => !isEmpty(f.value)).length
  const unverified = fields.filter((f) => !isEmpty(f.value) && !f.verified).length
  return (
    <Alert type="info" showIcon icon={<RobotOutlined />} className="mb"
      message={`ИИ заполнил ${filled} из ${total} полей${card.ai!.latency_s >= 1 ? ` за ${Math.round(card.ai!.latency_s)} с` : ''} — проверьте их`}
      description={
        <>
          Метка <Tag color="blue">ИИ</Tag> — значение из ваших материалов, под полем — цитата-источник.
          {unverified > 0 && <> Метка <Tag color="orange">проверьте</Tag> ({unverified}) — цитату не нашли в тексте, значение может быть неточным.</>}
          {' '}Пустые поля заполните сами, если сведения есть.
          {card.ai!.warnings.length > 0 && (
            <Collapse ghost size="small" items={[{ key: 'w', label: `Замечания при чтении файлов (${card.ai!.warnings.length})`,
              children: <ul className="warn">{card.ai!.warnings.map((w, i) => <li key={i}>{w}</li>)}</ul> }]} />
          )}
        </>
      } />
  )
}
