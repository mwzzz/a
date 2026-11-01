"""登录、当前用户、改密、登出。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import Actor, client_ip, get_current_user, get_write_db
from app.schemas import ChangePasswordIn, LoginIn
from app.security import create_access_token
from app.services import users as user_service
from app.services.audit import write_audit

router = APIRouter(prefix="/auth", tags=["认证"])


@router.post("/login")
def login(
    payload: LoginIn,
    request: Request,
    session: Session = Depends(get_write_db),
) -> dict:
    user = user_service.authenticate(session, payload.username, payload.password, client_ip(request))
    merchant = user_service.active_merchant(session, user.merchant_id)
    token, expires_in = create_access_token(user.id, user.role, user.password_hash)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": user_service.user_row(user, merchant),
    }


@router.get("/me")
def me(actor: Actor = Depends(get_current_user)) -> dict:
    return {
        "id": actor.id,
        "username": actor.username,
        "display_name": actor.name,
        "role": actor.role,
        "is_admin": actor.is_admin,
        "merchant_id": actor.merchant_id,
        "merchant": {"id": actor.merchant_id, "name": actor.merchant_name},
    }


@router.post("/password", status_code=204)
def change_password(
    payload: ChangePasswordIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> None:
    user_service.change_own_password(
        session, actor, payload.old_password, payload.new_password, client_ip(request)
    )


@router.post("/logout", status_code=204)
def logout(
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> None:
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="logout",
        target_type="user",
        target_id=actor.id,
        detail="退出登录",
        ip=client_ip(request),
    )
