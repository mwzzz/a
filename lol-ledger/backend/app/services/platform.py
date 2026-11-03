"""开发者（超管）控制台：跨商家管理商家与账号。

与门店接口的边界：
- 超管只做「商家 / 账号」运维，不进入任何门店的玩家、场次、流水。
- 门店管理员看不到、也改不了超管账号（列表过滤 + 取账号直接 404）。
"""

from __future__ import annotations

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError, ForbiddenError, NotFoundError
from app.models import Merchant, Player, User
from app.security import hash_password, validate_password_strength
from app.services import custody, options
from app.services.audit import write_audit
from app.services.users import normalize_username, user_row
from app.timeutil import now_text

DEFAULT_MERCHANT_SETTINGS = (
    ("last_tea_cents", 200),
    ("deposit_low_cents", 3000),
    ("deposit_high_cents", 6000),
    ("dividend_rate_percent", 50),
)


def _ensure_superadmin(actor: Actor) -> None:
    if not actor.is_superadmin:
        raise ForbiddenError("只有开发者账号可以操作")


def platform_merchant(session: Session) -> Merchant:
    merchant = session.scalar(select(Merchant).where(Merchant.is_system.is_(True)))
    if merchant is None:
        raise AppError("平台商家未初始化，请先执行数据库迁移")
    return merchant


def _merchant_or_404(session: Session, merchant_id: int) -> Merchant:
    merchant = session.get(Merchant, merchant_id)
    if merchant is None or merchant.is_system:
        raise NotFoundError("找不到这个商家")
    return merchant


def merchant_row(session: Session, merchant: Merchant) -> dict:
    user_count = session.scalar(
        select(func.count())
        .select_from(User)
        .where(User.merchant_id == merchant.id, User.is_superadmin.is_(False))
    )
    player_count = session.scalar(
        select(func.count())
        .select_from(Player)
        .where(Player.merchant_id == merchant.id, Player.deleted_at.is_(None))
    )
    return {
        "id": merchant.id,
        "name": merchant.name,
        "note": merchant.note,
        "status": merchant.status,
        "user_count": int(user_count or 0),
        "player_count": int(player_count or 0),
        "created_at": merchant.created_at,
        "updated_at": merchant.updated_at,
    }


def list_merchants(session: Session, actor: Actor) -> list[Merchant]:
    _ensure_superadmin(actor)
    return list(
        session.scalars(
            select(Merchant)
            .where(Merchant.is_system.is_(False))
            .order_by(Merchant.id)
        )
    )


def _clean_merchant_name(session: Session, raw: str, *, exclude_id: int | None = None) -> str:
    name = (raw or "").strip()
    if not name:
        raise AppError("商家名不能为空")
    if len(name) > 64:
        raise AppError("商家名不能超过 64 个字符")
    query = select(Merchant.id).where(Merchant.name == name)
    if exclude_id is not None:
        query = query.where(Merchant.id != exclude_id)
    if session.scalar(query) is not None:
        raise AppError("商家名已被占用")
    return name


def _create_merchant_admin(
    session: Session,
    actor: Actor,
    merchant: Merchant,
    *,
    username: str,
    password: str,
    display_name: str,
    ip: str,
) -> User:
    if not password:
        raise AppError("请填写管理员的初始密码")
    name = normalize_username(username)
    validate_password_strength(password, name)
    if session.scalar(select(User.id).where(User.username == name)) is not None:
        raise AppError(f"用户名 {name} 已存在")
    stamp = now_text()
    user = User(
        merchant_id=merchant.id,
        username=name,
        password_hash=hash_password(password),
        display_name=(display_name or "").strip()[:64],
        role="admin",
        is_active=True,
        is_superadmin=False,
        password_changed_at=stamp,
        last_login_at=None,
        created_at=stamp,
        updated_at=stamp,
    )
    session.add(user)
    session.flush()
    if merchant.custodian_user_id is None:
        merchant.custodian_user_id = user.id
        merchant.updated_at = stamp
    write_audit(
        session,
        merchant_id=merchant.id,
        user_id=actor.id,
        action="create_user",
        target_type="user",
        target_id=user.id,
        detail=f"开发者新建管理员 {name}",
        ip=ip,
    )
    return user


def create_merchant(
    session: Session,
    actor: Actor,
    *,
    name: str,
    note: str = "",
    admin_username: str | None = None,
    admin_password: str | None = None,
    admin_display_name: str = "",
    ip: str = "",
) -> tuple[Merchant, User | None]:
    _ensure_superadmin(actor)
    clean = _clean_merchant_name(session, name)
    if admin_username and not admin_password:
        raise AppError("填写了管理员用户名，就要同时填写初始密码")
    if admin_password and not admin_username:
        raise AppError("填写了初始密码，就要同时填写管理员用户名")

    stamp = now_text()
    merchant = Merchant(
        name=clean,
        note=(note or "").strip()[:200],
        status="active",
        is_system=False,
        created_at=stamp,
        updated_at=stamp,
    )
    session.add(merchant)
    session.flush()
    for key, value in DEFAULT_MERCHANT_SETTINGS:
        options.set_int(session, merchant.id, key, value, actor.id)

    admin = None
    if admin_username:
        admin = _create_merchant_admin(
            session,
            actor,
            merchant,
            username=admin_username,
            password=admin_password or "",
            display_name=admin_display_name,
            ip=ip,
        )

    write_audit(
        session,
        merchant_id=merchant.id,
        user_id=actor.id,
        action="create_merchant",
        target_type="merchant",
        target_id=merchant.id,
        detail=f"开发者开通商家 {merchant.name}",
        ip=ip,
    )
    return merchant, admin


def update_merchant(
    session: Session,
    actor: Actor,
    merchant_id: int,
    *,
    name: str | None = None,
    note: str | None = None,
    status: str | None = None,
    ip: str = "",
) -> Merchant:
    _ensure_superadmin(actor)
    merchant = _merchant_or_404(session, merchant_id)
    changes: list[str] = []

    if name is not None:
        clean = _clean_merchant_name(session, name, exclude_id=merchant.id)
        if clean != merchant.name:
            merchant.name = clean
            changes.append("商家名")
    if note is not None:
        merchant.note = note.strip()[:200]
        changes.append("备注")
    if status is not None:
        if status not in ("active", "disabled"):
            raise AppError("商家状态只能是 active 或 disabled")
        if status != merchant.status:
            merchant.status = status
            changes.append("停用" if status == "disabled" else "启用")
    if not changes:
        return merchant

    merchant.updated_at = now_text()
    write_audit(
        session,
        merchant_id=merchant.id,
        user_id=actor.id,
        action="update_merchant",
        target_type="merchant",
        target_id=merchant.id,
        detail="开发者修改商家：" + "、".join(changes),
        ip=ip,
    )
    return merchant


def list_users(session: Session, actor: Actor, merchant_id: int) -> list[User]:
    _ensure_superadmin(actor)
    _merchant_or_404(session, merchant_id)
    return list(
        session.scalars(
            select(User)
            .where(User.merchant_id == merchant_id, User.is_superadmin.is_(False))
            .order_by(User.id)
        )
    )


def create_user(
    session: Session,
    actor: Actor,
    merchant_id: int,
    *,
    username: str,
    password: str,
    display_name: str = "",
    role: str = "staff",
    ip: str = "",
) -> User:
    _ensure_superadmin(actor)
    merchant = _merchant_or_404(session, merchant_id)
    if merchant.status != "active":
        raise AppError("商家已停用，先启用再开账号")
    name = normalize_username(username)
    validate_password_strength(password, name)
    if role not in ("admin", "staff"):
        raise AppError("角色不正确")
    if session.scalar(select(User.id).where(User.username == name)) is not None:
        raise AppError("用户名已存在")

    stamp = now_text()
    user = User(
        merchant_id=merchant.id,
        username=name,
        password_hash=hash_password(password),
        display_name=(display_name or "").strip()[:64],
        role=role,
        is_active=True,
        is_superadmin=False,
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
    write_audit(
        session,
        merchant_id=merchant.id,
        user_id=actor.id,
        action="create_user",
        target_type="user",
        target_id=user.id,
        detail=f"开发者新建 {role} 账号 {name}",
        ip=ip,
    )
    return user


def _user_or_404(session: Session, user_id: int) -> User:
    user = session.get(User, user_id)
    if user is None or user.is_superadmin:
        raise NotFoundError("找不到这个账号")
    return user


def update_user(
    session: Session,
    actor: Actor,
    user_id: int,
    *,
    display_name: str | None = None,
    role: str | None = None,
    is_active: bool | None = None,
    ip: str = "",
) -> User:
    _ensure_superadmin(actor)
    user = _user_or_404(session, user_id)
    if role is not None and role not in ("admin", "staff"):
        raise AppError("角色不正确")
    if is_active is False and custody.is_holder(session, user.merchant_id, user.id):
        raise AppError("该账号正在保管现金，先让门店完成交班再停用")

    losing_admin = user.role == "admin" and user.is_active and (
        role == "staff" or is_active is False
    )
    if losing_admin:
        others = session.scalar(
            select(func.count())
            .select_from(User)
            .where(
                User.merchant_id == user.merchant_id,
                User.is_superadmin.is_(False),
                User.role == "admin",
                User.is_active.is_(True),
                User.id != user.id,
            )
        )
        if int(others or 0) <= 0:
            raise AppError("这是该商家最后一个启用的管理员，请先加一个管理员")

    if display_name is not None:
        user.display_name = display_name.strip()[:64]
    if role is not None:
        user.role = role
    if is_active is not None:
        user.is_active = is_active
    user.updated_at = now_text()
    write_audit(
        session,
        merchant_id=user.merchant_id,
        user_id=actor.id,
        action="update_user",
        target_type="user",
        target_id=user.id,
        detail=f"开发者修改账号 {user.username}",
        ip=ip,
    )
    return user


def reset_password(
    session: Session,
    actor: Actor,
    user_id: int,
    new_password: str,
    ip: str = "",
) -> None:
    _ensure_superadmin(actor)
    user = _user_or_404(session, user_id)
    validate_password_strength(new_password, user.username)
    stamp = now_text()
    user.password_hash = hash_password(new_password)
    user.password_changed_at = stamp
    user.updated_at = stamp
    write_audit(
        session,
        merchant_id=user.merchant_id,
        user_id=actor.id,
        action="reset_password",
        target_type="user",
        target_id=user.id,
        detail=f"开发者重置 {user.username} 的密码",
        ip=ip,
    )


def account_row(user: User) -> dict:
    return user_row(user)
