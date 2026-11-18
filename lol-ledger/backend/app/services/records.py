"""记录查询：押金流水、场次记录、划转配对。全部按商家过滤。"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, aliased

from app.errors import AppError, NotFoundError
from app.models import GameSession, LedgerEntry, Player, User
from app.serializers import entry_payload, entry_row, user_brief
from app.services.players import get_player
from app.services.sessions import list_sessions
from app.timeutil import bound_end_text, bound_start_text

SORT_OPTIONS = {"created_at_desc", "created_at_asc", "amount_desc"}


def _date_conditions(column, date_from: str | None, date_to: str | None) -> list:
    """按时间区间过滤，支持纯日期和精确到分钟两种写法。"""
    conditions = []
    try:
        if date_from:
            conditions.append(column >= bound_start_text(date_from))
        if date_to:
            conditions.append(column <= bound_end_text(date_to))
    except ValueError as exc:
        raise AppError("时间格式不正确，应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM") from exc
    return conditions


def list_deposit_records(
    session: Session,
    merchant_id: int,
    *,
    keyword: str = "",
    player_id: int | None = None,
    session_id: int | None = None,
    operator_id: int | None = None,
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
    if operator_id is not None:
        conditions.append(LedgerEntry.operator_id == int(operator_id))
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
        select(LedgerEntry, owner, operator, GameSession, other)
        .join(owner, owner.id == LedgerEntry.player_id)
        .join(operator, operator.id == LedgerEntry.operator_id)
        .outerjoin(GameSession, GameSession.id == LedgerEntry.session_id)
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
        entry_row(entry, player=player, operator=user, session=game, counterparty=peer)
        for entry, player, user, game, peer in rows
    ]
    _mark_bonus_voided(session, merchant_id, items)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def _mark_bonus_voided(session: Session, merchant_id: int, items: list[dict]) -> None:
    """给本页的加赠金流水标注是否已被撤销，供前端决定是否显示「撤销」入口。"""
    bonus_ids = [item["id"] for item in items if item["reason"] == "add_bonus"]
    if not bonus_ids:
        return
    voided = set(
        session.scalars(
            select(LedgerEntry.reverses_ledger_id).where(
                LedgerEntry.merchant_id == merchant_id,
                LedgerEntry.reason == "bonus_void",
                LedgerEntry.reverses_ledger_id.in_(bonus_ids),
            )
        ).all()
    )
    for item in items:
        if item["reason"] == "add_bonus":
            item["voided"] = item["id"] in voided


def list_session_records(
    session: Session,
    merchant_id: int,
    *,
    keyword: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    operator_id: int | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    return list_sessions(
        session,
        merchant_id,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        operator_id=operator_id,
        page=page,
        page_size=page_size,
    )


def list_operator_options(session: Session, merchant_id: int) -> list[dict]:
    """流水筛选用的操作人：含已停用账号，开发者账号不出现在门店里。"""
    users = session.scalars(
        select(User)
        .where(
            User.merchant_id == merchant_id,
            User.is_superadmin.is_(False),
        )
        .order_by(User.id)
    )
    return [
        {
            "id": user.id,
            "username": user.username,
            "display_name": user.display_name or user.username,
            "role": user.role,
            "is_active": bool(user.is_active),
        }
        for user in users
    ]


def operator_cash_summary(
    session: Session,
    merchant_id: int,
    *,
    operator_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    """按操作人统计加押金、退押金及差额；划转不计入。"""
    conditions = [
        LedgerEntry.merchant_id == merchant_id,
        LedgerEntry.operator_id == int(operator_id),
        LedgerEntry.reason.in_(("add_deposit", "refund")),
    ]
    conditions.extend(_date_conditions(LedgerEntry.created_at, date_from, date_to))

    rows = session.execute(
        select(
            LedgerEntry.reason,
            func.coalesce(func.sum(LedgerEntry.amount_cents), 0),
            func.count(),
        )
        .where(*conditions)
        .group_by(LedgerEntry.reason)
    ).all()

    add_cents = 0
    refund_cents = 0
    entry_count = 0
    for reason, amount, count in rows:
        if reason == "add_deposit":
            add_cents = int(amount)
        else:
            refund_cents = int(amount)
        entry_count += int(count)

    operator = session.scalar(
        select(User).where(
            User.id == int(operator_id),
            User.merchant_id == merchant_id,
        )
    )
    return {
        "operator": user_brief(operator),
        "add_deposit_cents": add_cents,
        "refund_cents": refund_cents,
        "cash_diff_cents": add_cents - refund_cents,
        "entry_count": entry_count,
    }


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
