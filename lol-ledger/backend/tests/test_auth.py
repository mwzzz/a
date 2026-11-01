"""登录、改密、令牌失效。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import jwt

from app.config import settings
from app.security import ALGORITHM
from tests.conftest import DEFAULT_PASSWORD, create_user_direct


def test_login_ok_returns_token_and_user(client, admin) -> None:
    response = client.post(
        "/api/v1/auth/login",
        json={"username": admin["username"], "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 200
    body = response.json()
    assert body["token_type"] == "bearer"
    assert body["expires_in"] == 12 * 3600
    assert body["user"]["role"] == "admin"
    assert body["access_token"]


def test_login_wrong_password_same_message(client, admin) -> None:
    wrong = client.post(
        "/api/v1/auth/login",
        json={"username": admin["username"], "password": "WrongPass123"},
    )
    missing = client.post(
        "/api/v1/auth/login",
        json={"username": "nobody-here", "password": "WrongPass123"},
    )
    assert wrong.status_code == 401
    assert missing.status_code == 401
    assert wrong.json()["detail"] == missing.json()["detail"] == "用户名或密码错误"


def test_login_disabled_user_rejected(client) -> None:
    create_user_direct("stopped", "staff", is_active=False)
    response = client.post(
        "/api/v1/auth/login",
        json={"username": "stopped", "password": DEFAULT_PASSWORD},
    )
    assert response.status_code == 401
    assert "停用" in response.json()["detail"]


def test_expired_token_rejected(client, admin) -> None:
    past = datetime.now(timezone.utc) - timedelta(hours=1)
    token = jwt.encode(
        {
            "sub": str(admin["id"]),
            "role": "admin",
            "iat": int((past - timedelta(hours=1)).timestamp()),
            "exp": int(past.timestamp()),
        },
        settings.jwt_secret,
        algorithm=ALGORITHM,
    )
    response = client.get("/api/v1/auth/me", headers={"Authorization": f"Bearer {token}"})
    assert response.status_code == 401
    assert "过期" in response.json()["detail"]


def test_token_invalid_after_password_change(client, admin) -> None:
    headers = admin["headers"]
    changed = client.post(
        "/api/v1/auth/password",
        json={"old_password": DEFAULT_PASSWORD, "new_password": "NewPassw0rd"},
        headers=headers,
    )
    assert changed.status_code == 204
    me = client.get("/api/v1/auth/me", headers=headers)
    assert me.status_code == 401
    assert "密码已修改" in me.json()["detail"]

    relogin = client.post(
        "/api/v1/auth/login",
        json={"username": admin["username"], "password": "NewPassw0rd"},
    )
    assert relogin.status_code == 200


def test_change_password_requires_old_password(client, staff) -> None:
    response = client.post(
        "/api/v1/auth/password",
        json={"old_password": "NotMyPass1", "new_password": "NewPassw0rd"},
        headers=staff["headers"],
    )
    assert response.status_code == 400
    assert "原密码" in response.json()["detail"]


def test_password_policy(client, admin) -> None:
    headers = admin["headers"]
    cases = [
        ("12345678", "字母"),
        ("abcdefgh", "数字"),
        ("Ab1", "至少 8 位"),
    ]
    for index, (password, keyword) in enumerate(cases):
        response = client.post(
            "/api/v1/users",
            json={
                "username": f"weak{index}",
                "password": password,
                "display_name": "",
                "role": "staff",
            },
            headers=headers,
        )
        assert response.status_code == 400, password
        assert keyword in response.json()["detail"]


def test_health_is_public(client) -> None:
    response = client.get("/api/health")
    assert response.status_code == 200
    assert response.json()["ok"] is True
