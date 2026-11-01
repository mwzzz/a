"""加押金、退押金、手动扣押、划转。所有金额变动都走 apply_delta。

每一次读写都带 merchant_id：别家的玩家与批次在这里一律当作不存在。
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError, NotFoundError
from app.models import Batch, LedgerEntry, Player
from app.serializers import entry_payload, player_row
from app.services import options
from app.services.money import require_positive
from app.services.players import clean_text, get_player
from app.timeutil import now_text


def apply_delta(
    session: Session,
    player_id: int,
    delta_cents: int,
    *,
    merchant_id: int,
    games_delta: int = 0,
) -> tuple[int, int]:
    """在 SQL 层做自增，返回 (变动前, 变动后)。必须在写事务里调用。"""
    stamp = now_text()
    result = session.execute(
        update(Player)
        .where(
            Player.id == player_id,
            Player.merchant_id == merchant_id,
            Player.deleted_at.is_(None),
        )
        .values(
            deposit_cents=Player.deposit_cents + int(delta_cents),
            games_played=Player.games_played + int(games_delta),
            updated_at=stamp,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        raise NotFoundError("找不到玩家")
    session.expire_all()
    after = session.scalar(
        select(Player.deposit_cents).where(
            Player.id == player_id, Player.merchant_id == merchant_id
        )
    )
    if after is None:
        raise NotFoundError("找不到玩家")
    return int(after) - int(delta_cents), int(after)


def current_batch_id(session: Session, merchant_id: int) -> int | None:
    return session.scalar(
        select(Batch.id).where(
            Batch.merchant_id == merchant_id, Batch.status == "open"
        )
    )


def _player_payload(session: Session, player_id: int, merchant_id: int) -> dict:
    player = get_player(session, player_id, merchant_id)
    low, high = options.thresholds(session, merchant_id)
    return player_row(player, low_cents=low, high_cents=high)


def _write_entry(
    session: Session,
    *,
    actor: Actor,
    player_id: int,
    reason: str,
    amount_cents: int,
    before: int,
    after: int,
    batch_id: int | None,
    session_id: int | None = None,
    counterparty_player_id: int | None = None,
    transfer_group_id: str | None = None,
    note: str = "",
) -> LedgerEntry:
    entry = LedgerEntry(
        merchant_id=actor.merchant_id,
        player_id=player_id,
        batch_id=batch_id,
        session_id=session_id,
        reason=reason,
        amount_cents=int(amount_cents),
        balance_before_cents=int(before),
        balance_after_cents=int(after),
        counterparty_player_id=counterparty_player_id,
        transfer_group_id=transfer_group_id,
        operator_id=actor.id,
        note=note,
        created_at=now_text(),
    )
    session.add(entry)
    session.flush()
    return entry


def add_deposit(
    session: Session,
    actor: Actor,
    player_id: int,
    amount_cents: int,
    note: str = "",
) -> dict:
    require_positive(amount_cents, "加押金金额必须大于 0")
    merchant_id = actor.merchant_id
    get_player(session, player_id, merchant_id)
    clean = clean_text(note, "备注", 200)
    before, after = apply_delta(
        session, player_id, int(amount_cents), merchant_id=merchant_id
    )
    entry = _write_entry(
        session,
        actor=actor,
        player_id=player_id,
        reason="add_deposit",
        amount_cents=amount_cents,
        before=before,
        after=after,
        batch_id=current_batch_id(session, merchant_id),
        note=clean,
    )
    return {
        "entry": entry_payload(session, entry),
        "player": _player_payload(session, player_id, merchant_id),
    }


def refund(
    session: Session,
    actor: Actor,
    player_id: int,
    amount_cents: int,
    note: str = "",
) -> dict:
    require_positive(amount_cents, "退押金金额必须大于 0")
    merchant_id = actor.merchant_id
    get_player(session, player_id, merchant_id)
    clean = clean_text(note, "备注", 200)
    before, after = apply_delta(
        session, player_id, -int(amount_cents), merchant_id=merchant_id
    )
    if after < 0:
        raise AppError("押金不足，不能退这么多")
    entry = _write_entry(
        session,
        actor=actor,
        player_id=player_id,
        reason="refund",
        amount_cents=amount_cents,
        before=before,
        after=after,
        batch_id=current_batch_id(session, merchant_id),
        note=clean,
    )
    return {
        "entry": entry_payload(session, entry),
        "player": _player_payload(session, player_id, merchant_id),
    }


def manual_deduct(
    session: Session,
    actor: Actor,
    player_id: int,
    amount_cents: int,
    note: str = "",
) -> dict:
    if amount_cents < 0:
        raise AppError("扣押金额不能为负")
    merchant_id = actor.merchant_id
    get_player(session, player_id, merchant_id)
    clean = clean_text(note, "备注", 200)
    before, after = apply_delta(
        session, player_id, -int(amount_cents), merchant_id=merchant_id
    )
    entry = _write_entry(
        session,
        actor=actor,
        player_id=player_id,
        reason="manual_deduct",
        amount_cents=amount_cents,
        before=before,
        after=after,
        batch_id=current_batch_id(session, merchant_id),
        note=clean,
    )
    return {
        "entry": entry_payload(session, entry),
        "player": _player_payload(session, player_id, merchant_id),
    }


def transfer(
    session: Session,
    actor: Actor,
    from_player_id: int,
    to_player_id: int,
    amount_cents: int,
    note: str = "",
) -> dict:
    if from_player_id == to_player_id:
        raise AppError("不能划给自己")
    require_positive(amount_cents, "划转金额必须大于 0")
    merchant_id = actor.merchant_id
    get_player(session, from_player_id, merchant_id)
    get_player(session, to_player_id, merchant_id)
    clean = clean_text(note, "备注", 200)

    group = uuid4().hex
    batch_id = current_batch_id(session, merchant_id)
    source_before, source_after = apply_delta(
        session, from_player_id, -int(amount_cents), merchant_id=merchant_id
    )
    target_before, target_after = apply_delta(
        session, to_player_id, int(amount_cents), merchant_id=merchant_id
    )

    out_entry = _write_entry(
        session,
        actor=actor,
        player_id=from_player_id,
        reason="transfer_out",
        amount_cents=amount_cents,
        before=source_before,
        after=source_after,
        batch_id=batch_id,
        counterparty_player_id=to_player_id,
        transfer_group_id=group,
        note=clean,
    )
    in_entry = _write_entry(
        session,
        actor=actor,
        player_id=to_player_id,
        reason="transfer_in",
        amount_cents=amount_cents,
        before=target_before,
        after=target_after,
        batch_id=batch_id,
        counterparty_player_id=from_player_id,
        transfer_group_id=group,
        note=clean,
    )
    return {
        "group_id": group,
        "out_entry": entry_payload(session, out_entry),
        "in_entry": entry_payload(session, in_entry),
        "from_player": _player_payload(session, from_player_id, merchant_id),
        "to_player": _player_payload(session, to_player_id, merchant_id),
    }
