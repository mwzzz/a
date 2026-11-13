import type { ZjPlayer, ZjStat } from '@/utils/zjStats'

export interface ZjResultRow {
  player: ZjPlayer
  stat: ZjStat | null
  error?: string
}

export type ZjSortKey = 'winRate' | 'games' | 'wins' | 'kda'

export const SORT_OPTIONS: { value: ZjSortKey; label: string }[] = [
  { value: 'winRate', label: '按胜率 ↓' },
  { value: 'games', label: '按新模式场次 ↓' },
  { value: 'wins', label: '按胜场 ↓' },
  { value: 'kda', label: '按平均 KDA ↓' },
]
