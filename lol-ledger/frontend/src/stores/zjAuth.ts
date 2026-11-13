import { defineStore } from 'pinia'

import { ZJ_TOKEN_KEY, ZJ_USER_KEY, zjApi } from '@/api/zj'
import type { ZjProfile, ZjQuota } from '@/api/types'

function readStoredUser(): ZjProfile | null {
  const raw = localStorage.getItem(ZJ_USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as ZjProfile
  } catch {
    return null
  }
}

interface State {
  token: string
  user: ZjProfile | null
  loading: boolean
}

/** 查战绩账号的登录态。和 stores/auth.ts 互不可见。 */
export const useZjAuthStore = defineStore('zjAuth', {
  state: (): State => ({
    token: localStorage.getItem(ZJ_TOKEN_KEY) || '',
    user: readStoredUser(),
    loading: false,
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
    displayName: (state) => state.user?.display_name || state.user?.username || '',
    quota: (state): ZjQuota => state.user?.quota ?? { total: 0, used: 0, remaining: 0 },
    remaining(): number {
      return this.quota.remaining
    },
    total(): number {
      return this.quota.total
    },
    exhausted(): boolean {
      return this.remaining <= 0
    },
  },
  actions: {
    persist() {
      if (this.token) {
        localStorage.setItem(ZJ_TOKEN_KEY, this.token)
      } else {
        localStorage.removeItem(ZJ_TOKEN_KEY)
      }
      if (this.user) {
        localStorage.setItem(ZJ_USER_KEY, JSON.stringify(this.user))
      } else {
        localStorage.removeItem(ZJ_USER_KEY)
      }
    },
    async login(username: string, password: string) {
      this.loading = true
      try {
        const data = await zjApi.login(username, password)
        this.token = data.access_token
        this.user = data.user
        this.persist()
        return data
      } finally {
        this.loading = false
      }
    },
    async fetchMe() {
      const profile = await zjApi.me()
      this.user = profile
      this.persist()
      return profile
    },
    setQuota(quota: ZjQuota) {
      if (!this.user) return
      this.user = { ...this.user, quota }
      this.persist()
    },
    clear() {
      this.token = ''
      this.user = null
      this.persist()
    },
    logout() {
      this.clear()
    },
  },
})
