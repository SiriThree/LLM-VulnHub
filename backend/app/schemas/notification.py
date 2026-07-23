from datetime import datetime

from pydantic import BaseModel, Field

from app.core.input_security import MAX_REVIEW_NOTE_CHARS


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
    total: int
    page: int
    page_size: int


class NotificationStatsRead(BaseModel):
    total: int
    unread: int


class NotificationAcknowledgeRequest(BaseModel):
    actor: str = Field(default="analyst", min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=MAX_REVIEW_NOTE_CHARS)


class NotificationBatchAcknowledgeRequest(BaseModel):
    task_ids: list[int] = Field(min_length=1, max_length=200)
    actor: str = Field(default="analyst", min_length=1, max_length=120)
    note: str | None = Field(default=None, max_length=MAX_REVIEW_NOTE_CHARS)
