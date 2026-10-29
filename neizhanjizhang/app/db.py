"""SQLite 连接、建表，以及交班用的整库导出和导入。"""

from __future__ import annotations

import os
import shutil
import sqlite3
import stat
import sys
from datetime import datetime
from pathlib import Path

from app.services import AppError

SCHEMA = (
    """
    CREATE TABLE IF NOT EXISTS players (
        game_id TEXT PRIMARY KEY,
        nickname TEXT NOT NULL DEFAULT '',
        deposit_cents INTEGER NOT NULL DEFAULT 0,
        games_played INTEGER NOT NULL DEFAULT 0 CHECK (games_played >= 0),
        created_at TEXT NOT NULL,
        updated_at TEXT NOT NULL,
        remark TEXT NOT NULL DEFAULT ''
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS sessions (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        tea_fee_cents INTEGER NOT NULL CHECK (tea_fee_cents >= 0),
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS ledger (
        id INTEGER PRIMARY KEY AUTOINCREMENT,
        player_game_id TEXT NOT NULL REFERENCES players(game_id),
        session_id INTEGER REFERENCES sessions(id),
        reason TEXT NOT NULL CHECK (
            reason IN ('normal_deduct', 'refund', 'add_deposit', 'transfer_out', 'transfer_in')
        ),
        amount_cents INTEGER NOT NULL CHECK (
            (reason = 'normal_deduct' AND amount_cents >= 0)
            OR (reason != 'normal_deduct' AND amount_cents > 0)
        ),
        balance_before_cents INTEGER NOT NULL,
        balance_after_cents INTEGER NOT NULL,
        counterparty_game_id TEXT,
        transfer_group_id TEXT,
        note TEXT NOT NULL DEFAULT '',
        created_at TEXT NOT NULL,
        CHECK (
            (reason = 'normal_deduct' AND session_id IS NOT NULL)
            OR (reason != 'normal_deduct')
        ),
        CHECK (
            (
                reason IN ('transfer_out', 'transfer_in')
                AND counterparty_game_id IS NOT NULL
                AND transfer_group_id IS NOT NULL
            )
            OR (reason NOT IN ('transfer_out', 'transfer_in'))
        )
    )
    """,
    """
    CREATE TABLE IF NOT EXISTS settings (
        key TEXT PRIMARY KEY,
        value TEXT NOT NULL
    )
    """,
    "CREATE INDEX IF NOT EXISTS idx_ledger_player ON ledger(player_game_id, id)",
    "CREATE INDEX IF NOT EXISTS idx_ledger_session ON ledger(session_id)",
)

REQUIRED_TABLES = {"players", "sessions", "ledger", "settings"}


def install_dir() -> Path:
    """开发时是项目目录，打包后是 exe 所在目录。账本放在这里，升级程序不会被清掉。"""
    if getattr(sys, "frozen", False):
        return Path(sys.executable).resolve().parent
    return Path(__file__).resolve().parent.parent


def default_db_path() -> Path:
    return install_dir() / "data" / "deposit.db"


def ensure_writable(path: Path) -> None:
    """去掉只读属性。别人发来的账本常带这个属性，复制后程序就写不进去。"""
    if not path.is_file():
        return
    try:
        os.chmod(path, stat.S_IWRITE | stat.S_IREAD)
    except OSError:
        return


def _replace_ledger_file(src: Path, dest: Path) -> None:
    """只复制账本内容。先去掉目标文件的只读，避免盖不上去，也不把来源的只读带过来。"""
    ensure_writable(dest)
    shutil.copyfile(src, dest)
    ensure_writable(dest)


def _remove_sidecars(path: Path) -> None:
    for suffix in ("-wal", "-shm"):
        sidecar = Path(str(path) + suffix)
        if sidecar.exists():
            sidecar.unlink()


def validate_ledger_file(path: Path) -> None:
    if not path.is_file():
        raise AppError("找不到要导入的文件")
    uri = path.resolve().as_uri() + "?mode=ro"
    try:
        conn = sqlite3.connect(uri, uri=True)
    except sqlite3.Error as exc:
        raise AppError("这个文件不是本程序的账本") from exc
    try:
        try:
            integrity = conn.execute("PRAGMA integrity_check").fetchone()
            names = {
                row[0]
                for row in conn.execute(
                    "SELECT name FROM sqlite_master WHERE type = 'table'"
                )
            }
        except sqlite3.Error as exc:
            raise AppError("这个文件不是本程序的账本") from exc
    finally:
        conn.close()
    if integrity is None or integrity[0] != "ok":
        raise AppError("账本文件已损坏")
    if not REQUIRED_TABLES <= names:
        raise AppError("这个文件不是本程序的账本")


class Database:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        ensure_writable(self.path)
        self.conn: sqlite3.Connection | None = None
        try:
            self._connect()
            self._init_schema()
        except sqlite3.OperationalError as exc:
            if "readonly" in str(exc).lower():
                raise AppError(
                    f"账本无法写入：\n{self.path}\n请把程序解压到可以保存文件的文件夹后再打开。"
                ) from exc
            raise

    def _connect(self) -> None:
        self.conn = sqlite3.connect(self.path, isolation_level=None)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA foreign_keys = ON")
        self.conn.execute("PRAGMA busy_timeout = 3000")
        self.conn.execute("PRAGMA journal_mode = DELETE")

    def _init_schema(self) -> None:
        assert self.conn is not None
        for statement in SCHEMA:
            self.conn.execute(statement)
        self._ensure_player_remark()
        self._relax_nonnegative_checks()
        for statement in SCHEMA[-2:]:
            self.conn.execute(statement)
        self.conn.execute(
            "INSERT OR IGNORE INTO settings (key, value) VALUES ('default_tea_cents', '0')"
        )

    def _ensure_player_remark(self) -> None:
        assert self.conn is not None
        columns = {row[1] for row in self.conn.execute("PRAGMA table_info(players)")}
        if "remark" not in columns:
            self.conn.execute("ALTER TABLE players ADD COLUMN remark TEXT NOT NULL DEFAULT ''")

    def _table_sql(self, name: str) -> str:
        assert self.conn is not None
        row = self.conn.execute(
            "SELECT sql FROM sqlite_master WHERE type = 'table' AND name = ?",
            (name,),
        ).fetchone()
        return "" if row is None or row["sql"] is None else row["sql"]

    def _relax_nonnegative_checks(self) -> None:
        """旧账本不允许负数。开局扣茶水现在可以记成负数，所以去掉这两处限制。"""
        assert self.conn is not None
        players_sql = self._table_sql("players")
        ledger_sql = self._table_sql("ledger")
        rebuild_players = "deposit_cents >= 0" in players_sql
        rebuild_ledger = "balance_before_cents >= 0" in ledger_sql or "balance_after_cents >= 0" in ledger_sql
        if not rebuild_players and not rebuild_ledger:
            return
        self.conn.execute("PRAGMA foreign_keys = OFF")
        try:
            self.conn.execute("BEGIN")
            if rebuild_players:
                self.conn.execute("ALTER TABLE players RENAME TO players_old")
                self.conn.execute(SCHEMA[0])
                self.conn.execute(
                    """
                    INSERT INTO players (
                        game_id, nickname, deposit_cents, games_played, created_at, updated_at, remark
                    )
                    SELECT game_id, nickname, deposit_cents, games_played, created_at, updated_at, remark
                    FROM players_old
                    """
                )
                self.conn.execute("DROP TABLE players_old")
            if rebuild_ledger:
                self.conn.execute("ALTER TABLE ledger RENAME TO ledger_old")
                self.conn.execute(SCHEMA[2])
                self.conn.execute(
                    """
                    INSERT INTO ledger (
                        id, player_game_id, session_id, reason, amount_cents,
                        balance_before_cents, balance_after_cents,
                        counterparty_game_id, transfer_group_id, note, created_at
                    )
                    SELECT id, player_game_id, session_id, reason, amount_cents,
                           balance_before_cents, balance_after_cents,
                           counterparty_game_id, transfer_group_id, note, created_at
                    FROM ledger_old
                    """
                )
                self.conn.execute("DROP TABLE ledger_old")
            self.conn.commit()
        except Exception:
            self.conn.rollback()
            raise
        finally:
            self.conn.execute("PRAGMA foreign_keys = ON")

    def close(self) -> None:
        if self.conn is None:
            return
        try:
            self.conn.execute("PRAGMA wal_checkpoint(TRUNCATE)")
        except sqlite3.Error:
            pass
        self.conn.close()
        self.conn = None

    def export_to(self, dest: Path) -> None:
        if self.conn is None:
            raise AppError("账本尚未打开")
        dest = Path(dest).resolve()
        if dest == self.path.resolve():
            raise AppError("不能把账本导出覆盖当前正在使用的文件")
        dest.parent.mkdir(parents=True, exist_ok=True)
        temporary = dest.with_name(dest.name + ".tmp")
        if temporary.exists():
            temporary.unlink()
        target = sqlite3.connect(temporary)
        try:
            self.conn.backup(target)
        except Exception:
            target.close()
            temporary.unlink(missing_ok=True)
            raise
        target.close()
        temporary.replace(dest)

    def import_from(self, src: Path) -> Path:
        """先把当前账本备份，再整库替换。失败时恢复备份。"""
        if self.conn is None:
            raise AppError("账本尚未打开")
        src = Path(src).resolve()
        if src == self.path.resolve():
            raise AppError("不能导入当前正在使用的账本")
        validate_ledger_file(src)
        stamp = datetime.now().strftime("%Y%m%d-%H%M%S-%f")
        backup_path = self.path.parent / f"backup-before-import-{stamp}.db"
        self.export_to(backup_path)
        self.close()
        _remove_sidecars(self.path)
        try:
            _replace_ledger_file(src, self.path)
            _remove_sidecars(self.path)
            validate_ledger_file(self.path)
        except Exception as exc:
            _replace_ledger_file(backup_path, self.path)
            _remove_sidecars(self.path)
            self._connect()
            self._init_schema()
            if isinstance(exc, AppError):
                raise
            raise AppError("导入失败，已恢复导入前的账本") from exc
        self._connect()
        self._init_schema()
        return backup_path
