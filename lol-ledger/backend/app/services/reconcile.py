"""对账：一个商家的现金押金与赠金两条恒等式必须始终成立。

现金：players.deposit_cents = 现金流水净额 = 末条 deposit_after_cents
赠金：players.bonus_cents   = 赠金流水净额 = 末条 bonus_after_cents
总额：players.deposit_cents + players.bonus_cents = 末条 balance_after_cents
"""

from __future__ import annotations

from sqlalchemy import case, func, select
from sqlalchemy.orm import Session

from app.models import LedgerEntry, Player
from app.services.money import INCOMING_REASONS


def reconcile(session: Session, merchant_id: int) -> dict:
    cash_incoming = tuple(reason for reason in INCOMING_REASONS if reason != "add_bonus")
    cash_signed = case(
        (LedgerEntry.reason == "add_bonus", 0),
        (
            LedgerEntry.reason.in_(cash_incoming),
            LedgerEntry.amount_cents - LedgerEntry.bonus_amount_cents,
        ),
        else_=-(LedgerEntry.amount_cents - LedgerEntry.bonus_amount_cents),
    )
    bonus_signed = case(
        (LedgerEntry.reason == "add_bonus", LedgerEntry.bonus_amount_cents),
        (LedgerEntry.reason == "normal_deduct", -LedgerEntry.bonus_amount_cents),
        else_=0,
    )

    rows = session.execute(
        select(
            Player.id,
            Player.game_id,
            Player.deposit_cents,
            Player.bonus_cents,
            func.coalesce(func.sum(cash_signed), 0).label("cash_sum"),
            func.coalesce(func.sum(bonus_signed), 0).label("bonus_sum"),
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
        stored_bonus = int(row.bonus_cents)
        cash_sum = int(row.cash_sum or 0)
        bonus_sum = int(row.bonus_sum or 0)
        last = session.execute(
            select(
                LedgerEntry.deposit_after_cents,
                LedgerEntry.bonus_after_cents,
            )
            .where(
                LedgerEntry.merchant_id == merchant_id,
                LedgerEntry.player_id == row.id,
            )
            .order_by(LedgerEntry.id.desc())
            .limit(1)
        ).one_or_none()
        last_cash = int(last[0]) if last is not None else 0
        last_bonus = int(last[1]) if last is not None else 0
        if (
            stored != cash_sum
            or stored != last_cash
            or stored_bonus != bonus_sum
            or stored_bonus != last_bonus
        ):
            problems.append(
                {
                    "player_id": row.id,
                    "game_id": row.game_id,
                    "stored_cents": stored,
                    "ledger_sum_cents": cash_sum,
                    "last_balance_cents": last_cash,
                    "stored_bonus_cents": stored_bonus,
                    "ledger_bonus_sum_cents": bonus_sum,
                    "last_bonus_cents": last_bonus,
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
    total_bonus = int(
        session.scalar(
            select(func.coalesce(func.sum(Player.bonus_cents), 0)).where(
                Player.merchant_id == merchant_id,
                Player.deleted_at.is_(None),
            )
        )
        or 0
    )
    total_cash_ledger = int(
        session.scalar(
            select(func.coalesce(func.sum(cash_signed), 0)).where(
                LedgerEntry.merchant_id == merchant_id
            )
        )
        or 0
    )
    total_bonus_ledger = int(
        session.scalar(
            select(func.coalesce(func.sum(bonus_signed), 0)).where(
                LedgerEntry.merchant_id == merchant_id
            )
        )
        or 0
    )
    total_ledger = total_cash_ledger + total_bonus_ledger

    return {
        "ok": (
            not problems
            and total_deposit == total_cash_ledger
            and total_bonus == total_bonus_ledger
        ),
        "checked": len(rows),
        "total_deposit_cents": total_deposit,
        "total_bonus_cents": total_bonus,
        "total_ledger_cents": total_ledger,
        "total_cash_ledger_cents": total_cash_ledger,
        "total_bonus_ledger_cents": total_bonus_ledger,
        "problems": problems,
    }
