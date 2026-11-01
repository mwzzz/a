"""场次接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import Actor, client_ip, get_current_user, get_read_db, get_write_db
from app.schemas import SessionCreateIn, SessionPreviewIn
from app.services import sessions as session_service

router = APIRouter(prefix="/sessions", tags=["场次"])


@router.get("")
def list_sessions(
    batch_id: int | None = None,
    keyword: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 20,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return session_service.list_sessions(
        session,
        actor.merchant_id,
        batch_id=batch_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


@router.post("/preview")
def preview(
    payload: SessionPreviewIn,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return session_service.preview_session(
        session, actor.merchant_id, payload.player_ids, payload.tea_fee_cents
    )


@router.get("/{session_id}")
def get_session(
    session_id: int,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return session_service.get_session_detail(
        session, session_id, actor.merchant_id
    )


@router.post("", status_code=201)
def create_session(
    payload: SessionCreateIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return session_service.open_session(
        session,
        actor,
        batch_id=payload.batch_id,
        name=payload.name,
        played_at=payload.played_at,
        note=payload.note,
        tea_fee_cents=payload.tea_fee_cents,
        player_ids=payload.player_ids,
        ip=client_ip(request),
    )
