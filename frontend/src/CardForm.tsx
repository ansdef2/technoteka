// Форма карточки строится из card_schema_v0.json (GET /api/schema) — без ручной вёрстки полей.
// Секции — x-section, виджет — x-match, обязательные — x-required-mvp.
// Рядом с полем, заполненным ИИ, — метка и цитата из материалов; если цитата не найдена — предупреждение.
import Form from '@rjsf/antd'
import type { FieldTemplateProps, ObjectFieldTemplateProps, RJSFSchema, UiSchema, WidgetProps } from '@rjsf/utils'
import validator from '@rjsf/validator-ajv8'
import { Button, Card, Checkbox, Input, Select, Space, Tag, Tooltip, Typography } from 'antd'
import { DeleteOutlined, PlusOutlined, RobotOutlined, WarningOutlined, EditOutlined } from '@ant-design/icons'
import { useMemo } from 'react'
import type { AIResult, Problems } from './api'

const { Text } = Typography

export const TRL_LABELS = [
  'Сформулированы базовые принципы',
  'Сформулирована концепция технологии',
  'Подтверждена работоспособность концепции',
  'Макет проверен в лаборатории',
  'Макет проверен в условиях, близких к реальным',
  'Прототип проверен в условиях, близких к реальным',
  'Прототип проверен в реальных условиях',
  'Система готова и испытана',
  'Система применяется в реальной эксплуатации',
]

export const isEmpty = (v: unknown) =>
  v === undefined || v === null || (typeof v === 'string' && !v.trim()) || (Array.isArray(v) && v.length === 0)
const same = (a: unknown, b: unknown) => JSON.stringify(a ?? null) === JSON.stringify(b ?? null)

// ---------------------------------------------------------------- схема → форма

export function prepare(schema: any): { schema: RJSFSchema; uiSchema: UiSchema } {
  const s = structuredClone(schema)
  s.required = s['x-required-mvp'] || []
  delete s.title
  delete s.description
  const ui: UiSchema = { 'ui:submitButtonOptions': { norender: true } }
  for (const [key, spec] of Object.entries<any>(s.properties)) {
    const m = spec['x-match']
    let widget = 'text'
    if (spec.enum) widget = 'search_select'
    else if (m === 'long_text') widget = 'long_text'
    else if (m === 'number') widget = 'trl'
    else if (m === 'table') widget = 'kv_table'
    else if (m === 'list' && spec.items?.enum) { widget = 'checks'; spec.uniqueItems = true }
    else if (m === 'list') widget = 'tags'
    ui[key] = { 'ui:widget': widget }
  }
  return { schema: s, uiSchema: ui }
}

// ---------------------------------------------------------------- виджеты

const off = (p: WidgetProps) => p.disabled || p.readonly

function TextWidget(p: WidgetProps) {
  return <Input id={p.id} value={(p.value as string) ?? ''} disabled={off(p)} maxLength={p.schema.maxLength}
    onChange={(e) => p.onChange(e.target.value === '' ? undefined : e.target.value)} />
}

function LongTextWidget(p: WidgetProps) {
  return <div className={off(p) ? '' : 'ta'}>
    <Input.TextArea id={p.id} value={(p.value as string) ?? ''} disabled={off(p)} maxLength={p.schema.maxLength}
      showCount={!off(p)} autoSize={{ minRows: 2, maxRows: 10 }}
      onChange={(e) => p.onChange(e.target.value === '' ? undefined : e.target.value)} />
  </div>
}

function SearchSelectWidget(p: WidgetProps) {
  const options = ((p.schema.enum as string[]) || []).map((v) => ({ value: v, label: v }))
  return <Select id={p.id} value={p.value ?? undefined} disabled={off(p)} options={options} allowClear showSearch
    placeholder="Выберите из списка" style={{ width: '100%' }} optionFilterProp="label"
    onChange={(v) => p.onChange(v ?? undefined)} />
}

function TrlWidget(p: WidgetProps) {
  const options = TRL_LABELS.map((l, i) => ({ value: i + 1, label: `${i + 1} — ${l}` }))
  return <Select id={p.id} value={p.value ?? undefined} disabled={off(p)} options={options} allowClear
    placeholder="Уровень 1–9" style={{ width: '100%' }} onChange={(v) => p.onChange(v ?? undefined)} />
}

function ChecksWidget(p: WidgetProps) {
  const opts = ((p.schema.items as any)?.enum as string[]) || []
  return <Checkbox.Group value={(p.value as string[]) || []} disabled={off(p)} options={opts} className="checks"
    onChange={(v) => p.onChange(v.length ? v : undefined)} />
}

function TagsWidget(p: WidgetProps) {
  return <Select id={p.id} mode="tags" value={(p.value as string[]) || []} disabled={off(p)} open={false}
    tokenSeparators={[',', ';']} placeholder="Введите тег и нажмите Enter" style={{ width: '100%' }}
    onChange={(v: string[]) => {
      const clean = [...new Set(v.map((x) => x.trim().toLowerCase()).filter(Boolean))]
      p.onChange(clean.length ? clean : undefined)
    }} />
}

function KvTableWidget(p: WidgetProps) {
  const rows: { name: string; value: string }[] = (p.value as any[]) || []
  const max = p.schema.maxItems ?? 10
  const set = (next: typeof rows) => p.onChange(next.length ? next : undefined)
  const edit = (i: number, k: 'name' | 'value', v: string) => set(rows.map((r, j) => (j === i ? { ...r, [k]: v } : r)))
  return (
    <div className="kv">
      {rows.map((r, i) => (
        <div className="kv-row" key={i}>
          <Input placeholder="Параметр" value={r.name} disabled={off(p)} onChange={(e) => edit(i, 'name', e.target.value)} />
          <Input placeholder="Значение с единицами" value={r.value} disabled={off(p)} onChange={(e) => edit(i, 'value', e.target.value)} />
          {!off(p) && <Button type="text" icon={<DeleteOutlined />} aria-label="Удалить строку"
            onClick={() => set(rows.filter((_, j) => j !== i))} />}
        </div>
      ))}
      {!off(p) && rows.length < max && (
        <Button size="small" icon={<PlusOutlined />} onClick={() => set([...rows, { name: '', value: '' }])}>Добавить строку</Button>
      )}
      {off(p) && !rows.length && <Text type="secondary">—</Text>}
    </div>
  )
}

const widgets = {
  text: TextWidget, long_text: LongTextWidget, search_select: SearchSelectWidget, trl: TrlWidget,
  checks: ChecksWidget, tags: TagsWidget, kv_table: KvTableWidget,
}

// ---------------------------------------------------------------- шаблоны

interface Ctx {
  ai: AIResult['card'] | null
  values: Record<string, unknown>
  problems: Problems
  schema: any
}

function FieldTemplate(p: FieldTemplateProps) {
  const ctx = p.registry.formContext as Ctx
  if (p.id === 'root') return <>{p.children}</>
  const key = p.id.replace(/^root_/, '')
  const spec = ctx.schema.properties[key]
  if (!spec) return <>{p.children}</>
  const ai = ctx.ai?.[key]
  const aiFilled = ai && !isEmpty(ai.value)
  const value = ctx.values[key]
  const changed = aiFilled && !same(ai!.value, value)
  const problem = ctx.problems[key]
  return (
    <div className={`field ${problem ? 'field-error' : ''} ${aiFilled && !changed ? 'field-ai' : ''}`} id={`field-${key}`}>
      <div className="field-head">
        <label htmlFor={p.id} className="field-label">
          {spec.title}{p.required && <span className="req" title="Обязательное поле"> *</span>}
        </label>
        <Space size={4} wrap>
          {aiFilled && !changed && <Tag color="blue" icon={<RobotOutlined />}>ИИ</Tag>}
          {changed && <Tag icon={<EditOutlined />}>исправлено</Tag>}
          {aiFilled && !ai!.verified && !changed && (
            <Tooltip title="ИИ не смог подтвердить значение дословной цитатой из ваших материалов. Проверьте особенно внимательно.">
              <Tag color="orange" icon={<WarningOutlined />}>проверьте</Tag>
            </Tooltip>
          )}
        </Space>
      </div>
      <div className="field-help">{spec.description}</div>
      {p.children}
      {problem && <div className="field-problem">{problem}</div>}
      {aiFilled && ai!.quote && (
        <div className={`quote ${ai!.verified ? '' : 'quote-bad'}`}>
          <span className="quote-label">{ai!.verified ? 'Источник в материалах:' : 'ИИ сослался на (в тексте не найдено):'}</span> «{ai!.quote}»
        </div>
      )}
      {ctx.ai && !aiFilled && isEmpty(value) && (
        <div className="field-note">В материалах не найдено — заполните, если сведения есть</div>
      )}
    </div>
  )
}

function ObjectFieldTemplate(p: ObjectFieldTemplateProps) {
  const ctx = p.registry.formContext as Ctx
  const sections: string[] = ctx.schema['x-sections'] || []
  const required: string[] = ctx.schema['x-required-mvp'] || []
  return (
    <>
      {sections.map((sec, i) => {
        const items = p.properties.filter((x) => ctx.schema.properties[x.name]?.['x-section'] === sec)
        const req = items.filter((x) => required.includes(x.name))
        const done = req.filter((x) => !isEmpty(ctx.values[x.name])).length
        return (
          <Card key={sec} id={`section-${i}`} className="section" size="small"
            title={<span>{sec}</span>}
            extra={req.length ? <Text type={done === req.length ? 'success' : 'secondary'}>{done} из {req.length} обязательных</Text> : null}>
            {items.map((x) => <div key={x.name}>{x.content}</div>)}
          </Card>
        )
      })}
    </>
  )
}

// ---------------------------------------------------------------- компонент

export function CardForm(props: {
  schema: any
  values: Record<string, unknown>
  ai: AIResult | null
  problems: Problems
  readonly?: boolean
  onChange?: (values: Record<string, unknown>) => void
}) {
  const prepared = useMemo(() => prepare(props.schema), [props.schema])
  const ctx: Ctx = { ai: props.ai?.card ?? null, values: props.values, problems: props.problems, schema: props.schema }
  return (
    <Form
      schema={prepared.schema}
      uiSchema={prepared.uiSchema}
      formData={props.values}
      validator={validator}
      widgets={widgets}
      templates={{ FieldTemplate, ObjectFieldTemplate }}
      formContext={ctx}
      readonly={props.readonly}
      noValidate
      noHtml5Validate
      showErrorList={false}
      onChange={(e) => props.onChange?.(e.formData || {})}
    >
      <></>
    </Form>
  )
}

export function requiredProgress(schema: any, values: Record<string, unknown>) {
  const req: string[] = schema['x-required-mvp'] || []
  return { done: req.filter((k) => !isEmpty(values[k])).length, total: req.length }
}
