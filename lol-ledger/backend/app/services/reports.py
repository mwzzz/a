"""总览：押金、玩家数、今日经营汇总、最近流水。全部限定在当前商家。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Player
from app.services import options
from app.services.options import thresholds
from app.services.records import list_deposit_records
from app.services.summary import operator_summary


def overview(session: Session, merchant_id: int) -> dict:
    low, high = thresholds(session, merchant_id)
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
    player_count = int(
        session.scalar(
            select(func.count())
            .select_from(Player)
            .where(
                Player.merchant_id == merchant_id,
                Player.deleted_at.is_(None),
            )
        )
        or 0
    )
    low_count = int(
        session.scalar(
            select(func.count())
            .select_from(Player)
            .where(
                Player.merchant_id == merchant_id,
                Player.deleted_at.is_(None),
                (Player.deposit_cents + Player.bonus_cents) < low,
            )
        )
        or 0
    )

    today = operator_summary(session, merchant_id)
    recent = list_deposit_records(session, merchant_id=merchant_id, page=1, page_size=10)

    return {
        "date": today["date_from"],
        "total_deposit_cents": total_deposit,
        "total_bonus_cents": total_bonus,
        "player_count": player_count,
        "low_deposit_count": low_count,
        "deposit_low_cents": low,
        "deposit_high_cents": high,
        "dividend_mode": options.dividend_mode(session, merchant_id),
        "dividend_rate_percent": options.dividend_rate(session, merchant_id),
        "dividend_fixed_cents": options.dividend_fixed_cents(session, merchant_id),
        "today": today["totals"],
        "today_operators": today["rows"],
        "recent_records": recent["items"],
    }
