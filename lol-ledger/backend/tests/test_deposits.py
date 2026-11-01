"""押金规则：加、退、扣、划，以及事务回滚与余额恒等式。"""

from __future__ import annotations

import pytest
from sqlalchemy import text
from sqlalchemy.exc import IntegrityError

from app import db as dbmod
from tests.test_players import add_money, new_player


def balance(client, headers, player_id: int) -> int:
    return client.get(f"/api/v1/players/{player_id}", headers=headers).json()["deposit_cents"]


def test_add_deposit_positive_only(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "加钱哥")
    for amount in (0, -100):
        response = client.post(
            f"/api/v1/players/{player['id']}/deposits",
            json={"amount_cents": amount},
            headers=admin_headers,
        )
        assert response.status_code == 400
        assert "大于 0" in response.json()["detail"]


def test_add_deposit_writes_entry_and_balance(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "加钱姐")
    body = client.post(
        f"/api/v1/players/{player['id']}/deposits",
        json={"amount_cents": 1000, "note": "微信"},
        headers=admin_headers,
    ).json()
    assert body["entry"]["reason"] == "add_deposit"
    assert body["entry"]["balance_before_cents"] == 0
    assert body["entry"]["balance_after_cents"] == 1000
    assert body["entry"]["signed_amount_cents"] == 1000
    assert body["entry"]["reason_label"] == "加押金"
    assert body["entry"]["note"] == "微信"
    assert body["player"]["deposit_cents"] == 1000


def test_refund_insufficient_rolls_back(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "退款哥")
    add_money(client, admin_headers, player["id"], 1000)
    response = client.post(
        f"/api/v1/players/{player['id']}/refunds",
        json={"amount_cents": 1001},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "押金不足" in response.json()["detail"]
    assert balance(client, admin_headers, player["id"]) == 1000

    ledger = client.get(
        f"/api/v1/players/{player['id']}/ledger", headers=admin_headers
    ).json()
    assert ledger["total"] == 1


def test_negative_account_cannot_refund(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "负翁")
    add_money(client, admin_headers, player["id"], 100)
    response = client.post(
        f"/api/v1/players/{player['id']}/deductions",
        json={"amount_cents": 300},
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert balance(client, admin_headers, player["id"]) == -200

    refund = client.post(
        f"/api/v1/players/{player['id']}/refunds",
        json={"amount_cents": 1},
        headers=admin_headers,
    )
    assert refund.status_code == 400


def test_refund_exact_balance_ok(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "退光了")
    add_money(client, admin_headers, player["id"], 1234)
    response = client.post(
        f"/api/v1/players/{player['id']}/refunds",
        json={"amount_cents": 1234},
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert balance(client, admin_headers, player["id"]) == 0
    assert response.json()["entry"]["signed_amount_cents"] == -1234


def test_manual_deduct_may_go_negative(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "罚款哥")
    add_money(client, admin_headers, player["id"], 100)
    body = client.post(
        f"/api/v1/players/{player['id']}/deductions",
        json={"amount_cents": 300},
        headers=admin_headers,
    ).json()
    assert body["entry"]["reason"] == "manual_deduct"
    assert body["entry"]["reason_label"] == "手动扣押"
    assert body["player"]["deposit_cents"] == -200
    assert body["player"]["deposit_level"] == "low"


def test_manual_deduct_zero_allowed(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "零扣")
    response = client.post(
        f"/api/v1/players/{player['id']}/deductions",
        json={"amount_cents": 0},
        headers=admin_headers,
    )
    assert response.status_code == 201
    assert response.json()["entry"]["amount_cents"] == 0


def test_transfer_creates_pair_with_same_group(client, admin_headers) -> None:
    source = new_player(client, admin_headers, "转出者")
    target = new_player(client, admin_headers, "接收者")
    add_money(client, admin_headers, source["id"], 5000)

    body = client.post(
        "/api/v1/transfers",
        json={
            "from_player_id": source["id"],
            "to_player_id": target["id"],
            "amount_cents": 1500,
            "note": "帮朋友付",
        },
        headers=admin_headers,
    ).json()

    assert body["group_id"]
    assert body["out_entry"]["transfer_group_id"] == body["group_id"]
    assert body["in_entry"]["transfer_group_id"] == body["group_id"]
    assert body["out_entry"]["counterparty"]["id"] == target["id"]
    assert body["in_entry"]["counterparty"]["id"] == source["id"]
    assert body["out_entry"]["reason_label"] == "划押转出 → 接收者"
    assert body["in_entry"]["reason_label"] == "划押转入 ← 转出者"
    assert body["out_entry"]["signed_amount_cents"] == -1500
    assert body["in_entry"]["signed_amount_cents"] == 1500
    assert body["from_player"]["deposit_cents"] == 3500
    assert body["to_player"]["deposit_cents"] == 1500


def test_transfer_rejects_self(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "自己划")
    add_money(client, admin_headers, player["id"], 100)
    response = client.post(
        "/api/v1/transfers",
        json={
            "from_player_id": player["id"],
            "to_player_id": player["id"],
            "amount_cents": 100,
        },
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "自己" in response.json()["detail"]


def test_transfer_may_go_negative(client, admin_headers) -> None:
    source = new_player(client, admin_headers, "划穿甲")
    target = new_player(client, admin_headers, "划穿乙")
    add_money(client, admin_headers, source["id"], 100)
    body = client.post(
        "/api/v1/transfers",
        json={
            "from_player_id": source["id"],
            "to_player_id": target["id"],
            "amount_cents": 300,
        },
        headers=admin_headers,
    ).json()
    assert body["from_player"]["deposit_cents"] == -200
    assert body["to_player"]["deposit_cents"] == 300


def test_ledger_balance_identity_enforced(client, admin_headers, admin) -> None:
    player = new_player(client, admin_headers, "坏人")
    with pytest.raises(IntegrityError):
        with dbmod.write_session() as session:
            session.execute(
                text(
                    """
                    INSERT INTO ledger (
                        player_id, batch_id, session_id, reason, amount_cents,
                        balance_before_cents, balance_after_cents,
                        counterparty_player_id, transfer_group_id, operator_id,
                        note, created_at
                    ) VALUES (
                        :pid, NULL, NULL, 'add_deposit', 100,
                        0, 999, NULL, NULL, :op, '', '2026-10-30T20:00:00+08:00'
                    )
                    """
                ),
                {"pid": player["id"], "op": admin["id"]},
            )


def test_operator_recorded(client, admin_headers, staff_headers, staff) -> None:
    player = new_player(client, admin_headers, "店员操作")
    body = client.post(
        f"/api/v1/players/{player['id']}/deposits",
        json={"amount_cents": 500},
        headers=staff_headers,
    ).json()
    assert body["entry"]["operator"]["id"] == staff["id"]
    assert body["entry"]["operator"]["display_name"] == "小美"


def test_missing_player_returns_404(client, admin_headers) -> None:
    response = client.post(
        "/api/v1/players/9999/deposits",
        json={"amount_cents": 100},
        headers=admin_headers,
    )
    assert response.status_code == 404


def test_unauthenticated_is_401(client) -> None:
    assert client.get("/api/v1/players").status_code == 401
