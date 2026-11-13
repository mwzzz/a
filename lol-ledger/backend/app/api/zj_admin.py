"""平台侧：查战绩账号与配额管理。仅开发者账号（超管）可用。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Query
from sqlalchemy.orm import Session

from app.deps import Actor, get_read_db, get_write_db, require_superadmin
from app.schemas import (
    PasswordResetIn,
    ZjQuotaGrantIn,
    ZjUserCreateIn,
    ZjUserUpdateIn,
)
from app.services import zjquota, zjuers

router = APIRouter(prefix="/platform/zj", tags=["查战绩配额"])


@router.get("/users")
def list_users(
    _: Actor = Depends(require_superadmin),
    session: Session = Depends(get_read_db),
) -> dict:
    users = zjuers.list_users(session)
    return {
        "overview": zjquota.overview(session),
        "users": [zjuers.admin_row(user) for user in users],
    }


@router.post("/users", status_code=201)
def create_user(
    payload: ZjUserCreateIn,
    _: Actor = Depends(require_superadmin),
    session: Session = Depends(get_write_db),
) -> dict:
    user = zjuers.create_user(
        session,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        note=payload.note,
        quota_total=payload.quota_total,
    )
    return zjuers.admin_row(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: ZjUserUpdateIn,
    _: Actor = Depends(require_superadmin),
    session: Session = Depends(get_write_db),
) -> dict:
    user = zjuers.update_user(
        session,
        user_id,
        display_name=payload.display_name,
        note=payload.note,
        is_active=payload.is_active,
    )
    return zjuers.admin_row(user)


@router.post("/users/{user_id}/quota")
def grant_quota(
    user_id: int,
    payload: ZjQuotaGrantIn,
    actor: Actor = Depends(require_superadmin),
    session: Session = Depends(get_write_db),
) -> dict:
    user = zjquota.grant_quota(
        session,
        user_id=user_id,
        delta=payload.delta,
        operator_id=actor.id,
        note=payload.note,
    )
    return {"user": zjuers.admin_row(user), "overview": zjquota.overview(session)}


@router.post("/users/{user_id}/password", status_code=204)
def reset_password(
    user_id: int,
    payload: PasswordResetIn,
    _: Actor = Depends(require_superadmin),
    session: Session = Depends(get_write_db),
) -> None:
    zjuers.reset_password(session, user_id, payload.new_password)


@router.get("/users/{user_id}/logs")
def user_logs(
    user_id: int,
    limit: int = Query(default=50, ge=1, le=200),
    offset: int = Query(default=0, ge=0),
    _: Actor = Depends(require_superadmin),
    session: Session = Depends(get_read_db),
) -> dict:
    return zjquota.recent_logs(session, user_id, limit=limit, offset=offset)
