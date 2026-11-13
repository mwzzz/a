"""操作人汇总接口：按日期区间统计每位店员的经营动作。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import Actor, get_current_user, get_read_db
from app.services import summary as summary_service

router = APIRouter(prefix="/summary", tags=["操作人汇总"])


@router.get("/operators")
def operator_summary(
    date_from: str | None = Query(
        default=None, max_length=25, description="YYYY-MM-DD 或 YYYY-MM-DDTHH:MM"
    ),
    date_to: str | None = Query(default=None, max_length=25),
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return summary_service.operator_summary(
        session, actor.merchant_id, date_from, date_to
    )
