"""查战绩账号：登录、建号、改密、启停与额度视图。

与记账系统的 services/users.py 平行但完全独立：没有商家、没有角色，
只有一个「次数包」额度。登录失败限流用独立字典，互不影响。
"""

from __future__ import annotations

import re
import threading
import time
from collections import deque

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.errors import AppError, AuthError, NotFoundError, RateLimitError
from app.models import ZjUser
from app.security import hash_password, validate_password_strength, verify_password
from app.timeutil import now_text

USERNAME_PATTERN = re.compile(r"^[a-z0-9_.-]{3,32}$")

MAX_QUOTA = 100_000
FAILURE_WINDOW_SECONDS = 300
FAILURE_LIMIT = 5

_failures: dict[str, deque[float]] = {}
_failures_lock = threading.Lock()


def normalize_username(raw: str) -> str:
    name = (raw or "").strip().lower()
    if not USERNAME_PATTERN.fullmatch(name):
        raise AppError("用户名只能用 3~32 位字母、数字、下划线、点或减号")
    return name


def _check_rate(name: str) -> None:
    now = time.time()
    with _failures_lock:
        bucket = _failures.get(name)
        if not bucket:
            return
        while bucket and now - bucket[0] > FAILURE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= FAILURE_LIMIT:
            raise RateLimitError("登录失败次数过多，请 5 分钟后再试")


def _note_failure(name: str) -> None:
    with _failures_lock:
        _failures.setdefault(name, deque()).append(time.time())


def _clear_failures(name: str) -> None:
    with _failures_lock:
        _failures.pop(name, None)


def reset_failures() -> None:
    """测试与排障用：清空登录失败计数。"""
    with _failures_lock:
        _failures.clear()


def quota_dict(user: ZjUser) -> dict:
    return {
        "total": int(user.quota_total),
        "used": int(user.quota_used),
        "remaining": max(int(user.quota_total) - int(user.quota_used), 0),
    }


def profile(user: ZjUser) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.name,
        "quota": quota_dict(user),
        "is_active": bool(user.is_active),
    }


def admin_row(user: ZjUser) -> dict:
    return {
        "id": user.id,
        "username": user.username,
        "display_name": user.name,
        "note": user.note,
        "quota_total": int(user.quota_total),
        "quota_used": int(user.quota_used),
        "quota_remaining": max(int(user.quota_total) - int(user.quota_used), 0),
        "is_active": bool(user.is_active),
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
    }


def get_user(session: Session, user_id: int) -> ZjUser:
    user = session.get(ZjUser, user_id)
    if user is None:
        raise NotFoundError("找不到这个账号")
    return user


def list_users(session: Session) -> list[ZjUser]:
    return list(session.scalars(select(ZjUser).order_by(ZjUser.id)))


def authenticate(session: Session, username: str, password: str) -> ZjUser:
    name = (username or "").strip().lower()
    _check_rate(name)
    user = session.scalar(select(ZjUser).where(ZjUser.username == name))
    if user is None or not verify_password(password, user.password_hash):
        _note_failure(name)
        raise AuthError("用户名或密码错误")
    if not user.is_active:
        raise AuthError("账号已停用，请联系管理员")

    stamp = now_text()
    user.last_login_at = stamp
    user.updated_at = stamp
    _clear_failures(name)
    return user


def _validate_quota(value: int) -> int:
    if value < 0:
        raise AppError("初始次数不能为负数")
    if value > MAX_QUOTA:
        raise AppError(f"次数不能超过 {MAX_QUOTA}")
    return int(value)


def create_user(
    session: Session,
    *,
    username: str,
    password: str,
    display_name: str = "",
    note: str = "",
    quota_total: int = 0,
) -> ZjUser:
    name = normalize_username(username)
    validate_password_strength(password, name)
    if session.scalar(select(ZjUser).where(ZjUser.username == name)) is not None:
        raise AppError("用户名已存在")

    stamp = now_text()
    user = ZjUser(
        username=name,
        password_hash=hash_password(password),
        display_name=(display_name or "").strip()[:64],
        note=(note or "").strip()[:200],
        quota_total=_validate_quota(quota_total),
        quota_used=0,
        is_active=True,
        password_changed_at=stamp,
        last_login_at=None,
        created_at=stamp,
        updated_at=stamp,
    )
    session.add(user)
    session.flush()
    return user


def update_user(
    session: Session,
    user_id: int,
    *,
    display_name: str | None = None,
    note: str | None = None,
    is_active: bool | None = None,
) -> ZjUser:
    user = get_user(session, user_id)
    if display_name is not None:
        user.display_name = display_name.strip()[:64]
    if note is not None:
        user.note = note.strip()[:200]
    if is_active is not None:
        user.is_active = bool(is_active)
    user.updated_at = now_text()
    return user


def reset_password(session: Session, user_id: int, new_password: str) -> ZjUser:
    user = get_user(session, user_id)
    validate_password_strength(new_password, user.username)
    stamp = now_text()
    user.password_hash = hash_password(new_password)
    user.password_changed_at = stamp
    user.updated_at = stamp
    return user


def change_own_password(
    session: Session, user_id: int, old_password: str, new_password: str
) -> ZjUser:
    user = get_user(session, user_id)
    if not verify_password(old_password, user.password_hash):
        raise AppError("原密码不正确")
    if old_password == new_password:
        raise AppError("新密码不能和原密码相同")
    validate_password_strength(new_password, user.username)
    stamp = now_text()
    user.password_hash = hash_password(new_password)
    user.password_changed_at = stamp
    user.updated_at = stamp
    return user
