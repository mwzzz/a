"""玩家库：增删改查、搜索、排序、软删除。所有入口都带 merchant_id。"""

from __future__ import annotations

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError, ForbiddenError, NotFoundError
from app.models import LedgerEntry, Player, User
from app.serializers import player_option, player_row
from app.scope import scoped_get
from app.services import options
from app.services.audit import write_audit
from app.timeutil import now_text

SORT_OPTIONS = {
    "games_played_desc",
    "deposit_desc",
    "deposit_asc",
    "last_active_desc",
    "game_id_asc",
}


def normalize_game_id(value: str) -> str:
    game_id = (value or "").strip()
    if not game_id:
        raise AppError("请填写游戏 id")
    if any(char in game_id for char in "\r\n\t"):
        raise AppError("游戏 id 不能包含换行")
    if len(game_id) > 64:
        raise AppError("游戏 id 不能超过 64 个字符")
    return game_id


def clean_text(value: str | None, field: str, limit: int = 64) -> str:
    text = (value or "").strip()
    if any(char in text for char in "\r\n\t"):
        raise AppError(f"{field}不能包含换行")
    if len(text) > limit:
        raise AppError(f"{field}不能超过 {limit} 个字符")
    return text


def get_player(session: Session, player_id: int, merchant_id: int) -> Player:
    """按 id + 商家取玩家。别家的玩家和已删除的玩家一律当作不存在。"""
    player = scoped_get(session, Player, player_id, merchant_id, "找不到玩家")
    if player.deleted_at is not None:
        raise NotFoundError("找不到玩家")
    return player


def create_player(
    session: Session,
    actor: Actor,
    *,
    game_id: str,
    nickname: str = "",
    account: str = "",
    remark: str = "",
    ip: str = "",
) -> Player:
    merchant_id = actor.merchant_id
    name = normalize_game_id(game_id)
    exists = session.scalar(
        select(Player.id).where(
            Player.merchant_id == merchant_id,
            Player.game_id == name,
            Player.deleted_at.is_(None),
        )
    )
    if exists is not None:
        raise AppError("游戏 id 已存在")

    stamp = now_text()
    player = Player(
        merchant_id=merchant_id,
        game_id=name,
        nickname=clean_text(nickname, "昵称"),
        account=clean_text(account, "账号"),
        remark=clean_text(remark, "备注", 200),
        deposit_cents=0,
        games_played=0,
        creator_id=actor.id,
        created_at=stamp,
        updated_at=stamp,
        deleted_at=None,
    )
    session.add(player)
    session.flush()
    write_audit(
        session,
        merchant_id=merchant_id,
        user_id=actor.id,
        action="create_player",
        target_type="player",
        target_id=player.id,
        detail=f"新增玩家 {player.game_id}",
        ip=ip,
    )
    return player


def update_player(
    session: Session,
    actor: Actor,
    player_id: int,
    *,
    game_id: str | None = None,
    nickname: str | None = None,
    account: str | None = None,
    remark: str | None = None,
    ip: str = "",
) -> Player:
    merchant_id = actor.merchant_id
    player = get_player(session, player_id, merchant_id)

    if game_id is not None:
        name = normalize_game_id(game_id)
        if name != player.game_id:
            clash = session.scalar(
                select(Player.id).where(
                    Player.merchant_id == merchant_id,
                    Player.game_id == name,
                    Player.deleted_at.is_(None),
                    Player.id != player.id,
                )
            )
            if clash is not None:
                raise AppError("游戏 id 已存在")
            player.game_id = name
    if nickname is not None:
        player.nickname = clean_text(nickname, "昵称")
    if account is not None:
        player.account = clean_text(account, "账号")
    if remark is not None:
        player.remark = clean_text(remark, "备注", 200)

    player.updated_at = now_text()
    write_audit(
        session,
        merchant_id=merchant_id,
        user_id=actor.id,
        action="update_player",
        target_type="player",
        target_id=player.id,
        detail=f"修改玩家 {player.game_id}",
        ip=ip,
    )
    return player


def soft_delete_player(
    session: Session,
    actor: Actor,
    player_id: int,
    *,
    ip: str = "",
) -> None:
    if not actor.is_admin:
        raise ForbiddenError("只有管理员可以删除玩家")
    player = get_player(session, player_id, actor.merchant_id)
    if int(player.deposit_cents) != 0:
        raise AppError("押金不为 0，不能删除")
    player.deleted_at = now_text()
    player.updated_at = player.deleted_at
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="delete_player",
        target_type="player",
        target_id=player.id,
        detail=f"删除玩家 {player.game_id}",
        ip=ip,
    )


def _filters(
    keyword: str,
    level: str | None,
    merchant_id: int,
    low: int,
    high: int,
):
    conditions = [
        Player.merchant_id == merchant_id,
        Player.deleted_at.is_(None),
    ]
    text = (keyword or "").strip()
    if text:
        like = f"%{text}%"
        conditions.append(
            or_(
                Player.game_id.like(like),
                Player.account.like(like),
                Player.nickname.like(like),
                Player.remark.like(like),
            )
        )
    if level == "low":
        conditions.append(Player.deposit_cents < low)
    elif level == "warn":
        conditions.append(Player.deposit_cents >= low)
        conditions.append(Player.deposit_cents <= high)
    elif level == "safe":
        conditions.append(Player.deposit_cents > high)
    return conditions


def list_players(
    session: Session,
    merchant_id: int,
    *,
    keyword: str = "",
    level: str | None = None,
    sort: str = "games_played_desc",
    page: int = 1,
    page_size: int = 20,
) -> dict:
    low, high = options.thresholds(session, merchant_id)
    if sort not in SORT_OPTIONS:
        sort = "games_played_desc"
    page = max(1, int(page))
    page_size = min(200, max(1, int(page_size)))

    conditions = _filters(keyword, level, merchant_id, low, high)
    total = int(
        session.scalar(select(func.count()).select_from(Player).where(*conditions)) or 0
    )

    last_active = func.max(LedgerEntry.created_at).label("last_active_at")
    stmt = (
        select(Player, last_active)
        .outerjoin(
            LedgerEntry,
            (LedgerEntry.player_id == Player.id)
            & (LedgerEntry.merchant_id == merchant_id),
        )
        .where(*conditions)
        .group_by(Player.id)
    )

    if sort == "deposit_desc":
        stmt = stmt.order_by(Player.deposit_cents.desc(), Player.game_id.asc())
    elif sort == "deposit_asc":
        stmt = stmt.order_by(Player.deposit_cents.asc(), Player.game_id.asc())
    elif sort == "last_active_desc":
        stmt = stmt.order_by(last_active.desc(), Player.id.desc())
    elif sort == "game_id_asc":
        stmt = stmt.order_by(Player.game_id.asc())
    else:
        stmt = stmt.order_by(Player.games_played.desc(), Player.game_id.asc())

    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    rows = session.execute(stmt).all()

    items = [
        player_row(player, low_cents=low, high_cents=high, last_active_at=active)
        for player, active in rows
    ]
    return {"items": items, "total": total, "page": page, "page_size": page_size}


def list_options(
    session: Session,
    merchant_id: int,
    *,
    keyword: str = "",
    exclude_ids: list[int] | None = None,
    limit: int = 20,
) -> list[dict]:
    conditions = [
        Player.merchant_id == merchant_id,
        Player.deleted_at.is_(None),
    ]
    text = (keyword or "").strip()
    if text:
        like = f"%{text}%"
        conditions.append(
            or_(
                Player.game_id.like(like),
                Player.account.like(like),
                Player.nickname.like(like),
            )
        )
    if exclude_ids:
        conditions.append(Player.id.notin_(exclude_ids))
    stmt = (
        select(Player)
        .where(*conditions)
        .order_by(Player.games_played.desc(), Player.game_id.asc())
        .limit(max(1, min(50, int(limit))))
    )
    return [player_option(player) for player in session.scalars(stmt)]


def player_detail(session: Session, merchant_id: int, player_id: int) -> dict:
    low, high = options.thresholds(session, merchant_id)
    player = get_player(session, player_id, merchant_id)
    entries = list(
        session.scalars(
            select(LedgerEntry)
            .where(
                LedgerEntry.merchant_id == merchant_id,
                LedgerEntry.player_id == player_id,
            )
            .order_by(LedgerEntry.id.desc())
        )
    )
    total_in = sum(
        int(entry.amount_cents)
        for entry in entries
        if entry.reason in ("add_deposit", "transfer_in")
    )
    total_out = sum(
        int(entry.amount_cents)
        for entry in entries
        if entry.reason not in ("add_deposit", "transfer_in")
    )
    last_active = entries[0].created_at if entries else player.created_at
    data = player_row(player, low_cents=low, high_cents=high, last_active_at=last_active)
    data["total_in_cents"] = total_in
    data["total_out_cents"] = total_out
    data["entry_count"] = len(entries)
    return data


def creator_rows(session: Session, ids: set[int], merchant_id: int) -> dict[int, User]:
    if not ids:
        return {}
    return {
        user.id: user
        for user in session.scalars(
            select(User).where(User.id.in_(ids), User.merchant_id == merchant_id)
        )
    }
