import { defineStore } from 'pinia'

import { authApi } from '@/api'
import { clearSession, readUser, saveSession } from '@/api/http'
import type { AuthUser } from '@/api/types'

interface State {
  token: string
  user: AuthUser | null
  loading: boolean
}

export const useAuthStore = defineStore('auth', {
  state: (): State => ({
    token: localStorage.getItem('lol_token') || '',
    user: readUser<AuthUser>(),
    loading: false,
  }),
  getters: {
    isLoggedIn: (state) => Boolean(state.token),
    isAdmin: (state) => state.user?.role === 'admin',
    displayName: (state) => state.user?.display_name || state.user?.username || '',
    merchantName: (state) => state.user?.merchant?.name || '',
  },
  actions: {
    async login(username: string, password: string) {
      this.loading = true
      try {
        const data = await authApi.login(username, password)
        this.token = data.access_token
        this.user = data.user
        saveSession(data.access_token, data.user)
        return data
      } finally {
        this.loading = false
      }
    },
    async fetchMe() {
      const user = await authApi.me()
      this.user = user
      saveSession(this.token, user)
      return user
    },
    async logout() {
      try {
        await authApi.logout()
      } catch {
        /* 网络失败也要退出 */
      }
      this.token = ''
      this.user = null
      clearSession()
    },
    reset() {
      this.token = ''
      this.user = null
      clearSession()
    },
  },
})
