"""平台侧查战绩配额：权限、建号、加减次数、启停、重置密码、流水。"""

from __future__ import annotations

BASE = "/api/v1/platform/zj"
STRONG_PASSWORD = "Passw0rd123"


def _create(client, headers, username: str = "zju01", quota: int = 20) -> dict:
    response = client.post(
        f"{BASE}/users",
        json={
            "username": username,
            "password": STRONG_PASSWORD,
            "display_name": "阿伟",
            "note": "老客户",
            "quota_total": quota,
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def test_requires_superadmin(client, admin) -> None:
    assert client.get(f"{BASE}/users", headers=admin["headers"]).status_code == 403


def test_create_and_list_accounts(client, superadmin_headers) -> None:
    row = _create(client, superadmin_headers)

    assert row["quota_total"] == 20
    assert row["quota_remaining"] == 20
    assert row["is_active"] is True

    listing = client.get(f"{BASE}/users", headers=superadmin_headers).json()
    assert listing["overview"]["users"] == 1
    assert listing["overview"]["remaining"] == 20
    assert listing["users"][0]["username"] == "zju01"


def test_duplicate_username_is_rejected(client, superadmin_headers) -> None:
    _create(client, superadmin_headers)

    duplicate = client.post(
        f"{BASE}/users",
        json={"username": "zju01", "password": STRONG_PASSWORD, "quota_total": 5},
        headers=superadmin_headers,
    )

    assert duplicate.status_code == 400
    assert "已存在" in duplicate.json()["detail"]


def test_weak_password_is_rejected(client, superadmin_headers) -> None:
    response = client.post(
        f"{BASE}/users",
        json={"username": "zju02", "password": "abcdefgh", "quota_total": 5},
        headers=superadmin_headers,
    )

    assert response.status_code == 400
    assert "数字" in response.json()["detail"]


def test_grant_and_reduce_quota(client, superadmin_headers, zj_user) -> None:
    added = client.post(
        f"{BASE}/users/{zj_user['id']}/quota",
        json={"delta": 50, "note": "首充"},
        headers=superadmin_headers,
    )
    assert added.status_code == 200
    assert added.json()["user"]["quota_total"] == 60

    reduced = client.post(
        f"{BASE}/users/{zj_user['id']}/quota",
        json={"delta": -10},
        headers=superadmin_headers,
    )
    assert reduced.status_code == 200
    assert reduced.json()["user"]["quota_total"] == 50

    too_low = client.post(
        f"{BASE}/users/{zj_user['id']}/quota",
        json={"delta": -99999},
        headers=superadmin_headers,
    )
    assert too_low.status_code == 400


def test_disable_account_blocks_login(client, superadmin_headers, zj_user) -> None:
    patched = client.patch(
        f"{BASE}/users/{zj_user['id']}",
        json={"is_active": False, "note": "暂停使用"},
        headers=superadmin_headers,
    )
    assert patched.status_code == 200
    assert patched.json()["is_active"] is False
    assert patched.json()["note"] == "暂停使用"

    login = client.post(
        "/api/v1/zj/auth/login",
        json={"username": zj_user["username"], "password": zj_user["password"]},
    )
    assert login.status_code == 401


def test_reset_password_invalidates_token(client, superadmin_headers, zj_user) -> None:
    reset = client.post(
        f"{BASE}/users/{zj_user['id']}/password",
        json={"new_password": "BrandNew123"},
        headers=superadmin_headers,
    )
    assert reset.status_code == 204

    stale = client.get("/api/v1/zj/auth/me", headers=zj_user["headers"])
    assert stale.status_code == 401

    login = client.post(
        "/api/v1/zj/auth/login",
        json={"username": zj_user["username"], "password": "BrandNew123"},
    )
    assert login.status_code == 200


def test_logs_include_grants(client, superadmin_headers, zj_user) -> None:
    client.post(
        f"{BASE}/users/{zj_user['id']}/quota",
        json={"delta": 5, "note": "补 5 次"},
        headers=superadmin_headers,
    )

    logs = client.get(
        f"{BASE}/users/{zj_user['id']}/logs", headers=superadmin_headers
    ).json()

    assert logs["items"][0]["type"] == "grant"
    assert logs["items"][0]["delta"] == 5
    assert logs["items"][0]["note"] == "补 5 次"
    assert logs["items"][0]["operator"] == "开发者"
