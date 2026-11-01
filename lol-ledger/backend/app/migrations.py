"""建表 DDL、版本迁移与种子数据。

结构唯一来源。v2 引入多商家：业务表全部带 merchant_id，唯一索引按商家维度重建。

迁移策略：
- 全新库：按 v2 直接建表，写入一个默认商家和默认配置。
- v1 库：先用 SQLite backup API 备份到 data/backups/pre-v2-*.db，
  再在单事务里「旧表改名 → 建 v2 表 → 拷数据 → 删旧表 → 建索引」。
- 只做加表 / 加列 / 加索引 / 一次性重建，不删业务列、不改业务名。
"""

from __future__ import annotations

import logging
import sqlite3
from datetime import datetime
from pathlib import Path

from app import db
from app.timeutil import now_text

logger = logging.getLogger(__name__)

SCHEMA_VERSION = 2
DEFAULT_MERCHANT_NAME = "默认商家"

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
)

DEFAULT_SETTINGS: tuple[tuple[str, str], ...] = (
    ("last_tea_cents", "200"),
    ("deposit_low_cents", "3000"),
    ("deposit_high_cents", "6000"),
)

TABLE_STATEMENTS: tuple[str, ...] = (
    """
    CREATE TABLE IF NOT EXISTS merchants (
        id         INTEGER PRIMARY KEY AUTOINCREMENT,
        name       TEXT    NOT NULL,
        note       TEXT    NOT NULL DEFAULT '',
        status     TEXT    NOT NULL DEFAULT 'active'
                           CHECK (status IN ('active', 'disabled')),
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
        deposit_cents INTEGER NOT NULL DEFAULT 0,
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
        CHECK ((status = 'open' AND closed_at IS NULL AND closed_by IS NULL)
            OR (status = 'closed' AND closed_at IS NOT NULL AND closed_by IS NOT NULL))
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id            INTEGER PRIMARY KEY AUTOINCREMENT,
        merchant_id   INTEGER NOT NULL REFERENCES merchants(id),
        batch_id      INTEGER NOT NULL REFERENCES batches(id),
        name          TEXT    NOT NULL DEFAULT '',
        played_at     TEXT    NOT NULL,
        tea_fee_cents INTEGER NOT NULL CHECK (tea_fee_cents >= 0),
        note          TEXT    NOT NULL DEFAULT '',
        operator_id   INTEGER NOT NULL REFERENCES users(id),
        player_count  INTEGER NOT NULL DEFAULT 0,
        created_at    TEXT    NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ledger (
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
        CHECK ((reason = 'normal_deduct' AND session_id IS NOT NULL)
            OR reason <> 'normal_deduct'),
        CHECK ((reason IN ('transfer_out', 'transfer_in')
                AND counterparty_player_id IS NOT NULL
                AND transfer_group_id IS NOT NULL)
            OR reason NOT IN ('transfer_out', 'transfer_in'))
    )
    """,
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
)

INDEX_STATEMENTS: tuple[str, ...] = (
    "CREATE UNIQUE INDEX IF NOT EXISTS ux_merchants_name ON merchants(name)",
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
    """
    CREATE INDEX IF NOT EXISTS ix_sessions_batch
        ON sessions(merchant_id, batch_id, played_at DESC, id DESC)
    """,
    "CREATE INDEX IF NOT EXISTS ix_sessions_played ON sessions(merchant_id, played_at DESC, id DESC)",
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
        INSERT INTO sessions (id, merchant_id, batch_id, name, played_at,
                              tea_fee_cents, note, operator_id, player_count, created_at)
        SELECT id, :mid, batch_id, name, played_at, tea_fee_cents, note,
               operator_id, player_count, created_at
        FROM sessions__old
        """,
    ),
    (
        "ledger",
        """
        INSERT INTO ledger (id, merchant_id, player_id, batch_id, session_id, reason,
                            amount_cents, balance_before_cents, balance_after_cents,
                            counterparty_player_id, transfer_group_id, operator_id,
                            note, created_at)
        SELECT id, :mid, player_id, batch_id, session_id, reason, amount_cents,
               balance_before_cents, balance_after_cents, counterparty_player_id,
               transfer_group_id, operator_id, note, created_at
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


def _insert_merchant(conn: sqlite3.Connection, name: str, note: str = "") -> int:
    stamp = now_text()
    cursor = conn.execute(
        "INSERT INTO merchants (name, note, status, created_at, updated_at) "
        "VALUES (?, ?, 'active', ?, ?)",
        (name, note, stamp, stamp),
    )
    return int(cursor.lastrowid or 0)


def _seed_settings(conn: sqlite3.Connection, merchant_id: int) -> None:
    stamp = now_text()
    for key, value in DEFAULT_SETTINGS:
        conn.execute(
            "INSERT OR IGNORE INTO merchant_settings "
            "(merchant_id, key, value, updated_at) VALUES (?, ?, ?, ?)",
            (merchant_id, key, value, stamp),
        )


def _backup_before_v2(conn: sqlite3.Connection, db_path: Path) -> Path:
    """迁移前整库备份。WAL 模式下必须走 backup API，不能直接 cp。"""
    folder = db_path.parent / "backups"
    folder.mkdir(parents=True, exist_ok=True)
    stamp = datetime.now().strftime("%Y%m%d-%H%M%S")
    target_path = folder / f"pre-v2-{stamp}.db"
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


def _create_fresh(conn: sqlite3.Connection) -> None:
    conn.execute("PRAGMA foreign_keys=OFF")
    conn.execute("BEGIN IMMEDIATE")
    try:
        for statement in TABLE_STATEMENTS:
            conn.execute(statement)
        merchant_id = _insert_merchant(conn, DEFAULT_MERCHANT_NAME)
        _seed_settings(conn, merchant_id)
        for statement in INDEX_STATEMENTS:
            conn.execute(statement)
        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("已初始化 v2 结构，默认商家 id=%s", merchant_id)
    except Exception:
        _rollback(conn)
        raise
    finally:
        conn.execute("PRAGMA foreign_keys=ON")


def _upgrade_v1(conn: sqlite3.Connection, db_path: Path) -> None:
    backup = _backup_before_v2(conn, db_path)
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

        for statement in INDEX_STATEMENTS:
            conn.execute(statement)

        conn.execute(f"PRAGMA user_version = {SCHEMA_VERSION}")
        _assert_foreign_keys(conn)
        conn.execute("COMMIT")
        logger.info("v1 → v2 迁移完成，默认商家 %s（id=%s）", default_name, merchant_id)
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
        _upgrade_v1(conn, path)
    finally:
        conn.close()


if __name__ == "__main__":
    from app.config import settings

    ensure_schema()
    print(f"数据库已就绪：{settings.db_path}（schema {SCHEMA_VERSION}）")
