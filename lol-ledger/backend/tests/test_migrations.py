"""迁移：v1/v2 库升级到 v3 不丢数据，全新库直接是 v3，重复执行幂等。"""

from __future__ import annotations

import re
import sqlite3
from pathlib import Path

from app import db as dbmod
from app import migrations
from app.migrations import SCHEMA_VERSION

STAMP = "2026-11-01T11:00:00+08:00"

V1_DDL = """
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username TEXT NOT NULL,
    password_hash TEXT NOT NULL,
    display_name TEXT NOT NULL DEFAULT '',
    role TEXT NOT NULL CHECK (role IN ('admin', 'staff')),
    is_active INTEGER NOT NULL DEFAULT 1 CHECK (is_active IN (0, 1)),
    password_changed_at TEXT NOT NULL,
    last_login_at TEXT,
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL
);
CREATE UNIQUE INDEX ux_users_username ON users(username);
CREATE TABLE players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    game_id TEXT NOT NULL,
    nickname TEXT NOT NULL DEFAULT '',
    account TEXT NOT NULL DEFAULT '',
    remark TEXT NOT NULL DEFAULT '',
    deposit_cents INTEGER NOT NULL DEFAULT 0,
    games_played INTEGER NOT NULL DEFAULT 0 CHECK (games_played >= 0),
    creator_id INTEGER NOT NULL REFERENCES users(id),
    created_at TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    deleted_at TEXT
);
CREATE UNIQUE INDEX ux_players_game_id_alive ON players(game_id) WHERE deleted_at IS NULL;
CREATE TABLE batches (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    label TEXT NOT NULL DEFAULT '',
    note TEXT NOT NULL DEFAULT '',
    status TEXT NOT NULL CHECK (status IN ('open', 'closed')),
    opened_by INTEGER NOT NULL REFERENCES users(id),
    opened_at TEXT NOT NULL,
    closed_by INTEGER REFERENCES users(id),
    closed_at TEXT,
    session_count INTEGER, player_times INTEGER, tea_total_cents INTEGER,
    add_total_cents INTEGER, refund_total_cents INTEGER, deduct_total_cents INTEGER,
    transfer_out_total_cents INTEGER, transfer_count INTEGER,
    net_change_cents INTEGER, deposit_total_cents INTEGER
);
CREATE UNIQUE INDEX ux_batches_single_open ON batches(status) WHERE status = 'open';
CREATE TABLE sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    batch_id INTEGER NOT NULL REFERENCES batches(id),
    name TEXT NOT NULL DEFAULT '',
    played_at TEXT NOT NULL,
    tea_fee_cents INTEGER NOT NULL CHECK (tea_fee_cents >= 0),
    note TEXT NOT NULL DEFAULT '',
    operator_id INTEGER NOT NULL REFERENCES users(id),
    player_count INTEGER NOT NULL DEFAULT 0,
    created_at TEXT NOT NULL
);
CREATE TABLE ledger (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    player_id INTEGER NOT NULL REFERENCES players(id),
    batch_id INTEGER REFERENCES batches(id),
    session_id INTEGER REFERENCES sessions(id),
    reason TEXT NOT NULL,
    amount_cents INTEGER NOT NULL,
    balance_before_cents INTEGER NOT NULL,
    balance_after_cents INTEGER NOT NULL,
    counterparty_player_id INTEGER REFERENCES players(id),
    transfer_group_id TEXT,
    operator_id INTEGER NOT NULL REFERENCES users(id),
    note TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
CREATE TABLE session_players (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    session_id INTEGER NOT NULL REFERENCES sessions(id) ON DELETE CASCADE,
    player_id INTEGER NOT NULL REFERENCES players(id),
    tea_fee_cents INTEGER NOT NULL CHECK (tea_fee_cents >= 0),
    balance_before_cents INTEGER NOT NULL,
    balance_after_cents INTEGER NOT NULL,
    ledger_id INTEGER REFERENCES ledger(id),
    UNIQUE (session_id, player_id)
);
CREATE TABLE settings (
    key TEXT PRIMARY KEY,
    value TEXT NOT NULL,
    updated_at TEXT NOT NULL,
    updated_by INTEGER REFERENCES users(id)
);
CREATE TABLE audit_logs (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER REFERENCES users(id),
    action TEXT NOT NULL,
    target_type TEXT,
    target_id TEXT,
    detail TEXT NOT NULL DEFAULT '',
    ip TEXT NOT NULL DEFAULT '',
    created_at TEXT NOT NULL
);
PRAGMA user_version = 1;
"""


def build_v1(path: Path) -> None:
    conn = sqlite3.connect(path)
    conn.executescript(V1_DDL)
    conn.executemany(
        "INSERT INTO settings (key, value, updated_at) VALUES (?, ?, ?)",
        [
            ("shop_name", "极光电竞", STAMP),
            ("last_tea_cents", "300", STAMP),
            ("deposit_low_cents", "3000", STAMP),
            ("deposit_high_cents", "6000", STAMP),
        ],
    )
    conn.execute(
        "INSERT INTO users (username, password_hash, display_name, role, is_active,"
        " password_changed_at, created_at, updated_at)"
        " VALUES ('jg-boss', 'x', '店长', 'admin', 1, ?, ?, ?)",
        (STAMP, STAMP, STAMP),
    )
    conn.execute(
        "INSERT INTO players (game_id, deposit_cents, games_played, creator_id, created_at, updated_at)"
        " VALUES ('jg001', 4700, 1, 1, ?, ?)",
        (STAMP, STAMP),
    )
    conn.execute(
        "INSERT INTO batches (label, status, opened_by, opened_at) VALUES ('早班', 'open', 1, ?)",
        (STAMP,),
    )
    conn.execute(
        "INSERT INTO sessions (batch_id, name, played_at, tea_fee_cents, operator_id,"
        " player_count, created_at) VALUES (1, '11月1日 第1局', ?, 300, 1, 1, ?)",
        (STAMP, STAMP),
    )
    conn.execute(
        "INSERT INTO ledger (player_id, batch_id, session_id, reason, amount_cents,"
        " balance_before_cents, balance_after_cents, operator_id, created_at)"
        " VALUES (1, 1, 1, 'normal_deduct', 300, 5000, 4700, 1, ?)",
        (STAMP,),
    )
    conn.execute(
        "INSERT INTO session_players (session_id, player_id, tea_fee_cents,"
        " balance_before_cents, balance_after_cents, ledger_id)"
        " VALUES (1, 1, 300, 5000, 4700, 1)"
    )
    conn.execute(
        "INSERT INTO audit_logs (user_id, action, created_at) VALUES (1, 'login', ?)",
        (STAMP,),
    )
    conn.commit()
    conn.close()


def test_upgrade_v1_keeps_data(tmp_path) -> None:
    path = tmp_path / "v1.db"
    build_v1(path)
    dbmod.configure_db(path)
    try:
        dbmod.ensure_schema()
        conn = sqlite3.connect(path)
        try:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            assert conn.execute("SELECT name FROM merchants WHERE id = 1").fetchone()[0] == "极光电竞"
            assert conn.execute("SELECT COUNT(*) FROM merchants WHERE is_system = 0").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM merchants WHERE is_system = 1").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM users").fetchone()[0] == 1
            assert conn.execute("SELECT merchant_id FROM users").fetchone()[0] == 1
            assert conn.execute("SELECT is_superadmin FROM users").fetchone()[0] == 0
            assert conn.execute("SELECT deposit_cents FROM players").fetchone()[0] == 4700
            assert conn.execute("SELECT merchant_id FROM ledger").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM session_players").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM audit_logs").fetchone()[0] == 1
            assert (
                conn.execute(
                    "SELECT value FROM merchant_settings WHERE key = 'last_tea_cents'"
                ).fetchone()[0]
                == "300"
            )
            assert (
                conn.execute(
                    "SELECT 1 FROM sqlite_master WHERE type='table' AND name='settings'"
                ).fetchone()
                is None
            )
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            conn.close()

        backups = list((tmp_path / "backups").glob("pre-v2-*.db"))
        assert len(backups) == 1

        dbmod.ensure_schema()
        conn = sqlite3.connect(path)
        try:
            assert conn.execute("SELECT COUNT(*) FROM merchants WHERE is_system = 0").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM merchants WHERE is_system = 1").fetchone()[0] == 1
        finally:
            conn.close()
        assert len(list((tmp_path / "backups").glob("pre-v2-*.db"))) == 1
    finally:
        dbmod.dispose()


def _ddl_for(version: int) -> tuple[list[str], list[str]]:
    """用当前 DDL 拼出旧版本结构：<3 去掉超管列，<4 去掉保管人/分红列和交接表。"""
    statements = []
    for statement in migrations.TABLE_STATEMENTS:
        if "cash_handovers" in statement:
            continue
        if version < 3:
            statement = re.sub(
                r"^\s*is_system\s+INTEGER[^\n]*\n", "", statement, flags=re.MULTILINE
            )
            statement = re.sub(
                r"^\s*is_superadmin\s+INTEGER[^\n]*\n", "", statement, flags=re.MULTILINE
            )
        if version < 4:
            statement = re.sub(
                r"^\s*custodian_user_id[^\n]*\n", "", statement, flags=re.MULTILINE
            )
            statement = re.sub(
                r"^\s*dividend_rate_percent[^\n]*\n",
                "",
                statement,
                flags=re.MULTILINE,
            )
        statements.append(statement)
    indexes = [
        item
        for item in migrations.INDEX_STATEMENTS
        if not (version < 3 and "ux_merchants_system" in item)
    ]
    return statements, indexes


def _build_old_db(path: Path, version: int) -> None:
    statements, indexes = _ddl_for(version)
    conn = sqlite3.connect(path)
    try:
        conn.execute("PRAGMA foreign_keys=OFF")
        conn.executescript(
            ";\n".join(statements + indexes)
            + f";\nPRAGMA user_version = {version};"
        )
        conn.execute(
            "INSERT INTO merchants (name, note, status, created_at, updated_at)"
            " VALUES ('老商家', '', 'active', ?, ?)",
            (STAMP, STAMP),
        )
        conn.execute(
            "INSERT INTO users (merchant_id, username, password_hash, display_name, role,"
            " is_active, password_changed_at, created_at, updated_at)"
            " VALUES (1, 'old-boss', 'x', '老店长', 'admin', 1, ?, ?, ?)",
            (STAMP, STAMP, STAMP),
        )
        if version >= 3:
            conn.execute(
                "INSERT INTO players (merchant_id, game_id, deposit_cents, games_played,"
                " creator_id, created_at, updated_at)"
                " VALUES (1, '老玩家', 900, 0, 1, ?, ?)",
                (STAMP, STAMP),
            )
            conn.execute(
                "INSERT INTO batches (merchant_id, label, status, opened_by, opened_at,"
                " closed_by, closed_at, session_count, player_times, tea_total_cents,"
                " add_total_cents, refund_total_cents, deduct_total_cents,"
                " transfer_out_total_cents, transfer_count, net_change_cents,"
                " deposit_total_cents)"
                " VALUES (1, '旧班次', 'closed', 1, ?, 1, ?, 0, 0, 0, 1000, 0, 100,"
                " 0, 0, 900, 900)",
                (STAMP, STAMP),
            )
            conn.executemany(
                "INSERT INTO ledger (merchant_id, player_id, batch_id, reason,"
                " amount_cents, balance_before_cents, balance_after_cents,"
                " operator_id, created_at) VALUES (1, 1, 1, ?, ?, ?, ?, 1, ?)",
                [
                    ("add_deposit", 1000, 0, 1000, STAMP),
                    ("manual_deduct", 100, 1000, 900, STAMP),
                ],
            )
        conn.commit()
    finally:
        conn.close()


def test_upgrade_v2_adds_v3_and_v4(tmp_path) -> None:
    path = tmp_path / "v2.db"
    _build_old_db(path, 2)
    dbmod.configure_db(path)
    try:
        dbmod.ensure_schema()
        conn = sqlite3.connect(path)
        try:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            columns = {
                row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
            }
            assert "is_superadmin" in columns
            assert (
                conn.execute("SELECT is_superadmin FROM users WHERE username='old-boss'").fetchone()[0]
                == 0
            )
            assert conn.execute("SELECT COUNT(*) FROM merchants WHERE is_system = 1").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM merchants WHERE is_system = 0").fetchone()[0] == 1
            assert conn.execute("SELECT custodian_user_id FROM merchants WHERE id=1").fetchone()[0] == 1
            assert _table_exists(path, "cash_handovers")
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            conn.close()
        assert len(list((tmp_path / "backups").glob("pre-v3-*.db"))) == 1
        assert len(list((tmp_path / "backups").glob("pre-v4-*.db"))) == 1

        # 幂等：再跑一次不新增商家、不再备份
        dbmod.ensure_schema()
        assert len(list((tmp_path / "backups").glob("pre-v4-*.db"))) == 1
    finally:
        dbmod.dispose()


def test_upgrade_v3_converts_manual_deduct_and_adds_custody(tmp_path) -> None:
    path = tmp_path / "v3.db"
    _build_old_db(path, 3)
    dbmod.configure_db(path)
    try:
        dbmod.ensure_schema()
        conn = sqlite3.connect(path)
        try:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            reasons = {
                row[0] for row in conn.execute("SELECT DISTINCT reason FROM ledger").fetchall()
            }
            assert reasons == {"add_deposit", "refund"}
            batch = conn.execute(
                "SELECT refund_total_cents, deduct_total_cents FROM batches WHERE id=1"
            ).fetchone()
            assert batch == (100, 0)
            assert conn.execute("SELECT custodian_user_id FROM merchants WHERE id=1").fetchone()[0] == 1
            rate = conn.execute(
                "SELECT value FROM merchant_settings WHERE merchant_id=1 AND key='dividend_rate_percent'"
            ).fetchone()
            assert rate == ("50",)
            batch_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(batches)").fetchall()
            }
            assert "dividend_rate_percent" in batch_columns
            assert _table_exists(path, "cash_handovers")
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            conn.close()
        assert len(list((tmp_path / "backups").glob("pre-v4-*.db"))) == 1
        assert list((tmp_path / "backups").glob("pre-v3-*.db")) == []
    finally:
        dbmod.dispose()


def _table_exists(path: Path, name: str) -> bool:
    conn = sqlite3.connect(path)
    try:
        return (
            conn.execute(
                "SELECT 1 FROM sqlite_master WHERE type='table' AND name=?", (name,)
            ).fetchone()
            is not None
        )
    finally:
        conn.close()


def test_fresh_database_is_v4(tmp_path) -> None:
    path = tmp_path / "fresh.db"
    dbmod.configure_db(path)
    try:
        dbmod.ensure_schema()
        conn = sqlite3.connect(path)
        try:
            assert conn.execute("PRAGMA user_version").fetchone()[0] == SCHEMA_VERSION
            assert conn.execute("SELECT COUNT(*) FROM merchants WHERE is_system = 0").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM merchants WHERE is_system = 1").fetchone()[0] == 1
            assert conn.execute("SELECT COUNT(*) FROM merchant_settings").fetchone()[0] == 4
            user_columns = {
                row[1] for row in conn.execute("PRAGMA table_info(users)").fetchall()
            }
            assert "is_superadmin" in user_columns
            assert _table_exists(path, "cash_handovers")
            assert conn.execute("PRAGMA foreign_key_check").fetchall() == []
        finally:
            conn.close()
    finally:
        dbmod.dispose()
