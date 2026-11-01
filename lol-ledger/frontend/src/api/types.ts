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
  merchant_id?: number
  merchant?: { id: number; name: string }
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
  deduct_total_cents: number
  transfer_out_total_cents: number
  transfer_count: number
  net_change_cents: number
  deposit_total_cents: number
  opening_total_cents: number
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
  sessions: SessionRow[]
}

export interface SettingsPayload {
  last_tea_cents: number
  deposit_low_cents: number
  deposit_high_cents: number
  shop_name: string
}

export interface OverviewPayload {
  total_deposit_cents: number
  player_count: number
  low_deposit_count: number
  deposit_low_cents: number
  deposit_high_cents: number
  today: {
    session_count: number
    player_times: number
    tea_total_cents: number
    add_total_cents: number
    refund_total_cents: number
    deduct_total_cents: number
    transfer_count: number
    transfer_total_cents: number
  }
  open_batch: {
    id: number
    label: string
    opened_at: string
    summary: BatchSummary
  } | null
  recent_records: LedgerEntryRow[]
}

export interface AccountRow {
  id: number
  username: string
  display_name: string
  role: 'admin' | 'staff'
  is_active: boolean
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
