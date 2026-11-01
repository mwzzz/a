"""对账：一个商家的三条恒等式必须始终成立。

单独成模块，避免 batches ↔ records ↔ reports 之间循环依赖。
只校验本商家，别家的脏数据不应该卡住这家交班。
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import LedgerEntry, Player
from app.services.money import INCOMING_REASONS


def reconcile(session: Session, merchant_id: int) -> dict:
    incoming = tuple(INCOMING_REASONS)
    signed = case(
        (LedgerEntry.reason.in_(incoming), LedgerEntry.amount_cents),
        else_=-LedgerEntry.amount_cents,
    )
    rows = session.execute(
        select(
            Player.id,
            Player.game_id,
            Player.deposit_cents,
            func.coalesce(func.sum(signed), 0).label("ledger_sum"),
        )
        .outerjoin(
            LedgerEntry,
            (LedgerEntry.player_id == Player.id)
            & (LedgerEntry.merchant_id == merchant_id),
        )
        .where(
            Player.merchant_id == merchant_id,
            Player.deleted_at.is_(None),
        )
        .group_by(Player.id)
    ).all()

    problems: list[dict] = []
    for row in rows:
        stored = int(row.deposit_cents)
        ledger_sum = int(row.ledger_sum or 0)
        last_balance = session.scalar(
            select(LedgerEntry.balance_after_cents)
            .where(
                LedgerEntry.merchant_id == merchant_id,
                LedgerEntry.player_id == row.id,
            )
            .order_by(LedgerEntry.id.desc())
            .limit(1)
        )
        last_balance = int(last_balance) if last_balance is not None else 0
        if stored != ledger_sum or stored != last_balance:
            problems.append(
                {
                    "player_id": row.id,
                    "game_id": row.game_id,
                    "stored_cents": stored,
                    "ledger_sum_cents": ledger_sum,
                    "last_balance_cents": last_balance,
                }
            )

    total_deposit = int(
        session.scalar(
            select(func.coalesce(func.sum(Player.deposit_cents), 0)).where(
                Player.merchant_id == merchant_id,
                Player.deleted_at.is_(None),
            )
        )
        or 0
    )
    total_ledger = int(
        session.scalar(
            select(func.coalesce(func.sum(signed), 0)).where(
                LedgerEntry.merchant_id == merchant_id
            )
        )
        or 0
    )

    return {
        "ok": not problems and total_deposit == total_ledger,
        "checked": len(rows),
        "total_deposit_cents": total_deposit,
        "total_ledger_cents": total_ledger,
        "problems": problems,
    }
