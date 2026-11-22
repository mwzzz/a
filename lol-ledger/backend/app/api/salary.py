"""发工资接口：预览、绑定工资账户、批量发放、整批撤销。全部仅门店管理员可用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import Actor, get_read_db, get_write_db, require_admin
from app.schemas import SalaryBindIn, SalaryPayIn, SalaryVoidIn
from app.services import salary as salary_service

router = APIRouter(prefix="/salary", tags=["发工资"])


@router.get("/preview")
def preview(
    date_from: str | None = Query(default=None, max_length=25),
    date_to: str | None = Query(default=None, max_length=25),
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_read_db),
) -> dict:
    return salary_service.preview(session, actor.merchant_id, date_from, date_to)


@router.get("/next-window")
def next_window(
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_read_db),
) -> dict:
    return salary_service.next_window(session, actor.merchant_id)


@router.post("/bind")
def bind(
    payload: SalaryBindIn,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> dict:
    return salary_service.bind(session, actor, payload.user_id, payload.player_id)


@router.post("/pay", status_code=201)
def pay(
    payload: SalaryPayIn,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> dict:
    return salary_service.pay(
        session, actor, payload.date_from, payload.date_to, payload.user_ids, payload.note
    )


@router.post("/void", status_code=201)
def void(
    payload: SalaryVoidIn,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> dict:
    return salary_service.void_batch(session, actor, payload.batch_id, payload.note)
