"""测试夹具：每个测试一个独立 SQLite 文件，默认带一个商家。"""

from __future__ import annotations

import os
import tempfile
from pathlib import Path

_TMP_ROOT = Path(tempfile.mkdtemp(prefix="lol-ledger-tests-"))
os.environ["DB_PATH"] = str(_TMP_ROOT / "import.db")
os.environ["JWT_SECRET"] = "test-secret-0123456789abcdef0123456789abcdef"
os.environ["DEBUG"] = "false"

import pytest  # noqa: E402
from fastapi.testclient import TestClient  # noqa: E402
from sqlalchemy import select  # noqa: E402

from app import db as dbmod  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Merchant, User, ZjUser  # noqa: E402
from app.security import create_access_token, create_zj_token, hash_password  # noqa: E402
from app.services import options  # noqa: E402
from app.timeutil import now_text  # noqa: E402

DEFAULT_PASSWORD = "Passw0rd123"
DEFAULT_MERCHANT_ID = 1
DEFAULT_MERCHANT_NAME = "默认商家"

DEFAULT_SETTINGS = (
    ("last_tea_cents", 200),
    ("deposit_low_cents", 3000),
    ("deposit_high_cents", 6000),
)


@pytest.fixture()
def database(tmp_path):
    path = tmp_path / "test.db"
    dbmod.configure_db(path)
    dbmod.ensure_schema()
    yield path
    dbmod.dispose()


@pytest.fixture()
def client(database):
    with TestClient(app) as test_client:
        yield test_client


def create_merchant_direct(name: str) -> int:
    """直接建一个商家并写入默认设置，返回 merchant_id。"""
    with dbmod.write_session() as session:
        stamp = now_text()
        merchant = Merchant(
            name=name,
            note="",
            status="active",
            created_at=stamp,
            updated_at=stamp,
        )
        session.add(merchant)
        session.flush()
        merchant_id = merchant.id
        for key, value in DEFAULT_SETTINGS:
            options.set_int(session, merchant_id, key, value)
    return merchant_id


def create_user_direct(
    username: str,
    role: str = "admin",
    password: str = DEFAULT_PASSWORD,
    display_name: str = "",
    is_active: bool = True,
    merchant_id: int = DEFAULT_MERCHANT_ID,
) -> dict:
    """直接建账号并签一个 token，不经过登录接口。"""
    with dbmod.write_session() as session:
        merchant = session.get(Merchant, merchant_id)
        if merchant is None:
            raise RuntimeError(f"商家 {merchant_id} 不存在，先建商家")
        merchant_name = merchant.name
        stamp = now_text()
        password_hash = hash_password(password)
        user = User(
            merchant_id=merchant_id,
            username=username,
            password_hash=password_hash,
            display_name=display_name or username,
            role=role,
            is_active=is_active,
            password_changed_at=stamp,
            last_login_at=None,
            created_at=stamp,
            updated_at=stamp,
        )
        session.add(user)
        session.flush()
        if role == "admin" and merchant.custodian_user_id is None:
            merchant.custodian_user_id = user.id
        user_id = user.id
    token, _ = create_access_token(user_id, role, password_hash)
    return {
        "id": user_id,
        "username": username,
        "password": password,
        "role": role,
        "merchant_id": merchant_id,
        "merchant_name": merchant_name,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def current_user_id(client, headers) -> int:
    return int(client.get("/api/v1/auth/me", headers=headers).json()["id"])


def settle_dividends(client, headers, user_ids: list[int], note: str = ""):
    """按当天区间结算分红（班次已取消，结算不再依赖班次）。"""
    return client.post(
        "/api/v1/reports/dividends/settle",
        json={"user_ids": user_ids, "note": note},
        headers=headers,
    )


def create_superadmin_direct(
    username: str = "root",
    password: str = DEFAULT_PASSWORD,
    display_name: str = "开发者",
) -> dict:
    """开发者账号挂在平台商家下，不经过登录接口。"""
    with dbmod.write_session() as session:
        merchant = session.scalar(select(Merchant).where(Merchant.is_system.is_(True)))
        if merchant is None:
            raise RuntimeError("平台商家不存在")
        stamp = now_text()
        password_hash = hash_password(password)
        user = User(
            merchant_id=merchant.id,
            username=username,
            password_hash=password_hash,
            display_name=display_name,
            role="admin",
            is_active=True,
            is_superadmin=True,
            password_changed_at=stamp,
            last_login_at=None,
            created_at=stamp,
            updated_at=stamp,
        )
        session.add(user)
        session.flush()
        user_id = user.id
        merchant_id = merchant.id
        merchant_name = merchant.name
    token, _ = create_access_token(user_id, "admin", password_hash)
    return {
        "id": user_id,
        "username": username,
        "password": password,
        "role": "admin",
        "merchant_id": merchant_id,
        "merchant_name": merchant_name,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


def create_zj_user_direct(
    username: str = "zju01",
    password: str = DEFAULT_PASSWORD,
    quota_total: int = 10,
    is_active: bool = True,
    display_name: str = "",
) -> dict:
    """直接建一个查战绩账号并签 zj 令牌，不经过登录接口。"""
    with dbmod.write_session() as session:
        stamp = now_text()
        password_hash = hash_password(password)
        user = ZjUser(
            username=username,
            password_hash=password_hash,
            display_name=display_name or username,
            note="",
            quota_total=quota_total,
            quota_used=0,
            is_active=is_active,
            password_changed_at=stamp,
            last_login_at=None,
            created_at=stamp,
            updated_at=stamp,
        )
        session.add(user)
        session.flush()
        user_id = user.id
    token, _ = create_zj_token(user_id, password_hash)
    return {
        "id": user_id,
        "username": username,
        "password": password,
        "quota_total": quota_total,
        "token": token,
        "headers": {"Authorization": f"Bearer {token}"},
    }


@pytest.fixture()
def zj_user(database) -> dict:
    return create_zj_user_direct()


@pytest.fixture()
def zj_headers(zj_user) -> dict:
    return zj_user["headers"]


@pytest.fixture()
def superadmin(database) -> dict:
    return create_superadmin_direct()


@pytest.fixture()
def superadmin_headers(superadmin) -> dict:
    return superadmin["headers"]


@pytest.fixture()
def admin(database) -> dict:
    return create_user_direct("admin", "admin", display_name="店长")


@pytest.fixture()
def staff(database) -> dict:
    return create_user_direct("xiaomei", "staff", display_name="小美")


@pytest.fixture()
def admin_headers(admin) -> dict:
    return admin["headers"]


@pytest.fixture()
def staff_headers(staff) -> dict:
    return staff["headers"]


@pytest.fixture()
def merchant_b(database) -> int:
    return create_merchant_direct("蜘蛛电竞")


@pytest.fixture()
def admin_b(merchant_b) -> dict:
    return create_user_direct(
        "zz-boss", "admin", display_name="蜘蛛店长", merchant_id=merchant_b
    )


@pytest.fixture()
def admin_b_headers(admin_b) -> dict:
    return admin_b["headers"]


@pytest.fixture()
def staff_b(merchant_b) -> dict:
    return create_user_direct(
        "zz-01", "staff", display_name="蜘蛛店员", merchant_id=merchant_b
    )


@pytest.fixture()
def staff_b_headers(staff_b) -> dict:
    return staff_b["headers"]
