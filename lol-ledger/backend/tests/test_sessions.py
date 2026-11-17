"""开局：扣费、去重、负数、上限、事务回滚。"""

from __future__ import annotations

from sqlalchemy import text

from app import db as dbmod
from tests.test_players import add_money, new_player


def open_batch(client, headers) -> int:
    """班次已取消；保留这个函数只是为了让老用例保持调用顺序，返回值不再有意义。"""
    return 0


def create_session(
    client,
    headers,
    batch_id: int,
    player_ids: list[int],
    tea: int = 200,
    **extra,
) -> dict:
    """batch_id 参数已废弃，仅为兼容旧用例保留位置。"""
    payload = {
        "name": extra.pop("name", ""),
        "played_at": extra.pop("played_at", None),
        "note": extra.pop("note", ""),
        "tea_fee_cents": tea,
        "player_ids": player_ids,
    }
    response = client.post("/api/v1/sessions", json=payload, headers=headers)
    assert response.status_code == 201, response.text
    return response.json()


def test_open_session_deducts_and_counts(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    ids = [new_player(client, admin_headers, f"队员{i}")["id"] for i in range(3)]
    for pid in ids:
        add_money(client, admin_headers, pid, 1000)

    body = create_session(client, admin_headers, batch_id, ids, tea=300)
    assert body["player_count"] == 3
    assert body["tea_total_cents"] == 900
    assert body["name"].endswith("第1局")

    for pid in ids:
        detail = client.get(f"/api/v1/players/{pid}", headers=admin_headers).json()
        assert detail["deposit_cents"] == 700
        assert detail["games_played"] == 1


def test_open_session_dedup_players(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    first = new_player(client, admin_headers, "重复甲")["id"]
    second = new_player(client, admin_headers, "重复乙")["id"]
    body = create_session(client, admin_headers, batch_id, [first, first, second], tea=100)
    assert body["player_count"] == 2


def test_open_session_allows_negative(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    pid = new_player(client, admin_headers, "余额不足")["id"]
    add_money(client, admin_headers, pid, 100)
    create_session(client, admin_headers, batch_id, [pid], tea=300)
    detail = client.get(f"/api/v1/players/{pid}", headers=admin_headers).json()
    assert detail["deposit_cents"] == -200
    assert detail["deposit_level"] == "low"


def test_zero_tea_writes_zero_entry(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    pid = new_player(client, admin_headers, "免单")["id"]
    add_money(client, admin_headers, pid, 500)
    body = create_session(client, admin_headers, batch_id, [pid], tea=0)
    assert body["tea_total_cents"] == 0
    ledger = client.get(f"/api/v1/players/{pid}/ledger", headers=admin_headers).json()
    assert ledger["items"][0]["reason"] == "normal_deduct"
    assert ledger["items"][0]["amount_cents"] == 0
    detail = client.get(f"/api/v1/players/{pid}", headers=admin_headers).json()
    assert detail["deposit_cents"] == 500
    assert detail["games_played"] == 1


def test_session_player_limits(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    players = [new_player(client, admin_headers, f"人{i}")["id"] for i in range(11)]

    empty = client.post(
        "/api/v1/sessions",
        json={"batch_id": batch_id, "tea_fee_cents": 100, "player_ids": []},
        headers=admin_headers,
    )
    assert empty.status_code == 400

    too_many = client.post(
        "/api/v1/sessions",
        json={"batch_id": batch_id, "tea_fee_cents": 100, "player_ids": players},
        headers=admin_headers,
    )
    assert too_many.status_code == 400
    assert "10" in too_many.json()["detail"]


def test_bad_player_rolls_back_whole_session(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    good = new_player(client, admin_headers, "好人")["id"]
    add_money(client, admin_headers, good, 1000)

    response = client.post(
        "/api/v1/sessions",
        json={"batch_id": batch_id, "tea_fee_cents": 300, "player_ids": [good, 999999]},
        headers=admin_headers,
    )
    assert response.status_code == 404
    detail = client.get(f"/api/v1/players/{good}", headers=admin_headers).json()
    assert detail["deposit_cents"] == 1000
    assert detail["games_played"] == 0
    with dbmod.read_session() as db:
        assert db.execute(text("SELECT COUNT(*) FROM sessions")).scalar_one() == 0

    listed = client.get("/api/v1/sessions", headers=admin_headers).json()
    assert listed["total"] == 0


def test_session_players_link_ledger(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    pid = new_player(client, admin_headers, "查流水")["id"]
    add_money(client, admin_headers, pid, 1000)
    body = create_session(client, admin_headers, batch_id, [pid], tea=200)

    assert body["players"][0]["balance_before_cents"] == 1000
    assert body["players"][0]["balance_after_cents"] == 800
    with dbmod.read_session() as db:
        linked = db.execute(
            text(
                "SELECT ledger_id FROM session_players WHERE session_id = :sid"
            ),
            {"sid": body["id"]},
        ).scalar_one()
        reason = db.execute(
            text("SELECT reason FROM ledger WHERE id = :lid"), {"lid": linked}
        ).scalar_one()
    assert reason == "normal_deduct"


def test_open_session_updates_last_tea(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    pid = new_player(client, admin_headers, "记茶水")["id"]
    create_session(client, admin_headers, batch_id, [pid], tea=350)
    settings = client.get("/api/v1/settings", headers=admin_headers).json()
    assert settings["last_tea_cents"] == 350


def test_sessions_sorted_by_played_at_desc(client, admin_headers) -> None:
    batch_id = open_batch(client, admin_headers)
    pid = new_player(client, admin_headers, "排序哥")["id"]
    create_session(
        client, admin_headers, batch_id, [pid], tea=100, played_at="2026-10-30T10:00:00+08:00"
    )
    create_session(
        client, admin_headers, batch_id, [pid], tea=100, played_at="2026-10-30T15:00:00+08:00"
    )
    listed = client.get("/api/v1/sessions", headers=admin_headers).json()
    played = [item["played_at"] for item in listed["items"]]
    assert played == sorted(played, reverse=True)


def test_preview_shows_negative_players(client, admin_headers) -> None:
    poor = new_player(client, admin_headers, "穷鬼")["id"]
    add_money(client, admin_headers, poor, 100)
    body = client.post(
        "/api/v1/sessions/preview",
        json={"player_ids": [poor], "tea_fee_cents": 300},
        headers=admin_headers,
    ).json()
    assert body["negative_count"] == 1
    assert body["negative_players"] == ["穷鬼"]
    assert body["items"][0]["after_cents"] == -200


def test_default_session_name_increments_same_day(client, admin_headers) -> None:
    pid = new_player(client, admin_headers, "连开哥")["id"]
    first = create_session(
        client,
        admin_headers,
        open_batch(client, admin_headers),
        [pid],
        tea=100,
        played_at="2026-11-13T10:00:00+08:00",
    )
    second = create_session(
        client,
        admin_headers,
        open_batch(client, admin_headers),
        [pid],
        tea=100,
        played_at="2026-11-13T11:00:00+08:00",
    )
    assert first["name"].endswith("第1局")
    assert second["name"].endswith("第2局")


def _tea_free_list_id(client, headers) -> int:
    lists = client.get("/api/v1/tools/name-lists", headers=headers).json()["lists"]
    return next(item for item in lists if item["name"] == "免茶水")["id"]


def test_tea_free_players_are_removed(client, admin_headers) -> None:
    free = new_player(client, admin_headers, "免茶哥#123")
    paid = new_player(client, admin_headers, "正常哥")
    list_id = _tea_free_list_id(client, admin_headers)
    created = client.post(
        f"/api/v1/tools/name-lists/{list_id}/items",
        json={"content": "免茶哥"},
        headers=admin_headers,
    )
    assert created.status_code == 201, created.text

    body = create_session(
        client,
        admin_headers,
        open_batch(client, admin_headers),
        [free["id"], paid["id"]],
        tea=100,
    )
    assert body["player_count"] == 1
    assert body["players"][0]["game_id"] == "正常哥"
    assert body["tea_free_removed"] == ["免茶哥#123"]

    free_detail = client.get(
        f"/api/v1/players/{free['id']}", headers=admin_headers
    ).json()
    assert free_detail["deposit_cents"] == 0
    assert free_detail["games_played"] == 0


def test_all_tea_free_players_rejected(client, admin_headers) -> None:
    free = new_player(client, admin_headers, "只免茶")["id"]
    list_id = _tea_free_list_id(client, admin_headers)
    client.post(
        f"/api/v1/tools/name-lists/{list_id}/items",
        json={"content": "只免茶"},
        headers=admin_headers,
    )
    response = client.post(
        "/api/v1/sessions",
        json={"tea_fee_cents": 100, "player_ids": [free]},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "免茶水" in response.json()["detail"]


def test_blacklisted_player_cannot_open_session(client, admin_headers) -> None:
    blocked = new_player(client, admin_headers, "黑名单哥", is_blacklisted=True)["id"]
    response = client.post(
        "/api/v1/sessions",
        json={"tea_fee_cents": 100, "player_ids": [blocked]},
        headers=admin_headers,
    )
    assert response.status_code == 400
    assert "黑名单" in response.json()["detail"]
