"""查战绩用户侧接口：登录、额度、改密，以及批次内的逐人查询。

鉴权只认 typ=zj 的令牌（见 deps.get_current_zj_user），与记账系统互斥。
"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import (
    ZjActor,
    client_ip,
    get_current_zj_user,
    get_read_db,
    get_write_db,
)
from app.schemas import ChangePasswordIn, ZjBatchCreateIn, ZjLoginIn, ZjQueryIn
from app.security import create_zj_token
from app.services import zjbatches, zjquota, zjuers

router = APIRouter(prefix="/zj", tags=["查战绩"])


@router.post("/auth/login")
def login(payload: ZjLoginIn, session: Session = Depends(get_write_db)) -> dict:
    user = zjuers.authenticate(session, payload.username, payload.password)
    token, expires_in = create_zj_token(user.id, user.password_hash)
    return {
        "access_token": token,
        "token_type": "bearer",
        "expires_in": expires_in,
        "user": zjuers.profile(user),
    }


@router.get("/auth/me")
def me(actor: ZjActor = Depends(get_current_zj_user)) -> dict:
    return {
        "id": actor.id,
        "username": actor.username,
        "display_name": actor.name,
        "quota": {
            "total": actor.quota_total,
            "used": actor.quota_used,
            "remaining": actor.quota_remaining,
        },
    }


@router.post("/auth/password", status_code=204)
def change_password(
    payload: ChangePasswordIn,
    actor: ZjActor = Depends(get_current_zj_user),
    session: Session = Depends(get_write_db),
) -> None:
    zjuers.change_own_password(
        session, actor.id, payload.old_password, payload.new_password
    )


@router.post("/batches")
def create_batch(
    payload: ZjBatchCreateIn,
    actor: ZjActor = Depends(get_current_zj_user),
    session: Session = Depends(get_write_db),
) -> dict:
    """点一次「开始查询」：扣 1 次额度并锁定这一批的玩家名单。"""
    batch, players, user = zjbatches.open_batch(
        session,
        user_id=actor.id,
        area_id=payload.area_id,
        all_count=payload.all_count,
        players=payload.players,
    )
    return {
        "batch_id": batch.id,
        "expires_at": batch.expires_at,
        "players": players,
        "quota": zjquota.quota_dict(user),
    }


@router.post("/batches/{batch_id}/queries")
def query_player(
    batch_id: int,
    payload: ZjQueryIn,
    request: Request,
    actor: ZjActor = Depends(get_current_zj_user),
    session: Session = Depends(get_read_db),
) -> dict:
    """批次内查一个玩家。只读事务 + 独立的短写事务记录流水。"""
    return zjbatches.query_player(
        session,
        user_id=actor.id,
        batch_id=batch_id,
        nickname=payload.nickname,
        ip=client_ip(request),
    )


@router.post("/batches/{batch_id}/close", status_code=204)
def close_batch(
    batch_id: int,
    actor: ZjActor = Depends(get_current_zj_user),
    session: Session = Depends(get_write_db),
) -> None:
    zjbatches.close_batch(session, user_id=actor.id, batch_id=batch_id)
