"""配额：原子扣次、边界拦截、管理员加减、流水与总览。"""

from __future__ import annotations

import pytest

from app import db as dbmod
from app.errors import AppError, AuthError
from app.models import ZjBatch, ZjQuery, ZjUser
from app.services import zjquota
from app.timeutil import now_text
from tests.conftest import create_superadmin_direct, create_zj_user_direct


def test_deduct_one_uses_one_quota(database) -> None:
    zj = create_zj_user_direct(quota_total=2)

    with dbmod.write_session() as session:
        user = zjquota.deduct_one(session, zj["id"])
        assert user.quota_used == 1
        assert user.quota_remaining == 1

    with dbmod.read_session() as session:
        assert session.get(ZjUser, zj["id"]).quota_used == 1


def test_deduct_stops_when_quota_is_used_up(database) -> None:
    zj = create_zj_user_direct(quota_total=1)
    with dbmod.write_session() as session:
        zjquota.deduct_one(session, zj["id"])

    with pytest.raises(AppError) as exc:
        with dbmod.write_session() as session:
            zjquota.deduct_one(session, zj["id"])

    assert "用完" in str(exc.value)
    with dbmod.read_session() as session:
        assert session.get(ZjUser, zj["id"]).quota_used == 1


def test_deduct_rejects_inactive_account(database) -> None:
    zj = create_zj_user_direct(quota_total=5, is_active=False)

    with pytest.raises(AuthError) as exc:
        with dbmod.write_session() as session:
            zjquota.deduct_one(session, zj["id"])

    assert "停用" in str(exc.value)


def test_grant_adds_quota_and_writes_flow(database) -> None:
    admin = create_superadmin_direct()
    zj = create_zj_user_direct(quota_total=5)

    with dbmod.write_session() as session:
        user = zjquota.grant_quota(
            session, user_id=zj["id"], delta=10, operator_id=admin["id"], note="首充"
        )
        assert user.quota_total == 15

    with dbmod.read_session() as session:
        logs = zjquota.recent_logs(session, zj["id"])
    item = logs["items"][0]
    assert item["type"] == "grant"
    assert item["delta"] == 10
    assert item["remaining"] == 15
    assert item["note"] == "首充"
    assert item["operator"] == "开发者"


def test_grant_cannot_go_below_used(database) -> None:
    admin = create_superadmin_direct()
    zj = create_zj_user_direct(quota_total=5)
    with dbmod.write_session() as session:
        zjquota.deduct_one(session, zj["id"])
        zjquota.deduct_one(session, zj["id"])

    with pytest.raises(AppError) as exc:
        with dbmod.write_session() as session:
            zjquota.grant_quota(
                session, user_id=zj["id"], delta=-4, operator_id=admin["id"]
            )

    assert "已用" in str(exc.value)
    with dbmod.read_session() as session:
        assert session.get(ZjUser, zj["id"]).quota_total == 5


def test_zero_delta_is_rejected(database) -> None:
    admin = create_superadmin_direct()
    zj = create_zj_user_direct()

    with pytest.raises(AppError) as exc:
        with dbmod.write_session() as session:
            zjquota.grant_quota(session, user_id=zj["id"], delta=0, operator_id=admin["id"])

    assert "不能为 0" in str(exc.value)


def test_logs_merge_grants_and_queries(database) -> None:
    admin = create_superadmin_direct()
    zj = create_zj_user_direct(quota_total=5)

    with dbmod.write_session() as session:
        stamp = now_text()
        batch = ZjBatch(
            user_id=zj["id"],
            area_id=1,
            all_count=60,
            player_count=1,
            query_count=1,
            status="open",
            created_at=stamp,
            expires_at=stamp,
        )
        session.add(batch)
        session.flush()
        session.add(
            ZjQuery(
                batch_id=batch.id,
                user_id=zj["id"],
                nickname="兜兜#45870",
                ok=True,
                err_code="",
                games=12,
                ip="127.0.0.1",
                created_at=stamp,
            )
        )
        zjquota.grant_quota(
            session, user_id=zj["id"], delta=5, operator_id=admin["id"], note="续费"
        )

    with dbmod.read_session() as session:
        logs = zjquota.recent_logs(session, zj["id"])

    kinds = {item["type"] for item in logs["items"]}
    assert kinds == {"grant", "query"}
    query_item = next(item for item in logs["items"] if item["type"] == "query")
    assert query_item["nickname"] == "兜兜#45870"
    assert query_item["games"] == 12


def test_overview_counts_users_and_remaining(database) -> None:
    first = create_zj_user_direct("zju01", quota_total=5)
    create_zj_user_direct("zju02", quota_total=3)

    with dbmod.write_session() as session:
        zjquota.deduct_one(session, first["id"])

    with dbmod.read_session() as session:
        overview = zjquota.overview(session)

    assert overview["users"] == 2
    assert overview["active_users"] == 2
    assert overview["remaining"] == 7
