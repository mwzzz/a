"""历史保管人判断。

v8 取消交班后不再有现金交接，只保留停用账号时的保管人拦截。
"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import Merchant


def is_holder(session: Session, merchant_id: int, user_id: int) -> bool:
    merchant = session.get(Merchant, merchant_id)
    return merchant is not None and merchant.custodian_user_id == user_id