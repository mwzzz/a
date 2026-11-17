"""设置接口。读所有人可看，写仅管理员，作用域都是当前商家。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.deps import Actor, client_ip, get_current_user, get_read_db, get_write_db, require_admin
from app.schemas import RechargeCampaignIn, SettingsUpdateIn
from app.services import campaigns as campaign_service
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
        dividend_rate_percent=payload.dividend_rate_percent,
        dividend_mode=payload.dividend_mode,
        dividend_fixed_cents=payload.dividend_fixed_cents,
        shop_name=payload.shop_name,
        ip=client_ip(request),
    )


@router.get("/recharge-campaigns")
def list_recharge_campaigns(
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> list[dict]:
    return campaign_service.list_campaigns(session, actor.merchant_id)


@router.post("/recharge-campaigns", status_code=201)
def create_recharge_campaign(
    payload: RechargeCampaignIn,
    request: Request,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> dict:
    return campaign_service.create_campaign(
        session,
        actor,
        threshold_cents=payload.threshold_cents,
        bonus_cents=payload.bonus_cents,
        ip=client_ip(request),
    )


@router.patch("/recharge-campaigns/{campaign_id}")
def update_recharge_campaign(
    campaign_id: int,
    payload: RechargeCampaignIn,
    request: Request,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> dict:
    return campaign_service.update_campaign(
        session,
        actor,
        campaign_id,
        threshold_cents=payload.threshold_cents,
        bonus_cents=payload.bonus_cents,
        ip=client_ip(request),
    )


@router.delete("/recharge-campaigns/{campaign_id}", status_code=204)
def delete_recharge_campaign(
    campaign_id: int,
    request: Request,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
):
    campaign_service.delete_campaign(
        session, actor, campaign_id, ip=client_ip(request)
    )
    return Response(status_code=204)
