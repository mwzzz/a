"""权限矩阵。"""

from __future__ import annotations

from tests.test_players import add_money, new_player


def test_unauthenticated_calls_are_401(client) -> None:
    checks = [
        ("get", "/api/v1/players"),
        ("get", "/api/v1/batches"),
        ("get", "/api/v1/records/deposits"),
        ("get", "/api/v1/overview"),
        ("post", "/api/v1/batches"),
        ("post", "/api/v1/transfers"),
    ]
    for method, path in checks:
        if method == "post":
            response = client.post(path, json={})
        else:
            response = client.get(path)
        assert response.status_code in (401, 422), (method, path, response.status_code)


def test_staff_can_do_money_operations(client, admin_headers, staff_headers) -> None:
    player = new_player(client, admin_headers, "店员能操作")
    pid = player["id"]
    assert client.post(
        f"/api/v1/players/{pid}/deposits",
        json={"amount_cents": 1000},
        headers=staff_headers,
    ).status_code == 201
    assert client.post(
        f"/api/v1/players/{pid}/refunds",
        json={"amount_cents": 200},
        headers=staff_headers,
    ).status_code == 201
    assert client.post(
        f"/api/v1/players/{pid}/deductions",
        json={"amount_cents": 100},
        headers=staff_headers,
    ).status_code == 201

    other = new_player(client, admin_headers, "店员划转目标")
    assert client.post(
        "/api/v1/transfers",
        json={"from_player_id": pid, "to_player_id": other["id"], "amount_cents": 100},
        headers=staff_headers,
    ).status_code == 201


def test_staff_can_create_and_edit_player(client, staff_headers) -> None:
    created = client.post(
        "/api/v1/players", json={"game_id": "店员建的"}, headers=staff_headers
    )
    assert created.status_code == 201
    pid = created.json()["id"]
    assert client.patch(
        f"/api/v1/players/{pid}", json={"remark": "改备注"}, headers=staff_headers
    ).status_code == 200


def test_staff_cannot_change_settings(client, staff_headers) -> None:
    response = client.patch(
        "/api/v1/settings", json={"last_tea_cents": 999}, headers=staff_headers
    )
    assert response.status_code == 403


def test_staff_cannot_reconcile(client, staff_headers) -> None:
    assert client.get("/api/v1/reconcile", headers=staff_headers).status_code == 403


def test_staff_can_read_settings(client, staff_headers) -> None:
    response = client.get("/api/v1/settings", headers=staff_headers)
    assert response.status_code == 200
    assert response.json()["last_tea_cents"] == 200


def test_admin_can_update_settings(client, admin_headers) -> None:
    response = client.patch(
        "/api/v1/settings",
        json={"last_tea_cents": 300, "deposit_low_cents": 2000, "deposit_high_cents": 5000},
        headers=admin_headers,
    )
    assert response.status_code == 200
    assert response.json()["last_tea_cents"] == 300
    assert response.json()["deposit_low_cents"] == 2000


def test_settings_reject_bad_thresholds(client, admin_headers) -> None:
    response = client.patch(
        "/api/v1/settings",
        json={"deposit_low_cents": 6000, "deposit_high_cents": 3000},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "上限" in response.json()["detail"]


def test_admin_reconcile_ok(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "对账哥")
    add_money(client, admin_headers, player["id"], 500)
    body = client.get("/api/v1/reconcile", headers=admin_headers).json()
    assert body["ok"] is True
    assert body["problems"] == []
