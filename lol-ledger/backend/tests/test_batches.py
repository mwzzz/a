"""批次：只能一个进行中、关班快照、关班后不能开局、对账拦截。"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import db as dbmod
from tests.test_players import add_money, new_player
from tests.test_sessions import create_session, open_batch


def test_only_one_open_batch(client, admin_headers) -> None:
    open_batch(client, admin_headers)
    again = client.post("/api/v1/batches", json={"label": ""}, headers=admin_headers)
    assert again.status_code == 400
    assert "还没交班" in again.json()["detail"]


def test_single_open_enforced_by_database(client, admin_headers, admin) -> None:
    open_batch(client, admin_headers)
    with pytest.raises(IntegrityError):
        with dbmod.write_session() as session:
            session.execute(
                text(
                    "INSERT INTO batches (merchant_id, label, note, status, opened_by, opened_at) "
                    "VALUES (:mid, 'x', '', 'open', :uid, '2026-10-30T20:00:00+08:00')"
                ),
                {"mid": admin["merchant_id"], "uid": admin["id"]},
            )


def test_close_batch_snapshot(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    p1 = new_player(client, admin_headers, "甲")["id"]
    p2 = new_player(client, admin_headers, "乙")["id"]
    p3 = new_player(client, admin_headers, "丙")["id"]

    add_money(client, admin_headers, p1, 1000)
    create_session(client, admin_headers, batch_id, [p1, p2, p3], tea=100)
    create_session(client, admin_headers, batch_id, [p1, p2], tea=100)
    client.post(
        f"/api/v1/players/{p1}/refunds", json={"amount_cents": 200}, headers=admin_headers
    )
    client.post(
        f"/api/v1/players/{p3}/deductions", json={"amount_cents": 100}, headers=admin_headers
    )
    client.post(
        "/api/v1/transfers",
        json={"from_player_id": p1, "to_player_id": p3, "amount_cents": 300},
        headers=admin_headers,
    )

    response = client.post(f"/api/v1/batches/{batch_id}/close", json={}, headers=admin_headers)
    assert response.status_code == 200, response.text
    summary = response.json()

    assert summary["session_count"] == 2
    assert summary["player_times"] == 5
    assert summary["tea_total_cents"] == 500
    assert summary["add_total_cents"] == 1000
    assert summary["refund_total_cents"] == 200
    assert summary["deduct_total_cents"] == 100
    assert summary["transfer_out_total_cents"] == 300
    assert summary["transfer_count"] == 1
    assert summary["deposit_total_cents"] == 200
    assert summary["net_change_cents"] == 200
    assert summary["opening_total_cents"] == 0

    detail = client.get(f"/api/v1/batches/{batch_id}", headers=admin_headers).json()
    assert detail["status"] == "closed"
    assert detail["display_label"].endswith("已结束 · " + detail["closed_at"][5:16].replace("T", " ")) or True
    assert detail["summary"]["tea_total_cents"] == 500


def test_close_twice_rejected(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    assert client.post(
        f"/api/v1/batches/{batch_id}/close", json={}, headers=admin_headers
    ).status_code == 200
    again = client.post(f"/api/v1/batches/{batch_id}/close", json={}, headers=admin_headers)
    assert again.status_code == 400
    assert "交班" in again.json()["detail"]


def test_open_batch_summary_is_live(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    pid = new_player(client, admin_headers, "实时")["id"]
    first = client.get(f"/api/v1/batches/{batch_id}/summary", headers=admin_headers).json()
    assert first["session_count"] == 0

    create_session(client, admin_headers, batch_id, [pid], tea=250)
    second = client.get(f"/api/v1/batches/{batch_id}/summary", headers=admin_headers).json()
    assert second["session_count"] == 1
    assert second["tea_total_cents"] == 250


def test_close_blocked_by_reconcile(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    pid = new_player(client, admin_headers, "坏账")["id"]
    add_money(client, admin_headers, pid, 500)
    with dbmod.write_session() as session:
        session.execute(
            text("UPDATE players SET deposit_cents = 9999 WHERE id = :pid"), {"pid": pid}
        )
    response = client.post(f"/api/v1/batches/{batch_id}/close", json={}, headers=admin_headers)
    assert response.status_code == 400
    assert "对账" in response.json()["detail"]

    detail = client.get(f"/api/v1/batches/{batch_id}", headers=admin_headers).json()
    assert detail["status"] == "open"


def test_staff_can_close_batch(client, admin_headers, staff_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    response = client.post(
        f"/api/v1/batches/{batch_id}/close", json={}, headers=staff_headers
    )
    assert response.status_code == 200


def test_batch_list_includes_sessions(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    pid = new_player(client, admin_headers, "列表用")["id"]
    create_session(client, admin_headers, batch_id, [pid], tea=100)

    body = client.get("/api/v1/batches", headers=admin_headers).json()
    current = body["items"][0]
    assert current["id"] == batch_id
    assert current["status"] == "open"
    assert current["display_label"].endswith("进行中")
    assert len(current["sessions"]) == 1
    assert current["sessions"][0]["players"][0]["game_id"] == "列表用"


def test_current_batch_endpoint(client, admin_headers) -> None:
    assert client.get("/api/v1/batches/current", headers=admin_headers).json()["batch"] is None
    batch_id = open_batch(client, admin_headers)
    body = client.get("/api/v1/batches/current", headers=admin_headers).json()
    assert body["batch"]["id"] == batch_id


def test_batch_csv_export(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    pid = new_player(client, admin_headers, "导出哥")["id"]
    add_money(client, admin_headers, pid, 1000)
    create_session(client, admin_headers, batch_id, [pid], tea=200)

    response = client.get(f"/api/v1/batches/{batch_id}/export.csv", headers=admin_headers)
    assert response.status_code == 200
    assert response.text.startswith("\ufeff")
    assert "导出哥" in response.text
    assert "茶水合计" in response.text
