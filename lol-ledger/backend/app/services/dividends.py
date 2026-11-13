"""分红结算：取消班次后，按日期区间统计每位操作人的场次并结算。

同一个区间（或与之重叠的区间）只能结算一次，避免重复发钱。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError
from app.models import DividendSettlement, User
from app.serializers import user_brief
from app.services.audit import write_audit
from app.services.summary import operator_summary, parse_bounds
from app.timeutil import now_text, parse_moment, to_text

MAX_SETTLE_USERS = 50


def _period(date_from: str | None, date_to: str | None) -> tuple[str, str]:
    """返回左右闭合的 ISO 起始/结束时间文本（支持精确到分钟）。"""
    return parse_bounds(date_from, date_to)


def _norm_start(value: str) -> str:
    """历史记录可能是纯日期，统一成当天 00:00。"""
    return to_text(parse_moment(value))


def _norm_end(value: str) -> str:
    """历史记录可能是纯日期，统一成当天 23:59:59。"""
    text = (value or "").strip()
    if len(text) == 10:
        text = text + "T23:59:59"
    return to_text(parse_moment(text))


def _empty_totals() -> dict:
    return {
        "session_count": 0,
        "player_times": 0,
        "tea_cents": 0,
        "dividend_cents": 0,
    }


def _aggregate(
    session: Session, merchant_id: int, start: str, end: str
) -> tuple[dict[int, dict], dict]:
    """返回 {user_id: 预览条目} 与汇总信息。已结算过的用户 pending 归零。

    start/end 是带时区的 ISO 文本；历史结算记录可能只存到日期，
    这里统一归一化后再判断重叠，避免漏判。
    """
    data = operator_summary(session, merchant_id, start, end)

    settled_rows = [
        row
        for row in session.scalars(
            select(DividendSettlement).where(
                DividendSettlement.merchant_id == merchant_id
            )
        )
        if _norm_start(row.period_start) <= end and _norm_end(row.period_end) >= start
    ]
    settled_map: dict[int, dict] = {}
    for row in settled_rows:
        item = settled_map.setdefault(int(row.user_id), _empty_totals())
        item["session_count"] += int(row.session_count)
        item["player_times"] += int(row.player_times)
        item["tea_cents"] += int(row.tea_cents)
        item["dividend_cents"] += int(row.dividend_cents)

    users = {
        user.id: user
        for user in session.scalars(select(User).where(User.merchant_id == merchant_id))
    }

    result: dict[int, dict] = {}
    for row in data["rows"]:
        user_id = int(row["user"]["id"])
        already = settled_map.get(user_id)
        if already is None and not row["session_count"]:
            # 纯 0 数据的人不进入分红预览，避免满屏空行
            continue
        pending = _empty_totals()
        if already is None:
            pending = {
                "session_count": row["session_count"],
                "player_times": row["player_times"],
                "tea_cents": row["tea_cents"],
                "dividend_cents": row["dividend_cents"],
            }
        result[user_id] = {
            "user": row["user"],
            "pending": pending,
            "settled": already or _empty_totals(),
            "pending_batches": [],
        }

    # 区间内有结算记录、但这段时间没有新场次的人也要列出来
    for user_id, settled in settled_map.items():
        if user_id in result:
            continue
        user = users.get(user_id)
        if user is None:
            continue
        result[user_id] = {
            "user": user_brief(user),
            "pending": _empty_totals(),
            "settled": settled,
            "pending_batches": [],
        }

    return result, {
        "mode": data["dividend_mode"],
        "rate": data["dividend_rate_percent"],
        "fixed": data["dividend_fixed_cents"],
        "settled_count": len(settled_rows),
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
    for user_id, entry in aggregated.items():
        pending = entry["pending"]
        settled = entry["settled"]
        items.append(
            {
                "user": entry["user"],
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
    if meta["settled_count"]:
        warnings.append("该区间已有结算记录，相关操作人不会重复结算，换一个不重叠的区间再试")

    return {
        "period": {"start": start, "end": end},
        "items": items,
        "totals": {
            "pending_dividend_cents": sum(item["pending"]["dividend_cents"] for item in items),
            "pending_tea_cents": sum(item["pending"]["tea_cents"] for item in items),
            "operator_count": len([item for item in items if item["pending"]["dividend_cents"] > 0]),
            "session_count": sum(item["pending"]["session_count"] for item in items),
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
    aggregated, meta = _aggregate(session, actor.merchant_id, start, end)
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
        ready.append((users[user_id], pending))
    if not ready:
        raise AppError("选中的操作人在这个区间没有可结算的分红")

    stamp = now_text()
    created: list[dict] = []
    for user, pending in ready:
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
            note=(note or "").strip()[:200],
            settled_by=actor.id,
            created_at=stamp,
        )
        session.add(row)
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

    total = sum(item["dividend_cents"] for _, item in ready)
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="dividend_settle",
        target_type="dividend",
        target_id=None,
        detail=(
            f"结算 {len(created)} 人，分红 {total / 100:.2f} 元，"
            f"区间 {start} ~ {end}"
        ),
        ip=ip,
    )
    return created


def list_settlements(
    session: Session,
    merchant_id: int,
    *,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(1, page)
    page_size = min(100, max(1, page_size))
    total = int(
        session.scalar(
            select(func.count())
            .select_from(DividendSettlement)
            .where(DividendSettlement.merchant_id == merchant_id)
        )
        or 0
    )
    rows = list(
        session.scalars(
            select(DividendSettlement)
            .where(DividendSettlement.merchant_id == merchant_id)
            .order_by(DividendSettlement.created_at.desc(), DividendSettlement.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    settler_ids = {row.settled_by for row in rows}
    setters = (
        {user.id: user for user in session.scalars(select(User).where(User.id.in_(settler_ids)))}
        if settler_ids
        else {}
    )
    return {
        "items": [
            {
                "id": row.id,
                "user": {
                    "id": row.user_id,
                    "username": row.username_snapshot,
                    "display_name": row.display_name_snapshot or row.username_snapshot,
                },
                "period": {"start": row.period_start, "end": row.period_end},
                "session_count": row.session_count,
                "player_times": row.player_times,
                "tea_cents": row.tea_cents,
                "dividend_cents": row.dividend_cents,
                "note": row.note,
                "settled_by": user_brief(setters.get(row.settled_by)),
                "created_at": row.created_at,
            }
            for row in rows
        ],
        "total": total,
        "page": page,
        "page_size": page_size,
    }
