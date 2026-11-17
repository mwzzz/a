"""充值活动档位：满额送赠金，每笔充值取满足条件的最高档一次。"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError, NotFoundError
from app.models import RechargeCampaign
from app.services.audit import write_audit
from app.timeutil import now_text


def campaign_row(campaign: RechargeCampaign) -> dict:
    return {
        "id": campaign.id,
        "threshold_cents": int(campaign.threshold_cents),
        "bonus_cents": int(campaign.bonus_cents),
        "created_at": campaign.created_at,
        "updated_at": campaign.updated_at,
    }


def list_campaigns(session: Session, merchant_id: int) -> list[dict]:
    rows = session.scalars(
        select(RechargeCampaign)
        .where(RechargeCampaign.merchant_id == merchant_id)
        .order_by(RechargeCampaign.threshold_cents.asc(), RechargeCampaign.id.asc())
    )
    return [campaign_row(row) for row in rows]


def get_campaign(session: Session, merchant_id: int, campaign_id: int) -> RechargeCampaign:
    campaign = session.scalar(
        select(RechargeCampaign).where(
            RechargeCampaign.id == int(campaign_id),
            RechargeCampaign.merchant_id == merchant_id,
        )
    )
    if campaign is None:
        raise NotFoundError("找不到这个充值档位")
    return campaign


def best_for_amount(
    session: Session, merchant_id: int, amount_cents: int
) -> RechargeCampaign | None:
    if amount_cents <= 0:
        return None
    return session.scalar(
        select(RechargeCampaign)
        .where(
            RechargeCampaign.merchant_id == merchant_id,
            RechargeCampaign.threshold_cents <= int(amount_cents),
        )
        .order_by(RechargeCampaign.threshold_cents.desc(), RechargeCampaign.id.desc())
        .limit(1)
    )


def _validate(threshold_cents: int, bonus_cents: int) -> None:
    if int(threshold_cents) <= 0:
        raise AppError("充值档位金额必须大于 0")
    if int(bonus_cents) <= 0:
        raise AppError("赠送赠金必须大于 0")


def _check_threshold(
    session: Session, merchant_id: int, threshold_cents: int, exclude_id: int | None = None
) -> None:
    stmt = select(RechargeCampaign.id).where(
        RechargeCampaign.merchant_id == merchant_id,
        RechargeCampaign.threshold_cents == int(threshold_cents),
    )
    if exclude_id is not None:
        stmt = stmt.where(RechargeCampaign.id != int(exclude_id))
    if session.scalar(stmt) is not None:
        raise AppError("这个充值档位已经存在")


def create_campaign(
    session: Session,
    actor: Actor,
    *,
    threshold_cents: int,
    bonus_cents: int,
    ip: str = "",
) -> dict:
    _validate(threshold_cents, bonus_cents)
    _check_threshold(session, actor.merchant_id, threshold_cents)
    stamp = now_text()
    campaign = RechargeCampaign(
        merchant_id=actor.merchant_id,
        threshold_cents=int(threshold_cents),
        bonus_cents=int(bonus_cents),
        created_at=stamp,
        updated_at=stamp,
    )
    session.add(campaign)
    session.flush()
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="create_recharge_campaign",
        target_type="recharge_campaign",
        target_id=campaign.id,
        detail=f"新增充值活动：满 {threshold_cents} 分送 {bonus_cents} 分",
        ip=ip,
    )
    return campaign_row(campaign)


def update_campaign(
    session: Session,
    actor: Actor,
    campaign_id: int,
    *,
    threshold_cents: int,
    bonus_cents: int,
    ip: str = "",
) -> dict:
    _validate(threshold_cents, bonus_cents)
    campaign = get_campaign(session, actor.merchant_id, campaign_id)
    _check_threshold(
        session, actor.merchant_id, threshold_cents, exclude_id=campaign.id
    )
    campaign.threshold_cents = int(threshold_cents)
    campaign.bonus_cents = int(bonus_cents)
    campaign.updated_at = now_text()
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="update_recharge_campaign",
        target_type="recharge_campaign",
        target_id=campaign.id,
        detail=f"修改充值活动：满 {threshold_cents} 分送 {bonus_cents} 分",
        ip=ip,
    )
    return campaign_row(campaign)


def delete_campaign(
    session: Session, actor: Actor, campaign_id: int, *, ip: str = ""
) -> None:
    campaign = get_campaign(session, actor.merchant_id, campaign_id)
    threshold = int(campaign.threshold_cents)
    bonus = int(campaign.bonus_cents)
    session.delete(campaign)
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="delete_recharge_campaign",
        target_type="recharge_campaign",
        target_id=campaign_id,
        detail=f"删除充值活动：满 {threshold} 分送 {bonus} 分",
        ip=ip,
    )
