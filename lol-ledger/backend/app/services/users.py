"""账号：登录、建号、改密、停用。"""

from __future__ import annotations

import re
import threading
import time
from collections import deque

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError, AuthError, ForbiddenError, NotFoundError, RateLimitError
from app.models import Merchant, User
from app.security import hash_password, validate_password_strength, verify_password
from app.services.audit import write_audit
from app.timeutil import now_text

USERNAME_PATTERN = re.compile(r"^[a-z0-9_.-]{3,32}$")

FAILURE_WINDOW_SECONDS = 300
FAILURE_LIMIT = 5
_failures: dict[str, deque[float]] = {}
_failures_lock = threading.Lock()


def normalize_username(raw: str) -> str:
    name = (raw or "").strip().lower()
    if not USERNAME_PATTERN.fullmatch(name):
        raise AppError("用户名只能用 3~32 位字母、数字、下划线、点或减号")
    return name


def _check_rate(username: str) -> None:
    now = time.time()
    with _failures_lock:
        bucket = _failures.get(username)
        if not bucket:
            return
        while bucket and now - bucket[0] > FAILURE_WINDOW_SECONDS:
            bucket.popleft()
        if len(bucket) >= FAILURE_LIMIT:
            raise RateLimitError("登录失败次数过多，请 5 分钟后再试")


def _note_failure(username: str) -> None:
    with _failures_lock:
        _failures.setdefault(username, deque()).append(time.time())


def _clear_failures(username: str) -> None:
    with _failures_lock:
        _failures.pop(username, None)


def active_merchant(session: Session, merchant_id: int) -> Merchant:
    merchant = session.get(Merchant, merchant_id)
    if merchant is None:
        raise NotFoundError("找不到这个商家")
    if merchant.status != "active":
        raise AppError("商家已停用，请联系管理员")
    return merchant


def get_user_in_merchant(session: Session, user_id: int, merchant_id: int) -> User:
    """按 id + 商家取账号。别家的账号一律当作不存在。"""
    user = session.get(User, user_id)
    if user is None or user.merchant_id != merchant_id:
        raise NotFoundError("找不到这个账号")
    return user


def authenticate(session: Session, username: str, password: str, ip: str = "") -> User:
    name = (username or "").strip().lower()
    _check_rate(name)
    user = session.scalar(select(User).where(User.username == name))
    if user is None or not verify_password(password, user.password_hash):
        _note_failure(name)
        raise AuthError("用户名或密码错误")
    if not user.is_active:
        raise AuthError("账号已停用")

    merchant = session.get(Merchant, user.merchant_id)
    if merchant is None:
        raise AuthError("账号所属商家不存在，请联系管理员")
    if merchant.status != "active":
        raise AuthError("商家已停用，请联系管理员")

    stamp = now_text()
    user.last_login_at = stamp
    user.updated_at = stamp
    write_audit(
        session,
        merchant_id=user.merchant_id,
        user_id=user.id,
        action="login",
        target_type="user",
        target_id=user.id,
        detail="登录成功",
        ip=ip,
    )
    _clear_failures(name)
    return user


def user_row(user: User, merchant: Merchant | None = None) -> dict:
    data = {
        "id": user.id,
        "username": user.username,
        "display_name": user.display_name or user.username,
        "role": user.role,
        "is_active": bool(user.is_active),
        "merchant_id": user.merchant_id,
        "last_login_at": user.last_login_at,
        "created_at": user.created_at,
    }
    if merchant is not None:
        data["merchant"] = {"id": merchant.id, "name": merchant.name}
    return data


def list_users(session: Session, merchant_id: int) -> list[User]:
    return list(
        session.scalars(
            select(User).where(User.merchant_id == merchant_id).order_by(User.id)
        )
    )


def create_user(
    session: Session,
    actor: Actor,
    *,
    username: str,
    password: str,
    display_name: str = "",
    role: str = "staff",
    ip: str = "",
) -> User:
    if not actor.is_admin:
        raise ForbiddenError("只有管理员可以开账号")
    merchant = active_merchant(session, actor.merchant_id)
    name = normalize_username(username)
    validate_password_strength(password, name)
    if role not in ("admin", "staff"):
        raise AppError("角色不正确")
    exists = session.scalar(select(User).where(User.username == name))
    if exists is not None:
        raise AppError("用户名已存在")

    stamp = now_text()
    user = User(
        merchant_id=merchant.id,
        username=name,
        password_hash=hash_password(password),
        display_name=(display_name or "").strip()[:64],
        role=role,
        is_active=True,
        password_changed_at=stamp,
        last_login_at=None,
        created_at=stamp,
        updated_at=stamp,
    )
    session.add(user)
    session.flush()
    write_audit(
        session,
        merchant_id=merchant.id,
        user_id=actor.id,
        action="create_user",
        target_type="user",
        target_id=user.id,
        detail=f"新建账号 {name}（{role}）",
        ip=ip,
    )
    return user


def update_user(
    session: Session,
    actor: Actor,
    user_id: int,
    *,
    display_name: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    ip: str = "",
) -> User:
    if not actor.is_admin:
        raise ForbiddenError("只有管理员可以改账号")
    user = get_user_in_merchant(session, user_id, actor.merchant_id)

    if user.id == actor.id and (
        (role is not None and role != user.role) or (is_active is False)
    ):
        raise AppError("不能改自己的角色或停用自己")
    if role is not None and role not in ("admin", "staff"):
        raise AppError("角色不正确")
    if (role == "staff" or is_active is False) and user.role == "admin" and user.is_active:
        active_admins = session.scalar(
            select(func.count()).select_from(User).where(
                User.merchant_id == actor.merchant_id,
                User.role == "admin",
                User.is_active.is_(True),
            )
        )
        if int(active_admins or 0) <= 1:
            raise AppError("至少要保留一个启用的管理员")

    if display_name is not None:
        user.display_name = display_name.strip()[:64]
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    user.updated_at = now_text()
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="update_user",
        target_type="user",
        target_id=user.id,
        detail=f"修改账号 {user.username}",
        ip=ip,
    )
    return user


def reset_password(
    session: Session,
    actor: Actor,
    user_id: int,
    new_password: str,
    ip: str = "",
) -> None:
    if not actor.is_admin:
        raise ForbiddenError("只有管理员可以重置密码")
    user = get_user_in_merchant(session, user_id, actor.merchant_id)
    validate_password_strength(new_password, user.username)
    stamp = now_text()
    user.password_hash = hash_password(new_password)
    user.password_changed_at = stamp
    user.updated_at = stamp
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="reset_password",
        target_type="user",
        target_id=user.id,
        detail=f"重置 {user.username} 的密码",
        ip=ip,
    )


def change_own_password(
    session: Session,
    actor: Actor,
    old_password: str,
    new_password: str,
    ip: str = "",
) -> None:
    user = session.get(User, actor.id)
    if user is None:
        raise AppError("账号不存在")
    if not verify_password(old_password, user.password_hash):
        raise AppError("原密码不正确")
    if old_password == new_password:
        raise AppError("新密码不能和原密码相同")
    validate_password_strength(new_password, user.username)
    stamp = now_text()
    user.password_hash = hash_password(new_password)
    user.password_changed_at = stamp
    user.updated_at = stamp
    write_audit(
        session,
        merchant_id=user.merchant_id,
        user_id=user.id,
        action="change_password",
        target_type="user",
        target_id=user.id,
        detail="修改自己的密码",
        ip=ip,
    )
