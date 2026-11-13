"""查战绩配额：原子扣次、管理员加减次数、用量流水与总览统计。

扣次口径：一次「开始查询」= 一个批次 = 扣 1 次，和批次里有多少玩家无关。
扣减用单条 UPDATE ... WHERE quota_used < quota_total，行数为 0 即额度不足或已停用。
"""

from __future__ import annotations

import logging

from sqlalchemy import func, select, text
from sqlalchemy.orm import Session

from app.errors import AppError, AuthError, NotFoundError
from app.models import User, ZjBatch, ZjGrant, ZjQuery, ZjUser
from app.timeutil import now_text, today_bounds

logger = logging.getLogger(__name__)

MAX_QUOTA = 100_000
LOG_PAGE_DEFAULT = 50
LOG_PAGE_MAX = 200


def quota_dict(user: ZjUser) -> dict:
    total = int(user.quota_total)
    used = int(user.quota_used)
    return {"total": total, "used": used, "remaining": max(total - used, 0)}


def deduct_one(session: Session, user_id: int) -> ZjUser:
    """为一次「开始查询」扣 1 次额度，返回扣后的账号。

    调用方必须在写事务里（get_write_db），否则并发下可能重复放行。
    """
    stamp = now_text()
    result = session.execute(
        text(
            "UPDATE zj_users SET quota_used = quota_used + 1, updated_at = :stamp "
            "WHERE id = :uid AND is_active = 1 AND quota_used < quota_total"
        ),
        {"stamp": stamp, "uid": user_id},
    )
    if result.rowcount == 0:
        user = session.get(ZjUser, user_id)
        if user is None:
            raise NotFoundError("账号不存在")
        if not user.is_active:
            raise AuthError("账号已停用，请联系管理员")
        raise AppError("查询次数已用完，请联系管理员充值")

    session.expire_all()
    user = session.get(ZjUser, user_id)
    if user is None:  # pragma: no cover - 同一事务内刚更新过，不会消失
        raise NotFoundError("账号不存在")
    return user


def grant_quota(
    session: Session,
    *,
    user_id: int,
    delta: int,
    operator_id: int,
    note: str = "",
) -> ZjUser:
    """管理员加/减次数。减到低于已用次数会被拒绝，流水里记调整后剩余。"""
    if delta == 0:
        raise AppError("调整数量不能为 0")
    if abs(delta) > MAX_QUOTA:
        raise AppError(f"单次调整不能超过 {MAX_QUOTA} 次")

    user = session.get(ZjUser, user_id)
    if user is None:
        raise NotFoundError("找不到这个账号")

    new_total = int(user.quota_total) + int(delta)
    if new_total < int(user.quota_used):
        raise AppError(f"调整后总次数不能低于已用次数（已用 {user.quota_used} 次）")
    if new_total > MAX_QUOTA:
        raise AppError(f"总次数不能超过 {MAX_QUOTA}")

    stamp = now_text()
    user.quota_total = new_total
    user.updated_at = stamp
    session.add(
        ZjGrant(
            user_id=user.id,
            delta=int(delta),
            quota_after=max(new_total - int(user.quota_used), 0),
            operator_id=operator_id,
            note=(note or "").strip()[:200],
            created_at=stamp,
        )
    )
    session.flush()
    logger.info(
        "配额调整：账号 %s %+d 次，总数 %s，操作人 %s",
        user.username,
        delta,
        new_total,
        operator_id,
    )
    return user


def _grant_items(session: Session, user_id: int, fetch: int) -> list[dict]:
    rows = session.execute(
        select(ZjGrant, User.display_name, User.username)
        .outerjoin(User, ZjGrant.operator_id == User.id)
        .where(ZjGrant.user_id == user_id)
        .order_by(ZjGrant.id.desc())
        .limit(fetch)
    ).all()
    return [
        {
            "type": "grant",
            "id": grant.id,
            "delta": int(grant.delta),
            "remaining": int(grant.quota_after),
            "note": grant.note,
            "operator": (display_name or username or "") if grant.operator_id else "",
            "created_at": grant.created_at,
        }
        for grant, display_name, username in rows
    ]


def _query_items(session: Session, user_id: int, fetch: int) -> list[dict]:
    rows = session.scalars(
        select(ZjQuery)
        .where(ZjQuery.user_id == user_id)
        .order_by(ZjQuery.id.desc())
        .limit(fetch)
    ).all()
    return [
        {
            "type": "query",
            "id": row.id,
            "nickname": row.nickname,
            "ok": bool(row.ok),
            "games": int(row.games),
            "err_code": row.err_code,
            "created_at": row.created_at,
        }
        for row in rows
    ]


def recent_logs(session: Session, user_id: int, limit: int = LOG_PAGE_DEFAULT, offset: int = 0) -> dict:
    """充值与查询流水混排，时间倒序。数据量小，两表各取一页在内存里合并。"""
    limit = max(1, min(int(limit), LOG_PAGE_MAX))
    offset = max(0, int(offset))
    fetch = offset + limit + 1

    merged = _grant_items(session, user_id, fetch) + _query_items(session, user_id, fetch)
    merged.sort(key=lambda item: (item["created_at"], item["type"], item["id"]), reverse=True)
    page = merged[offset : offset + limit]
    return {"items": page, "total_returned": len(page), "has_more": len(merged) > offset + limit}


def overview(session: Session) -> dict:
    """平台管理顶部统计：账号数、剩余次数合计、今日消耗次数。"""
    total_users = int(session.scalar(select(func.count()).select_from(ZjUser)) or 0)
    active_users = int(
        session.scalar(
            select(func.count()).select_from(ZjUser).where(ZjUser.is_active.is_(True))
        )
        or 0
    )
    remaining = int(
        session.scalar(
            select(
                func.coalesce(func.sum(ZjUser.quota_total - ZjUser.quota_used), 0)
            )
        )
        or 0
    )
    start, end = today_bounds()
    today_used = int(
        session.scalar(
            select(func.count())
            .select_from(ZjBatch)
            .where(ZjBatch.created_at >= start, ZjBatch.created_at < end)
        )
        or 0
    )
    return {
        "users": total_users,
        "active_users": active_users,
        "remaining": remaining,
        "today_used": today_used,
    }
