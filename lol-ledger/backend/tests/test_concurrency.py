"""并发：不丢更新、只有一个关班成功、并发后对账通过。"""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor

from app import db as dbmod
from app.deps import Actor
from app.errors import AppError
from app.services import batches as batch_service
from app.services import deposits as deposit_service
from app.services import sessions as session_service
from app.services.reconcile import reconcile
from tests.test_players import add_money, new_player


def make_actor(admin: dict) -> Actor:
    return Actor(
        id=admin["id"],
        username=admin["username"],
        display_name="店长",
        role="admin",
        merchant_id=admin["merchant_id"],
        merchant_name=admin["merchant_name"],
    )


def test_concurrent_add_deposit_no_lost_update(client, admin_headers, admin) -> None:
    pid = new_player(client, admin_headers, "并发加钱")["id"]
    actor = make_actor(admin)

    def task(_: int) -> None:
        with dbmod.write_session() as session:
            deposit_service.add_deposit(session, actor, pid, 100)

    with ThreadPoolExecutor(max_workers=10) as pool:
        list(pool.map(task, range(10)))

    detail = client.get(f"/api/v1/players/{pid}", headers=admin_headers).json()
    assert detail["deposit_cents"] == 1000

    items = client.get(
        "/api/v1/records/deposits", params={"player_id": pid, "page_size": 50}, headers=admin_headers
    ).json()["items"]
    assert len(items) == 10
    assert sorted(item["balance_after_cents"] for item in items) == [
        100 * step for step in range(1, 11)
    ]


def test_concurrent_close_only_one_wins(client, admin_headers, admin) -> None:
    batch_id = client.post("/api/v1/batches", json={}, headers=admin_headers).json()["id"]
    actor = make_actor(admin)

    def task(_: int) -> str:
        try:
            with dbmod.write_session() as session:
                batch_service.close_batch(session, actor, batch_id)
            return "ok"
        except AppError:
            return "rejected"

    with ThreadPoolExecutor(max_workers=2) as pool:
        results = list(pool.map(task, range(2)))

    assert sorted(results) == ["ok", "rejected"]
    detail = client.get(f"/api/v1/batches/{batch_id}", headers=admin_headers).json()
    assert detail["status"] == "closed"


def test_concurrent_sessions_keep_balances_consistent(client, admin_headers, admin) -> None:
    batch_id = client.post("/api/v1/batches", json={}, headers=admin_headers).json()["id"]
    first = new_player(client, admin_headers, "并发甲")["id"]
    second = new_player(client, admin_headers, "并发乙")["id"]
    add_money(client, admin_headers, first, 1000)
    add_money(client, admin_headers, second, 1000)
    actor = make_actor(admin)

    def task(_: int) -> None:
        with dbmod.write_session() as session:
            session_service.open_session(
                session,
                actor,
                batch_id=batch_id,
                tea_fee_cents=100,
                player_ids=[first, second],
            )

    with ThreadPoolExecutor(max_workers=2) as pool:
        list(pool.map(task, range(2)))

    for pid in (first, second):
        detail = client.get(f"/api/v1/players/{pid}", headers=admin_headers).json()
        assert detail["deposit_cents"] == 800
        assert detail["games_played"] == 2

    listed = client.get(
        "/api/v1/records/deposits", params={"batch_id": batch_id, "page_size": 50}, headers=admin_headers
    ).json()
    # 两笔加押金 + 两局 × 两人
    assert listed["total"] == 6
    assert len([item for item in listed["items"] if item["reason"] == "normal_deduct"]) == 4

    with dbmod.read_session() as session:
        report = reconcile(session, admin["merchant_id"])
    assert report["ok"] is True, report
