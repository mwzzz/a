"""账号管理的权限与约束。"""

from __future__ import annotations

from tests.conftest import DEFAULT_PASSWORD


def test_staff_cannot_create_user(client, staff_headers) -> None:
    response = client.post(
        "/api/v1/users",
        json={"username": "newbie", "password": DEFAULT_PASSWORD, "role": "staff"},
        headers=staff_headers,
    )
    assert response.status_code == 403


def test_admin_creates_staff(client, admin_headers) -> None:
    response = client.post(
        "/api/v1/users",
        json={
            "username": "XiaoMei",
            "password": DEFAULT_PASSWORD,
            "display_name": "小美",
            "role": "staff",
        },
        headers=admin_headers,
    )
    assert response.status_code == 201
    body = response.json()
    assert body["username"] == "xiaomei"
    assert body["role"] == "staff"
    assert body["display_name"] == "小美"

    listed = client.get("/api/v1/users", headers=admin_headers).json()
    assert {item["username"] for item in listed} >= {"xiaomei"}


def test_duplicate_username_rejected(client, admin_headers) -> None:
    payload = {"username": "sameone", "password": DEFAULT_PASSWORD, "role": "staff"}
    assert client.post("/api/v1/users", json=payload, headers=admin_headers).status_code == 201
    again = client.post("/api/v1/users", json=payload, headers=admin_headers)
    assert again.status_code == 400
    assert "已存在" in again.json()["detail"]


def test_invalid_username_rejected(client, admin_headers) -> None:
    response = client.post(
        "/api/v1/users",
        json={"username": "中文名", "password": DEFAULT_PASSWORD, "role": "staff"},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_admin_cannot_disable_self(client, admin_headers, admin) -> None:
    response = client.patch(
        f"/api/v1/users/{admin['id']}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "自己" in response.json()["detail"]


def test_last_admin_cannot_be_demoted(client, admin_headers, admin) -> None:
    response = client.patch(
        f"/api/v1/users/{admin['id']}",
        json={"role": "staff"},
        headers=admin_headers,
    )
    assert response.status_code == 400


def test_reset_password_invalidates_token(client, admin_headers, staff) -> None:
    response = client.post(
        f"/api/v1/users/{staff['id']}/password",
        json={"new_password": "ResetPass123"},
        headers=admin_headers,
    )
    assert response.status_code == 204
    me = client.get("/api/v1/auth/me", headers=staff["headers"])
    assert me.status_code == 401

    login = client.post(
        "/api/v1/auth/login",
        json={"username": staff["username"], "password": "ResetPass123"},
    )
    assert login.status_code == 200


def test_staff_cannot_list_users(client, staff_headers) -> None:
    assert client.get("/api/v1/users", headers=staff_headers).status_code == 403
