import { defineStore } from 'pinia'

const COLLAPSED_KEY = 'lol_collapsed_batches'
const THEME_KEY = 'lol_theme'

function readCollapsed(): number[] {
  try {
    const raw = localStorage.getItem(COLLAPSED_KEY)
    return raw ? (JSON.parse(raw) as number[]) : []
  } catch {
    return []
  }
}

export const useAppStore = defineStore('app', {
  state: () => ({
    theme: localStorage.getItem(THEME_KEY) || 'dark',
    collapsed: readCollapsed(),
    currentBatchId: null as number | null,
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
    isCollapsed(id: number) {
      return this.collapsed.includes(id)
    },
    toggleBatch(id: number) {
      if (this.collapsed.includes(id)) {
        this.collapsed = this.collapsed.filter((item) => item !== id)
      } else {
        this.collapsed = [...this.collapsed, id]
      }
      localStorage.setItem(COLLAPSED_KEY, JSON.stringify(this.collapsed))
    },
  },
})
