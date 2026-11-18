"""记录查询：分页、筛选、关键字、划转文案、时区边界。"""

from __future__ import annotations

from sqlalchemy import text

from app import db as dbmod
from tests.test_players import add_money, new_player
from tests.test_sessions import create_session


def test_deposit_records_pagination(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "流水哥")
    for _ in range(25):
        add_money(client, admin_headers, player["id"], 100)

    first = client.get(
        "/api/v1/records/deposits", params={"page": 1, "page_size": 10}, headers=admin_headers
    ).json()
    assert first["total"] == 25
    assert len(first["items"]) == 10

    third = client.get(
        "/api/v1/records/deposits", params={"page": 3, "page_size": 10}, headers=admin_headers
    ).json()
    assert len(third["items"]) == 5


def test_deposit_records_filter_by_reason(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "筛选哥")
    add_money(client, admin_headers, player["id"], 1000)
    client.post(
        f"/api/v1/players/{player['id']}/refunds",
        json={"amount_cents": 200},
        headers=admin_headers,
    )
    body = client.get(
        "/api/v1/records/deposits",
        params={"reason": "refund", "player_id": player["id"]},
        headers=admin_headers,
    ).json()
    assert body["total"] == 1
    assert body["items"][0]["reason"] == "refund"


def test_keyword_matches_player_and_session(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "关键字玩家")
    add_money(client, admin_headers, player["id"], 500)
    create_session(client, admin_headers, [player["id"]], tea=100, name="夜班第一局")

    by_player = client.get(
        "/api/v1/records/deposits", params={"keyword": "关键字"}, headers=admin_headers
    ).json()
    assert by_player["total"] >= 1

    by_session = client.get(
        "/api/v1/records/deposits", params={"keyword": "夜班第一局"}, headers=admin_headers
    ).json()
    assert by_session["total"] == 1
    assert by_session["items"][0]["session"]["name"] == "夜班第一局"


def test_transfer_label_and_pair(client, admin_headers) -> None:
    source = new_player(client, admin_headers, "划出方")
    target = new_player(client, admin_headers, "划入方")
    add_money(client, admin_headers, source["id"], 1000)
    body = client.post(
        "/api/v1/transfers",
        json={"from_player_id": source["id"], "to_player_id": target["id"], "amount_cents": 400},
        headers=admin_headers,
    ).json()

    rows = client.get(
        "/api/v1/records/deposits",
        params={"player_id": source["id"], "reason": "transfer_out"},
        headers=admin_headers,
    ).json()["items"]
    assert rows[0]["reason_label"] == "划押转出 → 划入方"
    assert rows[0]["counterparty"]["game_id"] == "划入方"

    pair = client.get(
        f"/api/v1/records/transfers/{body['group_id']}", headers=admin_headers
    ).json()
    assert len(pair["entries"]) == 2


def test_signed_amount_by_reason(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "符号哥")
    peer = new_player(client, admin_headers, "符号弟")["id"]
    pid = player["id"]
    add_money(client, admin_headers, pid, 5000)
    create_session(client, admin_headers, [pid], tea=200)
    client.post(f"/api/v1/players/{pid}/refunds", json={"amount_cents": 200}, headers=admin_headers)
    client.post(
        "/api/v1/transfers",
        json={"from_player_id": pid, "to_player_id": peer, "amount_cents": 300},
        headers=admin_headers,
    )

    items = client.get(
        "/api/v1/records/deposits", params={"player_id": pid, "page_size": 20}, headers=admin_headers
    ).json()["items"]
    signs = {item["reason"]: item["signed_amount_cents"] for item in items}
    assert signs["normal_deduct"] == -200
    assert signs["refund"] == -200
    assert signs["transfer_out"] == -300
    assert signs["add_deposit"] == 5000


def test_date_range_uses_china_timezone(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "跨时区")
    add_money(client, admin_headers, player["id"], 100)
    with dbmod.write_session() as session:
        session.execute(
            text("UPDATE ledger SET created_at = '2026-10-30T23:30:00+08:00' WHERE player_id = :pid"),
            {"pid": player["id"]},
        )

    inside = client.get(
        "/api/v1/records/deposits",
        params={"date_from": "2026-10-30", "date_to": "2026-10-30"},
        headers=admin_headers,
    ).json()
    assert inside["total"] == 1

    outside = client.get(
        "/api/v1/records/deposits",
        params={"date_from": "2026-10-31", "date_to": "2026-10-31"},
        headers=admin_headers,
    ).json()
    assert outside["total"] == 0


def test_session_records_include_totals(client, admin_headers) -> None:
    ids = [new_player(client, admin_headers, f"场次{i}")["id"] for i in range(4)]
    create_session(client, admin_headers, ids, tea=250, name="统计局")

    body = client.get(
        "/api/v1/records/sessions", params={"keyword": "统计局"}, headers=admin_headers
    ).json()
    assert body["total"] == 1
    row = body["items"][0]
    assert row["player_count"] == 4
    assert row["tea_total_cents"] == 1000
    assert len(row["players"]) == 4


def test_reason_labels_are_chinese(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "文案哥")
    add_money(client, admin_headers, player["id"], 100)
    items = client.get(
        "/api/v1/records/deposits", params={"player_id": player["id"]}, headers=admin_headers
    ).json()["items"]
    assert items[0]["reason_label"] == "加押金"


def test_overview_shape(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "总览哥")
    add_money(client, admin_headers, player["id"], 1000)
    body = client.get("/api/v1/overview", headers=admin_headers).json()
    assert body["player_count"] == 1
    assert body["total_deposit_cents"] == 1000
    assert body["low_deposit_count"] == 1
    assert len(body["recent_records"]) == 1
    assert body["today"]["session_count"] == 0
    assert body["today"]["add_deposit_cents"] == 1000
    assert body["today"]["cash_diff_cents"] == 1000
    assert body["dividend_mode"] == "percent"


def test_ai_status_shape(client, admin_headers) -> None:
    status = client.get("/api/v1/ai/status", headers=admin_headers).json()
    assert isinstance(status["enabled"], bool)
    assert isinstance(status["model"], str)


def test_records_filter_by_operator(
    client, admin_headers, staff_headers, admin, staff
) -> None:
    player = new_player(client, admin_headers, "操作人哥")
    peer = new_player(client, admin_headers, "操作人弟")
    pid = player["id"]

    add_money(client, admin_headers, pid, 1000)
    client.post(
        f"/api/v1/players/{pid}/refunds",
        json={"amount_cents": 200},
        headers=staff_headers,
    )
    add_money(client, staff_headers, pid, 500)
    client.post(
        "/api/v1/transfers",
        json={"from_player_id": pid, "to_player_id": peer["id"], "amount_cents": 300},
        headers=staff_headers,
    )

    admin_rows = client.get(
        "/api/v1/records/deposits",
        params={"operator_id": admin["id"]},
        headers=admin_headers,
    ).json()
    assert admin_rows["total"] == 1
    assert admin_rows["items"][0]["operator"]["id"] == admin["id"]

    staff_rows = client.get(
        "/api/v1/records/deposits",
        params={"operator_id": staff["id"]},
        headers=admin_headers,
    ).json()
    assert staff_rows["total"] == 4
    assert all(item["operator"]["id"] == staff["id"] for item in staff_rows["items"])

    create_session(client, staff_headers, [pid], tea=100)
    create_session(client, admin_headers, [pid], tea=100)
    staff_sessions = client.get(
        "/api/v1/records/sessions",
        params={"operator_id": staff["id"]},
        headers=admin_headers,
    ).json()
    assert staff_sessions["total"] == 1
    assert staff_sessions["items"][0]["operator"]["id"] == staff["id"]

    staff_cash = client.get(
        "/api/v1/records/operator-summary",
        params={"operator_id": staff["id"]},
        headers=admin_headers,
    ).json()
    assert staff_cash["add_deposit_cents"] == 500
    assert staff_cash["refund_cents"] == 200
    assert staff_cash["cash_diff_cents"] == 300
    assert staff_cash["entry_count"] == 2

    admin_cash = client.get(
        "/api/v1/records/operator-summary",
        params={"operator_id": admin["id"]},
        headers=admin_headers,
    ).json()
    assert admin_cash["add_deposit_cents"] == 1000
    assert admin_cash["refund_cents"] == 0
    assert admin_cash["cash_diff_cents"] == 1000
    assert admin_cash["entry_count"] == 1

    operators = client.get("/api/v1/records/operators", headers=admin_headers).json()
    assert {item["id"] for item in operators} >= {admin["id"], staff["id"]}
