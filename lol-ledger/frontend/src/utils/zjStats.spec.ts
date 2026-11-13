import { describe, expect, it } from 'vitest'

import type { ZjMatch } from '@/api/types'

import {
  isNewMode,
  kdaOfMatch,
  modeOfMatch,
  parsePlayers,
  posOfMatch,
  statPlayer,
  timeOfMatch,
} from './zjStats'

const newModeWin: ZjMatch = {
  isWin: 1,
  championId: 1,
  title: '新模式 五子登科',
  titleTime: '11-05 15:20:12 [上] 胜',
  detail: [{ isme: 1, info: '安妮 8.5 (3-1-5)' }],
}

const newModeLose: ZjMatch = {
  isWin: 0,
  championId: 2,
  title: '新模式 满载SUV',
  titleTime: '11-05 14:10:00 [野] 负',
  detail: [{ isme: 1, info: '盲僧 4.2 (0-4-2)' }],
}

const ranked: ZjMatch = {
  isWin: 1,
  championId: 3,
  title: '单双排位 胜利',
  titleTime: '11-04 20:00:00 [中] 胜',
  detail: [{ isme: 1, info: '辛德拉 9.1 (5-1-3)' }],
}

describe('parsePlayers', () => {
  it('解析客户端粘贴的「昵称#编号加入了队伍聊天」', () => {
    const text = '有多少人和我一样#60733加入了队伍聊天\n兜兜是俺滴儿#45870加入了队伍聊天'
    const players = parsePlayers(text)
    expect(players.map((player) => player.full)).toEqual([
      '有多少人和我一样#60733',
      '兜兜是俺滴儿#45870',
    ])
  })

  it('清掉不可见字符后再解析', () => {
    const players = parsePlayers('\u2068兜兜\u2069#45870')
    expect(players).toHaveLength(1)
    expect(players[0].full).toBe('兜兜#45870')
  })

  it('去重并忽略不含编号的行', () => {
    const players = parsePlayers('兜兜#45870\n兜兜#45870\n随便一行')
    expect(players).toHaveLength(1)
  })
})

describe('kdaOfMatch', () => {
  it('从 (3-1-5) 里取 KDA，评分取括号前的数字', () => {
    expect(kdaOfMatch(newModeWin)).toMatchObject({ k: 3, d: 1, a: 5, rating: 8.5 })
  })

  it('优先取 isme=1 的详情行', () => {
    const match: ZjMatch = {
      title: '新模式',
      detail: [
        { isme: 0, info: '队友 1.0 (1-9-2)' },
        { isme: 1, info: '我 6.5 (8-2-6)' },
      ],
    }
    expect(kdaOfMatch(match)).toMatchObject({ k: 8, d: 2, a: 6, rating: 6.5 })
  })

  it('没有 KDA 片段时返回 null', () => {
    expect(kdaOfMatch({ title: '新模式' })).toBeNull()
  })
})

describe('posOfMatch / modeOfMatch / timeOfMatch', () => {
  it('识别方括号位置标记', () => {
    expect(posOfMatch({ titleTime: '11-05 15:20:12 [野] 胜' })).toBe('打野')
  })

  it('识别文字位置', () => {
    expect(posOfMatch({ title: '新模式 辅助 胜' })).toBe('辅助')
  })

  it('识别模式与时间', () => {
    expect(modeOfMatch(ranked)).toBe('排位')
    expect(timeOfMatch(newModeWin)).toBe('11-05 15:20:12')
    expect(isNewMode(newModeWin)).toBe(true)
    expect(isNewMode(ranked)).toBe(false)
  })
})

describe('statPlayer', () => {
  it('只统计新模式，胜率与胜负正确', () => {
    const stat = statPlayer([newModeWin, newModeLose, ranked], 50, {})

    expect(stat.games).toBe(2)
    expect(stat.wins).toBe(1)
    expect(stat.losses).toBe(1)
    expect(stat.winRate).toBe(0.5)
    expect(stat.list.map((item) => item.mode)).toEqual(['新模式', '新模式'])
  })

  it('按统计上限截断', () => {
    const stat = statPlayer([newModeWin, newModeLose], 1, {})
    expect(stat.games).toBe(1)
    expect(stat.wins).toBe(1)
  })

  it('场均 KDA 用详情行里的评分均值', () => {
    const stat = statPlayer([newModeWin, newModeLose], 50, {})

    expect(stat.avgKDA).toMatchObject({ k: 2, d: 3, a: 4, rating: 6.35 })
    expect(stat.avgKDA?.text).toBe('6.35(2-3-4)')
  })

  it('英雄与位置榜单按原口径排序并取前二', () => {
    const names = { '1': '安妮', '2': '盲僧' }
    const stat = statPlayer([newModeWin, newModeLose, newModeWin], 50, names)

    expect(stat.champPlayRank[0]).toMatchObject({ id: '1', name: '安妮', play: 2, win: 2 })
    expect(stat.champWinRank[0]).toMatchObject({ id: '1', win: 2 })
    expect(stat.posRank.map((item) => item.name)).toEqual(['上单', '打野'])
  })

  it('没有新模式对局时给出零值而不炸', () => {
    const stat = statPlayer([ranked], 50, {})
    expect(stat.games).toBe(0)
    expect(stat.winRate).toBe(0)
    expect(stat.avgKDA).toBeNull()
  })
})
