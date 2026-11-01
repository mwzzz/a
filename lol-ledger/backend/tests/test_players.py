"""玩家库：默认值、排序、筛选、软删除。"""

from __future__ import annotations

from sqlalchemy import text

from app import db as dbmod


def new_player(client, headers, game_id: str, **extra) -> dict:
    payload = {"game_id": game_id, **extra}
    response = client.post("/api/v1/players", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def add_money(client, headers, player_id: int, cents: int) -> None:
    response = client.post(
        f"/api/v1/players/{player_id}/deposits",
        json={"amount_cents": cents},
        headers=headers,
    )
    assert response.status_code == 201, response.text


def deduct_money(client, headers, player_id: int, cents: int) -> None:
    response = client.post(
        f"/api/v1/players/{player_id}/deductions",
        json={"amount_cents": cents},
        headers=headers,
    )
    assert response.status_code == 201, response.text


def test_create_player_defaults(client, admin_headers, admin) -> None:
    body = new_player(client, admin_headers, "等风息y", account="ceb1", remark="老客")
    assert body["deposit_cents"] == 0
    assert body["games_played"] == 0
    assert body["deposit_level"] == "low"
    assert body["creator"]["id"] == admin["id"]
    assert body["account"] == "ceb1"
    assert body["remark"] == "老客"


def test_duplicate_game_id_rejected(client, admin_headers) -> None:
    new_player(client, admin_headers, "Alone")
    again = client.post("/api/v1/players", json={"game_id": "Alone"}, headers=admin_headers)
    assert again.status_code == 400
    assert "已存在" in again.json()["detail"]


def test_game_id_validation(client, admin_headers) -> None:
    for bad in ["", "a\nb", "x" * 65]:
        response = client.post(
            "/api/v1/players", json={"game_id": bad}, headers=admin_headers
        )
        assert response.status_code in (400, 422), bad


def test_sort_by_games_played_then_game_id_text(client, admin_headers) -> None:
    ids = {}
    for name in ["10", "2", "a"]:
        ids[name] = new_player(client, admin_headers, name)["id"]
    with dbmod.write_session() as session:
        session.execute(
            text("UPDATE players SET games_played = 2 WHERE id IN (:a, :b)"),
            {"a": ids["10"], "b": ids["2"]},
        )
        session.execute(
            text("UPDATE players SET games_played = 5 WHERE id = :a"), {"a": ids["a"]}
        )

    body = client.get("/api/v1/players", headers=admin_headers).json()
    assert [item["game_id"] for item in body["items"]] == ["a", "10", "2"]


def test_sort_by_deposit_desc(client, admin_headers) -> None:
    low = new_player(client, admin_headers, "low")
    high = new_player(client, admin_headers, "high")
    zero = new_player(client, admin_headers, "zero")
    add_money(client, admin_headers, low["id"], 10000)
    add_money(client, admin_headers, high["id"], 50000)

    body = client.get(
        "/api/v1/players", params={"sort": "deposit_desc"}, headers=admin_headers
    ).json()
    assert [item["id"] for item in body["items"]] == [high["id"], low["id"], zero["id"]]


def test_filter_by_deposit_level(client, admin_headers) -> None:
    cases = [
        ("neg", -1, "low"),
        ("almost", 2999, "low"),
        ("thirty", 3000, "warn"),
        ("sixty", 6000, "warn"),
        ("over", 6001, "safe"),
    ]
    for name, cents, _ in cases:
        player = new_player(client, admin_headers, name)
        if cents >= 0:
            add_money(client, admin_headers, player["id"], cents)
        else:
            add_money(client, admin_headers, player["id"], 100)
            deduct_money(client, admin_headers, player["id"], 101)

    for name, _, level in cases:
        body = client.get(
            "/api/v1/players", params={"level": level, "page_size": 50}, headers=admin_headers
        ).json()
        names = [item["game_id"] for item in body["items"]]
        assert name in names, (name, level, names)


def test_keyword_matches_game_id_account_remark(client, admin_headers) -> None:
    new_player(client, admin_headers, "阿尔法", account="acc-1", remark="备注甲")
    new_player(client, admin_headers, "贝塔", account="acc-2", remark="备注乙")

    for keyword, expected in [
        ("阿尔", "阿尔法"),
        ("acc-2", "贝塔"),
        ("备注甲", "阿尔法"),
    ]:
        body = client.get(
            "/api/v1/players", params={"keyword": keyword}, headers=admin_headers
        ).json()
        assert [item["game_id"] for item in body["items"]] == [expected]


def test_delete_requires_zero_deposit(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "有钱人")
    add_money(client, admin_headers, player["id"], 100)
    blocked = client.delete(f"/api/v1/players/{player['id']}", headers=admin_headers)
    assert blocked.status_code == 400
    assert "押金不为 0" in blocked.json()["detail"]

    response = client.post(
        f"/api/v1/players/{player['id']}/refunds",
        json={"amount_cents": 100},
        headers=admin_headers,
    )
    assert response.status_code == 201
    deleted = client.delete(f"/api/v1/players/{player['id']}", headers=admin_headers)
    assert deleted.status_code == 204

    listed = client.get("/api/v1/players", headers=admin_headers).json()
    assert player["id"] not in [item["id"] for item in listed["items"]]
    assert client.get(f"/api/v1/players/{player['id']}", headers=admin_headers).status_code == 404


def test_staff_cannot_delete_player(client, admin_headers, staff_headers) -> None:
    player = new_player(client, admin_headers, "待删")
    response = client.delete(f"/api/v1/players/{player['id']}", headers=staff_headers)
    assert response.status_code == 403


def test_deleted_player_ledger_preserved_and_name_reusable(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "循环名")
    add_money(client, admin_headers, player["id"], 500)
    deduct_money(client, admin_headers, player["id"], 500)
    assert client.delete(f"/api/v1/players/{player['id']}", headers=admin_headers).status_code == 204

    with dbmod.read_session() as session:
        count = session.execute(
            text("SELECT COUNT(*) FROM ledger WHERE player_id = :pid"), {"pid": player["id"]}
        ).scalar_one()
    assert count == 2

    again = new_player(client, admin_headers, "循环名")
    assert again["id"] != player["id"]


def test_player_options_excludes_selected(client, admin_headers) -> None:
    first = new_player(client, admin_headers, "甲玩家")
    new_player(client, admin_headers, "乙玩家")
    body = client.get(
        "/api/v1/players/options",
        params={"exclude_ids": str(first["id"])},
        headers=admin_headers,
    ).json()
    assert [item["game_id"] for item in body] == ["乙玩家"]


def test_player_detail_totals(client, admin_headers) -> None:
    player = new_player(client, admin_headers, "统计哥")
    add_money(client, admin_headers, player["id"], 3000)
    deduct_money(client, admin_headers, player["id"], 1200)
    detail = client.get(f"/api/v1/players/{player['id']}", headers=admin_headers).json()
    assert detail["total_in_cents"] == 3000
    assert detail["total_out_cents"] == 1200
    assert detail["deposit_cents"] == 1800
    assert detail["entry_count"] == 2
