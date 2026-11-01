"""场次：预览扣费、开局、列表。开局只能落在本商家自己的批次里。"""

from __future__ import annotations

from datetime import date as date_cls

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError
from app.models import GameSession, Player, SessionPlayer
from app.serializers import session_player_row, session_row
from app.scope import scoped_get
from app.services import options
from app.services.audit import write_audit
from app.services.batches import get_batch, get_open_batch
from app.services.deposits import _write_entry, apply_delta
from app.services.money import deposit_level
from app.services.players import clean_text, get_player
from app.timeutil import day_after_text, day_start_text, normalize_played_at, now_text, parse_text

MAX_PLAYERS = 10


def default_name(
    session: Session, batch_id: int, played_at: str, merchant_id: int
) -> str:
    day = parse_text(played_at)
    index = int(
        session.scalar(
            select(func.count())
            .select_from(GameSession)
            .where(
                GameSession.merchant_id == merchant_id,
                GameSession.batch_id == batch_id,
            )
        )
        or 0
    )
    return f"{day.month}月{day.day}日 第{index + 1}局"


def _unique_ids(player_ids: list[int]) -> list[int]:
    seen: set[int] = set()
    result: list[int] = []
    for raw in player_ids:
        try:
            value = int(raw)
        except (TypeError, ValueError) as exc:
            raise AppError("玩家参数不正确") from exc
        if value not in seen:
            seen.add(value)
            result.append(value)
    return result


def preview_session(
    session: Session, merchant_id: int, player_ids: list[int], tea_fee_cents: int
) -> dict:
    if tea_fee_cents < 0:
        raise AppError("茶水不能为负")
    ids = _unique_ids(player_ids)
    if len(ids) > MAX_PLAYERS:
        raise AppError(f"一局最多 {MAX_PLAYERS} 个人")
    low, high = options.thresholds(session, merchant_id)

    items: list[dict] = []
    for player_id in ids:
        player = get_player(session, player_id, merchant_id)
        before = int(player.deposit_cents)
        after = before - int(tea_fee_cents)
        items.append(
            {
                "player_id": player.id,
                "game_id": player.game_id,
                "account": player.account,
                "before_cents": before,
                "deduct_cents": int(tea_fee_cents),
                "after_cents": after,
                "level": deposit_level(after, low, high),
                "negative": after < 0,
            }
        )
    negative = [item for item in items if item["negative"]]
    return {
        "items": items,
        "count": len(items),
        "tea_fee_cents": int(tea_fee_cents),
        "tea_total_cents": int(tea_fee_cents) * len(items),
        "negative_count": len(negative),
        "negative_players": [item["game_id"] for item in negative],
    }


def open_session(
    session: Session,
    actor: Actor,
    *,
    batch_id: int | None = None,
    name: str = "",
    played_at: str | None = None,
    note: str = "",
    tea_fee_cents: int = 0,
    player_ids: list[int] | None = None,
    ip: str = "",
) -> dict:
    if tea_fee_cents < 0:
        raise AppError("茶水不能为负")
    ids = _unique_ids(player_ids or [])
    if not ids:
        raise AppError("请选择玩家")
    if len(ids) > MAX_PLAYERS:
        raise AppError(f"一局最多 {MAX_PLAYERS} 个人")

    merchant_id = actor.merchant_id
    if batch_id is None:
        batch = get_open_batch(session, merchant_id)
        if batch is None:
            raise AppError("当前没有进行中的批次，请先开班")
    else:
        batch = get_batch(session, batch_id, merchant_id)
        if batch.status != "open":
            raise AppError("这个批次已经交班了，不能开局")
    batch_id = batch.id

    try:
        moment = normalize_played_at(played_at)
    except ValueError as exc:
        raise AppError("场次时间格式不正确") from exc

    players = [get_player(session, player_id, merchant_id) for player_id in ids]
    title = clean_text(name, "场次名称", 64) or default_name(
        session, batch_id, moment, merchant_id
    )
    note_text = clean_text(note, "备注", 200)
    stamp = now_text()

    game = GameSession(
        merchant_id=merchant_id,
        batch_id=batch_id,
        name=title,
        played_at=moment,
        tea_fee_cents=int(tea_fee_cents),
        note=note_text,
        operator_id=actor.id,
        player_count=len(players),
        created_at=stamp,
    )
    session.add(game)
    session.flush()
    game_id = game.id

    members: list[SessionPlayer] = []
    for player_id in ids:
        before, after = apply_delta(
            session,
            player_id,
            -int(tea_fee_cents),
            merchant_id=merchant_id,
            games_delta=1,
        )
        entry = _write_entry(
            session,
            actor=actor,
            player_id=player_id,
            reason="normal_deduct",
            amount_cents=int(tea_fee_cents),
            before=before,
            after=after,
            batch_id=batch_id,
            session_id=game_id,
            note=note_text,
        )
        member = SessionPlayer(
            session_id=game_id,
            player_id=player_id,
            tea_fee_cents=int(tea_fee_cents),
            balance_before_cents=before,
            balance_after_cents=after,
            ledger_id=entry.id,
        )
        session.add(member)
        members.append(member)

    options.set_int(session, merchant_id, "last_tea_cents", int(tea_fee_cents), actor.id)
    session.flush()

    write_audit(
        session,
        merchant_id=merchant_id,
        user_id=actor.id,
        action="open_session",
        target_type="session",
        target_id=game_id,
        detail=f"开局 {title}，{len(players)} 人，每人 {tea_fee_cents} 分",
        ip=ip,
    )

    refreshed = get_session_model(session, game_id, merchant_id)
    return session_row(refreshed, members)


def get_session_model(session: Session, session_id: int, merchant_id: int) -> GameSession:
    return scoped_get(session, GameSession, session_id, merchant_id, "找不到这个场次")


def list_sessions(
    session: Session,
    merchant_id: int,
    *,
    batch_id: int | None = None,
    keyword: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 20,
) -> dict:
    page = max(1, int(page))
    page_size = min(200, max(1, int(page_size)))

    conditions = [GameSession.merchant_id == merchant_id]
    if batch_id is not None:
        conditions.append(GameSession.batch_id == batch_id)
    text = (keyword or "").strip()
    if text:
        like = f"%{text}%"
        matched_players = (
            select(SessionPlayer.session_id)
            .join(Player, Player.id == SessionPlayer.player_id)
            .where(Player.game_id.like(like), Player.merchant_id == merchant_id)
        )
        conditions.append(
            or_(GameSession.name.like(like), GameSession.id.in_(matched_players))
        )
    try:
        if date_from:
            conditions.append(
                GameSession.played_at >= day_start_text(date_cls.fromisoformat(date_from))
            )
        if date_to:
            conditions.append(
                GameSession.played_at < day_after_text(date_cls.fromisoformat(date_to))
            )
    except ValueError as exc:
        raise AppError("日期格式不正确") from exc

    total = int(
        session.scalar(
            select(func.count()).select_from(GameSession).where(*conditions)
        )
        or 0
    )
    games = list(
        session.scalars(
            select(GameSession)
            .where(*conditions)
            .order_by(GameSession.played_at.desc(), GameSession.id.desc())
            .offset((page - 1) * page_size)
            .limit(page_size)
        )
    )
    members: dict[int, list[SessionPlayer]] = {}
    if games:
        ids = [game.id for game in games]
        for item in session.scalars(
            select(SessionPlayer).where(SessionPlayer.session_id.in_(ids))
        ):
            members.setdefault(item.session_id, []).append(item)

    return {
        "items": [session_row(game, members.get(game.id, [])) for game in games],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


def get_session_detail(session: Session, session_id: int, merchant_id: int) -> dict:
    game = get_session_model(session, session_id, merchant_id)
    players = list(
        session.scalars(select(SessionPlayer).where(SessionPlayer.session_id == session_id))
    )
    data = session_row(game, players)
    data["batch"] = (
        {"id": game.batch.id, "label": game.batch.label, "opened_at": game.batch.opened_at}
        if game.batch
        else None
    )
    return data


def session_preview_rows(
    session: Session, session_id: int, merchant_id: int
) -> list[dict]:
    get_session_model(session, session_id, merchant_id)
    rows = list(
        session.scalars(select(SessionPlayer).where(SessionPlayer.session_id == session_id))
    )
    return [session_player_row(item) for item in rows]
