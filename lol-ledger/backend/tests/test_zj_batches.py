"""批次：开批扣 1 次、名单限制、重复查询、越权、过期、关批与失败流水。"""

from __future__ import annotations

import pytest
from sqlalchemy import select

from app import db as dbmod
from app.models import ZjBatch, ZjQuery
from app.services import zjyumi
from tests.conftest import create_zj_user_direct

BATCHES_URL = "/api/v1/zj/batches"
PLAYERS = ["兜兜是俺滴儿#45870", "有多少人和我一样#60733"]
MATCH = {"isWin": 1, "championId": 1, "title": "新模式 胜", "detail": []}


def _open(client, headers, players=None, area_id: int = 1) -> dict:
    response = client.post(
        BATCHES_URL,
        json={"area_id": area_id, "all_count": 60, "players": players or PLAYERS},
        headers=headers,
    )
    assert response.status_code == 200, response.text
    return response.json()


@pytest.fixture(autouse=True)
def _stub_upstream(monkeypatch):
    """默认不打真实上游，需要时由各用例覆盖。"""
    monkeypatch.setattr(
        zjyumi, "query_matches", lambda nickname, area_id, all_count: ([MATCH], False)
    )


def test_open_batch_deducts_one_and_locks_roster(client, zj_user) -> None:
    body = _open(client, zj_user["headers"])

    assert body["quota"] == {"total": 10, "used": 1, "remaining": 9}
    assert body["players"] == PLAYERS
    assert body["batch_id"] > 0


def test_open_batch_without_quota_is_rejected(client, database) -> None:
    zj = create_zj_user_direct("zju02", quota_total=0)

    response = client.post(
        BATCHES_URL,
        json={"area_id": 1, "all_count": 60, "players": PLAYERS[:1]},
        headers=zj["headers"],
    )

    assert response.status_code == 400
    assert "用完" in response.json()["detail"]


@pytest.mark.parametrize(
    "players, expected",
    [
        (["没有编号的昵称"], 400),
        (["昵称#abc"], 400),
        (["兜兜#45870", "兜兜#45870"], 200),
    ],
)
def test_open_batch_validates_players(client, zj_user, players, expected) -> None:
    response = client.post(
        BATCHES_URL,
        json={"area_id": 1, "all_count": 60, "players": players},
        headers=zj_user["headers"],
    )

    assert response.status_code == expected
    if expected == 200:
        # 重复项去重后只占 1 人
        assert response.json()["players"] == ["兜兜#45870"]


def test_open_batch_rejects_too_many_players(client, zj_user) -> None:
    players = [f"玩家{i}#12345" for i in range(11)]

    response = client.post(
        BATCHES_URL,
        json={"area_id": 1, "all_count": 60, "players": players},
        headers=zj_user["headers"],
    )

    assert response.status_code == 400
    assert "最多查 10" in response.json()["detail"]


def test_query_player_returns_matches(client, zj_user) -> None:
    batch = _open(client, zj_user["headers"])

    response = client.post(
        f"{BATCHES_URL}/{batch['batch_id']}/queries",
        json={"nickname": PLAYERS[0]},
        headers=zj_user["headers"],
    )

    assert response.status_code == 200
    assert response.json()["matches"] == [MATCH]
    assert response.json()["cached"] is False


def test_query_player_outside_roster_is_forbidden(client, zj_user) -> None:
    batch = _open(client, zj_user["headers"])

    response = client.post(
        f"{BATCHES_URL}/{batch['batch_id']}/queries",
        json={"nickname": "路人甲#99999"},
        headers=zj_user["headers"],
    )

    assert response.status_code == 403


def test_query_player_twice_is_rejected(client, zj_user) -> None:
    batch = _open(client, zj_user["headers"])
    url = f"{BATCHES_URL}/{batch['batch_id']}/queries"
    payload = {"nickname": PLAYERS[0]}

    assert client.post(url, json=payload, headers=zj_user["headers"]).status_code == 200
    second = client.post(url, json=payload, headers=zj_user["headers"])

    assert second.status_code == 400
    assert "查过" in second.json()["detail"]


def test_other_user_cannot_use_batch(client, zj_user) -> None:
    batch = _open(client, zj_user["headers"])
    other = create_zj_user_direct("zju09")

    response = client.post(
        f"{BATCHES_URL}/{batch['batch_id']}/queries",
        json={"nickname": PLAYERS[0]},
        headers=other["headers"],
    )

    assert response.status_code == 404


def test_expired_batch_is_rejected(client, zj_user) -> None:
    batch = _open(client, zj_user["headers"])
    with dbmod.write_session() as session:
        stored = session.get(ZjBatch, batch["batch_id"])
        stored.expires_at = "2026-01-01T00:00:00+08:00"

    response = client.post(
        f"{BATCHES_URL}/{batch['batch_id']}/queries",
        json={"nickname": PLAYERS[0]},
        headers=zj_user["headers"],
    )

    assert response.status_code == 400
    assert "过期" in response.json()["detail"]


def test_closed_batch_is_rejected(client, zj_user) -> None:
    batch = _open(client, zj_user["headers"])
    closed = client.post(
        f"{BATCHES_URL}/{batch['batch_id']}/close", headers=zj_user["headers"]
    )
    assert closed.status_code == 204

    response = client.post(
        f"{BATCHES_URL}/{batch['batch_id']}/queries",
        json={"nickname": PLAYERS[0]},
        headers=zj_user["headers"],
    )

    assert response.status_code == 400
    assert "已结束" in response.json()["detail"]


def test_upstream_failure_still_logs_query(client, zj_user, monkeypatch) -> None:
    def boom(nickname: str, area_id: int, all_count: int):
        raise zjyumi.ZjUpstreamError("上游查询失败，请稍后重试")

    monkeypatch.setattr(zjyumi, "query_matches", boom)
    batch = _open(client, zj_user["headers"])

    response = client.post(
        f"{BATCHES_URL}/{batch['batch_id']}/queries",
        json={"nickname": PLAYERS[0]},
        headers=zj_user["headers"],
    )

    assert response.status_code == 502
    with dbmod.read_session() as session:
        rows = session.scalars(
            select(ZjQuery).where(ZjQuery.batch_id == batch["batch_id"])
        ).all()
    assert len(rows) == 1
    assert rows[0].ok is False
    assert rows[0].nickname == PLAYERS[0]


def test_failed_query_can_be_retried(client, zj_user, monkeypatch) -> None:
    batch = _open(client, zj_user["headers"])

    monkeypatch.setattr(
        zjyumi,
        "query_matches",
        lambda *args: (_ for _ in ()).throw(zjyumi.ZjUpstreamTimeout("超时")),
    )
    failed = client.post(
        f"{BATCHES_URL}/{batch['batch_id']}/queries",
        json={"nickname": PLAYERS[0]},
        headers=zj_user["headers"],
    )
    assert failed.status_code == 504

    monkeypatch.setattr(
        zjyumi, "query_matches", lambda nickname, area_id, all_count: ([MATCH], False)
    )
    retried = client.post(
        f"{BATCHES_URL}/{batch['batch_id']}/queries",
        json={"nickname": PLAYERS[0]},
        headers=zj_user["headers"],
    )
    assert retried.status_code == 200
