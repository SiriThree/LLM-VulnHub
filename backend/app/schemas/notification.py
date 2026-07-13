from datetime import datetime

from pydantic import BaseModel


class NotificationEventRead(BaseModel):
    id: int
    task_status: str
    event_type: str
    channel: str
    severity: str
    title: str
    message: str
    payload: dict
    source_id: int | None = None
    document_id: int | None = None
    intel_item_id: int | None = None
    analysis_job_id: int | None = None
    queue_name: str | None = None
    notified_at: str | None = None
    acknowledged: bool = False
    acknowledged_at: str | None = None
    acknowledged_by: str | None = None
    acknowledgment_note: str | None = None
    created_at: datetime
    updated_at: datetime


class NotificationListResponse(BaseModel):
    items: list[NotificationEventRead]


class NotificationAcknowledgeRequest(BaseModel):
    actor: str = "analyst"
    note: str | None = None


class NotificationBatchAcknowledgeRequest(BaseModel):
    task_ids: list[int]
    actor: str = "analyst"
    note: str | None = None
