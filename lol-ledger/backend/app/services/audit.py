"""非资金操作留痕。资金流水已经带 operator_id，不重复写这里。"""

from __future__ import annotations

from sqlalchemy.orm import Session

from app.models import AuditLog
from app.timeutil import now_text


def write_audit(
    session: Session,
    *,
    user_id: int | None,
    action: str,
    merchant_id: int | None = None,
    target_type: str | None = None,
    target_id: str | int | None = None,
    detail: str = "",
    ip: str = "",
) -> None:
    session.add(
        AuditLog(
            merchant_id=merchant_id,
            user_id=user_id,
            action=action,
            target_type=target_type,
            target_id=str(target_id) if target_id is not None else None,
            detail=detail[:500],
            ip=ip[:64],
            created_at=now_text(),
        )
    )
