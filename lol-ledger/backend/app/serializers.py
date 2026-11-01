"""把 ORM 对象整理成接口返回的字典。调用时数据库会话必须还开着。"""

from __future__ import annotations

from app.models import (
    AuditLog,
    Batch,
    GameSession,
    LedgerEntry,
    Player,
    SessionPlayer,
    User,
)
from app.services.money import deposit_level, reason_label, signed_cents


def user_brief(user: User | None) -> dict | None:
    if user is None:
        return None
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
    }


def player_row(
    player: Player,
    *,
    low_cents: int,
    high_cents: int,
    last_active_at: str | None = None,
) -> dict:
    return {
        "id": player.id,
        "game_id": player.game_id,
        "nickname": player.nickname,
        "account": player.account,
        "remark": player.remark,
        "deposit_cents": int(player.deposit_cents),
        "deposit_level": deposit_level(int(player.deposit_cents), low_cents, high_cents),
        "games_played": int(player.games_played),
        "last_active_at": last_active_at or player.updated_at,
        "creator": user_brief(player.creator),
        "created_at": player.created_at,
    }


def player_option(player: Player) -> dict:
    return {
        "id": player.id,
        "game_id": player.game_id,
        "account": player.account,
        "deposit_cents": int(player.deposit_cents),
    }


def entry_row(
    entry: LedgerEntry,
    *,
    player: Player | None = None,
    operator: User | None = None,
    session: GameSession | None = None,
    batch: Batch | None = None,
    counterparty: Player | None = None,
    player_game_id: str | None = None,
) -> dict:
    game_id = player_game_id or (player.game_id if player else "")
    return {
        "id": entry.id,
        "created_at": entry.created_at,
        "reason": entry.reason,
        "reason_label": reason_label(entry.reason, counterparty.game_id if counterparty else None),
        "amount_cents": int(entry.amount_cents),
        "signed_amount_cents": signed_cents(entry.reason, int(entry.amount_cents)),
        "balance_before_cents": int(entry.balance_before_cents),
        "balance_after_cents": int(entry.balance_after_cents),
        "note": entry.note,
        "player": {"id": entry.player_id, "game_id": game_id},
        "counterparty": (
            {"id": counterparty.id, "game_id": counterparty.game_id} if counterparty else None
        ),
        "session": (
            {"id": session.id, "name": session.name} if session else None
        ),
        "batch": (
            {"id": batch.id, "label": batch.label, "opened_at": batch.opened_at}
            if batch
            else None
        ),
        "operator": user_brief(operator),
        "transfer_group_id": entry.transfer_group_id,
    }


def session_player_row(item: SessionPlayer) -> dict:
    player = item.player
    return {
        "player_id": item.player_id,
        "game_id": player.game_id if player else "",
        "account": player.account if player else "",
        "tea_fee_cents": int(item.tea_fee_cents),
        "balance_before_cents": int(item.balance_before_cents),
        "balance_after_cents": int(item.balance_after_cents),
    }


def session_row(
    session: GameSession,
    players: list[SessionPlayer] | None = None,
) -> dict:
    return {
        "id": session.id,
        "batch_id": session.batch_id,
        "name": session.name,
        "played_at": session.played_at,
        "tea_fee_cents": int(session.tea_fee_cents),
        "tea_total_cents": int(session.tea_fee_cents) * int(session.player_count),
        "note": session.note,
        "player_count": int(session.player_count),
        "operator": user_brief(session.operator),
        "creator": user_brief(session.operator),
        "created_at": session.created_at,
        "players": [session_player_row(item) for item in (players or [])],
    }


def audit_row(log: AuditLog) -> dict:
    return {
        "id": log.id,
        "user_id": log.user_id,
        "action": log.action,
        "target_type": log.target_type,
        "target_id": log.target_id,
        "detail": log.detail,
        "ip": log.ip,
        "created_at": log.created_at,
    }


def entry_payload(session, entry: LedgerEntry) -> dict:
    """单条流水的完整返回。调用时会话必须开着。"""
    from app.models import Batch, GameSession, Player, User

    player = session.get(Player, entry.player_id)
    operator = session.get(User, entry.operator_id)
    counterparty = (
        session.get(Player, entry.counterparty_player_id)
        if entry.counterparty_player_id
        else None
    )
    game_session = session.get(GameSession, entry.session_id) if entry.session_id else None
    batch = session.get(Batch, entry.batch_id) if entry.batch_id else None
    return entry_row(
        entry,
        player=player,
        operator=operator,
        session=game_session,
        batch=batch,
        counterparty=counterparty,
    )
