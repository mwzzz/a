"""玩家赠金与充值活动：规则、账务、对账与权限。"""

from __future__ import annotations

from io import BytesIO

from openpyxl import Workbook
from sqlalchemy import text

from app import db as dbmod
from tests.test_players import add_money, new_player
from tests.test_sessions import create_session, open_batch


def add_campaign(client, headers, threshold_cents: int, bonus_cents: int) -> dict:
    response = client.post(
        "/api/v1/settings/recharge-campaigns",
        json={"threshold_cents": threshold_cents, "bonus_cents": bonus_cents},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def add_bonus(client, headers, player_id: int, cents: int, note: str = "") -> dict:
    response = client.post(
        f"/api/v1/players/{player_id}/bonus",
        json={"amount_cents": cents, "note": note},
        headers=headers,
    )
    assert response.status_code == 201, response.text
    return response.json()


def _import_player(client, headers, game_id: str, deposit_yuan: int) -> dict:
    workbook = Workbook()
    sheet = workbook.active
    sheet.append(["玩家id", "押金"])
    sheet.append([game_id, deposit_yuan])
    buffer = BytesIO()
    workbook.save(buffer)
    workbook.close()
    response = client.post(
        "/api/v1/players/import",
        files={
            "file": (
                "players.xlsx",
                buffer.getvalue(),
                "application/vnd.openxmlformats-officedocument.spreadsheetml.sheet",
            )
        },
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


def test_campaign_crud_permissions_and_isolation(
    client, admin_headers, staff_headers, admin_b_headers
) -> None:
    first = add_campaign(client, admin_headers, 10000, 2000)
    assert first["threshold_cents"] == 10000
    assert first["bonus_cents"] == 2000

    duplicate = client.post(
        "/api/v1/settings/recharge-campaigns",
        json={"threshold_cents": 10000, "bonus_cents": 3000},
        headers=admin_headers,
    )
    assert duplicate.status_code == 400
    assert "已经存在" in duplicate.json()["detail"]

    staff_create = client.post(
        "/api/v1/settings/recharge-campaigns",
        json={"threshold_cents": 20000, "bonus_cents": 4000},
        headers=staff_headers,
    )
    assert staff_create.status_code == 403

    listed = client.get(
        "/api/v1/settings/recharge-campaigns", headers=staff_headers
    ).json()
    assert [item["id"] for item in listed] == [first["id"]]

    updated = client.patch(
        f"/api/v1/settings/recharge-campaigns/{first['id']}",
        json={"threshold_cents": 12000, "bonus_cents": 2500},
        headers=admin_headers,
    )
    assert updated.status_code == 200, updated.text
    assert updated.json()["threshold_cents"] == 12000

    other = client.get(
        "/api/v1/settings/recharge-campaigns", headers=admin_b_headers
    ).json()
    assert other == []

    deleted = client.delete(
        f"/api/v1/settings/recharge-campaigns/{first['id']}", headers=admin_headers
    )
    assert deleted.status_code == 204
    assert client.get("/api/v1/settings/recharge-campaigns", headers=admin_headers).json() == []


def test_add_deposit_auto_grants_highest_campaign(client, admin_headers) -> None:
    add_campaign(client, admin_headers, 10000, 2000)
    add_campaign(client, admin_headers, 50000, 15000)
    player = new_player(client, admin_headers, "活动哥")

    body = client.post(
        f"/api/v1/players/{player['id']}/deposits",
        json={"amount_cents": 60000, "note": "微信"},
        headers=admin_headers,
    ).json()
    assert body["campaign"]["threshold_cents"] == 50000
    assert body["campaign"]["bonus_cents"] == 15000
    assert body["bonus_entry"]["reason"] == "add_bonus"
    assert body["bonus_entry"]["amount_cents"] == 15000
    assert body["bonus_entry"]["signed_amount_cents"] == 15000
    assert body["bonus_entry"]["deposit_after_cents"] == 60000
    assert body["bonus_entry"]["bonus_after_cents"] == 15000
    assert body["player"]["deposit_cents"] == 60000
    assert body["player"]["bonus_cents"] == 15000
    assert body["player"]["balance_cents"] == 75000
    assert body["player"]["deposit_level"] == "safe"

    below = client.post(
        f"/api/v1/players/{player['id']}/deposits",
        json={"amount_cents": 5000},
        headers=admin_headers,
    ).json()
    assert below["campaign"] is None
    assert below["bonus_entry"] is None
    assert below["player"]["balance_cents"] == 80000

    ledger = client.get(
        f"/api/v1/players/{player['id']}/ledger", headers=admin_headers
    ).json()
    reasons = [item["reason"] for item in ledger["items"]]
    assert reasons == ["add_deposit", "add_bonus", "add_deposit"]
    assert ledger["items"][1]["reason_label"] == "加赠金"


def test_import_does_not_apply_campaign(client, admin_headers) -> None:
    add_campaign(client, admin_headers, 10000, 2000)
    result = _import_player(client, admin_headers, "导入赠金", 100)
    assert result["created"] == 1

    row = client.get(
        "/api/v1/players", params={"keyword": "导入赠金"}, headers=admin_headers
    ).json()["items"][0]
    assert row["deposit_cents"] == 10000
    assert row["bonus_cents"] == 0
    assert row["balance_cents"] == 10000

    ledger = client.get(
        f"/api/v1/players/{row['id']}/ledger", headers=admin_headers
    ).json()
    assert ledger["total"] == 1
    assert ledger["items"][0]["reason"] == "add_deposit"


def test_staff_can_add_manual_bonus(client, admin_headers, staff_headers, staff) -> None:
    player = new_player(client, admin_headers, "手动赠金")
    add_money(client, admin_headers, player["id"], 1000)
    body = add_bonus(client, staff_headers, player["id"], 500, "店长同意")

    assert body["entry"]["reason"] == "add_bonus"
    assert body["entry"]["operator"]["id"] == staff["id"]
    assert body["entry"]["note"] == "店长同意"
    assert body["entry"]["deposit_after_cents"] == 1000
    assert body["entry"]["bonus_after_cents"] == 500
    assert body["player"]["deposit_cents"] == 1000
    assert body["player"]["bonus_cents"] == 500
    assert body["player"]["balance_cents"] == 1500


def test_tea_deduction_uses_bonus_first(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "先扣赠金")
    add_money(client, admin_headers, player["id"], 1000)
    add_bonus(client, admin_headers, player["id"], 500)

    preview = client.post(
        "/api/v1/sessions/preview",
        json={"player_ids": [player["id"]], "tea_fee_cents": 300},
        headers=admin_headers,
    ).json()
    item = preview["items"][0]
    assert item["before_cents"] == 1500
    assert item["after_cents"] == 1200
    assert item["deposit_before_cents"] == 1000
    assert item["deposit_after_cents"] == 1000
    assert item["bonus_before_cents"] == 500
    assert item["bonus_after_cents"] == 200
    assert item["bonus_deduct_cents"] == 300
    assert preview["negative_count"] == 0

    create_session(
        client, admin_headers, open_batch(client, admin_headers), [player["id"]], tea=300
    )
    detail = client.get(f"/api/v1/players/{player['id']}", headers=admin_headers).json()
    assert detail["deposit_cents"] == 1000
    assert detail["bonus_cents"] == 200
    assert detail["balance_cents"] == 1200
    assert detail["games_played"] == 1

    ledger = client.get(
        f"/api/v1/players/{player['id']}/ledger", headers=admin_headers
    ).json()["items"]
    deduction = next(item for item in ledger if item["reason"] == "normal_deduct")
    assert deduction["amount_cents"] == 300
    assert deduction["bonus_amount_cents"] == 300
    assert deduction["deposit_after_cents"] == 1000
    assert deduction["bonus_after_cents"] == 200
    assert deduction["balance_after_cents"] == 1200


def test_bonus_exhausted_then_cash_and_negative_balance(
    client, admin_headers
) -> None:
    player = new_player(client, admin_headers, "扣穿赠金")
    add_money(client, admin_headers, player["id"], 1000)
    add_bonus(client, admin_headers, player["id"], 200)
    create_session(
        client, admin_headers, open_batch(client, admin_headers), [player["id"]], tea=500
    )
    detail = client.get(f"/api/v1/players/{player['id']}", headers=admin_headers).json()
    assert detail["deposit_cents"] == 700
    assert detail["bonus_cents"] == 0
    assert detail["balance_cents"] == 700

    create_session(
        client, admin_headers, open_batch(client, admin_headers), [player["id"]], tea=1000
    )
    detail = client.get(f"/api/v1/players/{player['id']}", headers=admin_headers).json()
    assert detail["deposit_cents"] == -300
    assert detail["bonus_cents"] == 0
    assert detail["balance_cents"] == -300
    assert detail["deposit_level"] == "low"


def test_refund_blocked_until_bonus_consumed(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "退款赠金")
    add_money(client, admin_headers, player["id"], 1000)
    add_bonus(client, admin_headers, player["id"], 500)

    blocked = client.post(
        f"/api/v1/players/{player['id']}/refunds",
        json={"amount_cents": 100},
        headers=admin_headers,
    )
    assert blocked.status_code == 400
    assert "赠金" in blocked.json()["detail"]
    assert "不能退" in blocked.json()["detail"]

    create_session(
        client, admin_headers, open_batch(client, admin_headers), [player["id"]], tea=500
    )
    refunded = client.post(
        f"/api/v1/players/{player['id']}/refunds",
        json={"amount_cents": 1000},
        headers=admin_headers,
    )
    assert refunded.status_code == 201, refunded.text
    assert refunded.json()["player"]["deposit_cents"] == 0
    assert refunded.json()["player"]["bonus_cents"] == 0


def test_transfer_cannot_touch_bonus(client, admin_headers) -> None:
    source = new_player(client, admin_headers, "赠金划出")
    target = new_player(client, admin_headers, "赠金划入")
    add_money(client, admin_headers, source["id"], 1000)
    add_bonus(client, admin_headers, source["id"], 500)

    blocked = client.post(
        "/api/v1/transfers",
        json={
            "from_player_id": source["id"],
            "to_player_id": target["id"],
            "amount_cents": 1200,
        },
        headers=admin_headers,
    )
    assert blocked.status_code == 400
    assert "赠金不能划转" in blocked.json()["detail"]

    body = client.post(
        "/api/v1/transfers",
        json={
            "from_player_id": source["id"],
            "to_player_id": target["id"],
            "amount_cents": 1000,
        },
        headers=admin_headers,
    ).json()
    assert body["from_player"]["deposit_cents"] == 0
    assert body["from_player"]["bonus_cents"] == 500
    assert body["from_player"]["balance_cents"] == 500
    assert body["to_player"]["deposit_cents"] == 1000
    assert body["to_player"]["bonus_cents"] == 0


def test_delete_requires_both_balances_zero(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "赠金删除")
    add_bonus(client, admin_headers, player["id"], 100)
    blocked = client.delete(f"/api/v1/players/{player['id']}", headers=admin_headers)
    assert blocked.status_code == 400
    assert "赠金" in blocked.json()["detail"]

    create_session(
        client, admin_headers, open_batch(client, admin_headers), [player["id"]], tea=100
    )
    assert (
        client.delete(f"/api/v1/players/{player['id']}", headers=admin_headers).status_code
        == 204
    )


def test_reconcile_detects_bonus_tampering(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "赠金对账")
    add_money(client, admin_headers, player["id"], 1000)
    add_bonus(client, admin_headers, player["id"], 200)

    report = client.get("/api/v1/reconcile", headers=admin_headers).json()
    assert report["ok"] is True
    assert report["total_deposit_cents"] == 1000
    assert report["total_bonus_cents"] == 200
    assert report["total_ledger_cents"] == 1200

    with dbmod.write_session() as session:
        session.execute(
            text("UPDATE players SET bonus_cents = bonus_cents + 1 WHERE id = :pid"),
            {"pid": player["id"]},
        )
    report = client.get("/api/v1/reconcile", headers=admin_headers).json()
    assert report["ok"] is False
    assert report["problems"][0]["stored_bonus_cents"] == 201
    assert report["problems"][0]["ledger_bonus_sum_cents"] == 200
    assert report["problems"][0]["last_bonus_cents"] == 200


def test_total_balance_controls_level_sort_and_overview(client, admin_headers) -> None:
    low_cash = new_player(client, admin_headers, "低现金")
    low_gift = new_player(client, admin_headers, "低现金高赠金")
    warn = new_player(client, admin_headers, "临界")
    add_money(client, admin_headers, low_cash["id"], 1000)
    add_money(client, admin_headers, low_gift["id"], 100)
    add_bonus(client, admin_headers, low_gift["id"], 2000)
    add_money(client, admin_headers, warn["id"], 3000)

    rows = client.get(
        "/api/v1/players",
        params={"sort": "deposit_desc", "page_size": 50},
        headers=admin_headers,
    ).json()["items"]
    assert [row["game_id"] for row in rows] == ["临界", "低现金高赠金", "低现金"]
    gift_row = next(row for row in rows if row["game_id"] == "低现金高赠金")
    assert gift_row["deposit_cents"] == 100
    assert gift_row["bonus_cents"] == 2000
    assert gift_row["balance_cents"] == 2100
    assert gift_row["deposit_level"] == "low"

    warn_rows = client.get(
        "/api/v1/players",
        params={"level": "warn", "page_size": 50},
        headers=admin_headers,
    ).json()["items"]
    assert [row["game_id"] for row in warn_rows] == ["临界"]

    overview = client.get("/api/v1/overview", headers=admin_headers).json()
    assert overview["total_deposit_cents"] == 4100
    assert overview["total_bonus_cents"] == 2000
    assert overview["low_deposit_count"] == 2
