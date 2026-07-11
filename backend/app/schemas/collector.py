from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DataSourceBase(BaseModel):
    name: str
    source_type: str = Field(default="local_file", pattern="^(rss|web|github|local_file)$")
    url: str
    enabled: bool = True
    interval_minutes: int = Field(default=30, ge=1)


class DataSourceCreate(DataSourceBase):
    pass


class DataSourceUpdate(BaseModel):
    name: str | None = None
    source_type: str | None = None
    url: str | None = None
    enabled: bool | None = None
    interval_minutes: int | None = Field(default=None, ge=1)


class DataSourceRead(DataSourceBase):
    model_config = ConfigDict(from_attributes=True)

    id: int
    last_collected_at: datetime | None
    created_at: datetime
    updated_at: datetime


class CollectedDocumentRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int | None
    title: str
    url: str | None
    raw_text: str
    content_hash: str
    is_ai_related: bool
    confidence: float
    status: str
    vulnerability_id: int | None
    collected_at: datetime


class CollectorRunRequest(BaseModel):
    source_id: int | None = None


class CollectorRunResult(BaseModel):
    task_id: int
    status: str
    current_stage: str
    queued_at: datetime
    message: str
