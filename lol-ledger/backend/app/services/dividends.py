"""分红结算：按日期区间统计每位操作人的场次并结算。

幂等口径是**每一局只会被结算一次**：结算时把区间内该操作人尚未认领的场次
逐局写进 `dividend_settlement_sessions`，之后任何区间都再拿不到这些局。
误结算可以冲销（只软标记），历史结算行的金额与区间永不修改。
"""

from __future__ import annotations

from sqlalchemy import func, select, update
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError, NotFoundError
from app.models import (
    DividendSettlement,
    DividendSettlementSession,
    GameSession,
    User,
)
from app.serializers import user_brief
from app.services import options
from app.services.audit import write_audit
from app.services.dividend_math import dividend_by_mode
from app.services.players import clean_text
from app.services.summary import parse_bounds
from app.timeutil import bound_end_text_safe, bound_start_text_safe, now_text

MAX_SETTLE_USERS = 50


def _period(date_from: str | None, date_to: str | None) -> tuple[str, str]:
    """返回左右闭合的 ISO 起始/结束时间文本（支持精确到分钟）。"""
    return parse_bounds(date_from, date_to)


def _empty_totals() -> dict:
    return {
        "session_count": 0,
        "player_times": 0,
        "tea_cents": 0,
        "dividend_cents": 0,
    }


def _tea_of(game: GameSession) -> int:
    """`tea_fee_cents` 是每人茶水，一局总额要乘人数。"""
    return int(game.tea_fee_cents) * int(game.player_count or 0)


def _pending_sessions(
    session: Session, merchant_id: int, start: str, end: str
) -> list[GameSession]:
    """区间内还没被任何未冲销结算认领的场次，按局时间排序。"""
    claimed = (
        select(DividendSettlementSession.session_id)
        .where(
            DividendSettlementSession.merchant_id == merchant_id,
            DividendSettlementSession.voided_at.is_(None),
        )
    )
    return list(
        session.scalars(
            select(GameSession)
            .where(
                GameSession.merchant_id == merchant_id,
                GameSession.played_at >= start,
                GameSession.played_at <= end,
                GameSession.id.not_in(claimed),
            )
            .order_by(GameSession.played_at, GameSession.id)
        )
    )


def _claimed_count(session: Session, merchant_id: int, start: str, end: str) -> int:
    """区间内已被认领（已结算过）的局数，用来解释为什么少了几局。"""
    return int(
        session.scalar(
            select(func.count())
            .select_from(DividendSettlementSession)
            .join(GameSession, GameSession.id == DividendSettlementSession.session_id)
            .where(
                DividendSettlementSession.merchant_id == merchant_id,
                DividendSettlementSession.voided_at.is_(None),
                GameSession.played_at >= start,
                GameSession.played_at <= end,
            )
        )
        or 0
    )


def _overlapping_settlements(
    session: Session, merchant_id: int, start: str, end: str
) -> tuple[dict[int, dict], int]:
    """返回 {user_id: 已结算汇总} 与重叠的结算行数。

    历史行的区间可能只存到日期，归一化后再比对；解析不了的行跳过，
    不能让一条脏数据把整页结算打挂。
    """
    settled_map: dict[int, dict] = {}
    overlaps = 0
    for row in session.scalars(
        select(DividendSettlement)
        .where(
            DividendSettlement.merchant_id == merchant_id,
            DividendSettlement.voided_at.is_(None),
        )
        .order_by(DividendSettlement.id)
    ):
        period_start = bound_start_text_safe(row.period_start)
        period_end = bound_end_text_safe(row.period_end)
        if period_start is None or period_end is None:
            continue
        if period_start > end or period_end < start:
            continue
        overlaps += 1
        item = settled_map.setdefault(int(row.user_id), _empty_totals())
        item["session_count"] += int(row.session_count)
        item["player_times"] += int(row.player_times)
        item["tea_cents"] += int(row.tea_cents)
        item["dividend_cents"] += int(row.dividend_cents)
    return settled_map, overlaps


def _aggregate(session: Session, merchant_id: int, start: str, end: str) -> tuple[dict, dict]:
    """返回 {user_id: 条目} 与本次结算的口径信息。"""
    mode = options.dividend_mode(session, merchant_id)
    rate = options.dividend_rate(session, merchant_id)
    fixed = options.dividend_fixed_cents(session, merchant_id)

    users = {
        user.id: user
        for user in session.scalars(select(User).where(User.merchant_id == merchant_id))
    }

    grouped: dict[int, list[GameSession]] = {}
    for game in _pending_sessions(session, merchant_id, start, end):
        grouped.setdefault(int(game.operator_id), []).append(game)

    settled_map, overlaps = _overlapping_settlements(session, merchant_id, start, end)
    claimed_count = _claimed_count(session, merchant_id, start, end)

    result: dict[int, dict] = {}
    for user_id, games in grouped.items():
        user = users.get(user_id)
        if user is None:
            continue
        tea = sum(_tea_of(game) for game in games)
        pending = {
            "session_count": len(games),
            "player_times": sum(int(game.player_count or 0) for game in games),
            "tea_cents": tea,
            "dividend_cents": dividend_by_mode(len(games), tea, mode, rate, fixed),
        }
        result[user_id] = {
            "user": user_brief(user),
            "user_active": bool(user.is_active),
            "pending": pending,
            "settled": settled_map.get(user_id) or _empty_totals(),
            "sessions": games,
        }

    for user_id, settled in settled_map.items():
        user = users.get(user_id)
        if user is None or user_id in result:
            continue
        result[user_id] = {
            "user": user_brief(user),
            "user_active": bool(user.is_active),
            "pending": _empty_totals(),
            "settled": settled,
            "sessions": [],
        }

    return result, {
        "mode": mode,
        "rate": rate,
        "fixed": fixed,
        "settled_count": overlaps,
        "claimed_count": claimed_count,
    }


def preview(
    session: Session,
    merchant_id: int,
    *,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    start, end = _period(date_from, date_to)
    aggregated, meta = _aggregate(session, merchant_id, start, end)

    items = []
    for entry in aggregated.values():
        pending = entry["pending"]
        settled = entry["settled"]
        items.append(
            {
                "user": entry["user"],
                "is_active": entry["user_active"],
                "pending": pending,
                "settled": settled,
                "status": "pending"
                if pending["dividend_cents"] > 0
                else ("settled" if settled["dividend_cents"] > 0 else "empty"),
                "dividend_mode": meta["mode"],
            }
        )
    items.sort(
        key=lambda item: (
            -item["pending"]["dividend_cents"],
            -item["settled"]["dividend_cents"],
        )
    )

    warnings: list[str] = []
    if meta["claimed_count"]:
        warnings.append(
            f"该区间已有 {meta['claimed_count']} 局结算过，本次只统计剩下的场次"
        )
    pending_games = sum(item["pending"]["session_count"] for item in items)
    if meta["settled_count"] and pending_games:
        warnings.append(
            f"其中 {pending_games} 局是结算之后补录或当初漏结的，可以现在补发"
        )

    return {
        "period": {"start": start, "end": end},
        "items": items,
        "totals": {
            "pending_dividend_cents": sum(item["pending"]["dividend_cents"] for item in items),
            "pending_tea_cents": sum(item["pending"]["tea_cents"] for item in items),
            "operator_count": len([item for item in items if item["pending"]["dividend_cents"] > 0]),
            "session_count": pending_games,
            "claimed_session_count": meta["claimed_count"],
        },
        "warnings": warnings,
    }


def settle(
    session: Session,
    actor: Actor,
    *,
    user_ids: list[int],
    date_from: str | None = None,
    date_to: str | None = None,
    note: str = "",
    ip: str = "",
) -> list[dict]:
    ids = list(dict.fromkeys(int(item) for item in user_ids))
    if not ids:
        raise AppError("请选择要结算的操作人")
    if len(ids) > MAX_SETTLE_USERS:
        raise AppError(f"一次最多结算 {MAX_SETTLE_USERS} 个人")

    start, end = _period(date_from, date_to)
    aggregated, _meta = _aggregate(session, actor.merchant_id, start, end)
    users = {
        user.id: user
        for user in session.scalars(
            select(User).where(User.merchant_id == actor.merchant_id, User.id.in_(ids))
        )
    }
    missing = [item for item in ids if item not in users]
    if missing:
        raise AppError("有账号不属于本店，不能结算")

    ready: list[tuple[User, dict]] = []
    for user_id in ids:
        entry = aggregated.get(user_id)
        pending = entry["pending"] if entry else None
        if not pending or pending["dividend_cents"] <= 0:
            continue
        ready.append((users[user_id], entry))
    if not ready:
        raise AppError("选中的操作人在这个区间没有可结算的分红")

    stamp = now_text()
    clean = clean_text(note, "备注", 200)
    created: list[dict] = []
    claimed_total = 0
    for user, entry in ready:
        pending = entry["pending"]
        row = DividendSettlement(
            merchant_id=actor.merchant_id,
            user_id=user.id,
            username_snapshot=user.username,
            display_name_snapshot=user.display_name or "",
            period_start=start,
            period_end=end,
            session_count=pending["session_count"],
            player_times=pending["player_times"],
            tea_cents=pending["tea_cents"],
            dividend_cents=pending["dividend_cents"],
            note=clean,
            settled_by=actor.id,
            created_at=stamp,
        )
        session.add(row)
        session.flush()
        for game in entry["sessions"]:
            session.add(
                DividendSettlementSession(
                    settlement_id=row.id,
                    session_id=game.id,
                    user_id=user.id,
                    merchant_id=actor.merchant_id,
                    tea_cents=_tea_of(game),
                    created_at=stamp,
                )
            )
        claimed_total += len(entry["sessions"])
        session.flush()
        created.append(
            {
                "id": row.id,
                "user": user_brief(user),
                "period": {"start": row.period_start, "end": row.period_end},
                "session_count": row.session_count,
                "player_times": row.player_times,
                "tea_cents": row.tea_cents,
                "dividend_cents": row.dividend_cents,
            }
        )

    total = sum(entry["pending"]["dividend_cents"] for _, entry in ready)
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="dividend_settle",
        target_type="dividend",
        target_id=None,
        detail=(
            f"结算 {len(created)} 人，分红 {total / 100:.2f} 元，"
            f"认领 {claimed_total} 场，区间 {start} ~ {end}"
        ),
        ip=ip,
    )
    return created


def void_settlement(
    session: Session,
    actor: Actor,
    settlement_id: int,
    *,
    note: str = "",
    ip: str = "",
) -> dict:
    """冲销一笔结算：只软标记，金额与区间一字不动，被认领的场次重新变为待结算。"""
    row = session.get(DividendSettlement, int(settlement_id))
    if row is None or row.merchant_id != actor.merchant_id:
        raise NotFoundError("结算记录不存在")
    if row.voided_at:
        raise AppError("这笔结算已经冲销过了")

    clean = clean_text(note, "备注", 200) or "冲销结算"
    stamp = now_text()
    released = int(
        session.scalar(
            select(func.count())
            .select_from(DividendSettlementSession)
            .where(
                DividendSettlementSession.settlement_id == row.id,
                DividendSettlementSession.voided_at.is_(None),
            )
        )
        or 0
    )
    row.voided_at = stamp
    row.voided_by = actor.id
    row.void_note = clean
    session.execute(
        update(DividendSettlementSession)
        .where(
            DividendSettlementSession.settlement_id == row.id,
            DividendSettlementSession.voided_at.is_(None),
        )
        .values(voided_at=stamp)
    )
    session.flush()

    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="dividend_settlement_void",
        target_type="dividend",
        target_id=row.id,
        detail=(
            f"冲销 {row.username_snapshot} 的分红 {row.dividend_cents / 100:.2f} 元，"
            f"区间 {row.period_start} ~ {row.period_end}，释放 {released} 场，"
            f"备注 {clean}"
        ),
        ip=ip,
    )
    return {
        "id": row.id,
        "user": user_brief(session.get(User, row.user_id)),
        "period": {"start": row.period_start, "end": row.period_end},
        "session_count": row.session_count,
        "dividend_cents": row.dividend_cents,
        "released_session_count": released,
        "voided_at": row.voided_at,
        "voided_by": user_brief(session.get(User, actor.id)),
        "void_note": row.void_note,
    }


def list_settlements(
    session: Session,
    merchant_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
    status: str = "all",
) -> dict:
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    conditions = [DividendSettlement.merchant_id == merchant_id]
    if status == "live":
        conditions.append(DividendSettlement.voided_at.is_(None))
    elif status == "voided":
        conditions.append(DividendSettlement.voided_at.is_not(None))

    total = int(
        session.scalar(
            select(func.count()).select_from(DividendSettlement).where(*conditions)
        )
        or 0
    )
    rows = list(
        session.scalars(
            select(DividendSettlement)
            .where(*conditions)
            .order_by(DividendSettlement.created_at.desc(), DividendSettlement.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    settler_ids = {row.settled_by for row in rows} | {
        row.voided_by for row in rows if row.voided_by
    }
    setters = (
        {user.id: user for user in session.scalars(select(User).where(User.id.in_(settler_ids)))}
        if settler_ids
        else {}
    )
    released_map: dict[int, int] = {}
    if rows:
        for settlement_id, count in session.execute(
            select(
                DividendSettlementSession.settlement_id,
                func.count(),
            )
            .where(DividendSettlementSession.settlement_id.in_([row.id for row in rows]))
            .group_by(DividendSettlementSession.settlement_id)
        ).all():
            released_map[int(settlement_id)] = int(count)

    return {
        "items": [
            {
                "id": row.id,
                "user": {
                    "id": row.user_id,
                    "username": row.username_snapshot,
                    "display_name": row.display_name_snapshot or row.username_snapshot,
                },
                "period": {
                    "start": bound_start_text_safe(row.period_start) or row.period_start,
                    "end": bound_end_text_safe(row.period_end) or row.period_end,
                },
                "session_count": row.session_count,
                "player_times": row.player_times,
                "tea_cents": row.tea_cents,
                "dividend_cents": row.dividend_cents,
                "note": row.note,
                "settled_by": user_brief(setters.get(row.settled_by)),
                "created_at": row.created_at,
                "status": "voided" if row.voided_at else "live",
                "voided_at": row.voided_at,
                "voided_by": user_brief(setters.get(row.voided_by)) if row.voided_by else None,
                "void_note": row.void_note,
                "claimed_session_count": released_map.get(int(row.id), 0),
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
