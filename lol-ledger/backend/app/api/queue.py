"""排队登记接口（小工具 → 排队登记）。店员和管理员都能用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query, Request
from sqlalchemy.orm import Session

from app.deps import Actor, client_ip, get_current_user, get_read_db, get_write_db
from app.schemas import QueueCreateIn, QueueStatusIn
from app.services import queue as queue_service

router = APIRouter(prefix="/queue", tags=["排队登记"])


@router.get("")
def list_queue(
    day: str | None = Query(default=None, max_length=10, description="YYYY-MM-DD，默认今天"),
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return queue_service.queue_today(session, actor.merchant_id, day)


@router.get("/snapshot")
def queue_snapshot(
    day: str | None = Query(default=None, max_length=10),
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    """生成阵容图用的数据：店名 + 当天队列 + 更新时间。"""
    return queue_service.queue_today(session, actor.merchant_id, day)


@router.post("", status_code=201)
def create_queue_entry(
    payload: QueueCreateIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return queue_service.create_entry(
        session,
        actor,
        game_id=payload.game_id,
        note=payload.note,
        ip=client_ip(request),
    )


@router.patch("/{entry_id}")
def update_queue_status(
    entry_id: int,
    payload: QueueStatusIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return queue_service.update_status(
        session,
        actor,
        entry_id,
        payload.status,
        ip=client_ip(request),
    )
