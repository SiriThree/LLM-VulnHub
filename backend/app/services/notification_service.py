from datetime import datetime, timezone

from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import Task


def _serialize_notification_task(task: Task) -> dict:
    output = dict(task.output_data or {})
    notification = dict(output.get("notification") or {})
    payload = dict(notification.get("payload") or output.get("payload") or {})
    return {
        "id": task.id,
        "task_status": task.status,
        "event_type": str(output.get("event_type") or notification.get("event_type") or "generic"),
        "channel": str(notification.get("channel") or "task-center"),
        "severity": str(notification.get("severity") or payload.get("severity") or "info"),
        "title": str(notification.get("title") or payload.get("title") or "generic"),
        "message": str(notification.get("message") or payload.get("message") or ""),
        "payload": payload,
        "source_id": payload.get("source_id"),
        "document_id": payload.get("document_id"),
        "intel_item_id": payload.get("intel_item_id"),
        "analysis_job_id": payload.get("analysis_job_id"),
        "queue_name": output.get("queue_name"),
        "notified_at": notification.get("notified_at"),
        "acknowledged": bool(output.get("acknowledged", False)),
        "acknowledged_at": output.get("acknowledged_at"),
        "acknowledged_by": output.get("acknowledged_by"),
        "acknowledgment_note": output.get("acknowledgment_note"),
        "created_at": task.created_at,
        "updated_at": task.updated_at,
    }


def list_notification_events(
    db: Session,
    *,
    event_type: str | None = None,
    status: str | None = None,
    acknowledged: bool | None = None,
    limit: int = 100,
) -> list[dict]:
    stmt = select(Task).where(Task.task_type == "notification").order_by(Task.created_at.desc(), Task.id.desc())
    if status:
        stmt = stmt.where(Task.status == status)
    stmt = stmt.limit(limit)

    items: list[dict] = []
    for task in db.scalars(stmt).all():
        item = _serialize_notification_task(task)
        current_event_type = item["event_type"]
        if event_type and current_event_type != event_type:
            continue
        current_acknowledged = bool(item["acknowledged"])
        if acknowledged is not None and current_acknowledged != acknowledged:
            continue
        items.append(item)
    return items


def acknowledge_notification(db: Session, task_id: int, actor: str, note: str | None = None) -> dict | None:
    task = db.get(Task, task_id)
    if not task or task.task_type != "notification":
        return None
    output = dict(task.output_data or {})
    output["acknowledged"] = True
    output["acknowledged_at"] = datetime.now(timezone.utc).isoformat()
    output["acknowledged_by"] = actor
    output["acknowledgment_note"] = note
    task.output_data = output
    db.add(task)
    db.commit()
    db.refresh(task)
    return _serialize_notification_task(task)


def unacknowledge_notification(db: Session, task_id: int) -> dict | None:
    task = db.get(Task, task_id)
    if not task or task.task_type != "notification":
        return None
    output = dict(task.output_data or {})
    output["acknowledged"] = False
    output["acknowledged_at"] = None
    output["acknowledged_by"] = None
    output["acknowledgment_note"] = None
    task.output_data = output
    db.add(task)
    db.commit()
    db.refresh(task)
    return _serialize_notification_task(task)


def batch_acknowledge_notifications(db: Session, task_ids: list[int], actor: str, note: str | None = None) -> list[dict]:
    items: list[dict] = []
    for task_id in task_ids:
        item = acknowledge_notification(db, task_id, actor=actor, note=note)
        if item:
            items.append(item)
    return items
