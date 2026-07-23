from datetime import datetime
from pydantic import BaseModel, ConfigDict


class TaskRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    task_type: str
    status: str
    input_data: dict
    output_data: dict
    error_message: str | None
    created_at: datetime
    updated_at: datetime


class TaskStatsRead(BaseModel):
    total: int
    queued: int
    running: int
    success: int
    failed: int
    dead_letter: int


class TaskListResponse(BaseModel):
    items: list[TaskRead]
    total: int
    page: int
    page_size: int
    stats: TaskStatsRead
