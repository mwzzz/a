"""分红结算：按日期区间统计，取消班次后不再依赖批次。"""

from __future__ import annotations

from datetime import datetime, timedelta, timezone

import pytest
from sqlalchemy import select
from sqlalchemy.exc import IntegrityError

from app import db as dbmod
from app.models import DividendSettlement, DividendSettlementSession
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


def test_overlapping_range_only_settles_new_sessions(client, admin_headers, admin) -> None:
    """区间重叠不再吞掉整段：已结算的那局排除，新那局照常结算。"""
    _session(client, admin_headers, ["甲"], tea=300)
    first = settle_dividends(client, admin_headers, [admin["id"]])
    assert first.status_code == 201
    assert first.json()[0]["dividend_cents"] == 150

    _session(client, admin_headers, ["乙"], tea=900)

    again = settle_dividends(client, admin_headers, [admin["id"]])
    assert again.status_code == 201, again.text
    assert again.json()[0]["session_count"] == 1
    assert again.json()[0]["tea_cents"] == 900
    assert again.json()[0]["dividend_cents"] == 450

    preview = _preview(client, admin_headers)
    assert preview["totals"]["pending_dividend_cents"] == 0
    assert preview["totals"]["claimed_session_count"] == 2
    assert any("结算过" in text for text in preview["warnings"])


def test_backdated_session_inside_settled_range_is_payable(
    client, admin_headers, admin
) -> None:
    """结算之后补录进同一区间的局，不会再被当成已结算而永久漏付。"""
    yesterday = (datetime.now(CN) - timedelta(days=1)).date().isoformat()
    first = new_player(client, admin_headers, "当晚客")
    later = new_player(client, admin_headers, "补录客")
    for item in (first, later):
        add_money(client, admin_headers, item["id"], 3000)

    create_session(
        client, admin_headers, [first["id"]], tea=300, played_at=f"{yesterday}T10:00:00"
    )
    settled = client.post(
        "/api/v1/reports/dividends/settle",
        json={
            "user_ids": [admin["id"]],
            "date_from": yesterday,
            "date_to": yesterday,
        },
        headers=admin_headers,
    )
    assert settled.status_code == 201, settled.text

    create_session(
        client, admin_headers, [later["id"]], tea=700, played_at=f"{yesterday}T18:00:00"
    )

    preview = _preview(client, admin_headers, yesterday, yesterday)
    row = next(item for item in preview["items"] if item["user"]["id"] == admin["id"])
    assert row["pending"]["session_count"] == 1
    assert row["pending"]["dividend_cents"] == 350
    assert row["settled"]["dividend_cents"] == 150
    assert any("漏结" in text for text in preview["warnings"])

    again = client.post(
        "/api/v1/reports/dividends/settle",
        json={
            "user_ids": [admin["id"]],
            "date_from": yesterday,
            "date_to": yesterday,
        },
        headers=admin_headers,
    )
    assert again.status_code == 201
    assert again.json()[0]["dividend_cents"] == 350


def test_minute_end_includes_second_tail(client, admin_headers, admin) -> None:
    """分钟级右边界要吃掉该分钟的 01~59 秒，否则这局两头都不在区间里。"""
    player = new_player(client, admin_headers, "深夜客")
    add_money(client, admin_headers, player["id"], 3000)
    create_session(
        client, admin_headers, [player["id"]], tea=600, played_at=f"{TODAY}T23:59:30"
    )

    narrow = client.get(
        "/api/v1/reports/dividends/preview",
        params={"date_from": f"{TODAY}T00:00", "date_to": f"{TODAY}T23:59"},
        headers=admin_headers,
    ).json()
    assert narrow["period"]["end"] == f"{TODAY}T23:59:59+08:00"
    row = next(item for item in narrow["items"] if item["user"]["id"] == admin["id"])
    assert row["pending"]["session_count"] == 1
    assert row["pending"]["tea_cents"] == 600

    assert settle_dividends(client, admin_headers, [admin["id"]]).status_code == 201


def test_settled_session_cannot_be_claimed_twice(client, admin_headers, admin) -> None:
    """数据库层兜底：同一局挂第二条未冲销的认领直接违反唯一索引。"""
    _session(client, admin_headers, ["甲"])
    assert settle_dividends(client, admin_headers, [admin["id"]]).status_code == 201

    with dbmod.write_session() as session:
        claim = session.scalars(
            select(DividendSettlementSession).order_by(DividendSettlementSession.id)
        ).all()[0]
        settlement_id = claim.settlement_id
        session_id = claim.session_id
        user_id = claim.user_id
        merchant_id = claim.merchant_id

    with pytest.raises(IntegrityError):
        with dbmod.write_session() as session:
            session.add(
                DividendSettlementSession(
                    settlement_id=settlement_id,
                    session_id=session_id,
                    user_id=user_id,
                    merchant_id=merchant_id,
                    tea_cents=300,
                    created_at=f"{TODAY}T12:00:00+08:00",
                )
            )
            session.flush()


def test_void_releases_sessions_for_repay(client, admin_headers, admin) -> None:
    """冲销只软标记：金额与区间不动，场次重新变为待结算。"""
    _session(client, admin_headers, ["甲"], tea=300)
    settled = settle_dividends(client, admin_headers, [admin["id"]], note="发错了")
    assert settled.status_code == 201
    settlement_id = settled.json()[0]["id"]

    voided = client.post(
        f"/api/v1/reports/dividends/settlements/{settlement_id}/void",
        json={"note": "金额算错，线下追回"},
        headers=admin_headers,
    )
    assert voided.status_code == 200, voided.text
    body = voided.json()
    assert body["released_session_count"] == 1
    assert body["dividend_cents"] == 150
    assert body["void_note"] == "金额算错，线下追回"

    preview = _preview(client, admin_headers)
    row = next(item for item in preview["items"] if item["user"]["id"] == admin["id"])
    assert row["pending"]["dividend_cents"] == 150
    assert row["settled"]["dividend_cents"] == 0

    # 重新结算拿到的还是同一局，金额不会翻倍
    again = settle_dividends(client, admin_headers, [admin["id"]])
    assert again.status_code == 201
    assert again.json()[0]["dividend_cents"] == 150

    history = client.get(
        "/api/v1/reports/dividends/settlements", headers=admin_headers
    ).json()
    assert history["total"] == 2
    statuses = {item["id"]: item["status"] for item in history["items"]}
    assert statuses[settlement_id] == "voided"
    original = next(i for i in history["items"] if i["id"] == settlement_id)
    assert original["dividend_cents"] == 150
    assert original["voided_by"]["id"] == admin["id"]

    repeat = client.post(
        f"/api/v1/reports/dividends/settlements/{settlement_id}/void",
        json={"note": "再冲一次"},
        headers=admin_headers,
    )
    assert repeat.status_code == 400
    assert "已经冲销" in repeat.json()["detail"]

    only_live = client.get(
        "/api/v1/reports/dividends/settlements",
        params={"status": "live"},
        headers=admin_headers,
    ).json()
    assert all(item["status"] == "live" for item in only_live["items"])
    assert only_live["total"] == 1


def test_void_requires_admin_and_own_merchant(client, admin_headers, staff_headers, admin) -> None:
    _session(client, admin_headers, ["甲"])
    settlement_id = settle_dividends(client, admin_headers, [admin["id"]]).json()[0]["id"]

    assert (
        client.post(
            f"/api/v1/reports/dividends/settlements/{settlement_id}/void",
            json={"note": "店员想冲销"},
            headers=staff_headers,
        ).status_code
        == 403
    )
    assert (
        client.post(
            "/api/v1/reports/dividends/settlements/424242/void",
            json={"note": "不存在"},
            headers=admin_headers,
        ).status_code
        == 404
    )


def test_disabled_user_still_settleable(client, admin_headers, staff_headers, staff) -> None:
    """人停用了，活儿是停之前干的：结算页标注但照样能结。"""
    _session(client, staff_headers, ["甲"], tea=300)
    assert (
        client.patch(
            f"/api/v1/users/{staff['id']}", json={"is_active": False}, headers=admin_headers
        ).status_code
        == 200
    )

    preview = _preview(client, admin_headers)
    row = next(item for item in preview["items"] if item["user"]["id"] == staff["id"])
    assert row["is_active"] is False
    assert row["pending"]["dividend_cents"] == 150

    settled = settle_dividends(client, admin_headers, [staff["id"]])
    assert settled.status_code == 201
    assert settled.json()[0]["dividend_cents"] == 150


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


def test_legacy_date_period_still_counts_as_settled(client, admin_headers, admin) -> None:
    """历史结算只存到日期：已结算列仍要认得它，不能显示成没结过。"""
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

    preview = _preview(client, admin_headers)
    row = next(item for item in preview["items"] if item["user"]["id"] == admin["id"])
    assert row["settled"]["dividend_cents"] == 150
    assert row["pending"]["dividend_cents"] == 0


def test_garbage_period_does_not_break_preview(client, admin_headers, admin) -> None:
    """一条脏 period 不能让整页结算 500，跳过即可。"""
    _session(client, admin_headers, ["甲"])
    with dbmod.write_session() as session:
        session.add(
            DividendSettlement(
                merchant_id=1,
                user_id=admin["id"],
                username_snapshot="脏数据",
                period_start="not-a-date",
                period_end="still-not-a-date",
                session_count=1,
                tea_cents=300,
                dividend_cents=150,
                settled_by=admin["id"],
                created_at=f"{TODAY}T10:00:00+08:00",
            )
        )

    preview = _preview(client, admin_headers)
    assert preview["totals"]["pending_dividend_cents"] == 150


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
