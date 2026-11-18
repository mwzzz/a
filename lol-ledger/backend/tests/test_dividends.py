"""分红结算：按日期区间统计，取消班次后不再依赖批次。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

from sqlalchemy import select

from app import db as dbmod
from app.models import DividendSettlement
from tests.conftest import settle_dividends
from tests.test_players import add_money, new_player
from tests.test_sessions import create_session

CN = timezone(timedelta(hours=8))
TODAY = datetime.now(CN).date().isoformat()


def _session(client, headers, names: list[str], tea: int = 300) -> dict:
    ids = []
    for name in names:
        player = new_player(client, headers, name)
        add_money(client, headers, player["id"], 2000)
        ids.append(player["id"])
    return create_session(client, headers, ids, tea=tea)


def _preview(client, headers, date_from: str = TODAY, date_to: str = TODAY) -> dict:
    return client.get(
        "/api/v1/reports/dividends/preview",
        params={"date_from": date_from, "date_to": date_to},
        headers=headers,
    ).json()


def test_preview_and_settle(client, admin_headers, admin) -> None:
    _session(client, admin_headers, ["甲", "乙"])
    _session(client, admin_headers, ["丙"], tea=500)

    preview = _preview(client, admin_headers)
    assert preview["period"]["start"] == f"{TODAY}T00:00:00+08:00"
    assert preview["period"]["end"] == f"{TODAY}T23:59:59+08:00"
    row = next(item for item in preview["items"] if item["user"]["id"] == admin["id"])
    assert row["pending"]["session_count"] == 2
    assert row["pending"]["player_times"] == 3
    assert row["pending"]["tea_cents"] == 1100
    assert row["pending"]["dividend_cents"] == 550
    assert row["status"] == "pending"

    response = settle_dividends(client, admin_headers, [admin["id"]])
    assert response.status_code == 201, response.text
    assert response.json()[0]["dividend_cents"] == 550

    # 结算后同一区间不再有待结
    assert _preview(client, admin_headers)["totals"]["pending_dividend_cents"] == 0

    history = client.get("/api/v1/reports/dividends/settlements", headers=admin_headers).json()
    assert history["total"] == 1
    assert history["items"][0]["session_count"] == 2
    assert history["items"][0]["period"]["start"] == f"{TODAY}T00:00:00+08:00"
    assert history["items"][0]["period"]["end"] == f"{TODAY}T23:59:59+08:00"


def test_repeat_settle_rejected(client, admin_headers, admin) -> None:
    _session(client, admin_headers, ["甲"])
    assert settle_dividends(client, admin_headers, [admin["id"]]).status_code == 201

    again = settle_dividends(client, admin_headers, [admin["id"]])
    assert again.status_code == 400
    assert "没有可结算" in again.json()["detail"]


def test_overlapping_period_rejected(client, admin_headers, admin) -> None:
    _session(client, admin_headers, ["甲"])
    assert settle_dividends(client, admin_headers, [admin["id"]]).status_code == 201
    _session(client, admin_headers, ["乙"])

    # 区间覆盖了已结算的今天
    again = settle_dividends(client, admin_headers, [admin["id"]]).status_code
    assert again == 400


def test_period_outside_is_empty(client, admin_headers) -> None:
    _session(client, admin_headers, ["甲"])
    preview = _preview(client, admin_headers, "2020-01-01", "2020-01-02")
    assert preview["items"] == []
    assert preview["totals"]["pending_dividend_cents"] == 0


def test_invalid_period(client, admin_headers) -> None:
    bad = client.get(
        "/api/v1/reports/dividends/preview",
        params={"date_from": "2026-13-40", "date_to": "2026-13-41"},
        headers=admin_headers,
    )
    assert bad.status_code == 400

    reversed_ = client.get(
        "/api/v1/reports/dividends/preview",
        params={"date_from": TODAY, "date_to": "2020-01-01"},
        headers=admin_headers,
    )
    assert reversed_.status_code == 400


def test_staff_cannot_settle(client, staff_headers, admin_headers) -> None:
    _session(client, admin_headers, ["甲"])
    assert (
        client.get("/api/v1/reports/dividends/preview", headers=staff_headers).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/reports/dividends/settle",
            json={"user_ids": [1]},
            headers=staff_headers,
        ).status_code
        == 403
    )
    assert (
        client.get(
            "/api/v1/reports/dividends/settlements", headers=staff_headers
        ).status_code
        == 403
    )


def test_empty_and_unknown_users(client, admin_headers) -> None:
    _session(client, admin_headers, ["甲"])
    assert (
        client.post(
            "/api/v1/reports/dividends/settle",
            json={"user_ids": []},
            headers=admin_headers,
        ).status_code
        == 422
    )
    unknown = client.post(
        "/api/v1/reports/dividends/settle",
        json={"user_ids": [999999]},
        headers=admin_headers,
    )
    assert unknown.status_code == 400


def test_fixed_mode_counts_sessions(client, admin_headers, admin) -> None:
    settings = client.patch(
        "/api/v1/settings",
        json={"dividend_mode": "fixed", "dividend_fixed_cents": 500},
        headers=admin_headers,
    )
    assert settings.status_code == 200

    _session(client, admin_headers, ["甲", "乙"], tea=0)
    _session(client, admin_headers, ["丙"], tea=1800)

    row = next(
        item
        for item in _preview(client, admin_headers)["items"]
        if item["user"]["id"] == admin["id"]
    )
    # 每局 5 元 × 2 局，与茶水多少无关
    assert row["pending"]["session_count"] == 2
    assert row["pending"]["dividend_cents"] == 1000


def test_no_data_gives_empty(client, admin_headers) -> None:
    preview = _preview(client, admin_headers)
    assert preview["items"] == []
    response = settle_dividends(client, admin_headers, [1])
    assert response.status_code == 400


def test_minute_level_range(client, admin_headers, admin) -> None:
    """精确到分钟时只统计区间内的场次。"""
    first = new_player(client, admin_headers, "上午场")
    second = new_player(client, admin_headers, "夜场")
    for item in (first, second):
        add_money(client, admin_headers, item["id"], 3000)

    create_session(
        client, admin_headers, [first["id"]], tea=300, played_at=f"{TODAY}T09:30:00"
    )
    create_session(
        client, admin_headers, [second["id"]], tea=500, played_at=f"{TODAY}T21:10:00"
    )

    narrow = client.get(
        "/api/v1/reports/dividends/preview",
        params={"date_from": f"{TODAY}T09:00", "date_to": f"{TODAY}T10:00"},
        headers=admin_headers,
    ).json()
    row = next(item for item in narrow["items"] if item["user"]["id"] == admin["id"])
    assert row["pending"]["session_count"] == 1
    assert row["pending"]["tea_cents"] == 300

    whole = _preview(client, admin_headers)
    row2 = next(item for item in whole["items"] if item["user"]["id"] == admin["id"])
    assert row2["pending"]["session_count"] == 2
    assert row2["pending"]["tea_cents"] == 800


def test_legacy_date_period_still_blocks(client, admin_headers, admin) -> None:
    """历史结算只存到日期，新的分钟级区间仍应判为重叠。"""
    _session(client, admin_headers, ["历史客"])
    assert settle_dividends(client, admin_headers, [admin["id"]]).status_code == 201

    with dbmod.write_session() as session:
        row = session.scalar(
            select(DividendSettlement).order_by(DividendSettlement.id.desc())
        )
        assert row is not None
        row.period_start = TODAY
        row.period_end = TODAY
        session.flush()

    again = settle_dividends(client, admin_headers, [admin["id"]])
    assert again.status_code == 400


def test_summary_supports_minutes(client, admin_headers, admin) -> None:
    """汇总接口同样吃分钟级区间。"""
    player = new_player(client, admin_headers, "分钟客")
    add_money(client, admin_headers, player["id"], 2000)
    create_session(
        client, admin_headers, [player["id"]], tea=400, played_at=f"{TODAY}T14:20:00"
    )

    inside = client.get(
        "/api/v1/summary/operators",
        params={"date_from": f"{TODAY}T14:00", "date_to": f"{TODAY}T14:30"},
        headers=admin_headers,
    ).json()
    assert inside["totals"]["session_count"] == 1
    assert inside["totals"]["tea_cents"] == 400

    outside = client.get(
        "/api/v1/summary/operators",
        params={"date_from": f"{TODAY}T15:00", "date_to": f"{TODAY}T16:00"},
        headers=admin_headers,
    ).json()
    assert outside["totals"]["session_count"] == 0
