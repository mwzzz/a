function toDate(iso: string | null | undefined): Date | null {
  if (!iso) return null
  const date = new Date(iso)
  return Number.isNaN(date.getTime()) ? null : date
}

const pad = (value: number) => String(value).padStart(2, '0')

/** 10-30 08:04 */
export function formatShort(iso?: string | null): string {
  const date = toDate(iso)
  if (!date) return '-'
  return `${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(date.getHours())}:${pad(date.getMinutes())}`
}

/** 2026-10-30 08:04:12 */
export function formatFull(iso?: string | null): string {
  const date = toDate(iso)
  if (!date) return '-'
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())} ${pad(
    date.getHours(),
  )}:${pad(date.getMinutes())}:${pad(date.getSeconds())}`
}

export function formatClock(iso?: string | null): string {
  const date = toDate(iso)
  if (!date) return '-'
  return `${pad(date.getHours())}:${pad(date.getMinutes())}`
}

export function relative(iso?: string | null): string {
  const date = toDate(iso)
  if (!date) return '-'
  const diff = Date.now() - date.getTime()
  if (diff < 60_000) return '刚刚'
  if (diff < 3_600_000) return `${Math.floor(diff / 60_000)} 分钟前`
  if (diff < 86_400_000) return `${Math.floor(diff / 3_600_000)} 小时前`
  if (diff < 7 * 86_400_000) return `${Math.floor(diff / 86_400_000)} 天前`
  return formatShort(iso)
}

/** Date -> 后端要的 ISO 字符串（带本地时区偏移） */
export function toIso(value: Date | string | null | undefined): string | null {
  if (!value) return null
  const date = value instanceof Date ? value : new Date(value)
  if (Number.isNaN(date.getTime())) return null
  const offset = -date.getTimezoneOffset()
  const sign = offset >= 0 ? '+' : '-'
  const abs = Math.abs(offset)
  return (
    `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}` +
    `T${pad(date.getHours())}:${pad(date.getMinutes())}:${pad(date.getSeconds())}` +
    `${sign}${pad(Math.floor(abs / 60))}:${pad(abs % 60)}`
  )
}

export function todayText(): string {
  const date = new Date()
  return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
}

/** 区间端点：纯日期显示 MM-DD，带时间显示 MM-DD HH:mm */
export function formatMoment(value?: string | null): string {
  if (!value) return '-'
  const text = value.trim()
  if (text.length === 10) {
    const [, month, day] = text.split('-')
    return `${month}-${day}`
  }
  return formatShort(text)
}

/** 今天的起止（精确到分钟），用作区间筛选的默认值 */
export function todayMomentRange(): [string, string] {
  const day = todayText()
  return [`${day}T00:00`, `${day}T23:59`]
}

/** 默认区间：daysBack 天前的 hour:00 到今天 hour:00（操作人汇总用，按早班交接点切） */
export function recentMorningRange(daysBack = 3, hour = 8): [string, string] {
  const stamp = (offset: number) => {
    const date = new Date()
    date.setDate(date.getDate() - offset)
    return `${date.getFullYear()}-${pad(date.getMonth() + 1)}-${pad(date.getDate())}`
  }
  const hhmm = `${pad(hour)}:00`
  return [`${stamp(daysBack)}T${hhmm}`, `${stamp(0)}T${hhmm}`]
}

/** 日期时间区间选择器的快捷项 */
export function momentShortcuts() {
  const dayStart = (offset: number) => {
    const date = new Date()
    date.setDate(date.getDate() - offset)
    date.setHours(0, 0, 0, 0)
    return date
  }
  const dayEnd = (offset: number) => {
    const date = new Date()
    date.setDate(date.getDate() - offset)
    date.setHours(23, 59, 0, 0)
    return date
  }
  return [
    { text: '今天', value: () => [dayStart(0), dayEnd(0)] },
    { text: '昨天', value: () => [dayStart(1), dayEnd(1)] },
    { text: '最近三天', value: () => [dayStart(2), dayEnd(0)] },
    { text: '最近一周', value: () => [dayStart(6), dayEnd(0)] },
  ]
}
