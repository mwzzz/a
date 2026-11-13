"""开发者控制台接口。所有路由都要求开发者账号（is_superadmin）。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import Actor, client_ip, get_read_db, get_write_db, require_superadmin
from app.schemas import (
    MerchantCreateIn,
    MerchantPurgeIn,
    MerchantUpdateIn,
    PasswordResetIn,
    UserCreateIn,
    UserUpdateIn,
)
from app.services import platform as platform_service
from app.services.users import user_row

router = APIRouter(prefix="/platform", tags=["平台"])


@router.get("/merchants")
def list_merchants(
    actor: Actor = Depends(require_superadmin),
    session: Session = Depends(get_read_db),
) -> list[dict]:
    return [
        platform_service.merchant_row(session, merchant)
        for merchant in platform_service.list_merchants(session, actor)
    ]


@router.post("/merchants", status_code=201)
def create_merchant(
    payload: MerchantCreateIn,
    request: Request,
    actor: Actor = Depends(require_superadmin),
    session: Session = Depends(get_write_db),
) -> dict:
    merchant, admin = platform_service.create_merchant(
        session,
        actor,
        name=payload.name,
        note=payload.note,
        admin_username=payload.admin_username,
        admin_password=payload.admin_password,
        admin_display_name=payload.admin_display_name,
        ip=client_ip(request),
    )
    return {
        "merchant": platform_service.merchant_row(session, merchant),
        "admin": user_row(admin) if admin is not None else None,
    }


@router.patch("/merchants/{merchant_id}")
def update_merchant(
    merchant_id: int,
    payload: MerchantUpdateIn,
    request: Request,
    actor: Actor = Depends(require_superadmin),
    session: Session = Depends(get_write_db),
) -> dict:
    merchant = platform_service.update_merchant(
        session,
        actor,
        merchant_id,
        name=payload.name,
        note=payload.note,
        status=payload.status,
        ip=client_ip(request),
    )
    return platform_service.merchant_row(session, merchant)


@router.get("/merchants/{merchant_id}/purge-preview")
def purge_preview(
    merchant_id: int,
    actor: Actor = Depends(require_superadmin),
    session: Session = Depends(get_read_db),
) -> dict:
    """清空前预览：将删除多少数据、保留什么。只读。"""
    return platform_service.purge_preview(session, actor, merchant_id)


@router.post("/merchants/{merchant_id}/purge")
def purge_merchant_data(
    merchant_id: int,
    payload: MerchantPurgeIn,
    request: Request,
    actor: Actor = Depends(require_superadmin),
    session: Session = Depends(get_write_db),
) -> dict:
    """清空该商家的玩家、班次、场次、流水、交接与分红结算（不可恢复）。"""
    return platform_service.purge_merchant_data(
        session,
        actor,
        merchant_id,
        confirm_name=payload.confirm_name,
        note=payload.note,
        ip=client_ip(request),
    )


@router.get("/merchants/{merchant_id}/users")
def list_merchant_users(
    merchant_id: int,
    actor: Actor = Depends(require_superadmin),
    session: Session = Depends(get_read_db),
) -> list[dict]:
    return [
        user_row(user)
        for user in platform_service.list_users(session, actor, merchant_id)
    ]


@router.post("/merchants/{merchant_id}/users", status_code=201)
def create_merchant_user(
    merchant_id: int,
    payload: UserCreateIn,
    request: Request,
    actor: Actor = Depends(require_superadmin),
    session: Session = Depends(get_write_db),
) -> dict:
    user = platform_service.create_user(
        session,
        actor,
        merchant_id,
        username=payload.username,
        password=payload.password,
        display_name=payload.display_name,
        role=payload.role,
        ip=client_ip(request),
    )
    return user_row(user)


@router.patch("/users/{user_id}")
def update_user(
    user_id: int,
    payload: UserUpdateIn,
    request: Request,
    actor: Actor = Depends(require_superadmin),
    session: Session = Depends(get_write_db),
) -> dict:
    user = platform_service.update_user(
        session,
        actor,
        user_id,
        display_name=payload.display_name,
        role=payload.role,
        is_active=payload.is_active,
        ip=client_ip(request),
    )
    return user_row(user)


@router.post("/users/{user_id}/password", status_code=204)
def reset_user_password(
    user_id: int,
    payload: PasswordResetIn,
    request: Request,
    actor: Actor = Depends(require_superadmin),
    session: Session = Depends(get_write_db),
) -> None:
    platform_service.reset_password(
        session, actor, user_id, payload.new_password, client_ip(request)
    )
