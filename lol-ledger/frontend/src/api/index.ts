import { http } from './http'
import type {
  AccountRow,
  AuthUser,
  BatchRow,
  BatchSummary,
  LedgerEntryRow,
  OverviewPayload,
  Paged,
  PlayerOption,
  PlayerRow,
  PreviewPayload,
  ReconcilePayload,
  SessionRow,
  SettingsPayload,
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
  deduct: (id: number, amount_cents: number, note = '') =>
    http
      .post(`/players/${id}/deductions`, { amount_cents, note })
      .then((res) => res.data as { entry: LedgerEntryRow; player: PlayerRow }),
  transfer: (from_player_id: number, to_player_id: number, amount_cents: number, note = '') =>
    http.post('/transfers', { from_player_id, to_player_id, amount_cents, note }).then((res) => res.data),
}

export const batchApi = {
  list: (params: Query) => http.get('/batches', { params }).then((res) => res.data as Paged<BatchRow>),
  current: () =>
    http.get('/batches/current').then((res) => res.data as { batch: BatchRow | null }),
  create: (payload: { label?: string; note?: string }) =>
    http.post('/batches', payload).then((res) => res.data as BatchRow),
  get: (id: number) => http.get(`/batches/${id}`).then((res) => res.data as BatchRow),
  summary: (id: number) =>
    http.get(`/batches/${id}/summary`).then((res) => res.data as BatchSummary),
  close: (id: number, note = '') =>
    http.post(`/batches/${id}/close`, { note }).then((res) => res.data as BatchSummary),
  ledger: (id: number, params: Query) =>
    http.get(`/batches/${id}/ledger`, { params }).then((res) => res.data as Paged<LedgerEntryRow>),
}

export async function downloadBatchCsv(batchId: number, label: string): Promise<void> {
  const response = await http.get(`/batches/${batchId}/export.csv`, { responseType: 'blob' })
  const url = URL.createObjectURL(response.data as Blob)
  const anchor = document.createElement('a')
  anchor.href = url
  anchor.download = `批次-${label || batchId}.csv`
  document.body.appendChild(anchor)
  anchor.click()
  anchor.remove()
  URL.revokeObjectURL(url)
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
  create: (payload: Record<string, unknown>) =>
    http.post('/users', payload).then((res) => res.data as AccountRow),
  update: (id: number, payload: Record<string, unknown>) =>
    http.patch(`/users/${id}`, payload).then((res) => res.data as AccountRow),
  resetPassword: (id: number, new_password: string) =>
    http.post(`/users/${id}/password`, { new_password }),
}

export const aiApi = {
  recognize: () => http.post('/ai/recognize-players'),
}
