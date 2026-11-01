"""密码哈希与 JWT。"""

from __future__ import annotations

import hashlib
from datetime import datetime, timezone
from uuid import uuid4

import bcrypt
import jwt

from app.config import settings
from app.errors import AppError, AuthError

ALGORITHM = "HS256"
MAX_PASSWORD_BYTES = 72


def hash_password(password: str) -> str:
    return bcrypt.hashpw(password.encode("utf-8"), bcrypt.gensalt(rounds=12)).decode("utf-8")


def verify_password(password: str, password_hash: str) -> bool:
    try:
        return bcrypt.checkpw(password.encode("utf-8"), password_hash.encode("utf-8"))
    except (ValueError, TypeError):
        return False


def validate_password_strength(password: str, username: str = "") -> None:
    if len(password) < 8:
        raise AppError("密码至少 8 位")
    if len(password) > 64:
        raise AppError("密码不能超过 64 位")
    if len(password.encode("utf-8")) > MAX_PASSWORD_BYTES:
        raise AppError("密码包含太多多字节字符，请换一个")
    if not any(char.isalpha() for char in password):
        raise AppError("密码必须包含字母")
    if not any(char.isdigit() for char in password):
        raise AppError("密码必须包含数字")
    if username and password.lower() == username.lower():
        raise AppError("密码不能和用户名相同")


def password_fingerprint(password_hash: str) -> str:
    """取密码哈希的摘要放进令牌。改密后哈希变了，旧令牌立刻失效。"""
    return hashlib.sha256(password_hash.encode("utf-8")).hexdigest()[:16]


def create_access_token(user_id: int, role: str, password_hash: str) -> tuple[str, int]:
    ttl_seconds = int(settings.token_ttl_hours) * 3600
    issued = int(datetime.now(timezone.utc).timestamp())
    payload = {
        "sub": str(user_id),
        "role": role,
        "pv": password_fingerprint(password_hash),
        "iat": issued,
        "exp": issued + ttl_seconds,
        "jti": uuid4().hex,
    }
    return jwt.encode(payload, settings.jwt_secret, algorithm=ALGORITHM), ttl_seconds


def decode_token(token: str) -> dict:
    try:
        return jwt.decode(
            token,
            settings.jwt_secret,
            algorithms=[ALGORITHM],
            options={"require": ["exp", "sub", "iat"]},
        )
    except jwt.ExpiredSignatureError as exc:
        raise AuthError("登录已过期，请重新登录") from exc
    except jwt.PyJWTError as exc:
        raise AuthError("登录状态无效，请重新登录") from exc
