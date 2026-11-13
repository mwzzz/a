import { defineStore } from 'pinia'

import { overviewApi } from '@/api'
import type { SummaryTotals } from '@/api/types'

const THEME_KEY = 'lol_theme'

export const useAppStore = defineStore('app', {
  state: () => ({
    theme: localStorage.getItem(THEME_KEY) || 'dark',
    today: null as SummaryTotals | null,
    todayLoaded: false,
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
    async refreshToday() {
      try {
        const payload = await overviewApi.get()
        this.today = payload.today
      } catch {
        this.today = null
      } finally {
        this.todayLoaded = true
      }
    },
  },
})
