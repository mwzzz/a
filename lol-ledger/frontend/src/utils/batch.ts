import type { BatchRow } from '@/api/types'

const pad = (value: number) => String(value).padStart(2, '0')

function toDate(iso?: string | null): Date | null {
  if (!iso) return null
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? null : date
}

function sameDay(a: Date, b: Date): boolean {
  return (
    a.getFullYear() === b.getFullYear() &&
    a.getMonth() === b.getMonth() &&
    a.getDate() === b.getDate()
  )
}

function point(date: Date, withYear: boolean): string {
  const md = `${pad(date.getMonth() + 1)}/${pad(date.getDate())}`
  const hm = `${pad(date.getHours())}:${pad(date.getMinutes())}`
  return withYear ? `${date.getFullYear()}/${md} ${hm}` : `${md} ${hm}`
}

export function formatDuration(milliseconds: number): string {
  const minutes = Math.floor(Math.max(0, milliseconds) / 60_000)
  if (minutes < 1) return '不到 1 分钟'
  if (minutes < 60) return `${minutes} 分钟`
  const hours = Math.floor(minutes / 60)
  const rest = minutes % 60
  if (hours < 24) return rest ? `${hours} 小时 ${rest} 分钟` : `${hours} 小时`
  const days = Math.floor(hours / 24)
  const restHours = hours % 24
  return restHours ? `${days} 天 ${restHours} 小时` : `${days} 天`
}

/** 批次标题只显示时间，不显示内部编号。 */
export function formatBatchTime(
  batch: Pick<BatchRow, 'opened_at' | 'closed_at' | 'status'>,
): string {
  const start = toDate(batch.opened_at)
  if (!start) return '-'
  const now = new Date()
  const startYear = start.getFullYear() !== now.getFullYear()

  if (batch.status === 'open') {
    return `${point(start, startYear)} 开始 · 进行中（已 ${formatDuration(
      now.getTime() - start.getTime(),
    )}）`
  }

  const end = toDate(batch.closed_at)
  if (!end) {
    return `${point(start, startYear)} 开始 · 已结束`
  }
  const duration = formatDuration(end.getTime() - start.getTime())
  if (sameDay(start, end)) {
    const hm = `${pad(end.getHours())}:${pad(end.getMinutes())}`
    return `${point(start, startYear)} – ${hm}（${duration}）`
  }
  const endYear = startYear || end.getFullYear() !== start.getFullYear()
  return `${point(start, startYear)} – ${point(end, endYear)}（${duration}）`
}
