import axios from 'axios'
import { ElMessage } from 'element-plus'

export const TOKEN_KEY = 'lol_token'
export const USER_KEY = 'lol_user'

export const http = axios.create({
  baseURL: '/api/v1',
  timeout: 20000,
})

http.interceptors.request.use((config) => {
  const token = localStorage.getItem(TOKEN_KEY)
  if (token) {
    config.headers.Authorization = `Bearer ${token}`
  }
  return config
})

let redirecting = false

function describe(error: any): string {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string') return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0]
    const field = Array.isArray(first?.loc) ? first.loc[first.loc.length - 1] : ''
    return field ? `参数不正确：${field}` : '参数不正确'
  }
  const status = error?.response?.status
  if (status === 500) return '服务异常，请稍后再试'
  if (status === 502 || status === 504) return '服务暂时不可用，请稍后再试'
  if (error?.code === 'ECONNABORTED') return '请求超时，请重试'
  if (!error?.response) return '网络异常，请检查连接'
  return '操作失败'
}

http.interceptors.response.use(
  (response) => response,
  (error) => {
    const status = error?.response?.status
    const message = describe(error)
    if (status === 401) {
      localStorage.removeItem(TOKEN_KEY)
      localStorage.removeItem(USER_KEY)
      if (!redirecting && window.location.pathname !== '/login') {
        redirecting = true
        ElMessage.warning(message === '操作失败' ? '登录已过期，请重新登录' : message)
        const redirect = encodeURIComponent(window.location.pathname + window.location.search)
        window.setTimeout(() => {
          window.location.href = `/login?redirect=${redirect}`
        }, 300)
      }
    } else {
      ElMessage.error(message)
    }
    return Promise.reject(error)
  },
)

export function saveSession(token: string, user: unknown): void {
  localStorage.setItem(TOKEN_KEY, token)
  localStorage.setItem(USER_KEY, JSON.stringify(user))
}

export function clearSession(): void {
  localStorage.removeItem(TOKEN_KEY)
  localStorage.removeItem(USER_KEY)
}

export function readUser<T>(): T | null {
  const raw = localStorage.getItem(USER_KEY)
  if (!raw) return null
  try {
    return JSON.parse(raw) as T
  } catch {
    return null
  }
}
