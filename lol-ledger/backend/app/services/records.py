"""记录查询：押金流水、场次记录、划转配对、批次流水与导出。全部按商家过滤。"""

from __future__ import annotations

import csv
import io
from datetime import date as date_cls

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.errors import AppError, NotFoundError
from app.models import Batch, GameSession, LedgerEntry, Player, User
from app.serializers import entry_payload, entry_row, session_row
from app.services.batches import compute_summary, get_batch, snapshot_summary
from app.services.players import get_player
from app.services.sessions import list_sessions
from app.timeutil import day_after_text, day_start_text

SORT_OPTIONS = {"created_at_desc", "created_at_asc", "amount_desc"}


def _date_conditions(column, date_from: str | None, date_to: str | None) -> list:
    conditions = []
    try:
        if date_from:
            conditions.append(column >= day_start_text(date_cls.fromisoformat(date_from)))
        if date_to:
            conditions.append(column < day_after_text(date_cls.fromisoformat(date_to)))
    except ValueError as exc:
        raise AppError("日期格式不正确") from exc
    return conditions


def list_deposit_records(
    session: Session,
    merchant_id: int,
    *,
    keyword: str = "",
    player_id: int | None = None,
    batch_id: int | None = None,
    session_id: int | None = None,
    reason: str | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    sort: str = "created_at_desc",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(1, int(page))
    page_size = min(200, max(1, int(page_size)))
    if sort not in SORT_OPTIONS:
        sort = "created_at_desc"

    owner = aliased(Player)
    other = aliased(Player)
    operator = aliased(User)

    conditions = [LedgerEntry.merchant_id == merchant_id]
    if player_id is not None:
        conditions.append(LedgerEntry.player_id == player_id)
    if batch_id is not None:
        conditions.append(LedgerEntry.batch_id == batch_id)
    if session_id is not None:
        conditions.append(LedgerEntry.session_id == session_id)
    if reason:
        conditions.append(LedgerEntry.reason == reason)
    text = (keyword or "").strip()
    if text:
        like = f"%{text}%"
        conditions.append(
            or_(
                owner.game_id.like(like),
                owner.account.like(like),
                GameSession.name.like(like),
            )
        )
    conditions.extend(_date_conditions(LedgerEntry.created_at, date_from, date_to))

    base = (
        select(LedgerEntry, owner, operator, GameSession, Batch, other)
        .join(owner, owner.id == LedgerEntry.player_id)
        .join(operator, operator.id == LedgerEntry.operator_id)
        .outerjoin(GameSession, GameSession.id == LedgerEntry.session_id)
        .outerjoin(Batch, Batch.id == LedgerEntry.batch_id)
        .outerjoin(other, other.id == LedgerEntry.counterparty_player_id)
        .where(*conditions)
    )

    total = int(
        session.scalar(
            select(func.count())
            .select_from(LedgerEntry)
            .join(owner, owner.id == LedgerEntry.player_id)
            .outerjoin(GameSession, GameSession.id == LedgerEntry.session_id)
            .where(*conditions)
        )
        or 0
    )

    if sort == "created_at_asc":
        base = base.order_by(LedgerEntry.created_at.asc(), LedgerEntry.id.asc())
    elif sort == "amount_desc":
        base = base.order_by(LedgerEntry.amount_cents.desc(), LedgerEntry.id.desc())
    else:
        base = base.order_by(LedgerEntry.created_at.desc(), LedgerEntry.id.desc())

    rows = session.execute(base.offset((page - 1) * page_size).limit(page_size)).all()
    items = [
        entry_row(entry, player=player, operator=user, session=game, batch=batch, counterparty=peer)
        for entry, player, user, game, batch, peer in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_session_records(
    session: Session,
    merchant_id: int,
    *,
    keyword: str = "",
    batch_id: int | None = None,
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    return list_sessions(
        session,
        merchant_id,
        batch_id=batch_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
    )


def player_ledger(
    session: Session,
    player_id: int,
    merchant_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    get_player(session, player_id, merchant_id)
    return list_deposit_records(
        session,
        merchant_id,
        player_id=player_id,
        page=page,
        page_size=page_size,
    )


def transfer_group(session: Session, group_id: str, merchant_id: int) -> dict:
    entries = list(
        session.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.merchant_id == merchant_id,
                LedgerEntry.transfer_group_id == group_id,
            )
            .order_by(LedgerEntry.id)
        )
    )
    if not entries:
        raise NotFoundError("找不到这笔划转")
    return {"group_id": group_id, "entries": [entry_payload(session, entry) for entry in entries]}


def batch_ledger(
    session: Session,
    batch_id: int,
    merchant_id: int,
    *,
    page: int = 1,
    page_size: int = 50,
) -> dict:
    get_batch(session, batch_id, merchant_id)
    return list_deposit_records(
        session, merchant_id, batch_id=batch_id, page=page, page_size=page_size
    )


def _reason_text(entry: dict) -> str:
    return entry["reason_label"]


def export_batch_csv(session: Session, batch_id: int, merchant_id: int) -> str:
    batch = get_batch(session, batch_id, merchant_id)
    summary = (
        snapshot_summary(batch)
        if batch.status == "closed"
        else compute_summary(session, batch_id, merchant_id)
    )
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["批次", batch.label or f"#{batch.id}"])
    writer.writerow(["开始", batch.opened_at])
    writer.writerow(["结束", batch.closed_at or "进行中"])
    if summary:
        writer.writerow(["局数", summary["session_count"]])
        writer.writerow(["人次", summary["player_times"]])
        writer.writerow(["茶水合计（元）", f"{summary['tea_total_cents'] / 100:.2f}"])
        writer.writerow(["加押金（元）", f"{summary['add_total_cents'] / 100:.2f}"])
        writer.writerow(["退押金（元）", f"{summary['refund_total_cents'] / 100:.2f}"])
        writer.writerow(["手动扣押（元）", f"{summary['deduct_total_cents'] / 100:.2f}"])
        writer.writerow(["划转（元）", f"{summary['transfer_out_total_cents'] / 100:.2f}"])
        writer.writerow(["期末总押金（元）", f"{summary['deposit_total_cents'] / 100:.2f}"])
    writer.writerow([])
    writer.writerow(["时间", "玩家", "原因", "变动金额", "变动后余额", "操作人", "场次", "备注"])

    rows = list_deposit_records(
        session, merchant_id, batch_id=batch_id, page=1, page_size=200
    )["items"]
    page = 2
    while True:
        for item in rows:
            writer.writerow(
                [
                    item["created_at"],
                    item["player"]["game_id"],
                    _reason_text(item),
                    f"{item['signed_amount_cents'] / 100:.2f}",
                    f"{item['balance_after_cents'] / 100:.2f}",
                    (item["operator"] or {}).get("display_name", ""),
                    (item["session"] or {}).get("name", ""),
                    item["note"],
                ]
            )
        chunk = list_deposit_records(
            session, merchant_id, batch_id=batch_id, page=page, page_size=200
        )["items"]
        if not chunk:
            break
        rows = chunk
        page += 1

    return "\ufeff" + buffer.getvalue()
