"""商家作用域助手。

原则：别家的数据一律表现为「不存在」，返回 404 而不是 403，避免被用来探测。
"""

from __future__ import annotations

from typing import TypeVar

from sqlalchemy.orm import Session

from app.errors import NotFoundError
from app.models import Base

T = TypeVar("T", bound=Base)


def scoped_get(
    session: Session,
    model: type[T],
    object_id: int,
    merchant_id: int,
    message: str = "找不到这条记录",
) -> T:
    """按 id + merchant_id 取一条记录，跨商家视为不存在。"""
    row = session.get(model, object_id)
    if row is None or getattr(row, "merchant_id", None) != merchant_id:
        raise NotFoundError(message)
    return row
