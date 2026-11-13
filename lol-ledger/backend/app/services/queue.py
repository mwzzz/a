"""排队登记（小工具 → 排队登记）。

一天的队列当天有效：列表按 created_at 的自然日过滤，
过期的记录留在库里不影响当天展示，也不占用「同一个名字不能重复排队」的判断。
"""

from __future__ import annotations

from datetime import datetime

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError, NotFoundError
from app.models import Merchant, QueueEntry
from app.serializers import user_brief
from app.services.audit import write_audit
from app.timeutil import now_cn, now_text

STATUS_LABELS = {
    "waiting": "排队中",
    "playing": "进行中",
    "done": "已完成",
    "cancelled": "已取消",
}

ACTIVE_STATUSES = ("waiting", "playing")

# 只允许这些流转，避免把已完成的又改回排队中
ALLOWED = {
    "waiting": {"playing", "cancelled"},
    "playing": {"done", "cancelled"},
    "done": set(),
    "cancelled": set(),
}


def _clean(value: str, limit: int, field: str) -> str:
    text = (value or "").strip()
    if not text:
        raise AppError(f"{field}不能为空")
    if len(text) > limit:
        raise AppError(f"{field}不能超过 {limit} 个字")
    return text


def _wait_minutes(entry: QueueEntry, now: datetime) -> int:
    try:
        created = datetime.fromisoformat(entry.created_at)
    except ValueError:
        return 0
    if created.tzinfo is None:
        created = created.replace(tzinfo=now.tzinfo)
    return max(0, int((now - created).total_seconds() // 60))


def entry_row(entry: QueueEntry, now: datetime | None = None) -> dict:
    current = now or now_cn()
    return {
        "id": entry.id,
        "game_id": entry.game_id,
        "note": entry.note,
        "status": entry.status,
        "status_label": STATUS_LABELS.get(entry.status, entry.status),
        "wait_minutes": _wait_minutes(entry, current),
        "created_at": entry.created_at,
        "called_at": entry.called_at,
        "finished_at": entry.finished_at,
        "operator": user_brief(entry.operator) if entry.operator else None,
    }


def queue_today(session: Session, merchant_id: int, day: str | None = None) -> dict:
    """某一天（默认今天）的队列，附带店名与统计，可直接用于生成阵容图。"""
    target = day or now_cn().date().isoformat()
    merchant = session.get(Merchant, merchant_id)
    rows = session.scalars(
        select(QueueEntry)
        .where(
            QueueEntry.merchant_id == merchant_id,
            QueueEntry.created_at.startswith(target),
        )
        .order_by(QueueEntry.id)
    ).all()

    now = now_cn()
    entries = [entry_row(row, now) for row in rows]
    counts = {key: 0 for key in STATUS_LABELS}
    for item in entries:
        counts[item["status"]] = counts.get(item["status"], 0) + 1

    return {
        "date": target,
        "shop_name": merchant.name if merchant else "",
        "updated_at": now_text(),
        "entries": entries,
        "counts": counts,
    }


def create_entry(
    session: Session,
    actor: Actor,
    *,
    game_id: str,
    note: str = "",
    ip: str = "",
) -> dict:
    name = _clean(game_id, 64, "游戏名")
    memo = (note or "").strip()
    if len(memo) > 100:
        raise AppError("备注不能超过 100 个字")

    today = now_cn().date().isoformat()
    exists = session.scalar(
        select(QueueEntry).where(
            QueueEntry.merchant_id == actor.merchant_id,
            QueueEntry.game_id == name,
            QueueEntry.status.in_(ACTIVE_STATUSES),
            QueueEntry.created_at.startswith(today),
        )
    )
    if exists is not None:
        raise AppError("这个名字已经在队列里了")

    entry = QueueEntry(
        merchant_id=actor.merchant_id,
        game_id=name,
        note=memo,
        status="waiting",
        operator_id=actor.id,
        created_at=now_text(),
    )
    session.add(entry)
    session.flush()
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="queue_create",
        target_type="queue",
        target_id=entry.id,
        detail=f"排队登记：{name}",
        ip=ip,
    )
    return entry_row(entry)


def update_status(
    session: Session,
    actor: Actor,
    entry_id: int,
    status: str,
    *,
    ip: str = "",
) -> dict:
    if status not in STATUS_LABELS:
        raise AppError("状态不合法")
    entry = session.scalar(
        select(QueueEntry).where(
            QueueEntry.id == entry_id,
            QueueEntry.merchant_id == actor.merchant_id,
        )
    )
    if entry is None:
        raise NotFoundError("找不到这条排队记录")
    if status not in ALLOWED.get(entry.status, set()):
        raise AppError(
            f"不能从「{STATUS_LABELS.get(entry.status, entry.status)}」"
            f"改成「{STATUS_LABELS[status]}」"
        )

    entry.status = status
    if status == "playing" and not entry.called_at:
        entry.called_at = now_text()
    if status in ("done", "cancelled"):
        entry.finished_at = now_text()
    session.flush()

    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="queue_status",
        target_type="queue",
        target_id=entry.id,
        detail=f"{entry.game_id}：{STATUS_LABELS[status]}",
        ip=ip,
    )
    return entry_row(entry)
