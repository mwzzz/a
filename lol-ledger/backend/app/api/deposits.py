"""押金操作接口：加、退、划。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import Actor, get_current_user, get_write_db
from app.schemas import AmountIn, BonusVoidIn, TransferIn
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


@router.post("/players/{player_id}/bonus", status_code=201)
def add_bonus(
    player_id: int,
    payload: AmountIn,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return deposit_service.add_bonus(
        session, actor, player_id, payload.amount_cents, payload.note
    )


@router.post("/ledger/entries/{entry_id}/void-bonus", status_code=201)
def void_bonus(
    entry_id: int,
    payload: BonusVoidIn,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return deposit_service.void_bonus(session, actor, entry_id, payload.note)


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
