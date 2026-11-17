export interface Paged<T> {
  items: T[]
  total: number
  page: number
  page_size: number
}

export interface UserBrief {
  id: number
  username?: string
  display_name: string
}

export interface AuthUser {
  id: number
  username: string
  display_name: string
  role: 'admin' | 'staff'
  is_admin?: boolean
  is_superadmin?: boolean
  merchant_id?: number
  merchant?: { id: number; name: string }
}

export interface PlatformMerchantRow {
  id: number
  name: string
  note: string
  status: 'active' | 'disabled'
  user_count: number
  player_count: number
  created_at: string
  updated_at: string
}

export interface ToolItemRow {
  id: number
  content: string
  note: string
  sort_order: number
}

export interface ToolListRow {
  id: number
  name: string
  sort_order: number
  items: ToolItemRow[]
}

export interface ToolListsPayload {
  lists: ToolListRow[]
}

export type QueueStatus = 'waiting' | 'playing' | 'done' | 'cancelled'

export interface QueueEntry {
  id: number
  game_id: string
  note: string
  status: QueueStatus
  status_label: string
  wait_minutes: number
  created_at: string
  called_at: string | null
  finished_at: string | null
  operator: UserBrief | null
}

export interface QueuePayload {
  date: string
  shop_name: string
  updated_at: string
  entries: QueueEntry[]
  counts: Record<QueueStatus, number>
}

export interface MerchantPurgeCounts {
  players: number
  players_alive: number
  batches: number
  batches_open: number
  sessions: number
  session_players: number
  ledger: number
  handovers: number
  settlements: number
}

export interface MerchantPurgePreview {
  merchant: { id: number; name: string; status: string }
  counts: MerchantPurgeCounts
  deposit_total_cents: number
  open_batch: { id: number; opened_at: string } | null
  keep: { accounts: boolean; settings: boolean; merchant: boolean }
  warnings: string[]
}

export interface MerchantPurgeResult {
  merchant_id: number
  merchant_name: string
  counts: MerchantPurgeCounts
  backup: string
}

export interface PlayerRow {
  id: number
  game_id: string
  nickname: string
  account: string
  remark: string
  is_blacklisted: boolean
  deposit_cents: number
  bonus_cents: number
  balance_cents: number
  deposit_level: 'low' | 'warn' | 'safe'
  games_played: number
  last_active_at: string
  creator: UserBrief | null
  created_at: string
  total_in_cents?: number
  total_out_cents?: number
  bonus_in_cents?: number
  bonus_used_cents?: number
  entry_count?: number
}

export interface PlayerOption {
  id: number
  game_id: string
  account: string
  is_blacklisted: boolean
  deposit_cents: number
  bonus_cents: number
  balance_cents: number
}

export interface PlayerImportResult {
  created: number
  deposited_cents: number
}

export interface PlayerImportError {
  row: number
  message: string
}

export interface AiPlayerRef {
  id: number
  game_id: string
  account: string
  deposit_cents: number
  bonus_cents: number
  balance_cents: number
  is_blacklisted: boolean
}

export interface AiCandidate {
  player: AiPlayerRef
  score: number
}

export interface AiPlayerItem {
  raw_name: string
  status: 'matched' | 'ambiguous' | 'unmatched'
  confidence: number | null
  team: number | null
  matched_player: AiPlayerRef | null
  candidates: AiCandidate[]
}

export interface AiRecognizePayload {
  items: AiPlayerItem[]
  count: number
  warnings: string[]
  elapsed_ms: number
}

export interface AiStatus {
  enabled: boolean
  model: string
}

export interface DividendTotals {
  session_count: number
  player_times: number
  tea_cents: number
  dividend_cents: number
}

export type DividendMode = 'percent' | 'fixed'

export interface DividendPreviewItem {
  user: UserBrief | null
  pending: DividendTotals
  settled: DividendTotals
  status: 'pending' | 'settled' | 'empty'
  dividend_mode: DividendMode | 'mixed' | null
}

export interface DividendPreview {
  period: { start: string; end: string }
  items: DividendPreviewItem[]
  totals: {
    pending_dividend_cents: number
    pending_tea_cents: number
    operator_count: number
    session_count: number
  }
  warnings: string[]
}

export interface DividendSettlementRow {
  id: number
  user: UserBrief
  period: { start: string; end: string }
  session_count: number
  player_times: number
  tea_cents: number
  dividend_cents: number
  note: string
  settled_by: UserBrief | null
  created_at: string
}

export interface LedgerEntryRow {
  id: number
  created_at: string
  reason: string
  reason_label: string
  amount_cents: number
  signed_amount_cents: number
  balance_before_cents: number
  balance_after_cents: number
  bonus_amount_cents: number
  deposit_after_cents: number
  bonus_after_cents: number
  note: string
  player: { id: number; game_id: string }
  counterparty: { id: number; game_id: string } | null
  session: { id: number; name: string } | null
  batch: { id: number; label: string; opened_at: string } | null
  operator: UserBrief | null
  transfer_group_id: string | null
}

export interface SessionPlayerRow {
  player_id: number
  game_id: string
  account: string
  tea_fee_cents: number
  balance_before_cents: number
  balance_after_cents: number
}

export interface SessionRow {
  id: number
  name: string
  played_at: string
  tea_fee_cents: number
  tea_total_cents: number
  note: string
  player_count: number
  operator: UserBrief | null
  creator: UserBrief | null
  created_at: string
  players: SessionPlayerRow[]
  tea_free_removed?: string[]
}

export interface BatchSummary {
  batch_id: number
  session_count: number
  player_times: number
  tea_total_cents: number
  add_total_cents: number
  refund_total_cents: number
  transfer_out_total_cents: number
  transfer_count: number
  net_change_cents: number
  deposit_total_cents: number
  opening_total_cents: number
}

export type HandoverMethod = 'wechat' | 'alipay' | 'cash' | 'bank' | 'other'

export interface OperatorStat {
  user: UserBrief | null
  session_count: number
  player_times: number
  tea_cents: number
  dividend_cents: number
}

export interface HandoverInfo {
  id: number
  from: UserBrief | null
  deposit_to: UserBrief | null
  tea_to: UserBrief | null
  deposit_cents: number
  tea_cents: number
  deposit_method: HandoverMethod
  deposit_method_label: string
  tea_method: HandoverMethod
  tea_method_label: string
  note: string
  created_at: string
}

export interface CustodyInfo {
  holder: UserBrief | null
  holder_id: number | null
  amount_cents: number
  deposit_cents: number
  tea_cents: number
  batch_id: number | null
}

export interface UserOption {
  id: number
  username: string
  display_name: string
  role: 'admin' | 'staff'
}

export interface BatchRow {
  id: number
  label: string
  display_label: string
  status: 'open' | 'closed'
  opened_at: string
  closed_at: string | null
  note: string
  opened_by: UserBrief | null
  closed_by: UserBrief | null
  session_count: number
  player_times: number
  summary: BatchSummary
  dividend_rate_percent: number
  dividend_mode: DividendMode
  dividend_fixed_cents: number
  operators: OperatorStat[]
  handover: HandoverInfo | null
  sessions: SessionRow[]
}

export interface SettingsPayload {
  last_tea_cents: number
  deposit_low_cents: number
  deposit_high_cents: number
  dividend_rate_percent: number
  dividend_mode: DividendMode
  dividend_fixed_cents: number
  shop_name: string
}

export interface SummaryTotals {
  session_count: number
  player_times: number
  tea_cents: number
  add_deposit_cents: number
  refund_cents: number
  cash_diff_cents: number
  dividend_cents: number
}

export interface OperatorSummaryRow extends SummaryTotals {
  user: UserBrief | null
}

export interface OperatorSummary {
  date_from: string
  date_to: string
  dividend_mode: DividendMode
  dividend_rate_percent: number
  dividend_fixed_cents: number
  rows: OperatorSummaryRow[]
  totals: SummaryTotals
}

export interface OperatorOption {
  id: number
  username: string
  display_name: string
  role: 'admin' | 'staff'
  is_active: boolean
}

export interface OperatorCashSummary {
  operator: UserBrief | null
  add_deposit_cents: number
  refund_cents: number
  cash_diff_cents: number
  entry_count: number
}

export interface OverviewPayload {
  date: string
  total_deposit_cents: number
  total_bonus_cents: number
  player_count: number
  low_deposit_count: number
  deposit_low_cents: number
  deposit_high_cents: number
  dividend_mode: DividendMode
  dividend_rate_percent: number
  dividend_fixed_cents: number
  today: SummaryTotals
  today_operators: OperatorSummaryRow[]
  recent_records: LedgerEntryRow[]
}

export interface AccountRow {
  id: number
  username: string
  display_name: string
  role: 'admin' | 'staff'
  is_active: boolean
  is_superadmin?: boolean
  merchant_id?: number
  last_login_at: string | null
  created_at: string
}

export interface PreviewPayload {
  items: {
    player_id: number
    game_id: string
    account: string
    before_cents: number
    deduct_cents: number
    after_cents: number
    deposit_before_cents: number
    deposit_after_cents: number
    bonus_before_cents: number
    bonus_after_cents: number
    bonus_deduct_cents: number
    level: string
    negative: boolean
  }[]
  count: number
  tea_fee_cents: number
  tea_total_cents: number
  negative_count: number
  negative_players: string[]
  tea_free_removed: string[]
}

export interface RechargeCampaign {
  id: number
  threshold_cents: number
  bonus_cents: number
  created_at: string
  updated_at: string
}

export interface ReconcilePayload {
  ok: boolean
  checked: number
  total_deposit_cents: number
  total_bonus_cents: number
  total_ledger_cents: number
  total_cash_ledger_cents: number
  total_bonus_ledger_cents: number
  problems: {
    player_id: number
    game_id: string
    stored_cents: number
    ledger_sum_cents: number
    last_balance_cents: number
    stored_bonus_cents: number
    ledger_bonus_sum_cents: number
    last_bonus_cents: number
  }[]
}


// ---------------- 查战绩（多用户版） ----------------

export interface ZjQuota {
  total: number
  used: number
  remaining: number
}

export interface ZjProfile {
  id: number
  username: string
  display_name: string
  quota: ZjQuota
  is_active?: boolean
}

export interface ZjLoginResult {
  access_token: string
  token_type: string
  expires_in: number
  user: ZjProfile
}

/** 上游返回的单场对局，字段随站点变化，统一按可选处理。 */
export interface ZjMatchDetail {
  isme?: number | string
  info?: string
}

export interface ZjMatch {
  isWin?: number | string
  championId?: number | string
  title?: string
  titleTime?: string
  detail?: ZjMatchDetail[]
}

export interface ZjBatchResult {
  batch_id: number
  expires_at: string
  players: string[]
  quota: ZjQuota
}

export interface ZjQueryResult {
  matches: ZjMatch[]
  cached: boolean
}

export interface ZjAdminUser {
  id: number
  username: string
  display_name: string
  note: string
  quota_total: number
  quota_used: number
  quota_remaining: number
  is_active: boolean
  last_login_at: string | null
  created_at: string
}

export interface ZjOverview {
  users: number
  active_users: number
  remaining: number
  today_used: number
}

export interface ZjAdminList {
  overview: ZjOverview
  users: ZjAdminUser[]
}

export interface ZjLogItem {
  type: 'grant' | 'query'
  id: number
  created_at: string
  delta?: number
  remaining?: number
  note?: string
  operator?: string
  nickname?: string
  ok?: boolean
  games?: number
  err_code?: string
}

export interface ZjLogs {
  items: ZjLogItem[]
  total_returned: number
  has_more: boolean
}
