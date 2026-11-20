import { defineStore } from 'pinia'

import { overviewApi } from '@/api'
import type { SummaryTotals } from '@/api/types'

const THEME_KEY = 'lol_theme'
const SUMMARY_RANGE_KEY = 'lol_summary_range'

const MOMENT_RE = /^\d{4}-\d{2}-\d{2}T\d{2}:\d{2}$/

function readSummaryRange(): [string, string] | null {
  try {
    const raw = localStorage.getItem(SUMMARY_RANGE_KEY)
    if (!raw) return null
    const parsed = JSON.parse(raw)
    if (
      Array.isArray(parsed) &&
      parsed.length === 2 &&
      typeof parsed[0] === 'string' &&
      typeof parsed[1] === 'string' &&
      MOMENT_RE.test(parsed[0]) &&
      MOMENT_RE.test(parsed[1])
    ) {
      return [parsed[0], parsed[1]]
    }
  } catch {
    // 脏数据直接忽略，用默认区间
  }
  return null
}

export const useAppStore = defineStore('app', {
  state: () => ({
    theme: localStorage.getItem(THEME_KEY) || 'dark',
    summaryRange: readSummaryRange() as [string, string] | null,
    today: null as SummaryTotals | null,
    todayLoaded: false,
    todayLoading: false,
    todayError: false,
  }),
  actions: {
    applyTheme() {
      document.documentElement.classList.toggle('dark', this.theme === 'dark')
    },
    toggleTheme() {
      this.theme = this.theme === 'dark' ? 'light' : 'dark'
      localStorage.setItem(THEME_KEY, this.theme)
      this.applyTheme()
    },
    setSummaryRange(range: [string, string]) {
      this.summaryRange = range
      try {
        localStorage.setItem(SUMMARY_RANGE_KEY, JSON.stringify(range))
      } catch {
        // 存储写满等异常不影响本次会话内记忆
      }
    },
    async refreshToday() {
      this.todayLoading = true
      this.todayError = false
      try {
        const payload = await overviewApi.get()
        this.today = payload.today
      } catch {
        this.today = null
        this.todayError = true
      } finally {
        this.todayLoading = false
        this.todayLoaded = true
      }
    },
  },
})
