"""多商家隔离：越权一律 404，写入不能串店，汇总与对账互不影响。"""

from __future__ import annotations

from sqlalchemy import text

from app import db as dbmod
from app.models import Merchant
from app.timeutil import now_text
from tests.test_players import add_money, new_player
from tests.test_sessions import create_session


def test_player_isolated_between_merchants(client, admin_headers, admin_b_headers) -> None:
    player = new_player(client, admin_headers, "跨店玩家")
    add_money(client, admin_headers, player["id"], 1000)

    assert client.get(f"/api/v1/players/{player['id']}", headers=admin_b_headers).status_code == 404
    assert (
        client.get(
            f"/api/v1/players/{player['id']}/ledger", headers=admin_b_headers
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/players/{player['id']}",
            json={"remark": "越权修改"},
            headers=admin_b_headers,
        ).status_code
        == 404
    )
    assert client.delete(f"/api/v1/players/{player['id']}", headers=admin_b_headers).status_code == 404

    listed = client.get("/api/v1/players", headers=admin_b_headers).json()
    assert listed["total"] == 0
    assert listed["items"] == []

    options = client.get("/api/v1/players/options", headers=admin_b_headers).json()
    assert options == []

    detail = client.get(f"/api/v1/players/{player['id']}", headers=admin_headers).json()
    assert detail["deposit_cents"] == 1000
    assert detail["remark"] != "越权修改"


def test_same_game_id_allowed_in_two_merchants(
    client, admin_headers, admin_b_headers
) -> None:
    first = new_player(client, admin_headers, "同名玩家")
    second = new_player(client, admin_b_headers, "同名玩家")
    assert first["id"] != second["id"]

    duplicate = client.post(
        "/api/v1/players", json={"game_id": "同名玩家"}, headers=admin_headers
    )
    assert duplicate.status_code == 400
    assert "已存在" in duplicate.json()["detail"]


def test_cannot_write_to_other_merchant_player(
    client, admin_headers, admin_b_headers
) -> None:
    player = new_player(client, admin_headers, "受害玩家")
    add_money(client, admin_headers, player["id"], 1000)

    for path, payload in (
        (f"/api/v1/players/{player['id']}/deposits", {"amount_cents": 500}),
        (f"/api/v1/players/{player['id']}/refunds", {"amount_cents": 100}),
    ):
        response = client.post(path, json=payload, headers=admin_b_headers)
        assert response.status_code == 404, response.text

    detail = client.get(f"/api/v1/players/{player['id']}", headers=admin_headers).json()
    assert detail["deposit_cents"] == 1000
    assert detail["games_played"] == 0


def test_transfer_must_stay_inside_one_merchant(
    client, admin_headers, admin_b_headers
) -> None:
    source = new_player(client, admin_headers, "甲店玩家")
    target = new_player(client, admin_b_headers, "乙店玩家")
    add_money(client, admin_headers, source["id"], 1000)
    add_money(client, admin_b_headers, target["id"], 1000)

    response = client.post(
        "/api/v1/transfers",
        json={
            "from_player_id": source["id"],
            "to_player_id": target["id"],
            "amount_cents": 100,
        },
        headers=admin_b_headers,
    )
    assert response.status_code == 404, response.text

    source_detail = client.get(
        f"/api/v1/players/{source['id']}", headers=admin_headers
    ).json()
    target_detail = client.get(
        f"/api/v1/players/{target['id']}", headers=admin_b_headers
    ).json()
    assert source_detail["deposit_cents"] == 1000
    assert target_detail["deposit_cents"] == 1000


def test_sessions_isolated(client, admin_headers, admin_b_headers) -> None:
    player = new_player(client, admin_headers, "甲店玩家")
    session = create_session(client, admin_headers, 0, [player["id"]], tea=100)

    assert client.get(f"/api/v1/sessions/{session['id']}", headers=admin_b_headers).status_code == 404

    cross = client.post(
        "/api/v1/sessions",
        json={"tea_fee_cents": 100, "player_ids": [player["id"]]},
        headers=admin_b_headers,
    )
    assert cross.status_code == 404, cross.text

    preview = client.post(
        "/api/v1/sessions/preview",
        json={"player_ids": [player["id"]], "tea_fee_cents": 100},
        headers=admin_b_headers,
    )
    assert preview.status_code == 404, preview.text

    detail = client.get(f"/api/v1/sessions/{session['id']}", headers=admin_headers).json()
    assert detail["player_count"] == 1


def test_records_and_overview_isolated(
    client, admin_headers, admin_b_headers
) -> None:
    player = new_player(client, admin_headers, "甲店流水")
    add_money(client, admin_headers, player["id"], 1000)
    create_session(client, admin_headers, 0, [player["id"]], tea=200)

    other = new_player(client, admin_b_headers, "乙店流水")
    add_money(client, admin_b_headers, other["id"], 5000)

    deposits = client.get("/api/v1/records/deposits", headers=admin_b_headers).json()
    assert deposits["total"] == 1
    assert deposits["items"][0]["player"]["game_id"] == "乙店流水"

    overview = client.get("/api/v1/overview", headers=admin_b_headers).json()
    assert overview["player_count"] == 1
    assert overview["total_deposit_cents"] == 5000
    assert overview["today"]["add_deposit_cents"] == 5000
    assert overview["today"]["session_count"] == 0
    assert overview["recent_records"][0]["player"]["game_id"] == "乙店流水"

    sessions = client.get("/api/v1/records/sessions", headers=admin_b_headers).json()
    assert sessions["total"] == 0


def test_transfer_group_isolated(client, admin_headers, admin_b_headers) -> None:
    source = new_player(client, admin_headers, "甲店转出")
    target = new_player(client, admin_headers, "甲店转入")
    add_money(client, admin_headers, source["id"], 1000)
    body = client.post(
        "/api/v1/transfers",
        json={
            "from_player_id": source["id"],
            "to_player_id": target["id"],
            "amount_cents": 300,
        },
        headers=admin_headers,
    ).json()

    assert (
        client.get(
            f"/api/v1/records/transfers/{body['group_id']}", headers=admin_b_headers
        ).status_code
        == 404
    )
    detail = client.get(
        f"/api/v1/records/transfers/{body['group_id']}", headers=admin_headers
    ).json()
    assert len(detail["entries"]) == 2


def test_accounts_isolated(client, admin_headers, admin_b_headers, staff) -> None:
    accounts = client.get("/api/v1/users", headers=admin_b_headers).json()
    assert [row["username"] for row in accounts] == ["zz-boss"]

    assert (
        client.post(
            f"/api/v1/users/{staff['id']}/password",
            json={"new_password": "Newpass123"},
            headers=admin_b_headers,
        ).status_code
        == 404
    )
    assert (
        client.patch(
            f"/api/v1/users/{staff['id']}",
            json={"is_active": False},
            headers=admin_b_headers,
        ).status_code
        == 404
    )

    own = client.post(
        "/api/v1/users",
        json={"username": "zz-02", "password": "Passw0rd123", "role": "staff"},
        headers=admin_b_headers,
    )
    assert own.status_code == 201, own.text
    assert own.json()["merchant_id"] == client.get(
        "/api/v1/auth/me", headers=admin_b_headers
    ).json()["merchant_id"]


def test_me_returns_merchant(client, admin_headers, admin) -> None:
    body = client.get("/api/v1/auth/me", headers=admin_headers).json()
    assert body["merchant"]["id"] == admin["merchant_id"]
    assert body["merchant"]["name"] == admin["merchant_name"]


def test_merchant_disabled_blocks_login_and_existing_token(
    client, admin, admin_headers
) -> None:
    with dbmod.write_session() as session:
        merchant = session.get(Merchant, admin["merchant_id"])
        assert merchant is not None
        merchant.status = "disabled"
        merchant.updated_at = now_text()

    assert client.get("/api/v1/overview", headers=admin_headers).status_code == 401

    response = client.post(
        "/api/v1/auth/login",
        json={"username": admin["username"], "password": admin["password"]},
    )
    assert response.status_code == 401
    assert "商家已停用" in response.json()["detail"]


def test_reconcile_and_close_scoped(client, admin_headers, admin_b_headers) -> None:
    broken = new_player(client, admin_headers, "甲店坏账")
    add_money(client, admin_headers, broken["id"], 100)
    with dbmod.write_session() as session:
        session.execute(
            text("UPDATE players SET deposit_cents = 9999 WHERE id = :pid"),
            {"pid": broken["id"]},
        )

    report_b = client.get("/api/v1/reconcile", headers=admin_b_headers).json()
    assert report_b["ok"] is True
    assert report_b["checked"] == 0

    report_a = client.get("/api/v1/reconcile", headers=admin_headers).json()
    assert report_a["ok"] is False
    assert len(report_a["problems"]) == 1
    assert report_a["problems"][0]["game_id"] == "甲店坏账"


def test_settings_isolated(client, admin_headers, admin_b_headers) -> None:
    response = client.patch(
        "/api/v1/settings",
        json={"shop_name": "甲店改名", "last_tea_cents": 300},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["shop_name"] == "甲店改名"

    other = client.get("/api/v1/settings", headers=admin_b_headers).json()
    assert other["shop_name"] == "蜘蛛电竞"
    assert other["last_tea_cents"] == 200

    clash = client.patch(
        "/api/v1/settings",
        json={"shop_name": "甲店改名"},
        headers=admin_b_headers,
    )
    assert clash.status_code == 400
    assert "已被占用" in clash.json()["detail"]
