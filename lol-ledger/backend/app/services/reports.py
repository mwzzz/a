"""总览：押金、本班统计、在库现金与保管人、最近流水。全部限定在当前商家。"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.models import Player
from app.services import custody
from app.services.batches import batch_row, get_open_batch
from app.services.options import thresholds
from app.services.records import list_deposit_records


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
        row = batch_row(session, batch, [])
        batch_payload = {
            "id": batch.id,
            "label": batch.label,
            "opened_at": batch.opened_at,
            "summary": row["summary"],
            "dividend_rate_percent": row["dividend_rate_percent"],
            "operators": row["operators"],
        }

    recent = list_deposit_records(session, merchant_id=merchant_id, page=1, page_size=10)
    return {
        "total_deposit_cents": total_deposit,
        "player_count": player_count,
        "low_deposit_count": low_count,
        "deposit_low_cents": low,
        "deposit_high_cents": high,
        "custody": custody.current(session, merchant_id),
        "open_batch": batch_payload,
        "recent_records": recent["items"],
    }
