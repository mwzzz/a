"""开发者控制台：跨商家管理商家与账号，同时守住门店隔离。"""

from __future__ import annotations

from tests.conftest import DEFAULT_PASSWORD
from tests.test_players import new_player
from tests.test_sessions import create_session


def _new_merchant(
    client,
    headers,
    *,
    name: str = "极光电竞",
    admin_username: str = "jg-boss",
) -> dict:
    response = client.post(
        "/api/v1/platform/merchants",
        json={
            "name": name,
            "note": "测试开通",
            "admin_username": admin_username,
            "admin_password": DEFAULT_PASSWORD,
            "admin_display_name": "店长",
        },
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _login(client, username: str, password: str = DEFAULT_PASSWORD):
    return client.post(
        "/api/v1/auth/login", json={"username": username, "password": password}
    )


def test_superadmin_sees_all_merchants_but_not_platform(client, superadmin_headers) -> None:
    rows = client.get("/api/v1/platform/merchants", headers=superadmin_headers).json()
    assert [row["name"] for row in rows] == ["默认商家"]
    assert rows[0]["user_count"] == 0
    assert rows[0]["status"] == "active"

    me = client.get("/api/v1/auth/me", headers=superadmin_headers).json()
    assert me["is_superadmin"] is True
    assert me["is_admin"] is False


def test_merchant_admin_cannot_use_platform(client, admin_headers) -> None:
    assert client.get("/api/v1/platform/merchants", headers=admin_headers).status_code == 403


def test_create_merchant_with_admin_then_login(client, superadmin_headers) -> None:
    body = _new_merchant(client, superadmin_headers)
    merchant = body["merchant"]
    assert merchant["name"] == "极光电竞"
    assert merchant["user_count"] == 1
    assert body["admin"]["username"] == "jg-boss"
    assert body["admin"]["role"] == "admin"
    assert body["admin"]["is_superadmin"] is False

    login = _login(client, "jg-boss")
    assert login.status_code == 200, login.text
    token = login.json()["access_token"]
    staff_headers = {"Authorization": f"Bearer {token}"}

    me = client.get("/api/v1/auth/me", headers=staff_headers).json()
    assert me["merchant"]["name"] == "极光电竞"
    assert me["is_admin"] is True
    assert client.get("/api/v1/overview", headers=staff_headers).status_code == 200

    listed = client.get("/api/v1/platform/merchants", headers=superadmin_headers).json()
    assert {row["name"] for row in listed} == {"默认商家", "极光电竞"}


def test_create_merchant_validation(client, superadmin_headers) -> None:
    duplicate = client.post(
        "/api/v1/platform/merchants",
        json={"name": "默认商家"},
        headers=superadmin_headers,
    )
    assert duplicate.status_code == 400
    assert "占用" in duplicate.json()["detail"]

    missing_password = client.post(
        "/api/v1/platform/merchants",
        json={"name": "只有用户名", "admin_username": "only-name"},
        headers=superadmin_headers,
    )
    assert missing_password.status_code == 400

    weak = client.post(
        "/api/v1/platform/merchants",
        json={
            "name": "弱密码店",
            "admin_username": "weak-boss",
            "admin_password": "12345678",
        },
        headers=superadmin_headers,
    )
    assert weak.status_code == 400
    assert "字母" in weak.json()["detail"]

    # 事务整体回滚：商家名不应该被占用
    assert (
        client.post(
            "/api/v1/platform/merchants",
            json={"name": "弱密码店"},
            headers=superadmin_headers,
        ).status_code
        == 201
    )


def test_username_is_globally_unique(client, superadmin_headers, admin) -> None:
    response = client.post(
        "/api/v1/platform/merchants",
        json={
            "name": "重名店",
            "admin_username": admin["username"],
            "admin_password": DEFAULT_PASSWORD,
        },
        headers=superadmin_headers,
    )
    assert response.status_code == 400
    assert "已存在" in response.json()["detail"]


def test_manage_staff_accounts_across_merchants(client, superadmin_headers) -> None:
    merchant = _new_merchant(client, superadmin_headers)["merchant"]
    merchant_id = merchant["id"]

    users = client.get(
        f"/api/v1/platform/merchants/{merchant_id}/users", headers=superadmin_headers
    ).json()
    assert [row["username"] for row in users] == ["jg-boss"]

    created = client.post(
        f"/api/v1/platform/merchants/{merchant_id}/users",
        json={
            "username": "JG-01",
            "password": DEFAULT_PASSWORD,
            "display_name": "小美",
            "role": "staff",
        },
        headers=superadmin_headers,
    )
    assert created.status_code == 201, created.text
    staff = created.json()
    assert staff["username"] == "jg-01"
    assert staff["merchant_id"] == merchant_id

    staff_login = _login(client, "jg-01")
    assert staff_login.status_code == 200
    staff_headers = {"Authorization": f"Bearer {staff_login.json()['access_token']}"}
    assert client.get("/api/v1/overview", headers=staff_headers).status_code == 200

    renamed = client.patch(
        f"/api/v1/platform/users/{staff['id']}",
        json={"display_name": "小美2", "role": "admin"},
        headers=superadmin_headers,
    )
    assert renamed.status_code == 200
    assert renamed.json()["display_name"] == "小美2"
    assert renamed.json()["role"] == "admin"

    reset = client.post(
        f"/api/v1/platform/users/{staff['id']}/password",
        json={"new_password": "ResetPass123"},
        headers=superadmin_headers,
    )
    assert reset.status_code == 204
    assert client.get("/api/v1/overview", headers=staff_headers).status_code == 401
    assert _login(client, "jg-01", "ResetPass123").status_code == 200


def test_superadmin_can_disable_merchant_and_account(client, superadmin_headers) -> None:
    body = _new_merchant(client, superadmin_headers, name="会停用的店", admin_username="stop-boss")
    merchant_id = body["merchant"]["id"]

    created = client.post(
        f"/api/v1/platform/merchants/{merchant_id}/users",
        json={"username": "stop-01", "password": DEFAULT_PASSWORD, "role": "staff"},
        headers=superadmin_headers,
    )
    assert created.status_code == 201
    staff_id = created.json()["id"]
    assert _login(client, "stop-01").status_code == 200

    assert (
        client.patch(
            f"/api/v1/platform/users/{staff_id}",
            json={"is_active": False},
            headers=superadmin_headers,
        ).status_code
        == 200
    )
    assert _login(client, "stop-01").status_code == 401

    client.patch(
        f"/api/v1/platform/users/{staff_id}",
        json={"is_active": True},
        headers=superadmin_headers,
    )
    login = _login(client, "stop-boss")
    assert login.status_code == 200
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    assert client.get("/api/v1/overview", headers=headers).status_code == 200

    disabled = client.patch(
        f"/api/v1/platform/merchants/{merchant_id}",
        json={"status": "disabled"},
        headers=superadmin_headers,
    )
    assert disabled.status_code == 200
    assert disabled.json()["status"] == "disabled"
    assert client.get("/api/v1/overview", headers=headers).status_code == 401
    assert "商家已停用" in _login(client, "stop-boss").json()["detail"]

    client.patch(
        f"/api/v1/platform/merchants/{merchant_id}",
        json={"status": "active"},
        headers=superadmin_headers,
    )
    assert _login(client, "stop-boss").status_code == 200


def test_last_admin_cannot_be_demoted_by_superadmin(client, superadmin_headers) -> None:
    body = _new_merchant(client, superadmin_headers, name="独苗店", admin_username="solo-boss")
    admin_id = body["admin"]["id"]

    demote = client.patch(
        f"/api/v1/platform/users/{admin_id}",
        json={"role": "staff"},
        headers=superadmin_headers,
    )
    assert demote.status_code == 400
    assert "管理员" in demote.json()["detail"]

    add = client.post(
        f"/api/v1/platform/merchants/{body['merchant']['id']}/users",
        json={
            "username": "solo-02",
            "password": DEFAULT_PASSWORD,
            "role": "admin",
        },
        headers=superadmin_headers,
    )
    assert add.status_code == 201
    assert (
        client.patch(
            f"/api/v1/platform/users/{admin_id}",
            json={"role": "staff"},
            headers=superadmin_headers,
        ).status_code
        == 200
    )


def test_superadmin_account_is_untouchable(client, superadmin_headers, superadmin, admin_headers) -> None:
    # 门店管理员改不了超管，也看不到
    assert (
        client.patch(
            f"/api/v1/users/{superadmin['id']}",
            json={"is_active": False},
            headers=admin_headers,
        ).status_code
        == 404
    )
    listed = client.get("/api/v1/users", headers=admin_headers).json()
    assert superadmin["id"] not in {row["id"] for row in listed}

    # 平台接口也不允许改超管自己（密码走「修改密码」）
    assert (
        client.patch(
            f"/api/v1/platform/users/{superadmin['id']}",
            json={"is_active": False},
            headers=superadmin_headers,
        ).status_code
        == 404
    )
    assert (
        client.post(
            f"/api/v1/platform/users/{superadmin['id']}/password",
            json={"new_password": "Another123"},
            headers=superadmin_headers,
        ).status_code
        == 404
    )
    # 平台商家本身也不能被停用/改名
    assert (
        client.patch(
            f"/api/v1/platform/merchants/{superadmin['merchant_id']}",
            json={"status": "disabled"},
            headers=superadmin_headers,
        ).status_code
        == 404
    )


def test_platform_scoped_to_merchant(client, superadmin_headers) -> None:
    first = _new_merchant(client, superadmin_headers, name="甲店", admin_username="a-boss")[
        "merchant"
    ]
    second = _new_merchant(client, superadmin_headers, name="乙店", admin_username="b-boss")[
        "merchant"
    ]

    first_users = client.get(
        f"/api/v1/platform/merchants/{first['id']}/users", headers=superadmin_headers
    ).json()
    second_users = client.get(
        f"/api/v1/platform/merchants/{second['id']}/users", headers=superadmin_headers
    ).json()
    assert {row["username"] for row in first_users} == {"a-boss"}
    assert {row["username"] for row in second_users} == {"b-boss"}

    assert (
        client.get(
            "/api/v1/platform/merchants/9999/users", headers=superadmin_headers
        ).status_code
        == 404
    )


# ---------------------------------------------------------------- 清空商家经营数据
def _seed_shop(client, headers, admin_id: int, *, tag: str = "极光") -> int:
    """造一条完整链路：玩家 + 押金 + 班次 + 一局 + 关班 + 分红结算。"""
    player = new_player(client, headers, f"{tag}玩家")["id"]
    client.post(
        f"/api/v1/players/{player}/deposits",
        json={"amount_cents": 1000, "note": "开卡"},
        headers=headers,
    )
    create_session(client, headers, 0, [player], tea=300)
    settle = client.post(
        "/api/v1/reports/dividends/settle",
        json={"user_ids": [admin_id]},
        headers=headers,
    )
    assert settle.status_code == 201, settle.text
    return 0


def _purge(client, headers, merchant_id: int, name: str, note: str = ""):
    return client.post(
        f"/api/v1/platform/merchants/{merchant_id}/purge",
        json={"confirm_name": name, "note": note},
        headers=headers,
    )


def test_purge_preview_shows_scope(client, superadmin_headers, admin_headers, admin) -> None:
    _seed_shop(client, admin_headers, admin["id"])
    preview = client.get(
        "/api/v1/platform/merchants/1/purge-preview", headers=superadmin_headers
    )
    assert preview.status_code == 200, preview.text
    body = preview.json()
    assert body["merchant"]["name"] == "默认商家"
    assert body["counts"]["players"] == 1
    assert body["counts"]["sessions"] == 1
    assert body["counts"]["settlements"] == 1
    assert body["counts"]["ledger"] >= 2
    assert body["deposit_total_cents"] == 700
    assert body["keep"] == {"accounts": True, "settings": True, "merchant": True}
    assert body["open_batch"] is None


def test_purge_requires_superadmin(client, admin_headers, admin) -> None:
    _seed_shop(client, admin_headers, admin["id"])
    assert (
        client.get(
            "/api/v1/platform/merchants/1/purge-preview", headers=admin_headers
        ).status_code
        == 403
    )
    assert _purge(client, admin_headers, 1, "默认商家").status_code == 403


def test_purge_rejects_wrong_name(client, superadmin_headers, admin_headers, admin) -> None:
    _seed_shop(client, admin_headers, admin["id"])
    response = _purge(client, superadmin_headers, 1, "默认商家 ")
    assert response.status_code == 200  # 首尾空格会被 strip

    _seed_shop(client, admin_headers, admin["id"])
    wrong = _purge(client, superadmin_headers, 1, "默认")
    assert wrong.status_code == 400
    assert "商家名不一致" in wrong.json()["detail"]
    still = client.get("/api/v1/players", headers=admin_headers).json()
    assert still["total"] >= 1


def test_purge_clears_target_and_keeps_everything_else(
    client, superadmin_headers, admin_headers, admin, admin_b_headers, admin_b, merchant_b
) -> None:
    _seed_shop(client, admin_headers, admin["id"], tag="极光")
    _seed_shop(client, admin_b_headers, admin_b["id"], tag="蜘蛛")

    response = _purge(client, superadmin_headers, 1, "默认商家", note="重来一季")
    assert response.status_code == 200, response.text
    body = response.json()
    assert body["counts"]["players"] == 1
    assert body["backup"].startswith("pre-purge-1-")
    assert body["backup"].endswith(".db")

    # 目标商家：业务数据清零，账号/设置/商家保留
    assert client.get("/api/v1/players", headers=admin_headers).json()["total"] == 0
    assert client.get("/api/v1/sessions", headers=admin_headers).json()["total"] == 0
    assert (
        client.get("/api/v1/reports/dividends/settlements", headers=admin_headers).json()[
            "total"
        ]
        == 0
    )
    assert client.get("/api/v1/users", headers=admin_headers).status_code == 200
    assert client.get("/api/v1/settings", headers=admin_headers).json()["shop_name"] == "默认商家"
    overview = client.get("/api/v1/overview", headers=admin_headers).json()
    assert overview["player_count"] == 0
    assert overview["total_deposit_cents"] == 0
    assert overview["today"]["session_count"] == 0
    assert client.get("/api/v1/reconcile", headers=admin_headers).json()["ok"] is True

    # 另一个商家完全没被碰
    other = client.get("/api/v1/players", headers=admin_b_headers).json()
    assert other["total"] == 1
    assert client.get("/api/v1/sessions", headers=admin_b_headers).json()["total"] == 1

    # 清空后可以直接开局
    fresh = new_player(client, admin_headers, "重新开始")["id"]
    session = create_session(client, admin_headers, 0, [fresh], tea=200)
    assert session["player_count"] == 1


def test_purge_writes_audit_and_backup(
    client, superadmin_headers, admin_headers, admin, database
) -> None:
    _seed_shop(client, admin_headers, admin["id"])
    assert _purge(client, superadmin_headers, 1, "默认商家").status_code == 200

    import sqlite3

    conn = sqlite3.connect(database)
    try:
        row = conn.execute(
            "SELECT action, detail, ip FROM audit_logs WHERE action='purge_merchant_data'"
        ).fetchone()
    finally:
        conn.close()
    assert row is not None
    assert "默认商家" in row[1]
    assert "pre-purge-1-" in row[1]
    assert row[2]  # 记录真实 IP

    backups = list(database.parent.glob("backups/pre-purge-1-*.db"))
    assert len(backups) == 1


def test_purge_rejects_platform_merchant(client, superadmin_headers, superadmin) -> None:
    platform_id = superadmin["merchant_id"]
    assert (
        client.get(
            f"/api/v1/platform/merchants/{platform_id}/purge-preview",
            headers=superadmin_headers,
        ).status_code
        == 404
    )
    assert _purge(client, superadmin_headers, platform_id, "平台管理").status_code == 404


def test_new_merchant_has_empty_tool_lists(client, superadmin_headers) -> None:
    _new_merchant(
        client,
        superadmin_headers,
        name="空白名单店",
        admin_username="blank-boss",
    )
    login = _login(client, "blank-boss")
    assert login.status_code == 200, login.text
    headers = {"Authorization": f"Bearer {login.json()['access_token']}"}
    payload = client.get("/api/v1/tools/name-lists", headers=headers).json()
    assert payload == {"lists": []}
