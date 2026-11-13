"""查询批次：开批扣 1 次、限定名单、逐人查询、关批。

「扣次后无限查」被三件事挡住：批次名单固定、每人只能成功查一次、批次有到期时间。
"""

from __future__ import annotations

import logging
import re
from datetime import timedelta
from typing import Any

from sqlalchemy import select
from sqlalchemy.orm import Session

from app import db as dbmod
from app.config import settings
from app.errors import AppError, ForbiddenError, NotFoundError
from app.models import ZjBatch, ZjBatchPlayer, ZjQuery, ZjUser
from app.services import zjquota, zjyumi
from app.timeutil import now_cn, now_text, parse_text, to_text

logger = logging.getLogger(__name__)

PLAYER_PATTERN = re.compile(r"^[^#\r\n]{1,64}#\d{3,8}$")
HARD_MAX_PLAYERS = 10
HARD_MAX_COUNT = 100


def _nickname_limit() -> int:
    return max(1, min(int(settings.zj_batch_max_players), HARD_MAX_PLAYERS))


def clean_players(raw_players: list[str]) -> list[str]:
    """去空白、去重、校验「昵称#编号」，并按配置限制人数。"""
    cleaned: list[str] = []
    seen: set[str] = set()
    for raw in raw_players:
        name = (raw or "").strip()[:80]
        if not name or name in seen:
            continue
        if not PLAYER_PATTERN.match(name):
            raise AppError(f"玩家格式不正确：{name}（需要「昵称#编号」）")
        seen.add(name)
        cleaned.append(name)

    if not cleaned:
        raise AppError("请先粘贴玩家列表（每行一个「昵称#编号」）")
    limit = _nickname_limit()
    if len(cleaned) > limit:
        raise AppError(f"一次最多查 {limit} 名玩家，请分批查询")
    return cleaned


def open_batch(
    session: Session,
    *,
    user_id: int,
    area_id: int,
    all_count: int,
    players: list[str],
) -> tuple[ZjBatch, list[str], ZjUser]:
    """校验名单 → 原子扣 1 次 → 建批次与名单。调用方需在写事务里。"""
    cleaned = clean_players(players)
    count = max(1, min(int(all_count), HARD_MAX_COUNT))
    area = int(area_id)
    if area not in zjyumi.AREAS:
        raise AppError("大区不正确")

    user = zjquota.deduct_one(session, user_id)

    stamp = now_text()
    ttl_minutes = max(5, int(settings.zj_batch_ttl_minutes))
    batch = ZjBatch(
        user_id=user.id,
        area_id=area,
        all_count=count,
        player_count=len(cleaned),
        query_count=0,
        status="open",
        created_at=stamp,
        expires_at=to_text(now_cn() + timedelta(minutes=ttl_minutes)),
        last_query_at=None,
    )
    session.add(batch)
    session.flush()
    for seq, nickname in enumerate(cleaned):
        session.add(ZjBatchPlayer(batch_id=batch.id, seq=seq, nickname=nickname))
    session.flush()
    logger.info(
        "开批：账号 %s 批次 %s，%s 名玩家，剩余 %s 次",
        user.username,
        batch.id,
        len(cleaned),
        user.quota_remaining,
    )
    return batch, cleaned, user


def _record_query(
    *,
    batch_id: int,
    user_id: int,
    nickname: str,
    ok: bool,
    err_code: str,
    games: int,
    ip: str,
) -> None:
    """用量流水单独起一个短事务：查询失败时主请求会抛错回滚，日志仍要留下。"""
    stamp = now_text()
    with dbmod.write_session() as session:
        session.add(
            ZjQuery(
                batch_id=batch_id,
                user_id=user_id,
                nickname=nickname,
                ok=ok,
                err_code=err_code[:32],
                games=max(int(games), 0),
                ip=ip[:64],
                created_at=stamp,
            )
        )
        batch = session.get(ZjBatch, batch_id)
        if batch is not None:
            batch.query_count += 1
            batch.last_query_at = stamp


def _load_batch(session: Session, user_id: int, batch_id: int) -> ZjBatch:
    batch = session.get(ZjBatch, batch_id)
    if batch is None or batch.user_id != user_id:
        raise NotFoundError("查询批次不存在")
    if batch.status != "open":
        raise AppError("这一批查询已结束，请重新开始查询")
    if parse_text(batch.expires_at) <= now_cn():
        raise AppError("这一批查询已过期，请重新开始查询")
    return batch


def query_player(
    session: Session,
    *,
    user_id: int,
    batch_id: int,
    nickname: str,
    ip: str = "",
) -> dict[str, Any]:
    """查一个玩家。只允许查本批名单内、且本批还没成功的玩家。"""
    name = (nickname or "").strip()[:80]
    batch = _load_batch(session, user_id, batch_id)

    allowed = session.scalar(
        select(ZjBatchPlayer.seq).where(
            ZjBatchPlayer.batch_id == batch.id, ZjBatchPlayer.nickname == name
        )
    )
    if allowed is None:
        raise ForbiddenError("只能查这一批名单里的玩家")

    done = session.scalar(
        select(ZjQuery.id).where(
            ZjQuery.batch_id == batch.id,
            ZjQuery.nickname == name,
            ZjQuery.ok.is_(True),
        )
    )
    if done is not None:
        raise AppError("这名玩家在本次查询里已经查过了")

    try:
        matches, cached = zjyumi.query_matches(name, batch.area_id, batch.all_count)
    except AppError as exc:
        _record_query(
            batch_id=batch.id,
            user_id=user_id,
            nickname=name,
            ok=False,
            err_code=str(exc.status_code),
            games=0,
            ip=ip,
        )
        raise

    _record_query(
        batch_id=batch.id,
        user_id=user_id,
        nickname=name,
        ok=True,
        err_code="",
        games=len(matches),
        ip=ip,
    )
    return {"matches": matches, "cached": cached}


def close_batch(session: Session, *, user_id: int, batch_id: int) -> None:
    batch = session.get(ZjBatch, batch_id)
    if batch is None or batch.user_id != user_id:
        raise NotFoundError("查询批次不存在")
    if batch.status != "open":
        return
    batch.status = "closed"
