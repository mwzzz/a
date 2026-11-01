"""商家级设置读写。缺失或非法时回落到默认值。

店名不在这张表里，统一存 merchants.name，避免两处不一致。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError, ForbiddenError, NotFoundError
from app.models import Merchant, MerchantSetting
from app.services.audit import write_audit
from app.timeutil import now_text

DEFAULTS = {
    "last_tea_cents": 200,
    "deposit_low_cents": 3000,
    "deposit_high_cents": 6000,
}


def _read_all(session: Session, merchant_id: int) -> dict[str, str]:
    rows = session.scalars(
        select(MerchantSetting).where(MerchantSetting.merchant_id == merchant_id)
    )
    return {row.key: row.value for row in rows}


def get_int(session: Session, merchant_id: int, key: str) -> int:
    raw = _read_all(session, merchant_id).get(key)
    try:
        return int(raw) if raw is not None else int(DEFAULTS[key])
    except (TypeError, ValueError, KeyError):
        return int(DEFAULTS.get(key, 0))


def get_merchant(session: Session, merchant_id: int) -> Merchant:
    merchant = session.get(Merchant, merchant_id)
    if merchant is None:
        raise NotFoundError("找不到这个商家")
    return merchant


def thresholds(session: Session, merchant_id: int) -> tuple[int, int]:
    low = get_int(session, merchant_id, "deposit_low_cents")
    high = get_int(session, merchant_id, "deposit_high_cents")
    if high <= low:
        return int(DEFAULTS["deposit_low_cents"]), int(DEFAULTS["deposit_high_cents"])
    return low, high


def last_tea_cents(session: Session, merchant_id: int) -> int:
    value = get_int(session, merchant_id, "last_tea_cents")
    return value if value >= 0 else int(DEFAULTS["last_tea_cents"])


def snapshot(session: Session, merchant_id: int) -> dict:
    merchant = get_merchant(session, merchant_id)
    low, high = thresholds(session, merchant_id)
    return {
        "last_tea_cents": last_tea_cents(session, merchant_id),
        "deposit_low_cents": low,
        "deposit_high_cents": high,
        "shop_name": merchant.name,
    }


def set_int(
    session: Session,
    merchant_id: int,
    key: str,
    value: int,
    actor_id: int | None = None,
) -> None:
    """内部用：开局后记住本次茶水，不校验管理员。"""
    stamp = now_text()
    row = session.get(MerchantSetting, (merchant_id, key))
    if row is None:
        session.add(
            MerchantSetting(
                merchant_id=merchant_id,
                key=key,
                value=str(int(value)),
                updated_at=stamp,
                updated_by=actor_id,
            )
        )
    else:
        row.value = str(int(value))
        row.updated_at = stamp
        row.updated_by = actor_id


def update(
    session: Session,
    actor: Actor,
    *,
    last_tea_cents: int | None = None,
    deposit_low_cents: int | None = None,
    deposit_high_cents: int | None = None,
    shop_name: str | None = None,
    ip: str = "",
) -> dict:
    if not actor.is_admin:
        raise ForbiddenError("只有管理员可以改设置")

    merchant_id = actor.merchant_id
    merchant = get_merchant(session, merchant_id)

    updates: dict[str, str] = {}
    if last_tea_cents is not None:
        if last_tea_cents < 0:
            raise AppError("茶水不能为负")
        updates["last_tea_cents"] = str(int(last_tea_cents))
    if deposit_low_cents is not None:
        if deposit_low_cents < 0:
            raise AppError("押金阈值不能为负")
        updates["deposit_low_cents"] = str(int(deposit_low_cents))
    if deposit_high_cents is not None:
        if deposit_high_cents < 0:
            raise AppError("押金阈值不能为负")
        updates["deposit_high_cents"] = str(int(deposit_high_cents))

    if "deposit_low_cents" in updates or "deposit_high_cents" in updates:
        current = snapshot(session, merchant_id)
        low = updates.get("deposit_low_cents", str(current["deposit_low_cents"]))
        high = updates.get("deposit_high_cents", str(current["deposit_high_cents"]))
        if int(high) <= int(low):
            raise AppError("押金上限必须大于下限")

    stamp = now_text()
    existing = {
        row.key: row
        for row in session.scalars(
            select(MerchantSetting).where(MerchantSetting.merchant_id == merchant_id)
        )
    }
    for key, value in updates.items():
        row = existing.get(key)
        if row is None:
            session.add(
                MerchantSetting(
                    merchant_id=merchant_id,
                    key=key,
                    value=value,
                    updated_at=stamp,
                    updated_by=actor.id,
                )
            )
        else:
            row.value = value
            row.updated_at = stamp
            row.updated_by = actor.id

    renamed = False
    if shop_name is not None:
        name = shop_name.strip()[:64]
        if not name:
            raise AppError("店名不能为空")
        clash = session.scalar(
            select(Merchant.id).where(
                Merchant.name == name, Merchant.id != merchant_id
            )
        )
        if clash is not None:
            raise AppError("店名已被占用")
        if name != merchant.name:
            merchant.name = name
            merchant.updated_at = stamp
            renamed = True

    if updates or renamed:
        detail = "修改 " + "、".join(list(updates) + (["shop_name"] if renamed else []))
        write_audit(
            session,
            merchant_id=merchant_id,
            user_id=actor.id,
            action="update_settings",
            target_type="settings",
            detail=detail,
            ip=ip,
        )
    return snapshot(session, merchant_id)
