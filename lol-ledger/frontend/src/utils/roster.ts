import type { QueuePayload } from '@/api/types'

const FONT = '"PingFang SC", "Microsoft YaHei", "Noto Sans SC", sans-serif'

function roundRect(
  ctx: CanvasRenderingContext2D,
  x: number,
  y: number,
  w: number,
  h: number,
  r: number,
) {
  ctx.beginPath()
  ctx.moveTo(x + r, y)
  ctx.arcTo(x + w, y, x + w, y + h, r)
  ctx.arcTo(x + w, y + h, x, y + h, r)
  ctx.arcTo(x, y + h, x, y, r)
  ctx.arcTo(x, y, x + w, y, r)
  ctx.closePath()
}

function fitText(ctx: CanvasRenderingContext2D, text: string, maxWidth: number): string {
  if (ctx.measureText(text).width <= maxWidth) return text
  let value = text
  while (value.length > 1 && ctx.measureText(`${value}…`).width > maxWidth) {
    value = value.slice(0, -1)
  }
  return `${value}…`
}

/**
 * 把当天队列画成一张适合发群的图片（750 宽，2 倍像素密度）。
 * 只画排队中和进行中的，最多 12 条，多出来的用一行提示。
 */
export function buildRosterImage(data: QueuePayload): string {
  const active = data.entries.filter(
    (item) => item.status === 'waiting' || item.status === 'playing',
  )
  const shown = active.slice(0, 12)
  const waitingCount = active.filter((item) => item.status === 'waiting').length

  const W = 750
  const pad = 44
  const headH = 210
  const rowH = 72
  const listH = Math.max(shown.length, 1) * rowH
  const overflow = active.length > shown.length ? 44 : 0
  const footH = 120
  const H = headH + listH + overflow + footH

  const dpr = 2
  const canvas = document.createElement('canvas')
  canvas.width = W * dpr
  canvas.height = H * dpr
  const ctx = canvas.getContext('2d')
  if (!ctx) return ''
  ctx.scale(dpr, dpr)

  const bg = ctx.createLinearGradient(0, 0, W * 0.7, H)
  bg.addColorStop(0, '#0b1220')
  bg.addColorStop(1, '#101a2e')
  ctx.fillStyle = bg
  ctx.fillRect(0, 0, W, H)

  const glow = ctx.createRadialGradient(W - 110, 30, 10, W - 110, 30, 340)
  glow.addColorStop(0, 'rgba(64,158,255,0.32)')
  glow.addColorStop(1, 'rgba(64,158,255,0)')
  ctx.fillStyle = glow
  ctx.fillRect(0, 0, W, 340)

  ctx.textBaseline = 'alphabetic'
  ctx.textAlign = 'left'

  ctx.fillStyle = '#f8fafc'
  ctx.font = `700 38px ${FONT}`
  ctx.fillText(fitText(ctx, data.shop_name || '本店', W - pad * 2), pad, 92)

  ctx.fillStyle = 'rgba(148,163,184,0.92)'
  ctx.font = `500 22px ${FONT}`
  ctx.fillText('当前排队', pad, 132)

  const badgeText = `${waitingCount} 人排队`
  ctx.font = `600 20px ${FONT}`
  const badgeW = ctx.measureText(badgeText).width + 32
  ctx.fillStyle = 'rgba(64,158,255,0.16)'
  roundRect(ctx, W - pad - badgeW, 104, badgeW, 40, 20)
  ctx.fill()
  ctx.fillStyle = '#7cb8ff'
  ctx.fillText(badgeText, W - pad - badgeW + 16, 131)

  let y = headH - 26
  shown.forEach((item, index) => {
    ctx.fillStyle = index % 2 === 0 ? 'rgba(255,255,255,0.035)' : 'rgba(255,255,255,0.015)'
    roundRect(ctx, pad, y, W - pad * 2, rowH - 10, 14)
    ctx.fill()

    ctx.fillStyle = 'rgba(64,158,255,0.14)'
    roundRect(ctx, pad + 12, y + 15, 32, 32, 10)
    ctx.fill()
    ctx.fillStyle = '#7cb8ff'
    ctx.font = `600 18px ${FONT}`
    ctx.textAlign = 'center'
    ctx.fillText(String(index + 1), pad + 28, y + 37)
    ctx.textAlign = 'left'

    ctx.fillStyle = '#e8eefc'
    ctx.font = `600 24px ${FONT}`
    const hasNote = Boolean(item.note)
    ctx.fillText(fitText(ctx, item.game_id, W - pad * 2 - 250), pad + 58, y + (hasNote ? 30 : 39))

    if (hasNote) {
      ctx.fillStyle = 'rgba(148,163,184,0.85)'
      ctx.font = `500 18px ${FONT}`
      ctx.fillText(fitText(ctx, item.note, W - pad * 2 - 250), pad + 58, y + 53)
    }

    ctx.textAlign = 'right'
    if (item.status === 'playing') {
      ctx.fillStyle = '#7ee2b8'
      ctx.font = `600 20px ${FONT}`
      ctx.fillText('上机中', W - pad - 16, y + 34)
    } else {
      ctx.fillStyle = 'rgba(203,213,225,0.9)'
      ctx.font = `500 20px ${FONT}`
      ctx.fillText(`等待 ${item.wait_minutes} 分钟`, W - pad - 16, y + 34)
    }
    ctx.textAlign = 'left'
    y += rowH
  })

  if (active.length === 0) {
    ctx.fillStyle = 'rgba(148,163,184,0.8)'
    ctx.font = `500 24px ${FONT}`
    ctx.textAlign = 'center'
    ctx.fillText('现在没人排队，来了就能上机', W / 2, y + 42)
    ctx.textAlign = 'left'
    y += rowH
  }

  if (overflow) {
    ctx.fillStyle = 'rgba(148,163,184,0.75)'
    ctx.font = `500 20px ${FONT}`
    ctx.fillText(`另有 ${active.length - shown.length} 人在排队`, pad, y + 32)
    y += overflow
  }

  const lineY = H - footH + 8
  ctx.strokeStyle = 'rgba(148,163,184,0.18)'
  ctx.lineWidth = 1
  ctx.beginPath()
  ctx.moveTo(pad, lineY)
  ctx.lineTo(W - pad, lineY)
  ctx.stroke()

  const stamp = new Date(data.updated_at)
  const hh = String(stamp.getHours()).padStart(2, '0')
  const mm = String(stamp.getMinutes()).padStart(2, '0')
  ctx.fillStyle = 'rgba(148,163,184,0.75)'
  ctx.font = `500 19px ${FONT}`
  ctx.fillText(`更新于 ${hh}:${mm} · 想上机请在群里 @ 店员登记`, pad, lineY + 54)

  return canvas.toDataURL('image/png')
}
