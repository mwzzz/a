"""卡密、到期日和当前占用的存储。"""

from __future__ import annotations

import secrets
import sqlite3
from dataclasses import dataclass
from datetime import datetime, timedelta, timezone
from pathlib import Path

CN_TIME = timezone(timedelta(hours=8))
LEASE_SECONDS = 60
_ALPHABET = "ABCDEFGHJKLMNPQRSTUVWXYZ23456789"


@dataclass
class Outcome:
    status: int
    body: dict


def now_cn() -> datetime:
    return datetime.now(CN_TIME).replace(microsecond=0)


def format_dt(value: datetime) -> str:
    return value.strftime("%Y-%m-%d %H:%M:%S")


def parse_dt(value: str) -> datetime:
    return datetime.strptime(value, "%Y-%m-%d %H:%M:%S").replace(tzinfo=CN_TIME)


def new_card_code() -> str:
    parts = ["".join(secrets.choice(_ALPHABET) for _ in range(4)) for _ in range(3)]
    return "-".join(parts)


class CardStore:
    def __init__(self, path: Path):
        self.path = Path(path)
        self.path.parent.mkdir(parents=True, exist_ok=True)
        self.conn = sqlite3.connect(self.path, isolation_level=None, check_same_thread=False)
        self.conn.row_factory = sqlite3.Row
        self.conn.execute("PRAGMA journal_mode = DELETE")
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS cards (
                card TEXT PRIMARY KEY,
                expires_at TEXT NOT NULL,
                holder_machine_id TEXT,
                last_seen TEXT,
                created_at TEXT NOT NULL
            )
            """
        )
        self.conn.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key TEXT PRIMARY KEY,
                value TEXT NOT NULL
            )
            """
        )

    def close(self) -> None:
        self.conn.close()

    def set_trial(self, enabled: bool) -> None:
        value = "1" if enabled else "0"
        with self._transaction():
            self.conn.execute(
                """
                INSERT INTO settings (key, value) VALUES ('trial', ?)
                ON CONFLICT(key) DO UPDATE SET value = excluded.value
                """,
                (value,),
            )

    def trial_enabled(self) -> bool:
        row = self.conn.execute("SELECT value FROM settings WHERE key = 'trial'").fetchone()
        return row is not None and row["value"] == "1"

    def issue(self, days: int, when: datetime | None = None) -> tuple[str, str]:
        if days <= 0:
            raise ValueError("天数必须大于 0")
        moment = when or now_cn()
        expires_at = format_dt(moment + timedelta(days=days))
        card = new_card_code()
        with self._transaction():
            self.conn.execute(
                """
                INSERT INTO cards (card, expires_at, holder_machine_id, last_seen, created_at)
                VALUES (?, ?, NULL, NULL, ?)
                """,
                (card, expires_at, format_dt(moment)),
            )
        return card, expires_at

    def extend(self, card: str, days: int, when: datetime | None = None) -> str:
        if days <= 0:
            raise ValueError("天数必须大于 0")
        moment = when or now_cn()
        with self._transaction():
            row = self._get(card.strip())
            if row is None:
                raise ValueError("没有这张卡密")
            current = parse_dt(row["expires_at"])
            base = current if current > moment else moment
            expires_at = format_dt(base + timedelta(days=days))
            self.conn.execute(
                "UPDATE cards SET expires_at = ? WHERE card = ?",
                (expires_at, row["card"]),
            )
            return expires_at

    def list_cards(self) -> list[dict]:
        rows = self.conn.execute(
            """
            SELECT card, expires_at, holder_machine_id, last_seen, created_at
            FROM cards
            ORDER BY created_at DESC
            """
        ).fetchall()
        return [dict(row) for row in rows]

    def login(self, card: str, machine_id: str, when: datetime | None = None) -> Outcome:
        trial = self._trial_guest(card)
        if trial is not None:
            return trial
        return self._touch(card, machine_id, when, take_over_expired_lease=True)

    def heartbeat(self, card: str, machine_id: str, when: datetime | None = None) -> Outcome:
        trial = self._trial_guest(card)
        if trial is not None:
            return trial
        return self._touch(card, machine_id, when, take_over_expired_lease=False)

    def logout(self, card: str, machine_id: str) -> Outcome:
        if self._trial_guest(card) is not None:
            return Outcome(200, {"ok": True})
        with self._transaction():
            row = self._get(card)
            if row is not None and row["holder_machine_id"] == machine_id:
                self.conn.execute(
                    "UPDATE cards SET holder_machine_id = NULL, last_seen = NULL WHERE card = ?",
                    (card,),
                )
        return Outcome(200, {"ok": True})

    def _trial_guest(self, card: str) -> Outcome | None:
        """试用开启时，空卡密和未登记的卡密都能进。已经发过的卡仍按原规则。"""
        if not self.trial_enabled():
            return None
        if card and self._get(card) is not None:
            return None
        return Outcome(200, {"ok": True, "expires_at": "试用"})

    def _touch(
        self,
        card: str,
        machine_id: str,
        when: datetime | None,
        take_over_expired_lease: bool,
    ) -> Outcome:
        moment = when or now_cn()
        with self._transaction():
            row = self._get(card)
            if row is None:
                return Outcome(403, {"ok": False, "error": "invalid"})
            if parse_dt(row["expires_at"]) < moment:
                return Outcome(403, {"ok": False, "error": "expired"})
            holder = row["holder_machine_id"]
            alive = self._lease_alive(row["last_seen"], moment)
            if holder and holder != machine_id and alive:
                return Outcome(409, {"ok": False, "error": "in_use"})
            if holder != machine_id and not take_over_expired_lease:
                return Outcome(409, {"ok": False, "error": "in_use"})
            self.conn.execute(
                "UPDATE cards SET holder_machine_id = ?, last_seen = ? WHERE card = ?",
                (machine_id, format_dt(moment), card),
            )
            return Outcome(200, {"ok": True, "expires_at": row["expires_at"]})

    def _lease_alive(self, last_seen: str | None, moment: datetime) -> bool:
        if not last_seen:
            return False
        return (moment - parse_dt(last_seen)).total_seconds() < LEASE_SECONDS

    def _get(self, card: str) -> sqlite3.Row | None:
        return self.conn.execute("SELECT * FROM cards WHERE card = ?", (card,)).fetchone()

    def _transaction(self):
        return _Immediate(self.conn)


class _Immediate:
    def __init__(self, conn: sqlite3.Connection):
        self.conn = conn

    def __enter__(self) -> None:
        self.conn.execute("BEGIN IMMEDIATE")

    def __exit__(self, exc_type, exc, tb) -> None:
        if exc_type is None:
            self.conn.commit()
        else:
            self.conn.rollback()
