from datetime import datetime
from pydantic import BaseModel, ConfigDict, Field


class DataSourceBase(BaseModel):
    name: str
    source_type: str = Field(default="rss", pattern="^(rss|web|github|local_file)$")
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


class CollectorRecentRunRead(BaseModel):
    task_id: int
    source_id: int | None = None
    source_name: str
    source_type: str
    status: str
    stage: str
    discovered: int
    prefilter_passed: int = 0
    processed: int
    queued_analysis: int
    analyzed: int = 0
    ai_related: int = 0
    saved: int
    duplicates: int
    pending_review: int
    ignored: int
    failed: int
    started_at: str | None = None
    finished_at: str | None = None
    elapsed_seconds: float | None = None
    error: str | None = None


class SourceHealthRead(BaseModel):
    source_id: int
    name: str
    source_type: str
    enabled: bool
    interval_minutes: int
    last_collected_at: datetime | None = None
    status: str
    trust_score: int
    trust_level: str
    documents_total: int
    ai_related_documents: int
    pending_review_documents: int
    stored_documents: int
    duplicate_documents: int
    recent_run_count: int
    recent_failure_count: int
    success_rate: float
    request_success_rate: float = 0.0
    prefilter_pass_rate: float = 0.0
    llm_hit_rate: float = 0.0
    library_conversion_rate: float = 0.0
    recent_discovered: int = 0
    recent_prefilter_passed: int = 0
    recent_queued_analysis: int = 0
    recent_analyzed: int = 0
    recent_ai_related: int = 0
    recent_saved: int = 0
    freshness_minutes: int | None = None
    signals: list[str] = []


class CollectorOverviewRead(BaseModel):
    source_metrics: dict[str, int]
    document_metrics: dict[str, int]
    queue_metrics: dict[str, int]
    source_health: list[SourceHealthRead]
    recent_runs: list[CollectorRecentRunRead]
    pending_documents: list[CollectedDocumentRead]
    recent_documents: list[CollectedDocumentRead]
