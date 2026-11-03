"""命令行：建库、商家、账号、重置密码。

    python -m app.cli init-db
    python -m app.cli create-superadmin --username admin      # 一次性引导开发者账号
    python -m app.cli create-merchant --name "极光电竞"
    python -m app.cli list-merchants
    python -m app.cli set-merchant-status --merchant "极光电竞" --status disabled
    python -m app.cli rename-merchant --merchant "极光电竞" --new-name "极光电竞（新）"
    python -m app.cli create-admin --username jg-boss --merchant "极光电竞"
    python -m app.cli create-user --username jg-01 --merchant "极光电竞" --role staff
    python -m app.cli reset-password --username admin
    python -m app.cli list-users

开发者账号建好后，商家和账号都在网页「平台管理」里维护，不需要再敲命令。
"""

from __future__ import annotations

import argparse
import getpass
import sys

from sqlalchemy import func, select

from app import db
from app.config import settings
from app.models import Merchant, Player, User
from app.security import hash_password, validate_password_strength
from app.services import options
from app.services.users import normalize_username
from app.timeutil import now_text


def _ask_password() -> str:
    first = getpass.getpass("密码: ")
    second = getpass.getpass("再输一次: ")
    if first != second:
        raise SystemExit("两次输入的密码不一致")
    return first


def _resolve_password(value: str | None) -> str:
    return value if value else _ask_password()


def _resolve_merchant(session, ref: str) -> Merchant:
    text = (ref or "").strip()
    if not text:
        raise SystemExit("请用 --merchant 指定商家（id 或名称）")
    merchant = None
    if text.isdigit():
        merchant = session.get(Merchant, int(text))
    if merchant is None:
        merchant = session.scalar(select(Merchant).where(Merchant.name == text))
    if merchant is None:
        raise SystemExit(f"找不到商家：{text}（先跑 list-merchants 看看）")
    if merchant.is_system:
        raise SystemExit("平台商家是系统保留商家，不能这样操作")
    return merchant


def _ensure_platform_merchant(session):
    """与迁移保持一致：平台商家只挂开发者账号，不出现在商家列表里。"""
    merchant = session.scalar(select(Merchant).where(Merchant.is_system.is_(True)))
    if merchant is not None:
        return merchant
    name = "平台管理"
    suffix = 2
    while session.scalar(select(Merchant.id).where(Merchant.name == name)) is not None:
        name = f"平台管理{suffix}"
        suffix += 1
    stamp = now_text()
    merchant = Merchant(
        name=name,
        note="开发者账号专属系统商家，不参与门店经营",
        status="active",
        is_system=True,
        created_at=stamp,
        updated_at=stamp,
    )
    session.add(merchant)
    session.flush()
    return merchant


def _create_merchant(name: str, note: str) -> int:
    clean = (name or "").strip()
    if not clean:
        raise SystemExit("商家名不能为空")
    if len(clean) > 64:
        raise SystemExit("商家名不能超过 64 个字符")
    with db.write_session() as session:
        exists = session.scalar(select(Merchant.id).where(Merchant.name == clean))
        if exists is not None:
            print(f"商家「{clean}」已存在（id={exists}）")
            return 1
        stamp = now_text()
        merchant = Merchant(
            name=clean,
            note=(note or "").strip()[:200],
            status="active",
            created_at=stamp,
            updated_at=stamp,
        )
        session.add(merchant)
        session.flush()
        for key, value in (
            ("last_tea_cents", 200),
            ("deposit_low_cents", 3000),
            ("deposit_high_cents", 6000),
            ("dividend_rate_percent", 50),
        ):
            options.set_int(session, merchant.id, key, value)
        print(f"已创建商家：{merchant.name}（id={merchant.id}）")
        print(f"接着建管理员：python -m app.cli create-admin --username <账号> --merchant \"{merchant.name}\"")
    return 0


def _list_merchants() -> int:
    with db.read_session() as session:
        merchants = list(session.scalars(select(Merchant).order_by(Merchant.id)))
        if not merchants:
            print("还没有商家，先执行 create-merchant --name ...")
            return 0
        for merchant in merchants:
            users = int(
                session.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(User.merchant_id == merchant.id)
                )
                or 0
            )
            players = int(
                session.scalar(
                    select(func.count())
                    .select_from(Player)
                    .where(
                        Player.merchant_id == merchant.id,
                        Player.deleted_at.is_(None),
                    )
                )
                or 0
            )
            if merchant.is_system:
                state = "系统"
            elif merchant.status == "active":
                state = "启用"
            else:
                state = "停用"
            print(
                f"{merchant.id:>3}  {merchant.name:<24} {state}  "
                f"账号 {users:>2}  玩家 {players:>3}  建于 {merchant.created_at[:10]}"
            )
    return 0


def _set_merchant_status(ref: str, status: str) -> int:
    if status not in ("active", "disabled"):
        raise SystemExit("--status 只能是 active 或 disabled")
    with db.write_session() as session:
        merchant = _resolve_merchant(session, ref)
        merchant.status = status
        merchant.updated_at = now_text()
        print(f"商家「{merchant.name}」已改为 {status}")
    return 0


def _rename_merchant(ref: str, new_name: str) -> int:
    clean = (new_name or "").strip()
    if not clean:
        raise SystemExit("新商家名不能为空")
    with db.write_session() as session:
        merchant = _resolve_merchant(session, ref)
        clash = session.scalar(
            select(Merchant.id).where(
                Merchant.name == clean, Merchant.id != merchant.id
            )
        )
        if clash is not None:
            print(f"商家名「{clean}」已被占用（id={clash}）")
            return 1
        old = merchant.name
        merchant.name = clean
        merchant.updated_at = now_text()
        print(f"商家已改名：{old} → {clean}")
    return 0


def _create_user(
    username: str,
    password: str,
    display_name: str,
    role: str,
    merchant_ref: str,
) -> int:
    name = normalize_username(username)
    validate_password_strength(password, name)
    with db.write_session() as session:
        merchant = _resolve_merchant(session, merchant_ref)
        if merchant.status != "active":
            print(f"商家「{merchant.name}」已停用，不能新增账号")
            return 1
        existing = session.scalar(select(User).where(User.username == name))
        if existing is not None:
            print(f"账号 {name} 已存在，未做修改")
            return 1
        stamp = now_text()
        user = User(
            merchant_id=merchant.id,
            username=name,
            password_hash=hash_password(password),
            display_name=display_name or name,
            role=role,
            is_active=True,
            password_changed_at=stamp,
            last_login_at=None,
            created_at=stamp,
            updated_at=stamp,
        )
        session.add(user)
        session.flush()
        if role == "admin" and merchant.custodian_user_id is None:
            merchant.custodian_user_id = user.id
            merchant.updated_at = stamp
    print(f"已在「{merchant.name}」创建 {role} 账号：{name}")
    return 0


def _create_superadmin(username: str, password: str, display_name: str) -> int:
    name = normalize_username(username)
    validate_password_strength(password, name)
    with db.write_session() as session:
        platform = _ensure_platform_merchant(session)
        user = session.scalar(select(User).where(User.username == name))
        stamp = now_text()
        if user is not None:
            if user.merchant_id != platform.id and user.role == "admin" and user.is_active:
                others = session.scalar(
                    select(func.count())
                    .select_from(User)
                    .where(
                        User.merchant_id == user.merchant_id,
                        User.role == "admin",
                        User.is_active.is_(True),
                        User.id != user.id,
                    )
                )
                if int(others or 0) <= 0:
                    old = session.get(Merchant, user.merchant_id)
                    raise SystemExit(
                        f"账号 {name} 是商家「{old.name if old else user.merchant_id}」"
                        "唯一的管理员，先给该店加一个管理员，或换一个用户名"
                    )
            user.is_superadmin = True
            user.role = "admin"
            user.is_active = True
            user.merchant_id = platform.id
            user.password_hash = hash_password(password)
            user.password_changed_at = stamp
            user.updated_at = stamp
            if display_name:
                user.display_name = display_name
            print(f"已把 {name} 升级为开发者账号，现在可以在网页「平台管理」里操作")
            return 0

        session.add(
            User(
                merchant_id=platform.id,
                username=name,
                password_hash=hash_password(password),
                display_name=display_name or name,
                role="admin",
                is_active=True,
                is_superadmin=True,
                password_changed_at=stamp,
                last_login_at=None,
                created_at=stamp,
                updated_at=stamp,
            )
        )
    print(f"已创建开发者账号：{name}（登录后进入「平台管理」）")
    return 0


def _reset_password(username: str, password: str) -> int:
    name = (username or "").strip().lower()
    with db.write_session() as session:
        user = session.scalar(select(User).where(User.username == name))
        if user is None:
            print(f"找不到账号 {name}")
            return 1
        validate_password_strength(password, user.username)
        stamp = now_text()
        user.password_hash = hash_password(password)
        user.password_changed_at = stamp
        user.updated_at = stamp
    print(f"已重置 {name} 的密码")
    return 0


def _list_users() -> int:
    with db.read_session() as session:
        rows = session.execute(
            select(User, Merchant)
            .join(Merchant, Merchant.id == User.merchant_id)
            .order_by(User.merchant_id, User.id)
        ).all()
    if not rows:
        print("还没有账号，先执行 create-merchant 和 create-admin")
        return 0
    for user, merchant in rows:
        state = "启用" if user.is_active else "停用"
        role = "开发者" if user.is_superadmin else user.role
        print(
            f"{user.id:>3}  {user.username:<16} {role:<6} {state}  "
            f"{merchant.name:<20} 最后登录 {user.last_login_at or '-'}"
        )
    return 0


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(prog="python -m app.cli", description="LOL 记录管理运维命令")
    sub = parser.add_subparsers(dest="command", required=True)

    sub.add_parser("init-db", help="建表、默认商家与默认配置")

    merchant = sub.add_parser("create-merchant", help="创建商家")
    merchant.add_argument("--name", required=True)
    merchant.add_argument("--note", default="")

    sub.add_parser("list-merchants", help="列出商家")

    status = sub.add_parser("set-merchant-status", help="启用或停用商家")
    status.add_argument("--merchant", required=True, help="商家 id 或名称")
    status.add_argument("--status", required=True, choices=["active", "disabled"])

    rename = sub.add_parser("rename-merchant", help="给商家改名")
    rename.add_argument("--merchant", required=True, help="商家 id 或名称")
    rename.add_argument("--new-name", required=True)

    superadmin = sub.add_parser("create-superadmin", help="创建/升级开发者账号（平台管理）")
    superadmin.add_argument("--username", required=True)
    superadmin.add_argument("--password")
    superadmin.add_argument("--display-name", default="")

    admin = sub.add_parser("create-admin", help="创建商家管理员")
    admin.add_argument("--username", required=True)
    admin.add_argument("--merchant", required=True, help="商家 id 或名称")
    admin.add_argument("--password")
    admin.add_argument("--display-name", default="")

    staff = sub.add_parser("create-user", help="创建账号")
    staff.add_argument("--username", required=True)
    staff.add_argument("--merchant", required=True, help="商家 id 或名称")
    staff.add_argument("--password")
    staff.add_argument("--display-name", default="")
    staff.add_argument("--role", choices=["admin", "staff"], default="staff")

    reset = sub.add_parser("reset-password", help="重置密码")
    reset.add_argument("--username", required=True)
    reset.add_argument("--password")

    sub.add_parser("list-users", help="列出账号（带商家）")

    args = parser.parse_args(argv)
    print(f"数据库：{settings.db_path}")

    if args.command == "init-db":
        db.ensure_schema()
        print("建表完成")
        return 0
    if args.command == "create-merchant":
        db.ensure_schema()
        return _create_merchant(args.name, args.note)
    if args.command == "list-merchants":
        db.ensure_schema()
        return _list_merchants()
    if args.command == "set-merchant-status":
        db.ensure_schema()
        return _set_merchant_status(args.merchant, args.status)
    if args.command == "rename-merchant":
        db.ensure_schema()
        return _rename_merchant(args.merchant, args.new_name)
    if args.command == "create-superadmin":
        db.ensure_schema()
        return _create_superadmin(
            args.username,
            _resolve_password(args.password),
            args.display_name,
        )
    if args.command in ("create-admin", "create-user"):
        db.ensure_schema()
        role = "admin" if args.command == "create-admin" else args.role
        return _create_user(
            args.username,
            _resolve_password(args.password),
            args.display_name,
            role,
            args.merchant,
        )
    if args.command == "reset-password":
        return _reset_password(args.username, _resolve_password(args.password))
    if args.command == "list-users":
        return _list_users()
    parser.print_help()
    return 2


if __name__ == "__main__":
    sys.exit(main())
