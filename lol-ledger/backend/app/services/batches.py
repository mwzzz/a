"""批次（班次）：开班、关班、汇总、列表。每个商家各自独立开班。"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError
from app.models import Batch, GameSession, LedgerEntry, Player, SessionPlayer
from app.serializers import session_row, user_brief
from app.scope import scoped_get
from app.services.audit import write_audit
from app.services.money import INCOMING_REASONS
from app.services.players import clean_text
from app.services.reconcile import reconcile
from app.timeutil import now_text, parse_text

REASON_KEYS = {
    "normal_deduct": "tea_total_cents",
    "add_deposit": "add_total_cents",
    "refund": "refund_total_cents",
    "manual_deduct": "deduct_total_cents",
    "transfer_out": "transfer_out_total_cents",
}


def short_time(value: str | None) -> str:
    if not value:
        return "-"
    return parse_text(value).strftime("%m/%d %H:%M")


def display_label(batch: Batch) -> str:
    opened = short_time(batch.opened_at)
    if batch.status == "open":
        return f"{opened} 进行中"
    return f"{opened} 已结束 · {short_time(batch.closed_at)}"


def get_open_batch(session: Session, merchant_id: int) -> Batch | None:
    return session.scalar(
        select(Batch).where(
            Batch.merchant_id == merchant_id, Batch.status == "open"
        )
    )


def get_batch(session: Session, batch_id: int, merchant_id: int) -> Batch:
    return scoped_get(session, Batch, batch_id, merchant_id, "找不到这个批次")


def compute_summary(session: Session, batch_id: int, merchant_id: int) -> dict:
    summary = {value: 0 for value in REASON_KEYS.values()}
    rows = session.execute(
        select(
            LedgerEntry.reason,
            func.coalesce(func.sum(LedgerEntry.amount_cents), 0),
            func.count(),
        )
        .where(
            LedgerEntry.merchant_id == merchant_id,
            LedgerEntry.batch_id == batch_id,
        )
        .group_by(LedgerEntry.reason)
    ).all()
    transfer_count = 0
    net = 0
    for reason, total, count in rows:
        key = REASON_KEYS.get(reason)
        if key:
            summary[key] = int(total or 0)
        if reason == "transfer_out":
            transfer_count = int(count or 0)
        amount = int(total or 0)
        net += amount if reason in INCOMING_REASONS else -amount

    session_count = int(
        session.scalar(
            select(func.count())
            .select_from(GameSession)
            .where(
                GameSession.merchant_id == merchant_id,
                GameSession.batch_id == batch_id,
            )
        )
        or 0
    )
    player_times = int(
        session.scalar(
            select(func.coalesce(func.sum(GameSession.player_count), 0)).where(
                GameSession.merchant_id == merchant_id,
                GameSession.batch_id == batch_id,
            )
        )
        or 0
    )
    deposit_total = int(
        session.scalar(
            select(func.coalesce(func.sum(Player.deposit_cents), 0)).where(
                Player.merchant_id == merchant_id,
                Player.deleted_at.is_(None),
            )
        )
        or 0
    )

    summary.update(
        {
            "batch_id": batch_id,
            "session_count": session_count,
            "player_times": player_times,
            "transfer_count": transfer_count,
            "net_change_cents": net,
            "deposit_total_cents": deposit_total,
            "opening_total_cents": deposit_total - net,
        }
    )
    return summary


def snapshot_summary(batch: Batch) -> dict:
    net = int(batch.net_change_cents or 0)
    deposit_total = int(batch.deposit_total_cents or 0)
    return {
        "batch_id": batch.id,
        "session_count": int(batch.session_count or 0),
        "player_times": int(batch.player_times or 0),
        "tea_total_cents": int(batch.tea_total_cents or 0),
        "add_total_cents": int(batch.add_total_cents or 0),
        "refund_total_cents": int(batch.refund_total_cents or 0),
        "deduct_total_cents": int(batch.deduct_total_cents or 0),
        "transfer_out_total_cents": int(batch.transfer_out_total_cents or 0),
        "transfer_count": int(batch.transfer_count or 0),
        "net_change_cents": net,
        "deposit_total_cents": deposit_total,
        "opening_total_cents": deposit_total - net,
    }


def open_batch(
    session: Session,
    actor: Actor,
    *,
    label: str = "",
    note: str = "",
    ip: str = "",
) -> Batch:
    existing = get_open_batch(session, actor.merchant_id)
    if existing is not None:
        raise AppError("当前批次还没交班，不能重复开班")
    batch = Batch(
        merchant_id=actor.merchant_id,
        label=clean_text(label, "批次名", 64),
        note=clean_text(note, "备注", 200),
        status="open",
        opened_by=actor.id,
        opened_at=now_text(),
        closed_by=None,
        closed_at=None,
    )
    session.add(batch)
    session.flush()
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="open_batch",
        target_type="batch",
        target_id=batch.id,
        detail="开班",
        ip=ip,
    )
    return batch


def close_batch(
    session: Session,
    actor: Actor,
    batch_id: int,
    *,
    note: str = "",
    ip: str = "",
) -> Batch:
    merchant_id = actor.merchant_id
    batch = get_batch(session, batch_id, merchant_id)
    if batch.status != "open":
        raise AppError("这个批次已经交班了")

    summary = compute_summary(session, batch_id, merchant_id)
    report = reconcile(session, merchant_id)
    if not report["ok"]:
        raise AppError("对账不通过，不能交班。请联系管理员检查押金余额。")

    stamp = now_text()
    batch.status = "closed"
    batch.closed_at = stamp
    batch.closed_by = actor.id
    if note:
        batch.note = clean_text(note, "备注", 200)
    batch.session_count = summary["session_count"]
    batch.player_times = summary["player_times"]
    batch.tea_total_cents = summary["tea_total_cents"]
    batch.add_total_cents = summary["add_total_cents"]
    batch.refund_total_cents = summary["refund_total_cents"]
    batch.deduct_total_cents = summary["deduct_total_cents"]
    batch.transfer_out_total_cents = summary["transfer_out_total_cents"]
    batch.transfer_count = summary["transfer_count"]
    batch.net_change_cents = summary["net_change_cents"]
    batch.deposit_total_cents = summary["deposit_total_cents"]

    write_audit(
        session,
        merchant_id=merchant_id,
        user_id=actor.id,
        action="close_batch",
        target_type="batch",
        target_id=batch.id,
        detail=f"交班：{summary['session_count']} 局，茶水 {summary['tea_total_cents']} 分",
        ip=ip,
    )
    return batch


def _summary_for(session: Session, batch: Batch) -> dict:
    if batch.status == "closed":
        return snapshot_summary(batch)
    return compute_summary(session, batch.id, batch.merchant_id)


def batch_row(session: Session, batch: Batch, sessions: list[dict] | None = None) -> dict:
    summary = _summary_for(session, batch)
    return {
        "id": batch.id,
        "label": batch.label,
        "display_label": display_label(batch),
        "status": batch.status,
        "opened_at": batch.opened_at,
        "closed_at": batch.closed_at,
        "note": batch.note,
        "opened_by": user_brief(batch.opener),
        "closed_by": user_brief(batch.closer),
        "session_count": summary["session_count"],
        "player_times": summary["player_times"],
        "summary": summary,
        "sessions": sessions or [],
    }


def sessions_for_batches(
    session: Session, batch_ids: list[int], merchant_id: int
) -> dict[int, list[dict]]:
    if not batch_ids:
        return {}
    games = list(
        session.scalars(
            select(GameSession)
            .where(
                GameSession.merchant_id == merchant_id,
                GameSession.batch_id.in_(batch_ids),
            )
            .order_by(GameSession.played_at.desc(), GameSession.id.desc())
        )
    )
    if not games:
        return {}
    ids = [game.id for game in games]
    members = list(
        session.scalars(select(SessionPlayer).where(SessionPlayer.session_id.in_(ids)))
    )
    grouped: dict[int, list[SessionPlayer]] = {}
    for item in members:
        grouped.setdefault(item.session_id, []).append(item)

    result: dict[int, list[dict]] = {}
    for game in games:
        result.setdefault(game.batch_id, []).append(session_row(game, grouped.get(game.id, [])))
    return result


def list_batches(
    session: Session,
    merchant_id: int,
    *,
    status: str = "all",
    keyword: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 20,
    include_sessions: bool = True,
) -> dict:
    page = max(1, int(page))
    page_size = min(100, max(1, int(page_size)))

    conditions = [Batch.merchant_id == merchant_id]
    if status in ("open", "closed"):
        conditions.append(Batch.status == status)
    text = (keyword or "").strip()
    if text:
        like = f"%{text}%"
        conditions.append(
            or_(
                Batch.label.like(like),
                Batch.id.in_(
                    select(GameSession.batch_id).where(
                        GameSession.merchant_id == merchant_id,
                        GameSession.name.like(like),
                    )
                ),
            )
        )
    if date_from or date_to:
        from datetime import date as date_cls

        from app.timeutil import day_after_text, day_start_text

        try:
            if date_from:
                conditions.append(
                    Batch.opened_at >= day_start_text(date_cls.fromisoformat(date_from))
                )
            if date_to:
                conditions.append(
                    Batch.opened_at < day_after_text(date_cls.fromisoformat(date_to))
                )
        except ValueError as exc:
            raise AppError("日期格式不正确") from exc

    total = int(
        session.scalar(select(func.count()).select_from(Batch).where(*conditions)) or 0
    )
    batches = list(
        session.scalars(
            select(Batch)
            .where(*conditions)
            .order_by(Batch.opened_at.desc(), Batch.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    grouped = (
        sessions_for_batches(session, [batch.id for batch in batches], merchant_id)
        if include_sessions
        else {}
    )
    return {
        "items": [batch_row(session, batch, grouped.get(batch.id, [])) for batch in batches],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def batch_detail(session: Session, batch_id: int, merchant_id: int) -> dict:
    batch = get_batch(session, batch_id, merchant_id)
    grouped = sessions_for_batches(session, [batch.id], merchant_id)
    return batch_row(session, batch, grouped.get(batch.id, []))
