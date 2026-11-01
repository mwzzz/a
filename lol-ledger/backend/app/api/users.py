"""账号管理，仅管理员。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import Actor, client_ip, get_write_db, require_admin
from app.schemas import PasswordResetIn, UserCreateIn, UserUpdateIn
from app.services import users as user_service

router = APIRouter(prefix="/users", tags=["账号"])


@router.get("")
def list_users(
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> list[dict]:
    return [
        user_service.user_row(user)
        for user in user_service.list_users(session, actor.merchant_id)
    ]


@router.post("", status_code=201)
def create_user(
    payload: UserCreateIn,
    request: Request,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> dict:
    user = user_service.create_user(
        session,
        actor,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        role=payload.role,
        ip=client_ip(request),
    )
    return user_service.user_row(user)


@router.patch("/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdateIn,
    request: Request,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> dict:
    user = user_service.update_user(
        session,
        actor,
        user_id,
        display_name=payload.display_name,
        role=payload.role,
        is_active=payload.is_active,
        ip=client_ip(request),
    )
    return user_service.user_row(user)


@router.post("/{user_id}/password", status_code=204)
def reset_password(
    user_id: int,
    payload: PasswordResetIn,
    request: Request,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> None:
    user_service.reset_password(
        session, actor, user_id, payload.new_password, client_ip(request)
    )
