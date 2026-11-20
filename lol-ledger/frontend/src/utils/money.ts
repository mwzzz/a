/**
 * 金额换算。全程整数分，禁止 parseFloat(x) * 100 这类浮点路径。
 */

export function parseYuan(input: string | number | null | undefined): number | null {
  if (input === null || input === undefined) return null
  const text = String(input).trim().replace(/,/g, '')
  if (!text) return null
  if (!/^\d{1,7}(\.\d{1,2})?$/.test(text)) return null
  const [yuan, fraction = ''] = text.split('.')
  const cents = (fraction + '00').slice(0, 2)
  return Number(yuan) * 100 + Number(cents)
}

export function formatCents(cents: number | null | undefined): string {
  const value = Number(cents || 0)
  const sign = value < 0 ? '-' : ''
  const abs = Math.abs(Math.trunc(value))
  return `${sign}${Math.trunc(abs / 100)}.${String(abs % 100).padStart(2, '0')}`
}

/** 元整数省略 .00、有小数才保留：249.00→"249"、157.50→"157.5"。工资汇总成稿文字用。 */
export function formatYuanShort(cents: number | null | undefined): string {
  return String(Number((Number(cents || 0) / 100).toFixed(2)))
}

/** 总余额（押金 + 赠金）；有赠金时括号里补现金押金。 */
export function formatBalance(
  balanceCents: number | null | undefined,
  bonusCents: number | null | undefined,
  depositCents: number | null | undefined,
): string {
  const total = formatCents(balanceCents)
  return Number(bonusCents || 0) > 0
    ? `${total}（押金 ${formatCents(depositCents)}）`
    : total
}

export function formatChange(cents: number | null | undefined): string {
  const value = Number(cents || 0)
  return value > 0 ? `+${formatCents(value)}` : formatCents(value)
}

export function centsToYuanText(cents: number | null | undefined): string {
  return formatCents(cents)
}

export function levelLabel(level: string): string {
  if (level === 'low') return '不足'
  if (level === 'warn') return '偏低'
  return '充足'
}

export function levelType(level: string): 'danger' | 'warning' | 'success' {
  if (level === 'low') return 'danger'
  if (level === 'warn') return 'warning'
  return 'success'
}
