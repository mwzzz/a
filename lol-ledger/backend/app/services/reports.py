"""总览：顶部数字、今日统计、当前批次、最近流水。全部限定在当前商家。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import GameSession, LedgerEntry, Player
from app.services.batches import batch_row, get_open_batch
from app.services.options import thresholds
from app.services.records import list_deposit_records
from app.timeutil import today_bounds


def _today_stats(session: Session, merchant_id: int) -> dict:
    start, end = today_bounds()
    rows = session.execute(
        select(
            LedgerEntry.reason,
            func.coalesce(func.sum(LedgerEntry.amount_cents), 0),
            func.count(),
        )
        .where(
            LedgerEntry.merchant_id == merchant_id,
            LedgerEntry.created_at >= start,
            LedgerEntry.created_at < end,
        )
        .group_by(LedgerEntry.reason)
    ).all()
    totals = {reason: (int(total or 0), int(count or 0)) for reason, total, count in rows}

    session_count = int(
        session.scalar(
            select(func.count())
            .select_from(GameSession)
            .where(
                GameSession.merchant_id == merchant_id,
                GameSession.played_at >= start,
                GameSession.played_at < end,
            )
        )
        or 0
    )
    player_times = int(
        session.scalar(
            select(func.coalesce(func.sum(GameSession.player_count), 0)).where(
                GameSession.merchant_id == merchant_id,
                GameSession.played_at >= start,
                GameSession.played_at < end,
            )
        )
        or 0
    )
    return {
        "session_count": session_count,
        "player_times": player_times,
        "tea_total_cents": totals.get("normal_deduct", (0, 0))[0],
        "add_total_cents": totals.get("add_deposit", (0, 0))[0],
        "refund_total_cents": totals.get("refund", (0, 0))[0],
        "deduct_total_cents": totals.get("manual_deduct", (0, 0))[0],
        "transfer_count": totals.get("transfer_out", (0, 0))[1],
        "transfer_total_cents": totals.get("transfer_out", (0, 0))[0],
    }


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
                Player.deposit_cents < low,
            )
        )
        or 0
    )

    batch = get_open_batch(session, merchant_id)
    batch_payload = None
    if batch is not None:
        batch_payload = {
            "id": batch.id,
            "label": batch.label,
            "opened_at": batch.opened_at,
            "summary": batch_row(session, batch, [])["summary"],
        }

    recent = list_deposit_records(session, merchant_id=merchant_id, page=1, page_size=10)
    return {
        "total_deposit_cents": total_deposit,
        "player_count": player_count,
        "low_deposit_count": low_count,
        "deposit_low_cents": low,
        "deposit_high_cents": high,
        "today": _today_stats(session, merchant_id),
        "open_batch": batch_payload,
        "recent_records": recent["items"],
    }
