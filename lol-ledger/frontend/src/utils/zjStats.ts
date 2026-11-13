import type { ZjMatch } from '@/api/types'

/** 原「查战绩」单文件页面的解析与统计逻辑，逐条移植为零副作用纯函数。 */

export interface ZjPlayer {
  name: string
  id: string
  full: string
  line: number
}

export interface ZjKda {
  k: number
  d: number
  a: number
  rating: number | null
  line: string
}

export interface ZjMatchItem {
  time: string
  win: boolean
  championId: number | string | null
  mode: string
  pos: string
  kda: ZjKda | null
  title: string
}

export interface ZjChampRank {
  id: string
  name: string
  win: number
  play: number
}

export interface ZjPosRank {
  key: string
  name: string
  count: number
}

export interface ZjAverageKda {
  rating: number
  k: number
  d: number
  a: number
  text: string
}

export interface ZjStat {
  games: number
  wins: number
  losses: number
  winRate: number
  avgKDA: ZjAverageKda | null
  champWinRank: ZjChampRank[]
  champPlayRank: ZjChampRank[]
  posRank: ZjPosRank[]
  list: ZjMatchItem[]
}

export const AREAS: Record<number, string> = {
  1: '艾欧尼亚',
  2: '比尔吉沃特',
  3: '祖安',
  4: '诺克萨斯',
  5: '班德尔城',
  6: '德玛西亚',
  7: '皮尔特沃夫',
  8: '战争学院',
  9: '弗雷尔卓德',
  10: '巨神峰',
  11: '雷瑟守备',
  12: '无畏先锋',
  13: '裁决之地',
  14: '黑色玫瑰',
  15: '暗影岛',
  16: '恕瑞玛',
  17: '钢铁烈阳',
  18: '水晶之痕',
  19: '均衡教派',
  20: '扭曲丛林',
  21: '教育网专区',
  22: '影流',
  30: '男爵领域',
  31: '峡谷之巅',
}

export const AREA_OPTIONS = Object.entries(AREAS).map(([id, name]) => ({
  value: Number(id),
  label: `${id} - ${name}`,
}))

const POS_MAP: Record<string, string> = {
  上: '上单',
  野: '打野',
  中: '中单',
  下: 'ADC',
  辅: '辅助',
  adc: 'ADC',
  AD: 'ADC',
  ad: 'ADC',
  上单: '上单',
  打野: '打野',
  中单: '中单',
  下路: 'ADC',
  辅助: '辅助',
}

export function champIcon(championId: number | string): string {
  return `https://wegame.gtimg.com/g.26-r.c2d3c/helper/lol/assis/images/resources/champions/${championId}.png`
}

// 客户端复制的文本常带不可见控制符（方向隔离符、零宽字符），会让「昵称#编号」解析失败
const INVISIBLE_RE = /[\u200B-\u200F\u202A-\u202E\u2060-\u2064\u2066-\u206F\uFEFF\u00AD]/g

export function cleanText(text: string): string {
  return String(text ?? '').replace(INVISIBLE_RE, '')
}

/** 每行一个玩家，兼容「昵称 #编号加入了队伍聊天」，自动去重。 */
export function parsePlayers(text: string): ZjPlayer[] {
  const out: ZjPlayer[] = []
  const seen = new Set<string>()
  cleanText(text)
    .split(/\r?\n/)
    .forEach((line, index) => {
      const matched = /([^#\r\n]{1,64})#(\d{3,8})/.exec(line)
      if (!matched) return
      const name = matched[1].replace(/\s+/g, '')
      const id = matched[2]
      const full = `${name}#${id}`
      if (seen.has(full)) return
      seen.add(full)
      out.push({ name, id, full, line: index })
    })
  return out
}

export function splitFull(full: string): ZjPlayer {
  const at = full.lastIndexOf('#')
  if (at <= 0) return { name: full, id: '', full, line: 0 }
  return { name: full.slice(0, at), id: full.slice(at + 1), full, line: 0 }
}

export function isNewMode(match: ZjMatch): boolean {
  const text = `${match.title ?? ''}|${(match.detail ?? []).map((d) => d.info ?? '').join('|')}`
  return text.includes('新模式')
}

/** 依次尝试：isme 详情行 → 全部详情行 → title，取第一条形如 (3-1-5) 的记录。 */
export function kdaOfMatch(match: ZjMatch): ZjKda | null {
  const lines = (match.detail ?? []).map((detail) => ({
    isme: Number(detail.isme) === 1,
    info: String(detail.info ?? ''),
  }))
  lines.sort((a, b) => Number(b.isme) - Number(a.isme))
  if (match.title) lines.push({ isme: true, info: String(match.title) })

  for (const line of lines) {
    const matched = /\((\d{1,3})-(\d{1,3})-(\d{1,3})\)/.exec(line.info)
    if (!matched || matched.index === undefined) continue
    const rest = line.info.slice(0, matched.index).trim()
    const rating = /([\d]+(?:\.\d+)?)(?:\/\d+)?\s*$/.exec(rest)
    return {
      k: Number(matched[1]),
      d: Number(matched[2]),
      a: Number(matched[3]),
      rating: rating ? Number.parseFloat(rating[1]) : null,
      line: line.info,
    }
  }
  return null
}

export function posOfMatch(match: ZjMatch): string {
  const text = [
    String(match.titleTime ?? ''),
    String(match.title ?? ''),
    (match.detail ?? []).map((detail) => detail.info ?? '').join(' | '),
  ].join(' | ')

  let matched = /[\[【(]\s*(上单|打野|中单|下路|辅助|ADC|adc|上|野|中|下|辅|AD|ad)\s*[\]】)]/.exec(text)
  if (!matched) {
    matched = /(上单|打野|中单|下路|辅助)/.exec(text)
    if (!matched) return ''
  }
  return POS_MAP[matched[1]] ?? matched[1]
}

export function timeOfMatch(match: ZjMatch): string {
  const matched = /(\d{1,2}-\d{1,2}\s+\d{1,2}:\d{1,2}(:\d{1,2})?)/.exec(String(match.titleTime ?? ''))
  return matched ? matched[1] : String(match.titleTime ?? '')
}

export function modeOfMatch(match: ZjMatch): string {
  const text = `${match.title ?? ''}|${(match.detail ?? []).map((d) => d.info ?? '').join('|')}`
  const matched = /(新模式|海牛|排位|灵活排位|匹配|大乱斗|无限火力|克隆)/.exec(text)
  return matched ? matched[1] : '其它'
}

/** 统计口径与原页面完全一致：只算「新模式」，最多取 capN 场。 */
export function statPlayer(
  matches: ZjMatch[],
  capN: number,
  champNames: Record<string, string> = {},
): ZjStat {
  const filtered = matches.filter(isNewMode).slice(0, capN)
  const champPlay: Record<string, { play: number; win: number }> = {}
  const posPlay: Record<string, number> = {}
  const list: ZjMatchItem[] = []

  let wins = 0
  let sumK = 0
  let sumD = 0
  let sumA = 0
  let kdaN = 0
  let sumRating = 0
  let ratingN = 0

  for (const match of filtered) {
    const win = Number(match.isWin) === 1
    if (win) {
      wins += 1
    }

    const championId = match.championId ?? null
    if (championId !== null && championId !== undefined && championId !== '') {
      const key = String(championId)
      if (!champPlay[key]) champPlay[key] = { play: 0, win: 0 }
      champPlay[key].play += 1
      if (win) champPlay[key].win += 1
    }

    const kda = kdaOfMatch(match)
    if (kda) {
      sumK += kda.k
      sumD += kda.d
      sumA += kda.a
      kdaN += 1
      sumRating += kda.rating != null ? kda.rating : kda.d > 0 ? (kda.k + kda.a) / kda.d : kda.k + kda.a
      ratingN += 1
    }

    const pos = posOfMatch(match)
    if (pos) posPlay[pos] = (posPlay[pos] ?? 0) + 1

    list.push({
      time: timeOfMatch(match),
      win,
      championId,
      mode: modeOfMatch(match),
      pos,
      kda,
      title: String(match.title ?? ''),
    })
  }

  const games = filtered.length
  const winRate = games ? wins / games : 0

  let avgKDA: ZjAverageKda | null = null
  if (kdaN) {
    const avgK = sumK / kdaN
    const avgD = sumD / kdaN
    const avgA = sumA / kdaN
    const avgRating = ratingN
      ? sumRating / ratingN
      : avgD > 0
        ? (avgK + avgA) / avgD
        : avgK + avgA
    avgKDA = {
      rating: avgRating,
      k: Math.round(avgK),
      d: Math.round(avgD),
      a: Math.round(avgA),
      text: `${avgRating.toFixed(2)}(${Math.round(avgK)}-${Math.round(avgD)}-${Math.round(avgA)})`,
    }
  }

  const champWinRank = Object.keys(champPlay)
    .map((id) => ({ id, ...champPlay[id] }))
    .sort((a, b) => b.win * 1000 + b.play - (a.win * 1000 + a.play))
    .slice(0, 2)
    .map((item) => ({ ...item, name: champNames[item.id] ?? `英雄${item.id}` }))

  const champPlayRank = Object.keys(champPlay)
    .map((id) => ({ id, ...champPlay[id] }))
    .sort((a, b) => b.play * 1000 + b.win - (a.play * 1000 + a.win))
    .slice(0, 2)
    .map((item) => ({ ...item, name: champNames[item.id] ?? `英雄${item.id}` }))

  const posRank = Object.keys(posPlay)
    .map((key) => ({ key, name: POS_MAP[key] ?? key, count: posPlay[key] }))
    .sort((a, b) => b.count - a.count)
    .slice(0, 2)

  return {
    games,
    wins,
    losses: games - wins,
    winRate,
    avgKDA,
    champWinRank,
    champPlayRank,
    posRank,
    list,
  }
}

const FALLBACK_VERSION = '15.20.1'

function loadChampionsByVersion(version: string): Promise<Record<string, string>> {
  return fetch(`https://ddragon.leagueoflegends.com/cdn/${version}/data/zh_CN/champion.json`)
    .then((response) => response.json())
    .then((payload: { data?: Record<string, { key: string; name: string }> }) => {
      const names: Record<string, string> = {}
      Object.values(payload.data ?? {}).forEach((champion) => {
        names[champion.key] = champion.name
      })
      return names
    })
}

/** 英雄名映射：失败只影响显示（退化成「英雄{id}」），不阻塞查询。 */
export function loadChampionNames(): Promise<Record<string, string>> {
  return fetch('https://ddragon.leagueoflegends.com/api/versions.json')
    .then((response) => response.json())
    .then((versions: string[]) => loadChampionsByVersion(versions[0] ?? FALLBACK_VERSION))
    .catch(() => loadChampionsByVersion(FALLBACK_VERSION))
    .catch(() => {
      console.error('英雄名加载失败，将显示英雄 ID')
      return {}
    })
}
