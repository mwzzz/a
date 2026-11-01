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

from app import db as dbmod  # noqa: E402
from app.main import app  # noqa: E402
from app.models import Merchant, User  # noqa: E402
from app.security import create_access_token, hash_password  # noqa: E402
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
