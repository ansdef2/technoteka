// Клиент API — по backend/openapi.yaml.

export type Mode = 'ai' | 'manual'
export type Status = 'draft' | 'processing' | 'ready' | 'submitted' | 'accepted' | 'returned'

export interface CardShort {
  id: number
  mode: Mode
  status: Status
  title: string | null
  updated_at: string
  org_label?: string
}
export interface FieldAI {
  value: unknown
  quote: string | null
  quote_score: number | null
  verified: boolean
}
export interface AIResult {
  card: Record<string, FieldAI>
  provider: string
  model: string
  schema_mode: string
  latency_s: number
  tokens_in: number
  tokens_out: number
  warnings: string[]
  errors: string[]
}
export interface FileInfo { id: number; name: string; size: number; mime: string }
export interface Card extends CardShort {
  schema_version: string
  values: Record<string, unknown>
  ai: AIResult | null
  files: FileInfo[]
  return_comment?: string | null
}
export interface Moderation {
  moderator?: string
  checklist: Record<string, boolean>
  verdict: 'accepted' | 'returned'
  comment: string | null
  created_at?: string
}
export interface AdminCard extends Card {
  moderation: Moderation[]
  minutes: number | null
}
export interface Session { org_label: string; plan: Mode[]; cards: CardShort[] }
export type Problems = Record<string, string>

export class ApiError extends Error {
  constructor(public status: number, message: string, public body?: any) { super(message) }
}

let adminAuth: string | null = null
try { adminAuth = sessionStorage.getItem('tt_admin') } catch { /* приватный режим */ }

export function setAdminAuth(user: string, password: string | null) {
  adminAuth = password === null ? null : 'Basic ' + btoa(unescape(encodeURIComponent(`${user}:${password}`)))
  try {
    if (adminAuth) sessionStorage.setItem('tt_admin', adminAuth)
    else sessionStorage.removeItem('tt_admin')
  } catch { /* приватный режим */ }
}
export const hasAdminAuth = () => !!adminAuth

async function req<T>(method: string, url: string, body?: unknown, opts: { admin?: boolean; raw?: boolean } = {}): Promise<T> {
  const headers: Record<string, string> = { 'X-Requested-With': 'fetch' }
  let payload: BodyInit | undefined
  if (body instanceof FormData) payload = body
  else if (body !== undefined) { headers['Content-Type'] = 'application/json'; payload = JSON.stringify(body) }
  if (opts.admin && adminAuth) headers['Authorization'] = adminAuth
  const r = await fetch('/api' + url, { method, headers, body: payload, credentials: 'same-origin' })
  if (opts.raw && r.ok) return r as unknown as T
  const text = await r.text()
  let data: any = undefined
  try { data = text ? JSON.parse(text) : undefined } catch { data = text }
  if (!r.ok) {
    const detail = typeof data?.detail === 'string' ? data.detail : r.status === 422 ? 'Проверьте поля' : `Ошибка ${r.status}`
    throw new ApiError(r.status, detail, data)
  }
  return data as T
}

export const api = {
  schema: () => req<any>('GET', '/schema'),
  health: () => req<{ provider: string; schema_version: string }>('GET', '/health'),
  login: (token: string) => req<Session>('POST', '/session', { token }),
  session: () => req<Session>('GET', '/session'),
  createCard: () => req<Card>('POST', '/cards'),
  card: (id: number) => req<Card>('GET', `/cards/${id}`),
  upload: (id: number, files: File[]) => {
    const fd = new FormData()
    files.forEach((f) => fd.append('files', f))
    return req<FileInfo[]>('POST', `/cards/${id}/files`, fd)
  },
  deleteFile: (id: number, fileId: number) => req<void>('DELETE', `/cards/${id}/files/${fileId}`),
  extract: (id: number) => req<CardShort>('POST', `/cards/${id}/extract`),
  save: (id: number, values: Record<string, unknown>) => req<{ problems: Problems }>('PUT', `/cards/${id}/values`, { values }),
  submit: (id: number) => req<CardShort>('POST', `/cards/${id}/submit`),

  admin: {
    cards: (status?: Status) => req<CardShort[]>('GET', '/admin/cards' + (status ? `?status=${status}` : ''), undefined, { admin: true }),
    card: (id: number) => req<AdminCard>('GET', `/admin/cards/${id}`, undefined, { admin: true }),
    moderate: (id: number, m: Moderation) => req<CardShort>('POST', `/admin/cards/${id}/moderation`, m, { admin: true }),
    download: async (url: string, filename: string) => {
      const r = await req<Response>('GET', url, undefined, { admin: true, raw: true })
      const blob = await r.blob()
      const a = document.createElement('a')
      a.href = URL.createObjectURL(blob)
      a.download = filename
      a.click()
      setTimeout(() => URL.revokeObjectURL(a.href), 5000)
    },
  },
}

export const STATUS: Record<Status, { label: string; color: string }> = {
  draft: { label: 'Черновик', color: 'default' },
  processing: { label: 'Заполняется ИИ', color: 'processing' },
  ready: { label: 'Проверьте и отправьте', color: 'gold' },
  submitted: { label: 'На модерации', color: 'blue' },
  accepted: { label: 'Принята', color: 'green' },
  returned: { label: 'Возвращена на доработку', color: 'red' },
}
export const MODE: Record<Mode, string> = { ai: 'С автозаполнением', manual: 'Вручную' }
