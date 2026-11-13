"""常用名单接口（小工具）。店员和管理员都能编辑。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request
from sqlalchemy.orm import Session

from app.deps import Actor, client_ip, get_current_user, get_read_db, get_write_db
from app.schemas import (
    ToolItemCreateIn,
    ToolItemUpdateIn,
    ToolListCreateIn,
    ToolMoveIn,
)
from app.services import tool_lists as tool_service

router = APIRouter(prefix="/tools/name-lists", tags=["常用名单"])


@router.get("")
def list_all(
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return tool_service.list_all(session, actor.merchant_id)


@router.post("", status_code=201)
def create_list(
    payload: ToolListCreateIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return tool_service.create_list(
        session, actor, payload.name, ip=client_ip(request)
    )


@router.patch("/{list_id}")
def rename_list(
    list_id: int,
    payload: ToolListCreateIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return tool_service.rename_list(
        session, actor, list_id, payload.name, ip=client_ip(request)
    )


@router.delete("/{list_id}")
def delete_list(
    list_id: int,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return tool_service.delete_list(
        session, actor, list_id, ip=client_ip(request)
    )


@router.post("/{list_id}/move")
def move_list(
    list_id: int,
    payload: ToolMoveIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return tool_service.move_list(
        session, actor, list_id, payload.direction, ip=client_ip(request)
    )


@router.post("/{list_id}/items", status_code=201)
def create_item(
    list_id: int,
    payload: ToolItemCreateIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return tool_service.create_item(
        session,
        actor,
        list_id,
        payload.content,
        payload.note,
        ip=client_ip(request),
    )


@router.patch("/{list_id}/items/{item_id}")
def update_item(
    list_id: int,
    item_id: int,
    payload: ToolItemUpdateIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return tool_service.update_item(
        session,
        actor,
        item_id,
        payload.content,
        payload.note,
        ip=client_ip(request),
    )


@router.delete("/{list_id}/items/{item_id}")
def delete_item(
    list_id: int,
    item_id: int,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return tool_service.delete_item(
        session, actor, item_id, ip=client_ip(request)
    )


@router.post("/{list_id}/items/{item_id}/move")
def move_item(
    list_id: int,
    item_id: int,
    payload: ToolMoveIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    return tool_service.move_item(
        session, actor, item_id, payload.direction, ip=client_ip(request)
    )
