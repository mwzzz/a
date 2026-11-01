"""押金操作接口：加、退、扣、划。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import Actor, get_current_user, get_write_db
from app.schemas import AmountIn, TransferIn
from app.services import deposits as deposit_service

router = APIRouter(tags=["押金"])


@router.post("/players/{player_id}/deposits", status_code=201)
def add_deposit(
    player_id: int,
    payload: AmountIn,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return deposit_service.add_deposit(
        session, actor, player_id, payload.amount_cents, payload.note
    )


@router.post("/players/{player_id}/refunds", status_code=201)
def refund(
    player_id: int,
    payload: AmountIn,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return deposit_service.refund(
        session, actor, player_id, payload.amount_cents, payload.note
    )


@router.post("/players/{player_id}/deductions", status_code=201)
def deduct(
    player_id: int,
    payload: AmountIn,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return deposit_service.manual_deduct(
        session, actor, player_id, payload.amount_cents, payload.note
    )


@router.post("/transfers", status_code=201)
def transfer(
    payload: TransferIn,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return deposit_service.transfer(
        session,
        actor,
        payload.from_player_id,
        payload.to_player_id,
        payload.amount_cents,
        payload.note,
    )
