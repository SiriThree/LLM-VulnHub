from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity, require_role
from app.db.session import get_db
from app.schemas.notification import (
    NotificationAcknowledgeRequest,
    NotificationBatchAcknowledgeRequest,
    NotificationEventRead,
    NotificationListResponse,
)
from app.services.notification_service import (
    acknowledge_notification,
    batch_acknowledge_notifications,
    list_notification_events,
    unacknowledge_notification,
)

router = APIRouter(prefix="/notifications", tags=["notifications"])


@router.get("", response_model=NotificationListResponse)
def list_notifications(
    event_type: str | None = Query(default=None, max_length=80),
    status: str | None = Query(default=None, max_length=40),
    acknowledged: bool | None = Query(default=None),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=10, ge=1, le=100),
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    items, total = list_notification_events(
        db,
        event_type=event_type,
        status=status,
        acknowledged=acknowledged,
        page=page,
        page_size=page_size,
    )
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.post("/{task_id}/acknowledge", response_model=NotificationEventRead)
def acknowledge(
    task_id: int,
    payload: NotificationAcknowledgeRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    item = acknowledge_notification(db, task_id, actor=identity.actor, note=payload.note)
    if not item:
        raise HTTPException(404, "notification not found")
    return item


@router.post("/{task_id}/unacknowledge", response_model=NotificationEventRead)
def unacknowledge(
    task_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    item = unacknowledge_notification(db, task_id)
    if not item:
        raise HTTPException(404, "notification not found")
    return item


@router.post("/batch-acknowledge", response_model=NotificationListResponse)
def batch_acknowledge(
    payload: NotificationBatchAcknowledgeRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    items = batch_acknowledge_notifications(db, payload.task_ids, actor=identity.actor, note=payload.note)
    return {"items": items, "total": len(items), "page": 1, "page_size": max(1, len(items))}
