"""玩家库接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.deps import Actor, client_ip, get_current_user, get_read_db, get_write_db, require_admin
from app.schemas import PlayerCreateIn, PlayerUpdateIn
from app.serializers import player_row
from app.services import options
from app.services import players as player_service
from app.services.records import player_ledger

router = APIRouter(prefix="/players", tags=["玩家"])


def _parse_ids(raw: str) -> list[int]:
    result: list[int] = []
    for part in (raw or "").split(","):
        part = part.strip()
        if part.isdigit():
            result.append(int(part))
    return result


@router.get("")
def list_players(
    keyword: str = "",
    level: str | None = None,
    sort: str = "games_played_desc",
    page: int = 1,
    page_size: int = 20,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return player_service.list_players(
        session,
        actor.merchant_id,
        keyword=keyword,
        level=level,
        sort=sort,
        page=page,
        page_size=page_size,
    )


@router.get("/options")
def player_options(
    keyword: str = "",
    exclude_ids: str = "",
    limit: int = 20,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> list[dict]:
    return player_service.list_options(
        session,
        actor.merchant_id,
        keyword=keyword,
        exclude_ids=_parse_ids(exclude_ids),
        limit=limit,
    )


@router.get("/{player_id}")
def get_player(
    player_id: int,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return player_service.player_detail(session, actor.merchant_id, player_id)


@router.get("/{player_id}/ledger")
def get_player_ledger(
    player_id: int,
    page: int = 1,
    page_size: int = 20,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return player_ledger(
        session, player_id, actor.merchant_id, page=page, page_size=page_size
    )


@router.post("", status_code=201)
def create_player(
    payload: PlayerCreateIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    player = player_service.create_player(
        session,
        actor,
        game_id=payload.game_id,
        nickname=payload.nickname,
        account=payload.account,
        remark=payload.remark,
        ip=client_ip(request),
    )
    low, high = options.thresholds(session, actor.merchant_id)
    return player_row(player, low_cents=low, high_cents=high)


@router.patch("/{player_id}")
def update_player(
    player_id: int,
    payload: PlayerUpdateIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    player = player_service.update_player(
        session,
        actor,
        player_id,
        game_id=payload.game_id,
        nickname=payload.nickname,
        account=payload.account,
        remark=payload.remark,
        ip=client_ip(request),
    )
    low, high = options.thresholds(session, actor.merchant_id)
    return player_row(player, low_cents=low, high_cents=high)


@router.delete("/{player_id}", status_code=204)
def delete_player(
    player_id: int,
    request: Request,
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_write_db),
) -> Response:
    player_service.soft_delete_player(session, actor, player_id, ip=client_ip(request))
    return Response(status_code=204)
