"""批次（班次）接口。"""

from __future__ import annotations

from fastapi import APIRouter, Depends, Request, Response
from sqlalchemy.orm import Session

from app.deps import Actor, client_ip, get_current_user, get_read_db, get_write_db
from app.schemas import BatchCloseIn, BatchCreateIn
from app.services import batches as batch_service
from app.services.batches import batch_row, get_open_batch
from app.services.records import batch_ledger, export_batch_csv

router = APIRouter(prefix="/batches", tags=["批次"])


@router.get("")
def list_batches(
    status: str = "all",
    keyword: str = "",
    date_from: str | None = None,
    date_to: str | None = None,
    page: int = 1,
    page_size: int = 20,
    include_sessions: bool = True,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return batch_service.list_batches(
        session,
        actor.merchant_id,
        status=status,
        keyword=keyword,
        date_from=date_from,
        date_to=date_to,
        page=page,
        page_size=page_size,
        include_sessions=include_sessions,
    )


@router.get("/current")
def current_batch(
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    batch = get_open_batch(session, actor.merchant_id)
    if batch is None:
        return {"batch": None}
    grouped = batch_service.sessions_for_batches(
        session, [batch.id], actor.merchant_id
    )
    return {"batch": batch_row(session, batch, grouped.get(batch.id, []))}


@router.post("", status_code=201)
def open_batch(
    payload: BatchCreateIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    batch = batch_service.open_batch(
        session, actor, label=payload.label, note=payload.note, ip=client_ip(request)
    )
    return batch_row(session, batch, [])


@router.get("/{batch_id}")
def get_batch(
    batch_id: int,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return batch_service.batch_detail(session, batch_id, actor.merchant_id)


@router.get("/{batch_id}/summary")
def batch_summary(
    batch_id: int,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    batch = batch_service.get_batch(session, batch_id, actor.merchant_id)
    if batch.status == "closed":
        return batch_service.snapshot_summary(batch)
    return batch_service.compute_summary(session, batch_id, actor.merchant_id)


@router.get("/{batch_id}/ledger")
def batch_ledger_route(
    batch_id: int,
    page: int = 1,
    page_size: int = 50,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> dict:
    return batch_ledger(
        session, batch_id, actor.merchant_id, page=page, page_size=page_size
    )


@router.post("/{batch_id}/close")
def close_batch(
    batch_id: int,
    payload: BatchCloseIn,
    request: Request,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_write_db),
) -> dict:
    batch = batch_service.close_batch(
        session, actor, batch_id, note=payload.note, ip=client_ip(request)
    )
    return batch_service.snapshot_summary(batch)


@router.get("/{batch_id}/export.csv")
def export_batch(
    batch_id: int,
    actor: Actor = Depends(get_current_user),
    session: Session = Depends(get_read_db),
) -> Response:
    content = export_batch_csv(session, batch_id, actor.merchant_id)
    return Response(
        content=content,
        media_type="text/csv; charset=utf-8",
        headers={
            "Content-Disposition": f'attachment; filename="batch-{batch_id}.csv"',
        },
    )
