"""现金保管与交班交接。

口径：
- 玩家押金余额 = 在用玩家 deposit_cents 之和
- 本班营业额 = 本班 normal_deduct（茶水）之和
- 在库现金 = 玩家押金余额 + 本班茶水（没有进行中班次时就是押金余额）
- 交班：茶水上缴给管理员，押金余额交给下一保管人（管理员或店员）
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError, NotFoundError
from app.models import Batch, CashHandover, LedgerEntry, Merchant, Player, User
from app.serializers import user_brief
from app.services.audit import write_audit
from app.timeutil import now_text

METHOD_LABELS = {
    "wechat": "微信",
    "alipay": "支付宝",
    "cash": "现金",
    "bank": "银行转账",
    "other": "其他",
}


def clean_method(value: str) -> str:
    method = (value or "wechat").strip().lower()
    if method not in METHOD_LABELS:
        raise AppError("收款方式不正确")
    return method


def get_holder(session: Session, merchant: Merchant) -> User | None:
    if merchant.custodian_user_id is None:
        return None
    return session.get(User, merchant.custodian_user_id)


def _open_batch(session: Session, merchant_id: int) -> Batch | None:
    return session.scalar(
        select(Batch).where(
            Batch.merchant_id == merchant_id, Batch.status == "open"
        )
    )


def current(session: Session, merchant_id: int) -> dict:
    """当前保管人 + 在库现金。读接口用，不做任何写入。"""
    merchant = session.get(Merchant, merchant_id)
    if merchant is None:
        raise NotFoundError("找不到这个商家")

    deposit_cents = int(
        session.scalar(
            select(func.coalesce(func.sum(Player.deposit_cents), 0)).where(
                Player.merchant_id == merchant_id,
                Player.deleted_at.is_(None),
            )
        )
        or 0
    )
    batch = _open_batch(session, merchant_id)
    tea_cents = 0
    if batch is not None:
        tea_cents = int(
            session.scalar(
                select(func.coalesce(func.sum(LedgerEntry.amount_cents), 0)).where(
                    LedgerEntry.merchant_id == merchant_id,
                    LedgerEntry.batch_id == batch.id,
                    LedgerEntry.reason == "normal_deduct",
                )
            )
            or 0
        )

    holder = get_holder(session, merchant)
    if holder is None and batch is not None:
        holder = session.get(User, batch.opened_by)

    return {
        "holder": user_brief(holder) if holder is not None else None,
        "holder_id": holder.id if holder is not None else None,
        "amount_cents": deposit_cents + tea_cents,
        "deposit_cents": deposit_cents,
        "tea_cents": tea_cents,
        "batch_id": batch.id if batch is not None else None,
    }


def is_holder(session: Session, merchant_id: int, user_id: int) -> bool:
    merchant = session.get(Merchant, merchant_id)
    return merchant is not None and merchant.custodian_user_id == user_id


def ensure_holder(session: Session, merchant_id: int, fallback_user_id: int) -> None:
    merchant = session.get(Merchant, merchant_id)
    if merchant is not None and merchant.custodian_user_id is None:
        merchant.custodian_user_id = fallback_user_id
        merchant.updated_at = now_text()


def _active_user(session: Session, user_id: int, merchant_id: int) -> User:
    user = session.get(User, user_id)
    if (
        user is None
        or user.merchant_id != merchant_id
        or not user.is_active
        or user.is_superadmin
    ):
        raise AppError("接收人不存在或已停用")
    return user


def record_close_handover(
    session: Session,
    actor: Actor,
    batch: Batch,
    summary: dict,
    *,
    tea_to_user_id: int,
    deposit_to_user_id: int,
    tea_method: str,
    deposit_method: str,
    note: str = "",
    ip: str = "",
) -> CashHandover:
    """交班时的现金拆分。调用方保证 batch 仍是进行中、汇总已算好。"""
    merchant = session.get(Merchant, batch.merchant_id)
    if merchant is None:
        raise NotFoundError("找不到这个商家")

    tea_to = _active_user(session, tea_to_user_id, batch.merchant_id)
    if tea_to.role != "admin":
        raise AppError("茶水营业款只能上缴给管理员")
    deposit_to = _active_user(session, deposit_to_user_id, batch.merchant_id)

    holder = get_holder(session, merchant)
    from_user = holder or session.get(User, batch.opened_by)
    if from_user is None:
        raise AppError("找不到当前保管人")
    if actor.id != from_user.id:
        raise AppError(
            f"现金当前在 {from_user.display_name or from_user.username} 手中，请由该保管人交班"
        )

    handover = CashHandover(
        merchant_id=batch.merchant_id,
        batch_id=batch.id,
        from_user_id=from_user.id,
        deposit_to_user_id=deposit_to.id,
        tea_to_user_id=tea_to.id,
        deposit_cents=int(summary["deposit_total_cents"]),
        tea_cents=int(summary["tea_total_cents"]),
        deposit_method=clean_method(deposit_method),
        tea_method=clean_method(tea_method),
        note=(note or "").strip()[:200],
        created_by=actor.id,
        created_at=now_text(),
    )
    session.add(handover)
    session.flush()

    merchant.custodian_user_id = deposit_to.id
    merchant.updated_at = now_text()

    write_audit(
        session,
        merchant_id=batch.merchant_id,
        user_id=actor.id,
        action="handover",
        target_type="batch",
        target_id=batch.id,
        detail=(
            f"交班交接：押金 {handover.deposit_cents} 分给 {deposit_to.username}，"
            f"茶水 {handover.tea_cents} 分上缴 {tea_to.username}"
        ),
        ip=ip,
    )
    return handover


def handover_row(handover: CashHandover) -> dict:
    return {
        "id": handover.id,
        "from": user_brief(handover.from_user),
        "deposit_to": user_brief(handover.deposit_to),
        "tea_to": user_brief(handover.tea_to),
        "deposit_cents": int(handover.deposit_cents),
        "tea_cents": int(handover.tea_cents),
        "deposit_method": handover.deposit_method,
        "deposit_method_label": METHOD_LABELS.get(
            handover.deposit_method, handover.deposit_method
        ),
        "tea_method": handover.tea_method,
        "tea_method_label": METHOD_LABELS.get(handover.tea_method, handover.tea_method),
        "note": handover.note,
        "created_at": handover.created_at,
    }


def latest_handover(session: Session, batch_id: int) -> CashHandover | None:
    return session.scalar(
        select(CashHandover)
        .where(CashHandover.batch_id == batch_id)
        .order_by(CashHandover.id.desc())
        .limit(1)
    )
