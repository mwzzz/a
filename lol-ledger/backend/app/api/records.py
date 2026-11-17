"""记录接口：押金记录、场次记录、划转配对。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import Actor, get_current_user, get_read_db
from app.services.records import (
    list_deposit_records,
    list_operator_options,
    list_session_records,
    operator_cash_summary,
    transfer_group,
)

router = APIRouter(prefix="/records", tags=["记录"])


@router.get("/deposits")
def deposit_records(
    keyword: str = "",
    player_id: int | None = None,
    batch_id: int | None = None,
    session_id: int | None = None,
    operator_id: int | None = None,
    reason: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str = "created_at_desc",
    page: int = 1,
    page_size: int = 20,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return list_deposit_records(
        session,
        actor.merchant_id,
        keyword=keyword,
        player_id=player_id,
        batch_id=batch_id,
        session_id=session_id,
        operator_id=operator_id,
        reason=reason,
        date_from=date_from,
        date_to=date_to,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/sessions")
def session_records(
    keyword: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    operator_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return list_session_records(
        session,
        actor.merchant_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        operator_id=operator_id,
        page=page,
        page_size=page_size,
    )


@router.get("/operators")
def operator_options(
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> list[dict]:
    return list_operator_options(session, actor.merchant_id)


@router.get("/operator-summary")
def operator_summary(
    operator_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return operator_cash_summary(
        session,
        actor.merchant_id,
        operator_id=operator_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.get("/transfers/{group_id}")
def transfer_detail(
    group_id: str,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return transfer_group(session, group_id, actor.merchant_id)
