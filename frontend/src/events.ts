// Журнал действий для замера времени заполнения (показатель 1).
// События копятся в очереди и уходят пачкой раз в 10 с и при уходе со страницы.

type EventType = 'card_opened' | 'files_uploaded' | 'extraction_started' | 'extraction_done' | 'field_changed' | 'submitted'
interface Ev { card_id: number; type: EventType; field?: string | null; ts: string }

let queue: Ev[] = []
const lastField: Record<string, number> = {}

export function track(card_id: number, type: EventType, field?: string) {
  if (type === 'field_changed' && field) {
    const k = `${card_id}:${field}`
    const t = Date.now()
    if (lastField[k] && t - lastField[k] < 5000) return // не чаще раза в 5 с на поле
    lastField[k] = t
  }
  queue.push({ card_id, type, field: field ?? null, ts: new Date().toISOString() })
  if (type === 'submitted' || type === 'card_opened') flush()
}

export function flush(beacon = false) {
  if (!queue.length) return
  const batch = queue
  queue = []
  const body = JSON.stringify(batch)
  if (beacon && navigator.sendBeacon) {
    navigator.sendBeacon('/api/events', new Blob([body], { type: 'application/json' }))
    return
  }
  fetch('/api/events', { method: 'POST', headers: { 'Content-Type': 'application/json' }, body, keepalive: true })
    .catch(() => { queue = batch.concat(queue) }) // сеть моргнула — отправим со следующей пачкой
}

setInterval(() => flush(), 10_000)
addEventListener('pagehide', () => flush(true))
document.addEventListener('visibilitychange', () => { if (document.visibilityState === 'hidden') flush(true) })
