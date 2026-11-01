"""总览与对账。"""

from __future__ import annotations

from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.deps import Actor, get_current_user, get_read_db, require_admin
from app.services.reconcile import reconcile
from app.services.reports import overview

router = APIRouter(tags=["总览"])


@router.get("/overview")
def get_overview(
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return overview(session, actor.merchant_id)


@router.get("/reconcile")
def get_reconcile(
    actor: Actor = Depends(require_admin),
    session: Session = Depends(get_read_db),
) -> dict:
    return reconcile(session, actor.merchant_id)
