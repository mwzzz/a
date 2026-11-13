import axios from 'axios'

import type {
  ZjBatchResult,
  ZjLoginResult,
  ZjProfile,
  ZjQueryResult,
} from './types'

export const ZJ_TOKEN_KEY = 'zj_token'
export const ZJ_USER_KEY = 'zj_user'

/**
 * 查战绩账号专用 axios 实例：token 与记账系统完全分离，
 * 401 只会跳 /zj/login，不会把人踢到记账登录页。
 */
export const zjHttp = axios.create({
  baseURL: '/api/v1/zj',
  timeout: 40000,
})

zjHttp.interceptors.request.use((config) => {
  const token = localStorage.getItem(ZJ_TOKEN_KEY)
  if (token) config.headers.Authorization = `Bearer ${token}`
  return config
})

let redirecting = false

zjHttp.interceptors.response.use(
  (response) => response,
  (error) => {
    if (error?.response?.status === 401) {
      localStorage.removeItem(ZJ_TOKEN_KEY)
      localStorage.removeItem(ZJ_USER_KEY)
      if (!redirecting && window.location.pathname !== '/zj/login') {
        redirecting = true
        const redirect = encodeURIComponent(window.location.pathname + window.location.search)
        window.setTimeout(() => {
          window.location.href = `/zj/login?redirect=${redirect}`
        }, 200)
      }
    }
    return Promise.reject(error)
  },
)

/** 把后端 detail / 常见状态码翻译成能直接给用户看的一句话。 */
export function zjErrorMessage(error: any): string {
  const detail = error?.response?.data?.detail
  if (typeof detail === 'string' && detail) return detail
  if (Array.isArray(detail) && detail.length) {
    const first = detail[0]
    const field = Array.isArray(first?.loc) ? first.loc[first.loc.length - 1] : ''
    return field ? `参数不正确：${field}` : '参数不正确'
  }
  const status = error?.response?.status
  if (status === 401) return '登录已过期，请重新登录'
  if (status === 403) return '没有权限执行这个操作'
  if (status === 429) return '操作太频繁，请稍后再试'
  if (status === 502 || status === 504) return '上游查询暂时不可用，请稍后再试'
  if (status === 500) return '服务异常，请稍后再试'
  if (error?.code === 'ECONNABORTED') return '请求超时，请重试'
  if (!error?.response) return '网络异常，请检查连接'
  return '操作失败'
}

export const zjApi = {
  login: (username: string, password: string) =>
    zjHttp
      .post('/auth/login', { username, password })
      .then((res) => res.data as ZjLoginResult),
  me: () => zjHttp.get('/auth/me').then((res) => res.data as ZjProfile),
  changePassword: (old_password: string, new_password: string) =>
    zjHttp.post('/auth/password', { old_password, new_password }),
  createBatch: (payload: { area_id: number; all_count: number; players: string[] }) =>
    zjHttp.post('/batches', payload).then((res) => res.data as ZjBatchResult),
  queryPlayer: (batchId: number, nickname: string) =>
    zjHttp
      .post(`/batches/${batchId}/queries`, { nickname })
      .then((res) => res.data as ZjQueryResult),
  closeBatch: (batchId: number) => zjHttp.post(`/batches/${batchId}/close`),
}
