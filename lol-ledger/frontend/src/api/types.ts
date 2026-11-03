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

export interface PlayerRow {
  id: number
  game_id: string
  nickname: string
  account: string
  remark: string
  deposit_cents: number
  deposit_level: 'low' | 'warn' | 'safe'
  games_played: number
  last_active_at: string
  creator: UserBrief | null
  created_at: string
  total_in_cents?: number
  total_out_cents?: number
  entry_count?: number
}

export interface PlayerOption {
  id: number
  game_id: string
  account: string
  deposit_cents: number
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

export interface LedgerEntryRow {
  id: number
  created_at: string
  reason: string
  reason_label: string
  amount_cents: number
  signed_amount_cents: number
  balance_before_cents: number
  balance_after_cents: number
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
  batch_id: number
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
  batch?: { id: number; label: string; opened_at: string } | null
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
  operators: OperatorStat[]
  handover: HandoverInfo | null
  sessions: SessionRow[]
}

export interface SettingsPayload {
  last_tea_cents: number
  deposit_low_cents: number
  deposit_high_cents: number
  dividend_rate_percent: number
  shop_name: string
}

export interface OverviewPayload {
  total_deposit_cents: number
  player_count: number
  low_deposit_count: number
  deposit_low_cents: number
  deposit_high_cents: number
  custody: CustodyInfo
  open_batch: {
    id: number
    label: string
    opened_at: string
    summary: BatchSummary
    dividend_rate_percent: number
    operators: OperatorStat[]
  } | null
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
    level: string
    negative: boolean
  }[]
  count: number
  tea_fee_cents: number
  tea_total_cents: number
  negative_count: number
  negative_players: string[]
}

export interface ReconcilePayload {
  ok: boolean
  checked: number
  total_deposit_cents: number
  total_ledger_cents: number
  problems: {
    player_id: number
    game_id: string
    stored_cents: number
    ledger_sum_cents: number
    last_balance_cents: number
  }[]
}
