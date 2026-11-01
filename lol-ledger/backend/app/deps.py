"""请求依赖：数据库会话、当前登录用户、管理员校验。"""

from __future__ import annotations

from dataclasses import dataclass
from typing import Iterator

from fastapi import Depends, Request
from fastapi.security import HTTPAuthorizationCredentials, HTTPBearer
from sqlalchemy.orm import Session

from app import db as dbmod
from app.errors import AuthError, ForbiddenError
from app.models import Merchant, User
from app.security import decode_token, password_fingerprint
from app.timeutil import parse_text

bearer = HTTPBearer(auto_error=False)


@dataclass(frozen=True)
class Actor:
    id: int
    username: str
    display_name: str
    role: str
    merchant_id: int
    merchant_name: str

    @property
    def is_admin(self) -> bool:
        return self.role == "admin"

    @property
    def name(self) -> str:
        return self.display_name or self.username


def get_read_db() -> Iterator[Session]:
    with dbmod.read_session() as session:
        yield session


def get_write_db() -> Iterator[Session]:
    """写请求：进入时开 BEGIN IMMEDIATE，正常退出提交，异常回滚。"""
    assert dbmod.WriteSession is not None, "数据库尚未初始化"
    session: Session = dbmod.WriteSession()
    try:
        with session.begin():
            yield session
    finally:
        session.close()


def client_ip(request: Request) -> str:
    forwarded = request.headers.get("x-forwarded-for")
    if forwarded:
        return forwarded.split(",")[0].strip()
    return request.client.host if request.client else ""


def get_current_user(
    credentials: HTTPAuthorizationCredentials | None = Depends(bearer),
    session: Session = Depends(get_read_db),
) -> Actor:
    if credentials is None:
        raise AuthError("请先登录")
    payload = decode_token(credentials.credentials)
    try:
        user_id = int(payload["sub"])
    except (KeyError, TypeError, ValueError) as exc:
        raise AuthError("登录状态无效，请重新登录") from exc

    user = session.get(User, user_id)
    if user is None:
        raise AuthError("账号不存在，请重新登录")
    if not user.is_active:
        raise AuthError("账号已停用")

    merchant = session.get(Merchant, user.merchant_id)
    if merchant is None:
        raise AuthError("账号所属商家不存在，请联系管理员")
    if merchant.status != "active":
        raise AuthError("商家已停用，请联系管理员")

    issued_at = int(payload.get("iat", 0))
    changed_at = int(parse_text(user.password_changed_at).timestamp())
    if issued_at < changed_at or payload.get("pv") != password_fingerprint(user.password_hash):
        raise AuthError("密码已修改，请重新登录")

    return Actor(
        id=user.id,
        username=user.username,
        display_name=user.display_name,
        role=user.role,
        merchant_id=merchant.id,
        merchant_name=merchant.name,
    )


def require_admin(actor: Actor = Depends(get_current_user)) -> Actor:
    if not actor.is_admin:
        raise ForbiddenError("只有管理员可以操作")
    return actor
