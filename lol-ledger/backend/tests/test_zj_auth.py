"""查战绩账号鉴权：登录换令牌、与记账令牌互斥、停用、改密、失败限流。"""

from __future__ import annotations

import pytest

from app import db as dbmod
from app.errors import AppError
from app.services import zjuers
from tests.conftest import DEFAULT_PASSWORD, create_zj_user_direct

LOGIN_URL = "/api/v1/zj/auth/login"


@pytest.fixture(autouse=True)
def _clear_failures():
    zjuers.reset_failures()
    yield
    zjuers.reset_failures()


def test_login_returns_token_and_quota(client, database) -> None:
    create_zj_user_direct("zju01", quota_total=8)

    response = client.post(LOGIN_URL, json={"username": "zju01", "password": DEFAULT_PASSWORD})

    assert response.status_code == 200
    body = response.json()
    assert body["user"]["username"] == "zju01"
    assert body["user"]["quota"] == {"total": 8, "used": 0, "remaining": 8}
    assert body["access_token"]

    me = client.get(
        "/api/v1/zj/auth/me",
        headers={"Authorization": f"Bearer {body['access_token']}"},
    )
    assert me.status_code == 200
    assert me.json()["quota"]["remaining"] == 8


def test_wrong_password_is_rejected(client, database) -> None:
    create_zj_user_direct("zju01")

    response = client.post(LOGIN_URL, json={"username": "zju01", "password": "WrongPass1"})

    assert response.status_code == 401
    assert "密码" in response.json()["detail"]


def test_failed_logins_are_rate_limited(client, database) -> None:
    create_zj_user_direct("zju01")

    for _ in range(5):
        client.post(LOGIN_URL, json={"username": "zju01", "password": "WrongPass1"})

    blocked = client.post(LOGIN_URL, json={"username": "zju01", "password": "WrongPass1"})
    assert blocked.status_code == 429


def test_inactive_account_cannot_login(client, database) -> None:
    create_zj_user_direct("zju01", is_active=False)

    response = client.post(LOGIN_URL, json={"username": "zju01", "password": DEFAULT_PASSWORD})

    assert response.status_code == 401
    assert "停用" in response.json()["detail"]


def test_ledger_token_cannot_call_zj_api(client, admin) -> None:
    response = client.get("/api/v1/zj/auth/me", headers=admin["headers"])
    assert response.status_code == 401


def test_zj_token_cannot_call_ledger_api(client, zj_user) -> None:
    assert client.get("/api/v1/auth/me", headers=zj_user["headers"]).status_code == 401
    assert client.get("/api/v1/players", headers=zj_user["headers"]).status_code == 401
    assert client.get("/api/v1/overview", headers=zj_user["headers"]).status_code == 401


def test_password_change_invalidates_old_token(client, database) -> None:
    zj = create_zj_user_direct("zju01")

    changed = client.post(
        "/api/v1/zj/auth/password",
        json={"old_password": DEFAULT_PASSWORD, "new_password": "NewPassw0rd9"},
        headers=zj["headers"],
    )
    assert changed.status_code == 204

    stale = client.get("/api/v1/zj/auth/me", headers=zj["headers"])
    assert stale.status_code == 401

    relogin = client.post(LOGIN_URL, json={"username": "zju01", "password": "NewPassw0rd9"})
    assert relogin.status_code == 200


def test_change_password_checks_old_password(client, zj_user) -> None:
    response = client.post(
        "/api/v1/zj/auth/password",
        json={"old_password": "NotMyPass1", "new_password": "NewPassw0rd9"},
        headers=zj_user["headers"],
    )
    assert response.status_code == 400
    assert "原密码" in response.json()["detail"]


def test_duplicate_username_is_rejected(database) -> None:
    create_zj_user_direct("zju01")

    with pytest.raises(AppError) as exc:
        with dbmod.write_session() as session:
            zjuers.create_user(session, username="zju01", password="Passw0rd123")

    assert "已存在" in str(exc.value)
