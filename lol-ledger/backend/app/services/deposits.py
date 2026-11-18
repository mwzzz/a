"""加押金、退押金、划转、赠金。所有金额变动都走这里。

现金押金和赠金分开记：deposit_cents 只能退/划，bonus_cents 只能扣茶水。
每一次读写都带 merchant_id：别家的玩家与批次在这里一律当作不存在。
"""

from __future__ import annotations

from uuid import uuid4

from sqlalchemy import select, update
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError, NotFoundError
from app.models import Batch, LedgerEntry, Player, RechargeCampaign
from app.serializers import entry_payload, player_row
from app.services import campaigns as campaign_service
from app.services import options
from app.services.money import format_yuan, require_positive
from app.services.players import clean_text, get_player
from app.timeutil import now_text


def apply_cash_delta(
    session: Session,
    player_id: int,
    delta_cents: int,
    *,
    merchant_id: int,
    games_delta: int = 0,
) -> tuple[int, int, int, int]:
    """只改现金押金，返回 (现金前, 现金后, 赠金前, 赠金后)。"""
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
    row = session.execute(
        select(Player.deposit_cents, Player.bonus_cents).where(
            Player.id == player_id, Player.merchant_id == merchant_id
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("找不到玩家")
    cash_after, bonus = int(row[0]), int(row[1])
    return cash_after - int(delta_cents), cash_after, bonus, bonus


def apply_bonus_delta(
    session: Session,
    player_id: int,
    delta_cents: int,
    *,
    merchant_id: int,
) -> tuple[int, int, int, int]:
    """只改赠金，返回 (现金前, 现金后, 赠金前, 赠金后)。"""
    stamp = now_text()
    result = session.execute(
        update(Player)
        .where(
            Player.id == player_id,
            Player.merchant_id == merchant_id,
            Player.deleted_at.is_(None),
        )
        .values(
            bonus_cents=Player.bonus_cents + int(delta_cents),
            updated_at=stamp,
        )
        .execution_options(synchronize_session=False)
    )
    if result.rowcount == 0:
        raise NotFoundError("找不到玩家")
    session.expire_all()
    row = session.execute(
        select(Player.deposit_cents, Player.bonus_cents).where(
            Player.id == player_id, Player.merchant_id == merchant_id
        )
    ).one_or_none()
    if row is None:
        raise NotFoundError("找不到玩家")
    cash, bonus_after = int(row[0]), int(row[1])
    return cash, cash, bonus_after - int(delta_cents), bonus_after


def apply_tea_deduction(
    session: Session,
    player_id: int,
    tea_cents: int,
    *,
    merchant_id: int,
) -> tuple[int, int, int, int, int]:
    """先扣赠金、再扣现金，返回现金前/后、赠金前/后、赠金抵扣额。"""
    player = get_player(session, player_id, merchant_id)
    cash_before = int(player.deposit_cents)
    bonus_before = int(player.bonus_cents)
    bonus_used = min(bonus_before, int(tea_cents))
    cash_used = int(tea_cents) - bonus_used
    cash_after = cash_before - cash_used
    bonus_after = bonus_before - bonus_used
    player.deposit_cents = cash_after
    player.bonus_cents = bonus_after
    player.games_played = int(player.games_played) + 1
    player.updated_at = now_text()
    session.flush()
    return cash_before, cash_after, bonus_before, bonus_after, bonus_used


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
    deposit_before: int,
    deposit_after: int,
    bonus_before: int,
    bonus_after: int,
    bonus_amount_cents: int = 0,
    batch_id: int | None,
    session_id: int | None = None,
    counterparty_player_id: int | None = None,
    transfer_group_id: str | None = None,
    reverses_ledger_id: int | None = None,
    note: str = "",
) -> LedgerEntry:
    entry = LedgerEntry(
        merchant_id=actor.merchant_id,
        player_id=player_id,
        batch_id=batch_id,
        session_id=session_id,
        reason=reason,
        amount_cents=int(amount_cents),
        balance_before_cents=int(deposit_before) + int(bonus_before),
        balance_after_cents=int(deposit_after) + int(bonus_after),
        bonus_amount_cents=int(bonus_amount_cents),
        deposit_after_cents=int(deposit_after),
        bonus_after_cents=int(bonus_after),
        counterparty_player_id=counterparty_player_id,
        transfer_group_id=transfer_group_id,
        reverses_ledger_id=reverses_ledger_id,
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
    *,
    apply_campaign: bool = True,
) -> dict:
    require_positive(amount_cents, "加押金金额必须大于 0")
    merchant_id = actor.merchant_id
    get_player(session, player_id, merchant_id)
    clean = clean_text(note, "备注", 200)
    cash_before, cash_after, bonus_before, bonus_after = apply_cash_delta(
        session, player_id, int(amount_cents), merchant_id=merchant_id
    )
    entry = _write_entry(
        session,
        actor=actor,
        player_id=player_id,
        reason="add_deposit",
        amount_cents=amount_cents,
        deposit_before=cash_before,
        deposit_after=cash_after,
        bonus_before=bonus_before,
        bonus_after=bonus_after,
        batch_id=current_batch_id(session, merchant_id),
        note=clean,
    )

    campaign = (
        campaign_service.best_for_amount(session, merchant_id, int(amount_cents))
        if apply_campaign
        else None
    )
    bonus_entry: LedgerEntry | None = None
    if campaign is not None and int(campaign.bonus_cents) > 0:
        bonus_amount = int(campaign.bonus_cents)
        cash, cash_again, gift_before, gift_after = apply_bonus_delta(
            session, player_id, bonus_amount, merchant_id=merchant_id
        )
        bonus_entry = _write_entry(
            session,
            actor=actor,
            player_id=player_id,
            reason="add_bonus",
            amount_cents=bonus_amount,
            deposit_before=cash,
            deposit_after=cash_again,
            bonus_before=gift_before,
            bonus_after=gift_after,
            bonus_amount_cents=bonus_amount,
            batch_id=current_batch_id(session, merchant_id),
            note=(
                f"充值活动：满 ¥{format_yuan(campaign.threshold_cents)} "
                f"送 ¥{format_yuan(campaign.bonus_cents)}"
            ),
        )

    return {
        "entry": entry_payload(session, entry),
        "bonus_entry": entry_payload(session, bonus_entry) if bonus_entry else None,
        "campaign": campaign_service.campaign_row(campaign) if campaign else None,
        "player": _player_payload(session, player_id, merchant_id),
    }


def add_bonus(
    session: Session,
    actor: Actor,
    player_id: int,
    amount_cents: int,
    note: str = "",
) -> dict:
    require_positive(amount_cents, "加赠金金额必须大于 0")
    merchant_id = actor.merchant_id
    get_player(session, player_id, merchant_id)
    clean = clean_text(note, "备注", 200) or "手动加赠金"
    cash, cash_again, bonus_before, bonus_after = apply_bonus_delta(
        session, player_id, int(amount_cents), merchant_id=merchant_id
    )
    entry = _write_entry(
        session,
        actor=actor,
        player_id=player_id,
        reason="add_bonus",
        amount_cents=amount_cents,
        deposit_before=cash,
        deposit_after=cash_again,
        bonus_before=bonus_before,
        bonus_after=bonus_after,
        bonus_amount_cents=amount_cents,
        batch_id=current_batch_id(session, merchant_id),
        note=clean,
    )
    return {
        "entry": entry_payload(session, entry),
        "player": _player_payload(session, player_id, merchant_id),
    }


def void_bonus(
    session: Session,
    actor: Actor,
    entry_id: int,
    note: str = "",
) -> dict:
    """撤销一笔误加的赠金：写一条反向 bonus_void 流水，只回退赠金、不碰现金。

    只允许撤销尚未被茶水消耗、且从未被撤销过的加赠金流水，避免赠金凭空变负或重复扣减。
    """
    merchant_id = actor.merchant_id
    entry = session.get(LedgerEntry, int(entry_id))
    if entry is None or int(entry.merchant_id) != merchant_id:
        raise NotFoundError("找不到这笔流水")
    if entry.reason != "add_bonus":
        raise AppError("只能撤销「加赠金」流水")
    amount_cents = int(entry.amount_cents)

    already = session.scalar(
        select(LedgerEntry.id).where(
            LedgerEntry.merchant_id == merchant_id,
            LedgerEntry.reason == "bonus_void",
            LedgerEntry.reverses_ledger_id == entry.id,
        )
    )
    if already is not None:
        raise AppError("这笔加赠金已经撤销过了")

    player = get_player(session, entry.player_id, merchant_id)
    if int(player.bonus_cents) < amount_cents:
        raise AppError(
            f"该笔赠金已被茶水消耗，当前赠金只剩 ¥{format_yuan(player.bonus_cents)}，"
            "无法撤销；请改为正常加押金"
        )

    clean = clean_text(note, "备注", 200) or "撤销误加的赠金"
    cash, cash_again, bonus_before, bonus_after = apply_bonus_delta(
        session, entry.player_id, -amount_cents, merchant_id=merchant_id
    )
    void_entry = _write_entry(
        session,
        actor=actor,
        player_id=entry.player_id,
        reason="bonus_void",
        amount_cents=amount_cents,
        deposit_before=cash,
        deposit_after=cash_again,
        bonus_before=bonus_before,
        bonus_after=bonus_after,
        batch_id=current_batch_id(session, merchant_id),
        reverses_ledger_id=entry.id,
        note=clean,
    )
    return {
        "entry": entry_payload(session, void_entry),
        "player": _player_payload(session, entry.player_id, merchant_id),
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
    player = get_player(session, player_id, merchant_id)
    if int(player.bonus_cents) > 0:
        raise AppError(
            f"该玩家还有赠金 ¥{format_yuan(player.bonus_cents)}，赠金不能退；"
            "请先用赠金扣茶水，赠金为 0 后再退押金"
        )
    if int(amount_cents) > int(player.deposit_cents):
        raise AppError("押金不足，不能退这么多")
    clean = clean_text(note, "备注", 200)
    cash_before, cash_after, bonus_before, bonus_after = apply_cash_delta(
        session, player_id, -int(amount_cents), merchant_id=merchant_id
    )
    entry = _write_entry(
        session,
        actor=actor,
        player_id=player_id,
        reason="refund",
        amount_cents=amount_cents,
        deposit_before=cash_before,
        deposit_after=cash_after,
        bonus_before=bonus_before,
        bonus_after=bonus_after,
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
    source_player = get_player(session, from_player_id, merchant_id)
    get_player(session, to_player_id, merchant_id)
    if (
        int(source_player.bonus_cents) > 0
        and int(amount_cents) > int(source_player.deposit_cents)
    ):
        raise AppError(
            f"赠金不能划转，最多可划现金押金 ¥{format_yuan(source_player.deposit_cents)}"
        )
    clean = clean_text(note, "备注", 200)

    group = uuid4().hex
    batch_id = current_batch_id(session, merchant_id)
    source_before, source_after, source_bonus_before, source_bonus_after = apply_cash_delta(
        session, from_player_id, -int(amount_cents), merchant_id=merchant_id
    )
    target_before, target_after, target_bonus_before, target_bonus_after = apply_cash_delta(
        session, to_player_id, int(amount_cents), merchant_id=merchant_id
    )

    out_entry = _write_entry(
        session,
        actor=actor,
        player_id=from_player_id,
        reason="transfer_out",
        amount_cents=amount_cents,
        deposit_before=source_before,
        deposit_after=source_after,
        bonus_before=source_bonus_before,
        bonus_after=source_bonus_after,
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
        deposit_before=target_before,
        deposit_after=target_after,
        bonus_before=target_bonus_before,
        bonus_after=target_bonus_after,
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
