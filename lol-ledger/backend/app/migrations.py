"""建表 DDL、版本迁移与种子数据。

结构唯一来源。v2 引入多商家：业务表全部带 merchant_id，唯一索引按商家维度重建。
v3 引入开发者账号：users.is_superadmin + merchants.is_system，并预置一个隐藏的
「平台管理」商家承接超管账号，超管不属于任何门店。
v4 引入现金保管与分红：merchants.custodian_user_id、batches.dividend_rate_percent、
cash_handovers 交接表；同时把手动扣押并入退押金。
v5 引入分红结算：dividend_settlements + dividend_settlement_batches。
v6 引入分红方式：按茶水比例（percent）或每局固定金额（fixed），
batches 增加 dividend_mode / dividend_fixed_cents 快照列。
v7 引入排队登记（queue_entries），v8 取消开班/交班（场次直接统计）。
v9 引入「查战绩」多用户版：zj_users / zj_batches / zj_batch_players /
zj_queries / zj_grants。只新增表，不动任何既有表。
v10 引入「常用名单」小工具；v11 给玩家增加黑名单标记；
v12 引入玩家赠金与充值活动：players.bonus_cents、ledger 现金/赠金拆分、
recharge_campaigns 档位表。
v13 引入「撤销加赠金」：ledger reason 白名单加 bonus_void，新增可空列
reverses_ledger_id 指向被撤销的加赠金流水；仅加宽约束/加列，不动历史数据。

迁移策略：
- 全新库：按 v6 直接建表，写入默认商家、平台商家和默认配置。
- v1 库：先用 SQLite backup API 备份到 data/backups/pre-v2-*.db，
  再在单事务里「旧表改名 → 建 v6 表 → 拷数据 → 删旧表 → 建索引」。
- v2 库：备份到 pre-v3-*.db 加超管/平台商家，再备份到 pre-v4-*.db 加保管/分红。
- v3 库：备份到 pre-v4-*.db，加保管/分红列和交接表，并转换手动扣押。
- v4 库：备份到 pre-v5-*.db，只加分红结算两张表。
- v5 库：备份到 pre-v6-*.db，加班次分红方式/固定金额列，并补上设置项。
- 只做加表 / 加列 / 加索引 / 一次性重建，不删业务列、不改业务名。
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from app import db
from app.defaults import DEFAULT_TOOL_LISTS
from app.timeutil import now_text

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 13
DEFAULT_MERCHANT_NAME = "默认商家"
PLATFORM_MERCHANT_NAME = "平台管理"
DEFAULT_DIVIDEND_RATE = 50
DEFAULT_DIVIDEND_MODE = "percent"
DEFAULT_DIVIDEND_FIXED_CENTS = 0

# v1 里存在的表，迁移时先改名再重建
LEGACY_TABLES: tuple[str, ...] = (
    "settings",
    "audit_logs",
    "ledger",
    "session_players",
    "sessions",
    "batches",
    "players",
    "users",
)

# 按商家存储的配置项。店名统一放 merchants.name，不再进设置表。
SETTING_KEYS: tuple[str, ...] = (
    "last_tea_cents",
    "deposit_low_cents",
    "deposit_high_cents",
    "dividend_rate_percent",
    "dividend_mode",
    "dividend_fixed_cents",
)

DEFAULT_SETTINGS: tuple[tuple[str, str], ...] = (
    ("last_tea_cents", "200"),
    ("deposit_low_cents", "3000"),
    ("deposit_high_cents", "6000"),
    ("dividend_rate_percent", "50"),
    ("dividend_mode", "percent"),
    ("dividend_fixed_cents", "0"),
)

CASH_HANDOVER_TABLE = """
CREATE TABLE IF NOT EXISTS cash_handovers (
    id                  INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id         INTEGER NOT NULL REFERENCES merchants(id),
    batch_id            INTEGER NOT NULL REFERENCES batches(id),
    from_user_id        INTEGER NOT NULL REFERENCES users(id),
    deposit_to_user_id  INTEGER NOT NULL REFERENCES users(id),
    tea_to_user_id      INTEGER NOT NULL REFERENCES users(id),
    deposit_cents       INTEGER NOT NULL DEFAULT 0,
    tea_cents           INTEGER NOT NULL DEFAULT 0,
    deposit_method      TEXT    NOT NULL DEFAULT 'wechat',
    tea_method          TEXT    NOT NULL DEFAULT 'wechat',
    note                TEXT    NOT NULL DEFAULT '',
    created_by          INTEGER NOT NULL REFERENCES users(id),
    created_at          TEXT    NOT NULL
)
"""

DIVIDEND_SETTLEMENT_TABLE = """
CREATE TABLE IF NOT EXISTS dividend_settlements (
    id                    INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id           INTEGER NOT NULL REFERENCES merchants(id),
    user_id               INTEGER NOT NULL REFERENCES users(id),
    username_snapshot     TEXT    NOT NULL,
    display_name_snapshot TEXT    NOT NULL DEFAULT '',
    period_start          TEXT    NOT NULL,
    period_end            TEXT    NOT NULL,
    session_count         INTEGER NOT NULL DEFAULT 0,
    player_times          INTEGER NOT NULL DEFAULT 0,
    tea_cents             INTEGER NOT NULL DEFAULT 0,
    dividend_cents        INTEGER NOT NULL DEFAULT 0,
    note                  TEXT    NOT NULL DEFAULT '',
    settled_by            INTEGER NOT NULL REFERENCES users(id),
    created_at            TEXT    NOT NULL
)
"""

DIVIDEND_SETTLEMENT_BATCH_TABLE = """
CREATE TABLE IF NOT EXISTS dividend_settlement_batches (
    id             INTEGER PRIMARY KEY AUTOINCREMENT,
    settlement_id  INTEGER NOT NULL REFERENCES dividend_settlements(id),
    batch_id       INTEGER NOT NULL REFERENCES batches(id),
    user_id        INTEGER NOT NULL REFERENCES users(id),
    merchant_id    INTEGER NOT NULL REFERENCES merchants(id),
    session_count  INTEGER NOT NULL DEFAULT 0,
    player_times   INTEGER NOT NULL DEFAULT 0,
    tea_cents      INTEGER NOT NULL DEFAULT 0,
    dividend_cents INTEGER NOT NULL DEFAULT 0,
    UNIQUE (batch_id, user_id)
)
"""

DIVIDEND_INDEX_STATEMENTS: tuple[str, ...] = (
    """
    CREATE INDEX IF NOT EXISTS ix_settlements_merchant_period
        ON dividend_settlements(merchant_id, period_end DESC, id DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_settlements_user
        ON dividend_settlements(merchant_id, user_id, period_end DESC)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_settlement_batches_settlement
        ON dividend_settlement_batches(settlement_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_settlement_batches_merchant
        ON dividend_settlement_batches(merchant_id, batch_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_settlement_batches_user
        ON dividend_settlement_batches(merchant_id, user_id)
    """,
)

# 小工具：排队登记（v7）
QUEUE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS queue_entries (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_id INTEGER NOT NULL REFERENCES merchants(id),
        game_id     TEXT    NOT NULL,
        note        TEXT    NOT NULL DEFAULT '',
        status      TEXT    NOT NULL DEFAULT 'waiting'
                    CHECK (status IN ('waiting', 'playing', 'done', 'cancelled')),
        operator_id INTEGER REFERENCES users(id),
        created_at  TEXT    NOT NULL,
        called_at   TEXT,
        finished_at TEXT
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_queue_merchant_status
        ON queue_entries(merchant_id, status, created_at)
    """,
)

# 查战绩多用户版（v9）：独立账号 + 批次 + 批次名单 + 用量 + 充值流水。
# 与记账系统完全解耦：zj_users 不关联 merchants/users，只有 zj_grants.operator_id
# 指向记账系统的开发者账号（谁加的次数）。
ZJ_TABLE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS zj_users (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        username            TEXT    NOT NULL,
        password_hash       TEXT    NOT NULL,
        display_name        TEXT    NOT NULL DEFAULT '',
        note                TEXT    NOT NULL DEFAULT '',
        quota_total         INTEGER NOT NULL DEFAULT 0 CHECK (quota_total >= 0),
        quota_used          INTEGER NOT NULL DEFAULT 0 CHECK (quota_used >= 0),
        is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
        password_changed_at TEXT    NOT NULL,
        last_login_at       TEXT,
        created_at          TEXT    NOT NULL,
        updated_at          TEXT    NOT NULL,
        CHECK (quota_used <= quota_total)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS zj_batches (
        id             INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id        INTEGER NOT NULL REFERENCES zj_users(id),
        area_id        INTEGER NOT NULL,
        all_count      INTEGER NOT NULL CHECK (all_count BETWEEN 1 AND 100),
        player_count   INTEGER NOT NULL CHECK (player_count >= 0),
        query_count    INTEGER NOT NULL DEFAULT 0 CHECK (query_count >= 0),
        status         TEXT    NOT NULL DEFAULT 'open'
                       CHECK (status IN ('open', 'closed')),
        created_at     TEXT    NOT NULL,
        expires_at     TEXT    NOT NULL,
        last_query_at  TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS zj_batch_players (
        batch_id INTEGER NOT NULL REFERENCES zj_batches(id) ON DELETE CASCADE,
        seq      INTEGER NOT NULL,
        nickname TEXT    NOT NULL,
        PRIMARY KEY (batch_id, seq)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS zj_queries (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        batch_id   INTEGER NOT NULL REFERENCES zj_batches(id),
        user_id    INTEGER NOT NULL REFERENCES zj_users(id),
        nickname   TEXT    NOT NULL,
        ok         INTEGER NOT NULL DEFAULT 0 CHECK (ok IN (0, 1)),
        err_code   TEXT    NOT NULL DEFAULT '',
        games      INTEGER NOT NULL DEFAULT 0 CHECK (games >= 0),
        ip         TEXT    NOT NULL DEFAULT '',
        created_at TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS zj_grants (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        user_id     INTEGER NOT NULL REFERENCES zj_users(id),
        delta       INTEGER NOT NULL,
        quota_after INTEGER NOT NULL CHECK (quota_after >= 0),
        operator_id INTEGER NOT NULL REFERENCES users(id),
        note        TEXT    NOT NULL DEFAULT '',
        created_at  TEXT    NOT NULL
    )
    """,
)

ZJ_INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_zj_users_username ON zj_users(username)",
    "CREATE INDEX IF NOT EXISTS ix_zj_batches_user ON zj_batches(user_id, id DESC)",
    "CREATE INDEX IF NOT EXISTS ix_zj_queries_user ON zj_queries(user_id, created_at DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS ix_zj_queries_batch ON zj_queries(batch_id, nickname)",
    "CREATE INDEX IF NOT EXISTS ix_zj_grants_user ON zj_grants(user_id, id DESC)",
)

# 迁移与全新安装共用同一份 DDL，顺序固定：先建表，再建索引。
ZJ_STATEMENTS: tuple[str, ...] = ZJ_TABLE_STATEMENTS + ZJ_INDEX_STATEMENTS

# 小工具：常用名单（v10）
TOOL_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS tool_lists (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_id INTEGER NOT NULL REFERENCES merchants(id),
        name        TEXT    NOT NULL,
        sort_order  INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT    NOT NULL,
        updated_at  TEXT    NOT NULL
    )
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_tool_lists_name
        ON tool_lists(merchant_id, name)
    """,
    """
    CREATE TABLE IF NOT EXISTS tool_items (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        list_id     INTEGER NOT NULL REFERENCES tool_lists(id) ON DELETE CASCADE,
        merchant_id INTEGER NOT NULL REFERENCES merchants(id),
        content     TEXT    NOT NULL,
        note        TEXT    NOT NULL DEFAULT '',
        sort_order  INTEGER NOT NULL DEFAULT 0,
        created_at  TEXT    NOT NULL
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_tool_items_list
        ON tool_items(list_id, sort_order, id)
    """,
)

# 玩家赠金与充值活动（v12）
LEDGER_TABLE_STATEMENT = """
CREATE TABLE IF NOT EXISTS ledger (
    id                     INTEGER PRIMARY KEY AUTOINCREMENT,
    merchant_id            INTEGER NOT NULL REFERENCES merchants(id),
    player_id              INTEGER NOT NULL REFERENCES players(id),
    batch_id               INTEGER REFERENCES batches(id),
    session_id             INTEGER REFERENCES sessions(id),
    reason                 TEXT    NOT NULL CHECK (reason IN (
                               'normal_deduct', 'manual_deduct', 'refund',
                               'add_deposit', 'transfer_out', 'transfer_in',
                               'add_bonus', 'bonus_void')),
    amount_cents           INTEGER NOT NULL,
    balance_before_cents   INTEGER NOT NULL,
    balance_after_cents    INTEGER NOT NULL,
    bonus_amount_cents     INTEGER NOT NULL DEFAULT 0,
    deposit_after_cents    INTEGER NOT NULL,
    bonus_after_cents      INTEGER NOT NULL DEFAULT 0,
    reverses_ledger_id     INTEGER REFERENCES ledger(id),
    counterparty_player_id INTEGER REFERENCES players(id),
    transfer_group_id      TEXT,
    operator_id            INTEGER NOT NULL REFERENCES users(id),
    note                   TEXT    NOT NULL DEFAULT '',
    created_at             TEXT    NOT NULL,

    CHECK (balance_after_cents = balance_before_cents
           + CASE WHEN reason IN ('add_deposit', 'transfer_in', 'add_bonus')
                  THEN amount_cents ELSE -amount_cents END),
    CHECK (balance_after_cents = deposit_after_cents + bonus_after_cents),
    CHECK (bonus_after_cents >= 0),
    CHECK (bonus_amount_cents >= 0 AND bonus_amount_cents <= amount_cents),
    CHECK (bonus_amount_cents = 0 OR reason IN ('normal_deduct', 'add_bonus')),
    CHECK (reason != 'add_bonus' OR bonus_amount_cents = amount_cents),
    CHECK ((reason IN ('normal_deduct', 'manual_deduct') AND amount_cents >= 0)
        OR (reason NOT IN ('normal_deduct', 'manual_deduct') AND amount_cents > 0)),
    CHECK ((reason IN ('transfer_out', 'transfer_in')
            AND counterparty_player_id IS NOT NULL
            AND transfer_group_id IS NOT NULL)
        OR reason NOT IN ('transfer_out', 'transfer_in'))
)
"""

RECHARGE_CAMPAIGN_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS recharge_campaigns (
        id              INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_id     INTEGER NOT NULL REFERENCES merchants(id),
        threshold_cents INTEGER NOT NULL CHECK (threshold_cents > 0),
        bonus_cents     INTEGER NOT NULL CHECK (bonus_cents > 0),
        created_at      TEXT    NOT NULL,
        updated_at      TEXT    NOT NULL,
        UNIQUE (merchant_id, threshold_cents)
    )
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_recharge_campaigns_merchant
        ON recharge_campaigns(merchant_id, threshold_cents)
    """,
)

TABLE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS merchants (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT    NOT NULL,
        note       TEXT    NOT NULL DEFAULT '',
        status     TEXT    NOT NULL DEFAULT 'active'
                           CHECK (status IN ('active', 'disabled')),
        is_system  INTEGER NOT NULL DEFAULT 0 CHECK (is_system IN (0, 1)),
        custodian_user_id INTEGER,
        created_at TEXT    NOT NULL,
        updated_at TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS users (
        id                  INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_id         INTEGER NOT NULL REFERENCES merchants(id),
        username            TEXT    NOT NULL,
        password_hash       TEXT    NOT NULL,
        display_name        TEXT    NOT NULL DEFAULT '',
        role                TEXT    NOT NULL CHECK (role IN ('admin', 'staff')),
        is_active           INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
        is_superadmin       INTEGER NOT NULL DEFAULT 0 CHECK (is_superadmin IN (0, 1)),
        password_changed_at TEXT    NOT NULL,
        last_login_at       TEXT,
        created_at          TEXT    NOT NULL,
        updated_at          TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS players (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_id   INTEGER NOT NULL REFERENCES merchants(id),
        game_id       TEXT    NOT NULL,
        nickname      TEXT    NOT NULL DEFAULT '',
        account       TEXT    NOT NULL DEFAULT '',
        remark        TEXT    NOT NULL DEFAULT '',
        is_blacklisted INTEGER NOT NULL DEFAULT 0 CHECK (is_blacklisted IN (0, 1)),
        deposit_cents INTEGER NOT NULL DEFAULT 0,
        bonus_cents   INTEGER NOT NULL DEFAULT 0 CHECK (bonus_cents >= 0),
        games_played  INTEGER NOT NULL DEFAULT 0 CHECK (games_played >= 0),
        creator_id    INTEGER NOT NULL REFERENCES users(id),
        created_at    TEXT    NOT NULL,
        updated_at    TEXT    NOT NULL,
        deleted_at    TEXT
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS batches (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_id INTEGER NOT NULL REFERENCES merchants(id),
        label       TEXT    NOT NULL DEFAULT '',
        note        TEXT    NOT NULL DEFAULT '',
        status      TEXT    NOT NULL CHECK (status IN ('open', 'closed')),
        opened_by   INTEGER NOT NULL REFERENCES users(id),
        opened_at   TEXT    NOT NULL,
        closed_by   INTEGER REFERENCES users(id),
        closed_at   TEXT,
        session_count            INTEGER,
        player_times             INTEGER,
        tea_total_cents          INTEGER,
        add_total_cents          INTEGER,
        refund_total_cents       INTEGER,
        deduct_total_cents       INTEGER,
        transfer_out_total_cents INTEGER,
        transfer_count           INTEGER,
        net_change_cents         INTEGER,
        deposit_total_cents      INTEGER,
        dividend_rate_percent    INTEGER NOT NULL DEFAULT 50,
        dividend_mode            TEXT    NOT NULL DEFAULT 'percent'
                                 CHECK (dividend_mode IN ('percent', 'fixed')),
        dividend_fixed_cents     INTEGER NOT NULL DEFAULT 0,
        CHECK ((status = 'open' AND closed_at IS NULL AND closed_by IS NULL)
            OR (status = 'closed' AND closed_at IS NOT NULL AND closed_by IS NOT NULL))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_id   INTEGER NOT NULL REFERENCES merchants(id),
        name          TEXT    NOT NULL DEFAULT '',
        played_at     TEXT    NOT NULL,
        tea_fee_cents INTEGER NOT NULL CHECK (tea_fee_cents >= 0),
        note          TEXT    NOT NULL DEFAULT '',
        operator_id   INTEGER NOT NULL REFERENCES users(id),
        player_count  INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT    NOT NULL
    )
    """,
    LEDGER_TABLE_STATEMENT,
    """
    CREATE TABLE IF NOT EXISTS session_players (
        id                   INTEGER PRIMARY KEY AUTOINCREMENT,
        session_id           INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
        player_id            INTEGER NOT NULL REFERENCES players(id),
        tea_fee_cents        INTEGER NOT NULL CHECK (tea_fee_cents >= 0),
        balance_before_cents INTEGER NOT NULL,
        balance_after_cents  INTEGER NOT NULL,
        ledger_id            INTEGER REFERENCES ledger(id),
        UNIQUE (session_id, player_id)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS merchant_settings (
        merchant_id INTEGER NOT NULL REFERENCES merchants(id),
        key         TEXT    NOT NULL,
        value       TEXT    NOT NULL,
        updated_at  TEXT    NOT NULL,
        updated_by  INTEGER REFERENCES users(id),
        PRIMARY KEY (merchant_id, key)
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS audit_logs (
        id          INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_id INTEGER REFERENCES merchants(id),
        user_id     INTEGER REFERENCES users(id),
        action      TEXT    NOT NULL,
        target_type TEXT,
        target_id   TEXT,
        detail      TEXT    NOT NULL DEFAULT '',
        ip          TEXT    NOT NULL DEFAULT '',
        created_at  TEXT    NOT NULL
    )
    """,
    CASH_HANDOVER_TABLE,
    DIVIDEND_SETTLEMENT_TABLE,
    DIVIDEND_SETTLEMENT_BATCH_TABLE,
    *QUEUE_STATEMENTS,
    *TOOL_STATEMENTS,
    *RECHARGE_CAMPAIGN_STATEMENTS,
)

INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_merchants_name ON merchants(name)",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_merchants_system ON merchants(is_system) WHERE is_system = 1",
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_users_username ON users(username)",
    "CREATE INDEX IF NOT EXISTS ix_users_merchant ON users(merchant_id)",
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_players_game_id_alive
        ON players(merchant_id, game_id) WHERE deleted_at IS NULL
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_players_sort
        ON players(merchant_id, deleted_at, games_played DESC, game_id)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_players_deposit
        ON players(merchant_id, deleted_at, deposit_cents DESC)
    """,
    """
    CREATE UNIQUE INDEX IF NOT EXISTS ux_batches_single_open
        ON batches(merchant_id) WHERE status = 'open'
    """,
    "CREATE INDEX IF NOT EXISTS ix_batches_opened ON batches(merchant_id, opened_at DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS ix_sessions_played ON sessions(merchant_id, played_at DESC, id DESC)",
    """
    CREATE INDEX IF NOT EXISTS ix_sessions_operator
        ON sessions(merchant_id, operator_id, played_at)
    """,
    """
    CREATE INDEX IF NOT EXISTS ix_session_players_player
        ON session_players(player_id, id DESC)
    """,
    "CREATE INDEX IF NOT EXISTS ix_ledger_player ON ledger(merchant_id, player_id, id DESC)",
    "CREATE INDEX IF NOT EXISTS ix_ledger_batch ON ledger(merchant_id, batch_id, id DESC)",
    "CREATE INDEX IF NOT EXISTS ix_ledger_session ON ledger(session_id)",
    "CREATE INDEX IF NOT EXISTS ix_ledger_created ON ledger(merchant_id, created_at DESC, id DESC)",
    "CREATE INDEX IF NOT EXISTS ix_ledger_transfer ON ledger(transfer_group_id)",
    """
    CREATE INDEX IF NOT EXISTS ix_ledger_reason_time
        ON ledger(merchant_id, reason, created_at DESC)
    """,
    "CREATE INDEX IF NOT EXISTS ix_audit_created ON audit_logs(merchant_id, created_at DESC, id DESC)",
)

HANDOVER_INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE INDEX IF NOT EXISTS ix_handovers_batch ON cash_handovers(batch_id)",
    """
    CREATE INDEX IF NOT EXISTS ix_handovers_merchant_time
        ON cash_handovers(merchant_id, created_at DESC, id DESC)
    """,
)

# v1 → v2 的数据搬运。全部按显式列名复制，merchant_id 统一填默认商家。
COPY_STATEMENTS: tuple[tuple[str, str], ...] = (
    (
        "users",
        """
        INSERT INTO users (id, merchant_id, username, password_hash, display_name,
                           role, is_active, password_changed_at, last_login_at,
                           created_at, updated_at)
        SELECT id, :mid, username, password_hash, display_name, role, is_active,
               password_changed_at, last_login_at, created_at, updated_at
        FROM users__old
        """,
    ),
    (
        "players",
        """
        INSERT INTO players (id, merchant_id, game_id, nickname, account, remark,
                             deposit_cents, games_played, creator_id, created_at,
                             updated_at, deleted_at)
        SELECT id, :mid, game_id, nickname, account, remark, deposit_cents,
               games_played, creator_id, created_at, updated_at, deleted_at
        FROM players__old
        """,
    ),
    (
        "batches",
        """
        INSERT INTO batches (id, merchant_id, label, note, status, opened_by,
                             opened_at, closed_by, closed_at, session_count,
                             player_times, tea_total_cents, add_total_cents,
                             refund_total_cents, deduct_total_cents,
                             transfer_out_total_cents, transfer_count,
                             net_change_cents, deposit_total_cents)
        SELECT id, :mid, label, note, status, opened_by, opened_at, closed_by,
               closed_at, session_count, player_times, tea_total_cents,
               add_total_cents, refund_total_cents, deduct_total_cents,
               transfer_out_total_cents, transfer_count, net_change_cents,
               deposit_total_cents
        FROM batches__old
        """,
    ),
    (
        "sessions",
        """
        INSERT INTO sessions (id, merchant_id, name, played_at,
                              tea_fee_cents, note, operator_id, player_count, created_at)
        SELECT id, :mid, name, played_at, tea_fee_cents, note,
               operator_id, player_count, created_at
        FROM sessions__old
        """,
    ),
    (
        "ledger",
        """
        INSERT INTO ledger (id, merchant_id, player_id, batch_id, session_id, reason,
                            amount_cents, balance_before_cents, balance_after_cents,
                            bonus_amount_cents, deposit_after_cents, bonus_after_cents,
                            counterparty_player_id, transfer_group_id, operator_id,
                            note, created_at)
        SELECT id, :mid, player_id, NULL, NULL, reason, amount_cents,
               balance_before_cents, balance_after_cents,
               0, balance_after_cents, 0,
               counterparty_player_id, transfer_group_id, operator_id, note, created_at
        FROM ledger__old
        """,
    ),
    (
        "session_players",
        """
        INSERT INTO session_players (id, session_id, player_id, tea_fee_cents,
                                     balance_before_cents, balance_after_cents, ledger_id)
        SELECT id, session_id, player_id, tea_fee_cents, balance_before_cents,
               balance_after_cents, ledger_id
        FROM session_players__old
        """,
    ),
    (
        "audit_logs",
        """
        INSERT INTO audit_logs (id, merchant_id, user_id, action, target_type,
                                target_id, detail, ip, created_at)
        SELECT id, :mid, user_id, action, target_type, target_id, detail, ip, created_at
        FROM audit_logs__old
        """,
    ),
)


def _table_exists(conn: sqlite3.Connection, name: str) -> bool:
    row = conn.execute(
        "SELECT 1 FROM sqlite_master WHERE type = 'table' AND name = ?", (name,)
    ).fetchone()
    return row is not None


def _rollback(conn: sqlite3.Connection) -> None:
    try:
        conn.execute("ROLLBACK")
    except sqlite3.Error:  # pragma: no cover - 事务可能已结束
        pass


def _assert_foreign_keys(conn: sqlite3.Connection) -> None:
    rows = conn.execute("PRAGMA foreign_key_check").fetchall()
    if rows:
        raise RuntimeError(f"外键校验失败：{rows[:5]}")


def _column_exists(conn: sqlite3.Connection, table: str, column: str) -> bool:
    rows = conn.execute(f'PRAGMA table_info("{table}")').fetchall()
    return any(row[1] == column for row in rows)


def _insert_merchant(
    conn: sqlite3.Connection, name: str, note: str = "", is_system: int = 0
) -> int:
    stamp = now_text()
    cursor = conn.execute(
        "INSERT INTO merchants (name, note, status, is_system, created_at, updated_at) "
        "VALUES (?, ?, 'active', ?, ?, ?)",
        (name, note, int(is_system), stamp, stamp),
    )
    return int(cursor.lastrowid or 0)


def _ensure_platform_merchant(conn: sqlite3.Connection) -> int:
    """平台商家只用于挂开发者账号，不参与门店经营，也不出现在商家列表里。"""
    row = conn.execute("SELECT id FROM merchants WHERE is_system = 1").fetchone()
    if row is not None:
        return int(row[0])
    name = PLATFORM_MERCHANT_NAME
    suffix = 2
    while conn.execute("SELECT 1 FROM merchants WHERE name = ?", (name,)).fetchone():
        name = f"{PLATFORM_MERCHANT_NAME}{suffix}"
        suffix += 1
    return _insert_merchant(
        conn, name, "开发者账号专属系统商家，不参与门店经营", is_system=1
    )


def _seed_settings(conn: sqlite3.Connection, merchant_id: int) -> None:
    stamp = now_text()
    for key, value in DEFAULT_SETTINGS:
        conn.execute(
            "INSERT OR IGNORE INTO merchant_settings "
            "(merchant_id, key, value, updated_at) VALUES (?, ?, ?, ?)",
            (merchant_id, key, value, stamp),
        )


def _backup(conn: sqlite3.Connection, db_path: Path, label: str) -> Path:
    """迁移前整库备份。WAL 模式下必须走 backup API，不能直接 cp。"""
    folder = db_path.parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_path = folder / f"{label}-{stamp}.db"
    target = sqlite3.connect(str(target_path))
    try:
        with target:
            conn.backup(target)
        result = target.execute("PRAGMA integrity_check").fetchone()[0]
        if result != "ok":
            raise RuntimeError(f"迁移前备份完整性检查失败：{result}")
    finally:
        target.close()
    return target_path


def _legacy_shop_name(conn: sqlite3.Connection) -> str:
    if not _table_exists(conn, "settings"):
        return ""
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'shop_name'"
    ).fetchone()
    return (row[0] or "").strip() if row else ""


def _copy_settings(conn: sqlite3.Connection, merchant_id: int) -> None:
    if not _table_exists(conn, "settings__old"):
        return
    stamp = now_text()
    placeholders = ",".join("?" for _ in SETTING_KEYS)
    rows = conn.execute(
        f"SELECT key, value FROM settings__old WHERE key IN ({placeholders})",
        SETTING_KEYS,
    ).fetchall()
    for key, value in rows:
        conn.execute(
            "INSERT OR REPLACE INTO merchant_settings "
            "(merchant_id, key, value, updated_at) VALUES (?, ?, ?, ?)",
            (merchant_id, key, value, stamp),
        )


def _seed_dividend_rate(conn: sqlite3.Connection) -> None:
    stamp = now_text()
    conn.execute(
        "INSERT OR IGNORE INTO merchant_settings (merchant_id, key, value, updated_at) "
        "SELECT id, 'dividend_rate_percent', ?, ? FROM merchants WHERE is_system = 0",
        (str(DEFAULT_DIVIDEND_RATE), stamp),
    )


def _seed_dividend_mode(conn: sqlite3.Connection) -> None:
    """v6：老商家默认按比例分红，固定金额 0，行为与升级前一致。"""
    stamp = now_text()
    conn.execute(
        "INSERT OR IGNORE INTO merchant_settings (merchant_id, key, value, updated_at) "
        "SELECT id, 'dividend_mode', ?, ? FROM merchants WHERE is_system = 0",
        (DEFAULT_DIVIDEND_MODE, stamp),
    )
    conn.execute(
        "INSERT OR IGNORE INTO merchant_settings (merchant_id, key, value, updated_at) "
        "SELECT id, 'dividend_fixed_cents', ?, ? FROM merchants WHERE is_system = 0",
        (str(DEFAULT_DIVIDEND_FIXED_CENTS), stamp),
    )


def _set_initial_custodians(conn: sqlite3.Connection) -> None:
    """老库没有交接记录：有进行中班次就给开班人，否则给第一个启用的管理员。"""
    conn.execute(
        """
        UPDATE merchants
        SET custodian_user_id = COALESCE(
            (SELECT b.opened_by FROM batches b
              WHERE b.merchant_id = merchants.id AND b.status = 'open'
              ORDER BY b.id DESC LIMIT 1),
            (SELECT u.id FROM users u
              WHERE u.merchant_id = merchants.id
                AND u.role = 'admin' AND u.is_active = 1 AND u.is_superadmin = 0
              ORDER BY u.id LIMIT 1)
        )
        WHERE is_system = 0 AND custodian_user_id IS NULL
        """
    )


def _convert_manual_deduct(conn: sqlite3.Connection) -> None:
    """手动扣押并入退押金：金额与余额方向完全一致，顺便修正已关班快照。"""
    conn.execute(
        "UPDATE ledger SET reason = 'refund' "
        "WHERE reason = 'manual_deduct' AND amount_cents > 0"
    )
    conn.execute(
        """
        UPDATE batches
        SET refund_total_cents = COALESCE(refund_total_cents, 0) + COALESCE(deduct_total_cents, 0),
            deduct_total_cents = 0
        WHERE status = 'closed' AND COALESCE(deduct_total_cents, 0) > 0
        """
    )


def _create_fresh(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in TABLE_STATEMENTS:
            conn.execute(statement)
        merchant_id = _insert_merchant(conn, DEFAULT_MERCHANT_NAME)
        _seed_settings(conn, merchant_id)
        _seed_tool_lists(conn)
        platform_id = _ensure_platform_merchant(conn)
        for statement in (
            INDEX_STATEMENTS + HANDOVER_INDEX_STATEMENTS + DIVIDEND_INDEX_STATEMENTS
        ):
            conn.execute(statement)
        for statement in ZJ_STATEMENTS:
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info(
            "已初始化 v%s 结构，默认商家 id=%s，平台商家 id=%s",
            SCHEMA_VERSION,
            merchant_id,
            platform_id,
        )
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v1(conn: sqlite3.Connection, db_path: Path) -> None:
    backup = _backup(conn, db_path, "pre-v2")
    logger.info("迁移前已备份：%s", backup)

    default_name = _legacy_shop_name(conn) or DEFAULT_MERCHANT_NAME
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for table in LEGACY_TABLES:
            if _table_exists(conn, table):
                conn.execute(f'ALTER TABLE "{table}" RENAME TO "{table}__old"')

        for statement in TABLE_STATEMENTS:
            conn.execute(statement)

        merchant_id = _insert_merchant(conn, default_name)
        for table, statement in COPY_STATEMENTS:
            if _table_exists(conn, f"{table}__old"):
                conn.execute(statement, {"mid": merchant_id})
        _seed_settings(conn, merchant_id)
        _copy_settings(conn, merchant_id)

        for table in LEGACY_TABLES:
            if _table_exists(conn, f"{table}__old"):
                conn.execute(f'DROP TABLE "{table}__old"')

        _ensure_platform_merchant(conn)
        _seed_dividend_rate(conn)
        _set_initial_custodians(conn)
        _convert_manual_deduct(conn)

        # v8 起取消班次：清空场次/班次历史，押金流水保留但断开关联
        conn.execute("DELETE FROM session_players")
        conn.execute("DELETE FROM sessions")
        conn.execute("DELETE FROM cash_handovers")
        conn.execute("DELETE FROM dividend_settlement_batches")
        conn.execute("DELETE FROM dividend_settlements")
        conn.execute("UPDATE ledger SET session_id = NULL, batch_id = NULL")
        conn.execute("DELETE FROM batches")

        for statement in (
            INDEX_STATEMENTS + HANDOVER_INDEX_STATEMENTS + DIVIDEND_INDEX_STATEMENTS
        ):
            conn.execute(statement)
        for statement in ZJ_STATEMENTS:
            conn.execute(statement)

        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info(
            "v1 → v%s 迁移完成，默认商家 %s（id=%s）", SCHEMA_VERSION, default_name, merchant_id
        )
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v2_to_v3(conn: sqlite3.Connection, db_path: Path) -> None:
    """v2 → v3：加超管标记列，预置平台商家。只加列，不动业务数据。"""
    backup = _backup(conn, db_path, "pre-v3")
    logger.info("迁移前已备份：%s", backup)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not _column_exists(conn, "merchants", "is_system"):
            conn.execute(
                "ALTER TABLE merchants ADD COLUMN is_system INTEGER NOT NULL DEFAULT 0"
            )
        if not _column_exists(conn, "users", "is_superadmin"):
            conn.execute(
                "ALTER TABLE users ADD COLUMN is_superadmin INTEGER NOT NULL DEFAULT 0"
            )
        platform_id = _ensure_platform_merchant(conn)
        for statement in INDEX_STATEMENTS:
            conn.execute(statement)
        conn.execute("PRAGMA user_version = 3")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v2 → v3 迁移完成，平台商家 id=%s", platform_id)
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v3_to_v4(conn: sqlite3.Connection, db_path: Path) -> None:
    """v3 → v4：保管人、交班交接记录、分红比例，并把手动扣押并入退押金。"""
    backup = _backup(conn, db_path, "pre-v4")
    logger.info("迁移前已备份：%s", backup)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not _column_exists(conn, "merchants", "custodian_user_id"):
            conn.execute("ALTER TABLE merchants ADD COLUMN custodian_user_id INTEGER")
        if not _column_exists(conn, "batches", "dividend_rate_percent"):
            conn.execute(
                "ALTER TABLE batches ADD COLUMN dividend_rate_percent INTEGER NOT NULL DEFAULT 50"
            )
        conn.execute(CASH_HANDOVER_TABLE)
        _seed_dividend_rate(conn)
        _set_initial_custodians(conn)
        _convert_manual_deduct(conn)
        for statement in HANDOVER_INDEX_STATEMENTS:
            conn.execute(statement)
        conn.execute("PRAGMA user_version = 4")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v3 → v4 迁移完成：交接表、保管人、分红比例就绪")
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v4_to_v5(conn: sqlite3.Connection, db_path: Path) -> None:
    """v4 → v5：只新增分红结算表和索引，不动现有业务数据。"""
    backup = _backup(conn, db_path, "pre-v5")
    logger.info("迁移前已备份：%s", backup)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(DIVIDEND_SETTLEMENT_TABLE)
        conn.execute(DIVIDEND_SETTLEMENT_BATCH_TABLE)
        for statement in DIVIDEND_INDEX_STATEMENTS:
            conn.execute(statement)
        conn.execute("PRAGMA user_version = 5")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v4 → v5 迁移完成：分红结算表就绪")
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v5_to_v6(conn: sqlite3.Connection, db_path: Path) -> None:
    """v5 → v6：分红方式（比例/每局固定）与固定金额，班次存快照。"""
    backup = _backup(conn, db_path, "pre-v6")
    logger.info("迁移前已备份：%s", backup)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not _column_exists(conn, "batches", "dividend_mode"):
            conn.execute(
                "ALTER TABLE batches ADD COLUMN dividend_mode TEXT NOT NULL DEFAULT 'percent'"
            )
        if not _column_exists(conn, "batches", "dividend_fixed_cents"):
            conn.execute(
                "ALTER TABLE batches ADD COLUMN dividend_fixed_cents INTEGER NOT NULL DEFAULT 0"
            )
        _seed_dividend_mode(conn)
        conn.execute("PRAGMA user_version = 6")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v5 → v6 迁移完成：分红方式与固定金额就绪")
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v6_to_v7(conn: sqlite3.Connection, db_path: Path) -> None:
    """v6 → v7：新增排队登记表（小工具 → 排队登记）。"""
    backup = _backup(conn, db_path, "pre-v7")
    logger.info("迁移前已备份：%s", backup)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in QUEUE_STATEMENTS:
            conn.execute(statement)
        conn.execute("PRAGMA user_version = 7")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v6 → v7 迁移完成：排队登记表就绪")
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v7_to_v8(conn: sqlite3.Connection, db_path: Path) -> None:
    """v7 → v8：取消开班/交班。

    - 场次不再归属班次（重建 sessions 表，去掉 batch_id）
    - 清空班次、现金交接、分红结算历史（按约定重来，玩家和押金流水保留）
    - 押金流水保留，但解除与班次/场次的关联
    """
    backup = _backup(conn, db_path, "pre-v8")
    logger.info("迁移前已备份：%s", backup)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute("DELETE FROM session_players")
        conn.execute("DELETE FROM dividend_settlement_batches")
        conn.execute("DELETE FROM dividend_settlements")
        conn.execute("DELETE FROM cash_handovers")

        # 重建 ledger：保留全部流水，但断开 batch/session 关联，
        # 并去掉「normal_deduct 必须带 session_id」的历史约束。
        conn.execute(
            """
            CREATE TABLE ledger__new (
                id                     INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id            INTEGER NOT NULL REFERENCES merchants(id),
                player_id              INTEGER NOT NULL REFERENCES players(id),
                batch_id               INTEGER REFERENCES batches(id),
                session_id             INTEGER REFERENCES sessions(id),
                reason                 TEXT    NOT NULL CHECK (reason IN (
                                           'normal_deduct', 'manual_deduct', 'refund',
                                           'add_deposit', 'transfer_out', 'transfer_in')),
                amount_cents           INTEGER NOT NULL,
                balance_before_cents   INTEGER NOT NULL,
                balance_after_cents    INTEGER NOT NULL,
                counterparty_player_id INTEGER REFERENCES players(id),
                transfer_group_id      TEXT,
                operator_id            INTEGER NOT NULL REFERENCES users(id),
                note                   TEXT    NOT NULL DEFAULT '',
                created_at             TEXT    NOT NULL,

                CHECK (balance_after_cents = balance_before_cents
                       + CASE WHEN reason IN ('add_deposit', 'transfer_in') THEN amount_cents
                              ELSE -amount_cents END),
                CHECK ((reason IN ('normal_deduct', 'manual_deduct') AND amount_cents >= 0)
                    OR (reason NOT IN ('normal_deduct', 'manual_deduct') AND amount_cents > 0)),
                CHECK ((reason IN ('transfer_out', 'transfer_in')
                        AND counterparty_player_id IS NOT NULL
                        AND transfer_group_id IS NOT NULL)
                    OR reason NOT IN ('transfer_out', 'transfer_in'))
            )
            """
        )
        conn.execute(
            """
            INSERT INTO ledger__new (id, merchant_id, player_id, batch_id, session_id, reason,
                                     amount_cents, balance_before_cents, balance_after_cents,
                                     counterparty_player_id, transfer_group_id, operator_id,
                                     note, created_at)
            SELECT id, merchant_id, player_id, NULL, NULL, reason,
                   amount_cents, balance_before_cents, balance_after_cents,
                   counterparty_player_id, transfer_group_id, operator_id,
                   note, created_at
            FROM ledger
            """
        )
        conn.execute("DROP TABLE ledger")
        conn.execute("ALTER TABLE ledger__new RENAME TO ledger")
        for statement in (
            "CREATE INDEX IF NOT EXISTS ix_ledger_player ON ledger(merchant_id, player_id, id DESC)",
            "CREATE INDEX IF NOT EXISTS ix_ledger_batch ON ledger(merchant_id, batch_id, id DESC)",
            "CREATE INDEX IF NOT EXISTS ix_ledger_session ON ledger(session_id)",
            "CREATE INDEX IF NOT EXISTS ix_ledger_created ON ledger(merchant_id, created_at DESC, id DESC)",
            "CREATE INDEX IF NOT EXISTS ix_ledger_transfer ON ledger(transfer_group_id)",
            """
            CREATE INDEX IF NOT EXISTS ix_ledger_reason_time
                ON ledger(merchant_id, reason, created_at DESC)
            """,
        ):
            conn.execute(statement)

        conn.execute("DELETE FROM sessions")
        conn.execute("DROP TABLE IF EXISTS sessions")
        conn.execute(
            """
            CREATE TABLE sessions (
                id            INTEGER PRIMARY KEY AUTOINCREMENT,
                merchant_id   INTEGER NOT NULL REFERENCES merchants(id),
                name          TEXT    NOT NULL DEFAULT '',
                played_at     TEXT    NOT NULL,
                tea_fee_cents INTEGER NOT NULL CHECK (tea_fee_cents >= 0),
                note          TEXT    NOT NULL DEFAULT '',
                operator_id   INTEGER NOT NULL REFERENCES users(id),
                player_count  INTEGER NOT NULL DEFAULT 0,
                created_at    TEXT    NOT NULL
            )
            """
        )
        conn.execute(
            "CREATE INDEX ix_sessions_played ON sessions(merchant_id, played_at DESC, id DESC)"
        )
        conn.execute(
            "CREATE INDEX ix_sessions_operator ON sessions(merchant_id, operator_id, played_at)"
        )
        conn.execute("DELETE FROM batches")
        conn.execute("PRAGMA user_version = 8")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v7 → v8 迁移完成：已取消班次，场次改为直接统计")
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v8_to_v9(conn: sqlite3.Connection, db_path: Path) -> None:
    """v8 → v9：新增「查战绩」多用户版五张表。

    只建表建索引，不改任何既有表：zj_users 独立于 merchants/users，
    zj_grants.operator_id 仅记录是哪个开发者账号加的次数。
    旧代码不认识这些表，回滚时保留它们即可，不影响记账逻辑。
    """
    backup = _backup(conn, db_path, "pre-v9")
    logger.info("迁移前已备份：%s", backup)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in ZJ_STATEMENTS:
            conn.execute(statement)
        conn.execute("PRAGMA user_version = 9")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v8 → v9 迁移完成：查战绩账号、批次与配额表就绪")
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _seed_tool_lists(conn: sqlite3.Connection) -> None:
    """给每个非系统商家预置分类与条目；已存在的分类跳过（幂等）。"""
    stamp = now_text()
    merchants = [
        row[0]
        for row in conn.execute(
            "select id from merchants where is_system = 0 order by id"
        ).fetchall()
    ]
    for merchant_id in merchants:
        for index, (name, items) in enumerate(DEFAULT_TOOL_LISTS):
            exists = conn.execute(
                "select id from tool_lists where merchant_id = ? and name = ?",
                (merchant_id, name),
            ).fetchone()
            if exists:
                continue
            cursor = conn.execute(
                """
                insert into tool_lists (merchant_id, name, sort_order, created_at, updated_at)
                values (?, ?, ?, ?, ?)
                """,
                (merchant_id, name, index, stamp, stamp),
            )
            list_id = int(cursor.lastrowid)
            for order, content in enumerate(items):
                conn.execute(
                    """
                    insert into tool_items
                        (list_id, merchant_id, content, note, sort_order, created_at)
                    values (?, ?, ?, '', ?, ?)
                    """,
                    (list_id, merchant_id, content, order, stamp),
                )


def _upgrade_v9_to_v10(conn: sqlite3.Connection, db_path: Path) -> None:
    """v9 → v10：新增「常用名单」小工具的两张表，并预置分类与条目。"""
    backup = _backup(conn, db_path, "pre-v10")
    logger.info("迁移前已备份：%s", backup)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in TOOL_STATEMENTS:
            conn.execute(statement)
        _seed_tool_lists(conn)
        conn.execute("PRAGMA user_version = 10")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v9 → v10 迁移完成：常用名单就绪")
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v10_to_v11(conn: sqlite3.Connection, db_path: Path) -> None:
    """v10 → v11：玩家增加黑名单标记。只加列，不动历史数据。"""
    backup = _backup(conn, db_path, "pre-v11")
    logger.info("迁移前已备份：%s", backup)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        conn.execute(
            "ALTER TABLE players ADD COLUMN is_blacklisted INTEGER NOT NULL DEFAULT 0"
            " CHECK (is_blacklisted IN (0, 1))"
        )
        conn.execute("PRAGMA user_version = 11")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v10 → v11 迁移完成：玩家黑名单标记就绪")
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v11_to_v12(conn: sqlite3.Connection, db_path: Path) -> None:
    """v11 → v12：玩家赠金、流水现金/赠金拆分与充值活动。

    ledger 需要扩 reason 枚举和新增列，SQLite 不支持直接改 CHECK，因此按原顺序
    重建表并复制全部历史行；旧行的赠金部分统一回填为 0。
    """
    backup = _backup(conn, db_path, "pre-v12")
    logger.info("迁移前已备份：%s", backup)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not _column_exists(conn, "players", "bonus_cents"):
            conn.execute(
                "ALTER TABLE players ADD COLUMN bonus_cents INTEGER NOT NULL DEFAULT 0"
                " CHECK (bonus_cents >= 0)"
            )

        if not _column_exists(conn, "ledger", "bonus_amount_cents"):
            new_table = LEDGER_TABLE_STATEMENT.replace(
                "CREATE TABLE IF NOT EXISTS ledger",
                "CREATE TABLE ledger__v12",
                1,
            )
            conn.execute(new_table)
            conn.execute(
                """
                INSERT INTO ledger__v12 (
                    id, merchant_id, player_id, batch_id, session_id, reason,
                    amount_cents, balance_before_cents, balance_after_cents,
                    bonus_amount_cents, deposit_after_cents, bonus_after_cents,
                    counterparty_player_id, transfer_group_id, operator_id,
                    note, created_at
                )
                SELECT id, merchant_id, player_id, batch_id, session_id, reason,
                       amount_cents, balance_before_cents, balance_after_cents,
                       0, balance_after_cents, 0,
                       counterparty_player_id, transfer_group_id, operator_id,
                       note, created_at
                FROM ledger
                """
            )
            conn.execute("DROP TABLE ledger")
            conn.execute("ALTER TABLE ledger__v12 RENAME TO ledger")
            for statement in INDEX_STATEMENTS:
                if " ON ledger" in statement:
                    conn.execute(statement)

        for statement in RECHARGE_CAMPAIGN_STATEMENTS:
            conn.execute(statement)

        conn.execute("PRAGMA user_version = 12")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v11 → v12 迁移完成：玩家赠金与充值活动就绪")
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v12_to_v13(conn: sqlite3.Connection, db_path: Path) -> None:
    """v12 → v13：新增撤销加赠金原因 bonus_void 与流水指向列 reverses_ledger_id。

    只加宽 reason 白名单并新增一可空列，全部历史行、ID 与 session_players
    关联原样保留，非破坏性；SQLite 不能改 CHECK，因此重建 ledger 表。
    """
    backup = _backup(conn, db_path, "pre-v13")
    logger.info("迁移前已备份：%s", backup)

    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        if not _column_exists(conn, "ledger", "reverses_ledger_id"):
            new_table = LEDGER_TABLE_STATEMENT.replace(
                "CREATE TABLE IF NOT EXISTS ledger",
                "CREATE TABLE ledger__v13",
                1,
            )
            conn.execute(new_table)
            conn.execute(
                """
                INSERT INTO ledger__v13 (
                    id, merchant_id, player_id, batch_id, session_id, reason,
                    amount_cents, balance_before_cents, balance_after_cents,
                    bonus_amount_cents, deposit_after_cents, bonus_after_cents,
                    counterparty_player_id, transfer_group_id, operator_id,
                    note, created_at, reverses_ledger_id
                )
                SELECT id, merchant_id, player_id, batch_id, session_id, reason,
                       amount_cents, balance_before_cents, balance_after_cents,
                       bonus_amount_cents, deposit_after_cents, bonus_after_cents,
                       counterparty_player_id, transfer_group_id, operator_id,
                       note, created_at, NULL
                FROM ledger
                """
            )
            conn.execute("DROP TABLE ledger")
            conn.execute("ALTER TABLE ledger__v13 RENAME TO ledger")
            for statement in INDEX_STATEMENTS:
                if " ON ledger" in statement:
                    conn.execute(statement)

        conn.execute("PRAGMA user_version = 13")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v12 → v13 迁移完成：撤销加赠金就绪")
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def ensure_schema() -> None:
    path = db.current_path()
    conn = sqlite3.connect(str(path), isolation_level=None, timeout=20)
    try:
        conn.execute("PRAGMA busy_timeout=20000")
        version = int(conn.execute("PRAGMA user_version").fetchone()[0])
        if version >= SCHEMA_VERSION:
            return
        if version == 0 and not _table_exists(conn, "users"):
            _create_fresh(conn)
            return
        if version < 2:
            _upgrade_v1(conn, path)
            return
        if version < 3:
            _upgrade_v2_to_v3(conn, path)
        if version < 4:
            _upgrade_v3_to_v4(conn, path)
        if version < 5:
            _upgrade_v4_to_v5(conn, path)
        if version < 6:
            _upgrade_v5_to_v6(conn, path)
        if version < 7:
            _upgrade_v6_to_v7(conn, path)
        if version < 8:
            _upgrade_v7_to_v8(conn, path)
        if version < 9:
            _upgrade_v8_to_v9(conn, path)
        if version < 10:
            _upgrade_v9_to_v10(conn, path)
        if version < 11:
            _upgrade_v10_to_v11(conn, path)
        if version < 12:
            _upgrade_v11_to_v12(conn, path)
        if version < 13:
            _upgrade_v12_to_v13(conn, path)
    finally:
        conn.close()


if __name__ == "__main__":
    from app.config import settings

    ensure_schema()
    print(f"数据库已就绪：{settings.db_path}（schema {SCHEMA_VERSION}）")
