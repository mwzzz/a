"""玩家、开局和押金流水规则。金额在库里用整数分。"""

from __future__ import annotations

import sqlite3
from contextlib import contextmanager
from datetime import datetime
from decimal import Decimal, InvalidOperation, ROUND_HALF_UP
from typing import Iterator
from uuid import uuid4

REASON_LABELS = {
    "normal_deduct": "正常扣押",
    "refund": "退押金",
    "add_deposit": "加押金",
    "transfer_out": "划给其他人押金",
    "transfer_in": "收到他人划入",
}

_INCOMING = {"add_deposit", "transfer_in"}


class AppError(Exception):
    """可直接展示给管理员的业务错误。"""


def now_text() -> str:
    return datetime.now().strftime("%Y-%m-%d %H:%M:%S")


def parse_yuan(text: str) -> int:
    raw = text.strip().replace(",", "")
    if not raw:
        raise AppError("请输入金额")
    if "e" in raw.lower():
        raise AppError("金额格式不正确")
    try:
        value = Decimal(raw)
    except InvalidOperation as exc:
        raise AppError("金额格式不正确") from exc
    if not value.is_finite() or value < 0:
        raise AppError("金额不能为负" if value < 0 else "金额格式不正确")
    quantized = value.quantize(Decimal("0.01"), rounding=ROUND_HALF_UP)
    if quantized != value:
        raise AppError("金额最多保留两位小数")
    return int(quantized * 100)


def format_yuan(cents: int) -> str:
    sign = "-" if cents < 0 else ""
    cents = abs(int(cents))
    return f"{sign}{cents // 100}.{cents % 100:02d}"


def format_change(cents: int) -> str:
    if cents > 0:
        return f"+{format_yuan(cents)}"
    return format_yuan(cents)


def normalize_game_id(value: str) -> str:
    game_id = value.strip()
    if not game_id:
        raise AppError("请填写游戏 id")
    if any(char in game_id for char in "\r\n\t"):
        raise AppError("游戏 id 不能包含换行")
    if len(game_id) > 64:
        raise AppError("游戏 id 不能超过 64 个字符")
    return game_id


def normalize_nickname(value: str) -> str:
    nickname = value.strip()
    if any(char in nickname for char in "\r\n\t"):
        raise AppError("昵称不能包含换行")
    if len(nickname) > 64:
        raise AppError("昵称不能超过 64 个字符")
    return nickname


def _note(value: str) -> str:
    note = value.strip()
    if len(note) > 200:
        raise AppError("备注不能超过 200 字")
    return note


def _positive_amount(amount_cents: int, message: str) -> None:
    if amount_cents <= 0:
        raise AppError(message)


@contextmanager
def transaction(conn: sqlite3.Connection) -> Iterator[None]:
    conn.execute("BEGIN IMMEDIATE")
    try:
        yield
    except Exception:
        conn.rollback()
        raise
    else:
        try:
            conn.commit()
        except Exception:
            conn.rollback()
            raise


def _require_player(conn: sqlite3.Connection, game_id: str) -> sqlite3.Row:
    row = conn.execute(
        "SELECT * FROM players WHERE game_id = ?",
        (game_id,),
    ).fetchone()
    if row is None:
        raise AppError(f"找不到玩家：{game_id}")
    return row


def _insert_ledger(
    conn: sqlite3.Connection,
    *,
    player_game_id: str,
    session_id: int | None,
    reason: str,
    amount_cents: int,
    before: int,
    after: int,
    counterparty: str | None,
    group: str | None,
    note: str,
    created_at: str,
) -> None:
    conn.execute(
        """
        INSERT INTO ledger (
            player_game_id, session_id, reason, amount_cents,
            balance_before_cents, balance_after_cents,
            counterparty_game_id, transfer_group_id, note, created_at
        ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """,
        (
            player_game_id,
            session_id,
            reason,
            amount_cents,
            before,
            after,
            counterparty,
            group,
            note,
            created_at,
        ),
    )


def _set_balance(
    conn: sqlite3.Connection,
    game_id: str,
    deposit_cents: int,
    games_played: int,
    updated_at: str,
) -> None:
    conn.execute(
        """
        UPDATE players
        SET deposit_cents = ?, games_played = ?, updated_at = ?
        WHERE game_id = ?
        """,
        (deposit_cents, games_played, updated_at, game_id),
    )


def create_player(conn: sqlite3.Connection, game_id: str, nickname: str = "") -> str:
    game_id = normalize_game_id(game_id)
    nickname = normalize_nickname(nickname)
    created_at = now_text()
    try:
        with transaction(conn):
            conn.execute(
                """
                INSERT INTO players (
                    game_id, nickname, deposit_cents, games_played, created_at, updated_at
                ) VALUES (?, ?, 0, 0, ?, ?)
                """,
                (game_id, nickname, created_at, created_at),
            )
    except sqlite3.IntegrityError as exc:
        raise AppError("游戏 id 已存在") from exc
    return game_id


def update_nickname(conn: sqlite3.Connection, game_id: str, nickname: str) -> None:
    game_id = normalize_game_id(game_id)
    nickname = normalize_nickname(nickname)
    updated_at = now_text()
    with transaction(conn):
        _require_player(conn, game_id)
        conn.execute(
            "UPDATE players SET nickname = ?, updated_at = ? WHERE game_id = ?",
            (nickname, updated_at, game_id),
        )


def delete_player(conn: sqlite3.Connection, game_id: str) -> None:
    game_id = normalize_game_id(game_id)
    with transaction(conn):
        player = _require_player(conn, game_id)
        count = conn.execute(
            "SELECT COUNT(*) AS n FROM ledger WHERE player_game_id = ?",
            (game_id,),
        ).fetchone()["n"]
        if count or player["deposit_cents"] or player["games_played"]:
            raise AppError("已有流水的玩家不能删除")
        conn.execute("DELETE FROM players WHERE game_id = ?", (game_id,))


def list_players(conn: sqlite3.Connection) -> list[dict]:
    rows = conn.execute(
        """
        SELECT game_id, nickname, deposit_cents, games_played, created_at, updated_at
        FROM players
        ORDER BY game_id
        """
    ).fetchall()
    return [dict(row) for row in rows]


def get_player(conn: sqlite3.Connection, game_id: str) -> dict | None:
    try:
        game_id = normalize_game_id(game_id)
    except AppError:
        return None
    row = conn.execute(
        "SELECT * FROM players WHERE game_id = ?",
        (game_id,),
    ).fetchone()
    return dict(row) if row else None


def add_deposit(conn: sqlite3.Connection, game_id: str, amount_cents: int, note: str = "") -> None:
    game_id = normalize_game_id(game_id)
    note = _note(note)
    _positive_amount(amount_cents, "加押金金额必须大于 0")
    created_at = now_text()
    with transaction(conn):
        player = _require_player(conn, game_id)
        before = int(player["deposit_cents"])
        after = before + amount_cents
        _insert_ledger(
            conn,
            player_game_id=game_id,
            session_id=None,
            reason="add_deposit",
            amount_cents=amount_cents,
            before=before,
            after=after,
            counterparty=None,
            group=None,
            note=note,
            created_at=created_at,
        )
        _set_balance(conn, game_id, after, int(player["games_played"]), created_at)


def refund(conn: sqlite3.Connection, game_id: str, amount_cents: int, note: str = "") -> None:
    game_id = normalize_game_id(game_id)
    note = _note(note)
    _positive_amount(amount_cents, "退押金金额必须大于 0")
    created_at = now_text()
    with transaction(conn):
        player = _require_player(conn, game_id)
        before = int(player["deposit_cents"])
        if before < amount_cents:
            raise AppError("押金不足，不能退这么多")
        after = before - amount_cents
        _insert_ledger(
            conn,
            player_game_id=game_id,
            session_id=None,
            reason="refund",
            amount_cents=amount_cents,
            before=before,
            after=after,
            counterparty=None,
            group=None,
            note=note,
            created_at=created_at,
        )
        _set_balance(conn, game_id, after, int(player["games_played"]), created_at)


def transfer(
    conn: sqlite3.Connection,
    from_game_id: str,
    to_game_id: str,
    amount_cents: int,
    note: str = "",
) -> str:
    from_game_id = normalize_game_id(from_game_id)
    to_game_id = normalize_game_id(to_game_id)
    note = _note(note)
    if from_game_id == to_game_id:
        raise AppError("不能划给自己")
    _positive_amount(amount_cents, "划转金额必须大于 0")
    created_at = now_text()
    group = uuid4().hex
    with transaction(conn):
        source = _require_player(conn, from_game_id)
        target = _require_player(conn, to_game_id)
        source_before = int(source["deposit_cents"])
        if source_before < amount_cents:
            raise AppError("押金不足，不能划出这么多")
        source_after = source_before - amount_cents
        target_before = int(target["deposit_cents"])
        target_after = target_before + amount_cents
        _insert_ledger(
            conn,
            player_game_id=from_game_id,
            session_id=None,
            reason="transfer_out",
            amount_cents=amount_cents,
            before=source_before,
            after=source_after,
            counterparty=to_game_id,
            group=group,
            note=note,
            created_at=created_at,
        )
        _insert_ledger(
            conn,
            player_game_id=to_game_id,
            session_id=None,
            reason="transfer_in",
            amount_cents=amount_cents,
            before=target_before,
            after=target_after,
            counterparty=from_game_id,
            group=group,
            note=note,
            created_at=created_at,
        )
        _set_balance(conn, from_game_id, source_after, int(source["games_played"]), created_at)
        _set_balance(conn, to_game_id, target_after, int(target["games_played"]), created_at)
    return group


def preview_session(
    conn: sqlite3.Connection,
    game_ids: list[str],
    tea_fee_cents: int,
) -> list[dict]:
    if tea_fee_cents < 0:
        raise AppError("茶水不能为负")
    rows: list[dict] = []
    seen: set[str] = set()
    for raw_id in game_ids:
        game_id = normalize_game_id(raw_id)
        if game_id in seen:
            continue
        seen.add(game_id)
        player = _require_player(conn, game_id)
        before = int(player["deposit_cents"])
        after = before - tea_fee_cents
        rows.append(
            {
                "game_id": game_id,
                "nickname": player["nickname"],
                "before": before,
                "deduct": tea_fee_cents,
                "after": after,
            }
        )
    return rows


def open_session(
    conn: sqlite3.Connection,
    game_ids: list[str],
    tea_fee_cents: int,
    note: str = "",
) -> int:
    if tea_fee_cents < 0:
        raise AppError("茶水不能为负")
    note = _note(note)
    ids: list[str] = []
    seen: set[str] = set()
    for raw_id in game_ids:
        game_id = normalize_game_id(raw_id)
        if game_id not in seen:
            seen.add(game_id)
            ids.append(game_id)
    if not ids:
        raise AppError("请选择玩家")
    created_at = now_text()
    with transaction(conn):
        players = [_require_player(conn, game_id) for game_id in ids]
        cursor = conn.execute(
            "INSERT INTO sessions (tea_fee_cents, note, created_at) VALUES (?, ?, ?)",
            (tea_fee_cents, note, created_at),
        )
        session_id = int(cursor.lastrowid)
        for player in players:
            before = int(player["deposit_cents"])
            after = before - tea_fee_cents
            _insert_ledger(
                conn,
                player_game_id=player["game_id"],
                session_id=session_id,
                reason="normal_deduct",
                amount_cents=tea_fee_cents,
                before=before,
                after=after,
                counterparty=None,
                group=None,
                note=note,
                created_at=created_at,
            )
            _set_balance(
                conn,
                player["game_id"],
                after,
                int(player["games_played"]) + 1,
                created_at,
            )
    return session_id


def list_ledger(conn: sqlite3.Connection, game_id: str) -> list[dict]:
    game_id = normalize_game_id(game_id)
    rows = conn.execute(
        """
        SELECT id, player_game_id, session_id, reason, amount_cents,
               balance_before_cents, balance_after_cents,
               counterparty_game_id, transfer_group_id, note, created_at
        FROM ledger
        WHERE player_game_id = ?
        ORDER BY created_at DESC, id DESC
        """,
        (game_id,),
    ).fetchall()
    result: list[dict] = []
    for row in rows:
        item = dict(row)
        item["reason_label"] = REASON_LABELS[item["reason"]]
        amount = int(item["amount_cents"])
        item["signed_amount_cents"] = amount if item["reason"] in _INCOMING else -amount
        result.append(item)
    return result


def get_default_tea_cents(conn: sqlite3.Connection) -> int:
    row = conn.execute(
        "SELECT value FROM settings WHERE key = 'default_tea_cents'"
    ).fetchone()
    if row is None:
        return 0
    try:
        value = int(row["value"])
    except (TypeError, ValueError):
        return 0
    return max(value, 0)


def set_default_tea_cents(conn: sqlite3.Connection, tea_fee_cents: int) -> None:
    if tea_fee_cents < 0:
        raise AppError("茶水不能为负")
    with transaction(conn):
        conn.execute(
            """
            INSERT INTO settings (key, value) VALUES ('default_tea_cents', ?)
            ON CONFLICT(key) DO UPDATE SET value = excluded.value
            """,
            (str(tea_fee_cents),),
        )
