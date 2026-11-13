"""操作人汇总：取消班次后，按日期区间直接统计每位店员的经营动作。

- 场次：按 `played_at` 归属（补录昨天的局算昨天的）
- 押金：按 `created_at` 归属（钱是什么时候收/退的）
- 差额 = 加押金 - 退押金；正数是店员应交给店长的现金，负数是店长应补给店员
"""

from __future__ import annotations

from datetime import date

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.errors import AppError
from app.models import GameSession, LedgerEntry, User
from app.serializers import user_brief
from app.services import options
from app.services.dividend_math import dividend_by_mode
from app.timeutil import moment_bounds, now_cn, parse_moment

CASH_REASONS = ("add_deposit", "refund")
MAX_DAYS = 366


def parse_bounds(date_from: str | None, date_to: str | None) -> tuple[str, str]:
    """把区间参数规整成左右闭合的 ISO 文本，支持精确到分钟。"""
    try:
        start_text, end_text = moment_bounds(date_from, date_to)
        start = parse_moment(start_text)
        end = parse_moment(end_text)
    except ValueError as exc:
        raise AppError("时间格式不正确，应为 YYYY-MM-DD 或 YYYY-MM-DD HH:MM") from exc
    if (end - start).days > MAX_DAYS:
        raise AppError("一次最多统计一年")
    return start_text, end_text


def operator_summary(
    session: Session,
    merchant_id: int,
    date_from: str | None = None,
    date_to: str | None = None,
) -> dict:
    start_text, end_text = parse_bounds(date_from, date_to)

    mode = options.dividend_mode(session, merchant_id)
    rate = options.dividend_rate(session, merchant_id)
    fixed = options.dividend_fixed_cents(session, merchant_id)

    buckets: dict[int, dict] = {}

    def bucket(user_id: int) -> dict:
        return buckets.setdefault(
            int(user_id),
            {
                "session_count": 0,
                "player_times": 0,
                "tea_cents": 0,
                "add_deposit_cents": 0,
                "refund_cents": 0,
            },
        )

    game_rows = session.execute(
        select(
            GameSession.operator_id,
            func.count(),
            func.coalesce(func.sum(GameSession.player_count), 0),
            # tea_fee_cents 是每人茶水，总茶水要乘人数
            func.coalesce(func.sum(GameSession.tea_fee_cents * GameSession.player_count), 0),
        )
        .where(
            GameSession.merchant_id == merchant_id,
            GameSession.played_at >= start_text,
            GameSession.played_at <= end_text,
        )
        .group_by(GameSession.operator_id)
    ).all()
    for user_id, count, times, tea in game_rows:
        item = bucket(user_id)
        item["session_count"] = int(count)
        item["player_times"] = int(times)
        item["tea_cents"] = int(tea)

    cash_rows = session.execute(
        select(
            LedgerEntry.operator_id,
            LedgerEntry.reason,
            func.coalesce(func.sum(LedgerEntry.amount_cents), 0),
        )
        .where(
            LedgerEntry.merchant_id == merchant_id,
            LedgerEntry.reason.in_(CASH_REASONS),
            LedgerEntry.created_at >= start_text,
            LedgerEntry.created_at <= end_text,
        )
        .group_by(LedgerEntry.operator_id, LedgerEntry.reason)
    ).all()
    for user_id, reason, amount in cash_rows:
        item = bucket(user_id)
        item["add_deposit_cents" if reason == "add_deposit" else "refund_cents"] = int(amount)

    users = {
        user.id: user
        for user in session.scalars(select(User).where(User.merchant_id == merchant_id))
    }

    rows: list[dict] = []
    for user_id, item in buckets.items():
        user = users.get(user_id)
        if user is None:
            continue
        dividend = dividend_by_mode(
            item["session_count"],
            item["tea_cents"],
            mode,
            rate,
            fixed,
        )
        rows.append(
            {
                "user": user_brief(user),
                "session_count": item["session_count"],
                "player_times": item["player_times"],
                "tea_cents": item["tea_cents"],
                "add_deposit_cents": item["add_deposit_cents"],
                "refund_cents": item["refund_cents"],
                "cash_diff_cents": item["add_deposit_cents"] - item["refund_cents"],
                "dividend_cents": dividend,
            }
        )

    # 没开过局但还在职的店员也列出来，方便对账
    for user_id, user in users.items():
        if user_id in buckets or not user.is_active:
            continue
        rows.append(
            {
                "user": user_brief(user),
                "session_count": 0,
                "player_times": 0,
                "tea_cents": 0,
                "add_deposit_cents": 0,
                "refund_cents": 0,
                "cash_diff_cents": 0,
                "dividend_cents": 0,
            }
        )

    rows.sort(key=lambda row: (-row["cash_diff_cents"], -row["session_count"], row["user"]["id"]))

    totals = {
        "session_count": sum(row["session_count"] for row in rows),
        "player_times": sum(row["player_times"] for row in rows),
        "tea_cents": sum(row["tea_cents"] for row in rows),
        "add_deposit_cents": sum(row["add_deposit_cents"] for row in rows),
        "refund_cents": sum(row["refund_cents"] for row in rows),
        "cash_diff_cents": sum(row["cash_diff_cents"] for row in rows),
        "dividend_cents": sum(row["dividend_cents"] for row in rows),
    }

    today_text = now_cn().date().isoformat()
    return {
        "date_from": date_from or today_text,
        "date_to": date_to or today_text,
        "start_text": start_text,
        "end_text": end_text,
        "dividend_mode": mode,
        "dividend_rate_percent": rate,
        "dividend_fixed_cents": fixed,
        "rows": rows,
        "totals": totals,
    }
