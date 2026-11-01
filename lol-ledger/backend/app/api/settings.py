"""设置接口。读所有人可看，写仅管理员，作用域都是当前商家。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import Actor, client_ip, get_current_user, get_read_db, get_write_db, require_admin
from app.schemas import SettingsUpdateIn
from app.services import options

router = APIRouter(prefix="/settings", tags=["设置"])


@router.get("")
def read_settings(
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return options.snapshot(session, actor.merchant_id)


@router.patch("")
def update_settings(
    payload: SettingsUpdateIn,
    request: Request,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> dict:
    return options.update(
        session,
        actor,
        last_tea_cents=payload.last_tea_cents,
        deposit_low_cents=payload.deposit_low_cents,
        deposit_high_cents=payload.deposit_high_cents,
        shop_name=payload.shop_name,
        ip=client_ip(request),
    )
