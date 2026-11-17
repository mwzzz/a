"""常用名单：店铺规则类的小抄（打手、免茶水、每天up、免押金…）。

店员和管理员都能编辑；数据按商家隔离，分类名同店内唯一。
"""

from __future__ import annotations

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.deps import Actor
from app.errors import AppError, NotFoundError
from app.models import ToolItem, ToolList
from app.services.ai_matching import base_name
from app.services.audit import write_audit
from app.timeutil import now_text

MAX_LISTS = 20
MAX_ITEMS = 200
TEA_FREE_LIST_NAME = "免茶水"


def tea_free_name_keys(session: Session, merchant_id: int) -> set[str]:
    """「免茶水」分类里的名字，按游戏 id 口径归一化（忽略 #后缀和大小写）。"""
    row = session.scalar(
        select(ToolList).where(
            ToolList.merchant_id == merchant_id,
            ToolList.name == TEA_FREE_LIST_NAME,
        )
    )
    if row is None:
        return set()
    keys: set[str] = set()
    for item in row.items:
        key = base_name(item.content)
        if key:
            keys.add(key)
    return keys


def _clean(value: str, field: str, limit: int) -> str:
    text = (value or "").strip()
    if not text:
        raise AppError(f"{field}不能为空")
    if len(text) > limit:
        raise AppError(f"{field}不能超过 {limit} 个字")
    return text


def _item_row(item: ToolItem) -> dict:
    return {
        "id": item.id,
        "content": item.content,
        "note": item.note,
        "sort_order": item.sort_order,
    }


def list_row(item: ToolList) -> dict:
    return {
        "id": item.id,
        "name": item.name,
        "sort_order": item.sort_order,
        "items": [_item_row(row) for row in item.items],
    }


def list_all(session: Session, merchant_id: int) -> dict:
    rows = session.scalars(
        select(ToolList)
        .where(ToolList.merchant_id == merchant_id)
        .order_by(ToolList.sort_order, ToolList.id)
    ).all()
    return {"lists": [list_row(row) for row in rows]}


def get_list(session: Session, list_id: int, merchant_id: int) -> ToolList:
    row = session.scalar(
        select(ToolList).where(
            ToolList.id == list_id, ToolList.merchant_id == merchant_id
        )
    )
    if row is None:
        raise NotFoundError("找不到这个分类")
    return row


def get_item(session: Session, item_id: int, merchant_id: int) -> ToolItem:
    row = session.scalar(
        select(ToolItem).where(
            ToolItem.id == item_id, ToolItem.merchant_id == merchant_id
        )
    )
    if row is None:
        raise NotFoundError("找不到这条记录")
    return row


def create_list(session: Session, actor: Actor, name: str, *, ip: str = "") -> dict:
    title = _clean(name, "分类名", 32)
    count = len(
        session.scalars(
            select(ToolList.id).where(ToolList.merchant_id == actor.merchant_id)
        ).all()
    )
    if count >= MAX_LISTS:
        raise AppError(f"最多 {MAX_LISTS} 个分类")
    exists = session.scalar(
        select(ToolList).where(
            ToolList.merchant_id == actor.merchant_id, ToolList.name == title
        )
    )
    if exists is not None:
        raise AppError("这个分类已经存在了")

    stamp = now_text()
    row = ToolList(
        merchant_id=actor.merchant_id,
        name=title,
        sort_order=count,
        created_at=stamp,
        updated_at=stamp,
    )
    session.add(row)
    session.flush()
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="tool_list_create",
        target_type="tool_list",
        target_id=row.id,
        detail=f"新增名单分类：{title}",
        ip=ip,
    )
    return list_row(row)


def rename_list(
    session: Session, actor: Actor, list_id: int, name: str, *, ip: str = ""
) -> dict:
    row = get_list(session, list_id, actor.merchant_id)
    title = _clean(name, "分类名", 32)
    clash = session.scalar(
        select(ToolList).where(
            ToolList.merchant_id == actor.merchant_id,
            ToolList.name == title,
            ToolList.id != row.id,
        )
    )
    if clash is not None:
        raise AppError("这个分类已经存在了")
    old = row.name
    row.name = title
    row.updated_at = now_text()
    session.flush()
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="tool_list_rename",
        target_type="tool_list",
        target_id=row.id,
        detail=f"分类改名：{old} → {title}",
        ip=ip,
    )
    return list_row(row)


def delete_list(session: Session, actor: Actor, list_id: int, *, ip: str = "") -> dict:
    row = get_list(session, list_id, actor.merchant_id)
    name = row.name
    session.delete(row)
    session.flush()
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="tool_list_delete",
        target_type="tool_list",
        target_id=list_id,
        detail=f"删除名单分类：{name}",
        ip=ip,
    )
    return {"ok": True}


def move_list(
    session: Session, actor: Actor, list_id: int, direction: str, *, ip: str = ""
) -> dict:
    if direction not in ("up", "down"):
        raise AppError("方向不正确")
    rows = list(
        session.scalars(
            select(ToolList)
            .where(ToolList.merchant_id == actor.merchant_id)
            .order_by(ToolList.sort_order, ToolList.id)
        )
    )
    row = get_list(session, list_id, actor.merchant_id)
    index = rows.index(row)
    target = index - 1 if direction == "up" else index + 1
    if 0 <= target < len(rows):
        rows[index], rows[target] = rows[target], rows[index]
        for order, item in enumerate(rows):
            item.sort_order = order
        session.flush()
    return list_all(session, actor.merchant_id)


def create_item(
    session: Session,
    actor: Actor,
    list_id: int,
    content: str,
    note: str = "",
    *,
    ip: str = "",
) -> dict:
    parent = get_list(session, list_id, actor.merchant_id)
    name = _clean(content, "内容", 64)
    memo = (note or "").strip()
    if len(memo) > 100:
        raise AppError("备注不能超过 100 个字")
    if len(parent.items) >= MAX_ITEMS:
        raise AppError(f"一个分类最多 {MAX_ITEMS} 条")

    row = ToolItem(
        list_id=parent.id,
        merchant_id=actor.merchant_id,
        content=name,
        note=memo,
        sort_order=len(parent.items),
        created_at=now_text(),
    )
    session.add(row)
    parent.updated_at = now_text()
    session.flush()
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="tool_item_create",
        target_type="tool_item",
        target_id=row.id,
        detail=f"{parent.name} 新增：{name}",
        ip=ip,
    )
    return _item_row(row)


def update_item(
    session: Session,
    actor: Actor,
    item_id: int,
    content: str | None = None,
    note: str | None = None,
    *,
    ip: str = "",
) -> dict:
    row = get_item(session, item_id, actor.merchant_id)
    if content is not None:
        row.content = _clean(content, "内容", 64)
    if note is not None:
        memo = note.strip()
        if len(memo) > 100:
            raise AppError("备注不能超过 100 个字")
        row.note = memo
    session.flush()
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="tool_item_update",
        target_type="tool_item",
        target_id=row.id,
        detail=f"更新名单条目：{row.content}",
        ip=ip,
    )
    return _item_row(row)


def delete_item(session: Session, actor: Actor, item_id: int, *, ip: str = "") -> dict:
    row = get_item(session, item_id, actor.merchant_id)
    name = row.content
    list_id = row.list_id
    session.delete(row)
    session.flush()
    parent = session.get(ToolList, list_id)
    if parent is not None:
        parent.updated_at = now_text()
        remaining = list(
            session.scalars(
                select(ToolItem)
                .where(ToolItem.list_id == list_id)
                .order_by(ToolItem.sort_order, ToolItem.id)
            )
        )
        for order, item in enumerate(remaining):
            item.sort_order = order
        session.flush()
    write_audit(
        session,
        merchant_id=actor.merchant_id,
        user_id=actor.id,
        action="tool_item_delete",
        target_type="tool_item",
        target_id=item_id,
        detail=f"删除名单条目：{name}",
        ip=ip,
    )
    return {"ok": True}


def move_item(
    session: Session, actor: Actor, item_id: int, direction: str, *, ip: str = ""
) -> dict:
    if direction not in ("up", "down"):
        raise AppError("方向不正确")
    row = get_item(session, item_id, actor.merchant_id)
    siblings = list(
        session.scalars(
            select(ToolItem)
            .where(ToolItem.list_id == row.list_id)
            .order_by(ToolItem.sort_order, ToolItem.id)
        )
    )
    index = siblings.index(row)
    target = index - 1 if direction == "up" else index + 1
    if 0 <= target < len(siblings):
        siblings[index], siblings[target] = siblings[target], siblings[index]
        for order, item in enumerate(siblings):
            item.sort_order = order
        session.flush()
    return _item_row(row)
