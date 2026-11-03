"""保管人、交班现金拆分、操作人统计与分红。"""

from __future__ import annotations

from tests.conftest import close_batch
from tests.test_players import add_money, new_player
from tests.test_sessions import create_session, open_batch


def _session(client, headers, batch_id: int, player_ids: list[int], tea: int):
    return create_session(client, headers, batch_id, player_ids, tea=tea)


def test_current_cash_is_deposit_plus_tea(client, admin_headers, admin) -> None:
    batch_id = open_batch(client, admin_headers)
    player = new_player(client, admin_headers, "现金哥")
    add_money(client, admin_headers, player["id"], 1000)
    peer = new_player(client, admin_headers, "陪打")["id"]
    _session(client, admin_headers, batch_id, [player["id"], peer], tea=100)

    body = client.get("/api/v1/batches/current", headers=admin_headers).json()
    custody = body["custody"]
    assert custody["holder"]["id"] == admin["id"]
    assert custody["deposit_cents"] == 800
    assert custody["tea_cents"] == 200
    assert custody["amount_cents"] == 1000


def test_close_splits_tea_and_deposit(
    client, admin_headers, staff_headers, admin, staff
) -> None:
    batch_id = open_batch(client, admin_headers)
    player = new_player(client, admin_headers, "交班哥")
    add_money(client, admin_headers, player["id"], 1000)
    peer = new_player(client, admin_headers, "交班弟")["id"]
    _session(client, admin_headers, batch_id, [player["id"], peer], tea=100)

    response = close_batch(
        client,
        batch_id,
        admin_headers,
        tea_to_id=admin["id"],
        deposit_to_id=staff["id"],
    )
    assert response.status_code == 200, response.text
    summary = response.json()
    assert summary["deposit_total_cents"] == 800
    assert summary["tea_total_cents"] == 200

    detail = client.get(f"/api/v1/batches/{batch_id}", headers=admin_headers).json()
    handover = detail["handover"]
    assert handover["from"]["id"] == admin["id"]
    assert handover["tea_to"]["id"] == admin["id"]
    assert handover["deposit_to"]["id"] == staff["id"]
    assert handover["deposit_cents"] == 800
    assert handover["tea_cents"] == 200

    current = client.get("/api/v1/batches/current", headers=admin_headers).json()
    assert current["batch"] is None
    assert current["custody"]["holder"]["id"] == staff["id"]
    assert current["custody"]["amount_cents"] == 800
    assert current["custody"]["tea_cents"] == 0


def test_tea_recipient_must_be_admin(client, admin_headers, staff, staff_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    # 当前保管人是 admin，先让 admin 尝试把茶水上缴给店员
    response = close_batch(
        client,
        batch_id,
        admin_headers,
        tea_to_id=staff["id"],
        deposit_to_id=staff["id"],
    )
    assert response.status_code == 400
    assert "管理员" in response.json()["detail"]


def test_only_current_holder_can_close(
    client, admin_headers, staff_headers, admin
) -> None:
    batch_id = open_batch(client, admin_headers)
    response = close_batch(
        client,
        batch_id,
        staff_headers,
        tea_to_id=admin["id"],
        deposit_to_id=admin["id"],
    )
    assert response.status_code == 400
    assert "保管人" in response.json()["detail"]


def test_operator_stats_and_dividend(client, admin_headers, staff_headers, admin, staff) -> None:
    batch_id = open_batch(client, admin_headers)
    players = [new_player(client, admin_headers, f"统计{i}")["id"] for i in range(4)]
    _session(client, admin_headers, batch_id, players[:2], tea=100)  # admin: 1局 2人次 200分
    _session(client, staff_headers, batch_id, players[2:], tea=250)  # staff: 1局 2人次 500分

    detail = client.get(f"/api/v1/batches/{batch_id}", headers=admin_headers).json()
    assert detail["dividend_rate_percent"] == 50
    rows = {row["user"]["id"]: row for row in detail["operators"]}
    assert rows[admin["id"]]["session_count"] == 1
    assert rows[admin["id"]]["player_times"] == 2
    assert rows[admin["id"]]["tea_cents"] == 200
    assert rows[admin["id"]]["dividend_cents"] == 100
    assert rows[staff["id"]]["tea_cents"] == 500
    assert rows[staff["id"]]["dividend_cents"] == 250


def test_dividend_rate_is_snapshotted_at_close(client, admin_headers) -> None:
    updated = client.patch(
        "/api/v1/settings", json={"dividend_rate_percent": 30}, headers=admin_headers
    )
    assert updated.status_code == 200
    assert updated.json()["dividend_rate_percent"] == 30

    batch_id = open_batch(client, admin_headers)
    player = new_player(client, admin_headers, "分红哥")["id"]
    _session(client, admin_headers, batch_id, [player], tea=500)

    open_detail = client.get(f"/api/v1/batches/{batch_id}", headers=admin_headers).json()
    assert open_detail["operators"][0]["dividend_cents"] == 150

    assert close_batch(client, batch_id, admin_headers).status_code == 200

    client.patch(
        "/api/v1/settings", json={"dividend_rate_percent": 80}, headers=admin_headers
    )
    closed = client.get(f"/api/v1/batches/{batch_id}", headers=admin_headers).json()
    assert closed["dividend_rate_percent"] == 30
    assert closed["operators"][0]["dividend_cents"] == 150


def test_rate_out_of_range_rejected(client, admin_headers) -> None:
    response = client.patch(
        "/api/v1/settings", json={"dividend_rate_percent": 101}, headers=admin_headers
    )
    assert response.status_code == 422


def test_cannot_disable_current_holder(
    client, admin_headers, staff_headers, admin, staff
) -> None:
    batch_id = open_batch(client, admin_headers)
    player = new_player(client, admin_headers, "停用测试")["id"]
    add_money(client, admin_headers, player, 1000)
    assert (
        close_batch(
            client,
            batch_id,
            admin_headers,
            tea_to_id=admin["id"],
            deposit_to_id=staff["id"],
        ).status_code
        == 200
    )

    # 现在店员是保管人，管理员不能直接停用
    response = client.patch(
        f"/api/v1/users/{staff['id']}",
        json={"is_active": False},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "现金" in response.json()["detail"]


def test_close_with_same_person_keeps_custody(client, admin_headers, admin) -> None:
    batch_id = open_batch(client, admin_headers)
    player = new_player(client, admin_headers, "自己保管")["id"]
    add_money(client, admin_headers, player, 500)
    response = close_batch(client, batch_id, admin_headers)
    assert response.status_code == 200
    current = client.get("/api/v1/batches/current", headers=admin_headers).json()
    assert current["custody"]["holder"]["id"] == admin["id"]
    assert current["custody"]["amount_cents"] == 500


def test_overview_shows_batch_stats_not_today(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    player = new_player(client, admin_headers, "总览本班")["id"]
    add_money(client, admin_headers, player, 1000)
    _session(client, admin_headers, batch_id, [player], tea=200)
    body = client.get("/api/v1/overview", headers=admin_headers).json()
    assert body["open_batch"]["summary"]["tea_total_cents"] == 200
    assert body["open_batch"]["summary"]["session_count"] == 1
    assert body["open_batch"]["operators"][0]["tea_cents"] == 200
    assert body["custody"]["amount_cents"] == 1000
    assert "today" not in body
