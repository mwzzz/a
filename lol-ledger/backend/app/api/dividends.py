"""分红结算接口，仅管理员。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import Actor, client_ip, get_read_db, get_write_db, require_admin
from app.schemas import DividendSettleIn, DividendVoidIn
from app.services import dividends as dividend_service

router = APIRouter(prefix="/reports/dividends", tags=["分红结算"])


@router.get("/preview")
def dividend_preview(
    date_from: str | None = None,
    date_to: str | None = None,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_read_db),
) -> dict:
    return dividend_service.preview(
        session,
        actor.merchant_id,
        date_from=date_from,
        date_to=date_to,
    )


@router.post("/settle", status_code=201)
def settle_dividend(
    payload: DividendSettleIn,
    request: Request,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> list[dict]:
    return dividend_service.settle(
        session,
        actor,
        user_ids=payload.user_ids,
        date_from=payload.date_from,
        date_to=payload.date_to,
        note=payload.note,
        ip=client_ip(request),
    )


@router.get("/settlements")
def settlement_list(
    page: int = 1,
    page_size: int = 20,
    status: str = "all",
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_read_db),
) -> dict:
    return dividend_service.list_settlements(
        session,
        actor.merchant_id,
        page=page,
        page_size=page_size,
        status=status,
    )


@router.post("/settlements/{settlement_id}/void")
def void_settlement(
    settlement_id: int,
    payload: DividendVoidIn,
    request: Request,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> dict:
    return dividend_service.void_settlement(
        session,
        actor,
        settlement_id,
        note=payload.note,
        ip=client_ip(request),
    )
