import { http } from './http'
import type {
  AccountRow,
  AiRecognizePayload,
  AiStatus,
  AuthUser,
  DividendPreview,
  DividendSettlementRow,
  LedgerEntryRow,
  MerchantPurgePreview,
  MerchantPurgeResult,
  OperatorSummary,
  OverviewPayload,
  Paged,
  PlatformMerchantRow,
  QueueEntry,
  QueuePayload,
  QueueStatus,
  PlayerImportResult,
  PlayerOption,
  PlayerRow,
  PreviewPayload,
  ReconcilePayload,
  SessionRow,
  SettingsPayload,
  ToolItemRow,
  ToolListRow,
  ToolListsPayload,
  UserOption,
  ZjAdminList,
  ZjAdminUser,
  ZjLogs,
  ZjOverview,
} from './types'

type Query = Record<string, string | number | boolean | undefined | null>

export const authApi = {
  login: (username: string, password: string) =>
    http
      .post('/auth/login', { username, password })
      .then((res) => res.data as { access_token: string; expires_in: number; user: AuthUser }),
  me: () => http.get('/auth/me').then((res) => res.data as AuthUser),
  changePassword: (old_password: string, new_password: string) =>
    http.post('/auth/password', { old_password, new_password }),
  logout: () => http.post('/auth/logout'),
}

export const playerApi = {
  list: (params: Query) => http.get('/players', { params }).then((res) => res.data as Paged<PlayerRow>),
  options: (params: Query) =>
    http.get('/players/options', { params }).then((res) => res.data as PlayerOption[]),
  get: (id: number) => http.get(`/players/${id}`).then((res) => res.data as PlayerRow),
  ledger: (id: number, params: Query) =>
    http.get(`/players/${id}/ledger`, { params }).then((res) => res.data as Paged<LedgerEntryRow>),
  create: (payload: Record<string, unknown>) =>
    http.post('/players', payload).then((res) => res.data as PlayerRow),
  update: (id: number, payload: Record<string, unknown>) =>
    http.patch(`/players/${id}`, payload).then((res) => res.data as PlayerRow),
  remove: (id: number) => http.delete(`/players/${id}`),
  importFile: (file: File) => {
    const form = new FormData()
    form.append('file', file)
    return http
      .post('/players/import', form)
      .then((res) => res.data as PlayerImportResult)
  },
}

export const moneyApi = {
  addDeposit: (id: number, amount_cents: number, note = '') =>
    http
      .post(`/players/${id}/deposits`, { amount_cents, note })
      .then((res) => res.data as { entry: LedgerEntryRow; player: PlayerRow }),
  refund: (id: number, amount_cents: number, note = '') =>
    http
      .post(`/players/${id}/refunds`, { amount_cents, note })
      .then((res) => res.data as { entry: LedgerEntryRow; player: PlayerRow }),
  transfer: (from_player_id: number, to_player_id: number, amount_cents: number, note = '') =>
    http.post('/transfers', { from_player_id, to_player_id, amount_cents, note }).then((res) => res.data),
}

export const summaryApi = {
  operators: (date_from?: string, date_to?: string) =>
    http
      .get('/summary/operators', { params: { date_from, date_to } })
      .then((res) => res.data as OperatorSummary),
}

export const sessionApi = {
  list: (params: Query) =>
    http.get('/sessions', { params }).then((res) => res.data as Paged<SessionRow>),
  preview: (player_ids: number[], tea_fee_cents: number) =>
    http
      .post('/sessions/preview', { player_ids, tea_fee_cents })
      .then((res) => res.data as PreviewPayload),
  create: (payload: Record<string, unknown>) =>
    http.post('/sessions', payload).then((res) => res.data as SessionRow),
  get: (id: number) => http.get(`/sessions/${id}`).then((res) => res.data as SessionRow),
}

export const recordApi = {
  deposits: (params: Query) =>
    http.get('/records/deposits', { params }).then((res) => res.data as Paged<LedgerEntryRow>),
  sessions: (params: Query) =>
    http.get('/records/sessions', { params }).then((res) => res.data as Paged<SessionRow>),
}

export const dividendApi = {
  preview: (date_from?: string, date_to?: string) =>
    http
      .get('/reports/dividends/preview', { params: { date_from, date_to } })
      .then((res) => res.data as DividendPreview),
  settle: (payload: {
    user_ids: number[]
    date_from?: string
    date_to?: string
    note?: string
  }) =>
    http
      .post('/reports/dividends/settle', payload)
      .then((res) => res.data as DividendSettlementRow[]),
  settlements: (page = 1, page_size = 10) =>
    http
      .get('/reports/dividends/settlements', { params: { page, page_size } })
      .then((res) => res.data as Paged<DividendSettlementRow>),
}

export const overviewApi = {
  get: () => http.get('/overview').then((res) => res.data as OverviewPayload),
  reconcile: () => http.get('/reconcile').then((res) => res.data as ReconcilePayload),
}

export const settingsApi = {
  get: () => http.get('/settings').then((res) => res.data as SettingsPayload),
  update: (payload: Partial<SettingsPayload>) =>
    http.patch('/settings', payload).then((res) => res.data as SettingsPayload),
}

export const accountApi = {
  list: () => http.get('/users').then((res) => res.data as AccountRow[]),
  options: () => http.get('/users/options').then((res) => res.data as UserOption[]),
  create: (payload: Record<string, unknown>) =>
    http.post('/users', payload).then((res) => res.data as AccountRow),
  update: (id: number, payload: Record<string, unknown>) =>
    http.patch(`/users/${id}`, payload).then((res) => res.data as AccountRow),
  resetPassword: (id: number, new_password: string) =>
    http.post(`/users/${id}/password`, { new_password }),
}

export const toolListApi = {
  list: () => http.get('/tools/name-lists').then((res) => res.data as ToolListsPayload),
  createList: (name: string) =>
    http.post('/tools/name-lists', { name }).then((res) => res.data as ToolListRow),
  renameList: (id: number, name: string) =>
    http.patch(`/tools/name-lists/${id}`, { name }).then((res) => res.data as ToolListRow),
  deleteList: (id: number) => http.delete(`/tools/name-lists/${id}`),
  moveList: (id: number, direction: 'up' | 'down') =>
    http
      .post(`/tools/name-lists/${id}/move`, { direction })
      .then((res) => res.data as ToolListsPayload),
  createItem: (listId: number, content: string, note = '') =>
    http
      .post(`/tools/name-lists/${listId}/items`, { content, note })
      .then((res) => res.data as ToolItemRow),
  updateItem: (listId: number, itemId: number, payload: { content?: string; note?: string }) =>
    http
      .patch(`/tools/name-lists/${listId}/items/${itemId}`, payload)
      .then((res) => res.data as ToolItemRow),
  deleteItem: (listId: number, itemId: number) =>
    http.delete(`/tools/name-lists/${listId}/items/${itemId}`),
  moveItem: (listId: number, itemId: number, direction: 'up' | 'down') =>
    http
      .post(`/tools/name-lists/${listId}/items/${itemId}/move`, { direction })
      .then((res) => res.data as ToolItemRow),
}

export const queueApi = {
  list: (day?: string) =>
    http.get('/queue', { params: day ? { day } : {} }).then((res) => res.data as QueuePayload),
  snapshot: (day?: string) =>
    http
      .get('/queue/snapshot', { params: day ? { day } : {} })
      .then((res) => res.data as QueuePayload),
  create: (payload: { game_id: string; note?: string }) =>
    http.post('/queue', payload).then((res) => res.data as QueueEntry),
  setStatus: (id: number, status: QueueStatus) =>
    http.patch(`/queue/${id}`, { status }).then((res) => res.data as QueueEntry),
}

export const platformApi = {
  merchants: () =>
    http.get('/platform/merchants').then((res) => res.data as PlatformMerchantRow[]),
  createMerchant: (payload: Record<string, unknown>) =>
    http
      .post('/platform/merchants', payload)
      .then((res) => res.data as { merchant: PlatformMerchantRow; admin: AccountRow | null }),
  updateMerchant: (id: number, payload: Record<string, unknown>) =>
    http.patch(`/platform/merchants/${id}`, payload).then((res) => res.data as PlatformMerchantRow),
  users: (merchantId: number) =>
    http
      .get(`/platform/merchants/${merchantId}/users`)
      .then((res) => res.data as AccountRow[]),
  createUser: (merchantId: number, payload: Record<string, unknown>) =>
    http
      .post(`/platform/merchants/${merchantId}/users`, payload)
      .then((res) => res.data as AccountRow),
  updateUser: (id: number, payload: Record<string, unknown>) =>
    http.patch(`/platform/users/${id}`, payload).then((res) => res.data as AccountRow),
  resetPassword: (id: number, new_password: string) =>
    http.post(`/platform/users/${id}/password`, { new_password }),
  purgePreview: (id: number) =>
    http
      .get(`/platform/merchants/${id}/purge-preview`)
      .then((res) => res.data as MerchantPurgePreview),
  purge: (id: number, payload: { confirm_name: string; note?: string }) =>
    http
      .post(`/platform/merchants/${id}/purge`, payload)
      .then((res) => res.data as MerchantPurgeResult),
}

export const zjAdminApi = {
  users: () => http.get('/platform/zj/users').then((res) => res.data as ZjAdminList),
  create: (payload: Record<string, unknown>) =>
    http.post('/platform/zj/users', payload).then((res) => res.data as ZjAdminUser),
  update: (id: number, payload: Record<string, unknown>) =>
    http.patch(`/platform/zj/users/${id}`, payload).then((res) => res.data as ZjAdminUser),
  grant: (id: number, delta: number, note = '') =>
    http
      .post(`/platform/zj/users/${id}/quota`, { delta, note })
      .then((res) => res.data as { user: ZjAdminUser; overview: ZjOverview }),
  resetPassword: (id: number, new_password: string) =>
    http.post(`/platform/zj/users/${id}/password`, { new_password }),
  logs: (id: number, limit = 50, offset = 0) =>
    http
      .get(`/platform/zj/users/${id}/logs`, { params: { limit, offset } })
      .then((res) => res.data as ZjLogs),
}

export const aiApi = {
  status: () => http.get('/ai/status').then((res) => res.data as AiStatus),
  recognize: (file: File, signal?: AbortSignal) => {
    const form = new FormData()
    form.append('file', file)
    return http
      .post('/ai/recognize-players', form, { signal })
      .then((res) => res.data as AiRecognizePayload)
  },
}
