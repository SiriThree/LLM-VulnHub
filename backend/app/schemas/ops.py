from pydantic import BaseModel


class QueueMetricsRead(BaseModel):
    queued: int
    running: int
    success: int
    failed: int


class SourceHealthRead(BaseModel):
    total_sources: int
    enabled_sources: int
    disabled_sources: int
    recently_failed_notifications: int


class ProviderMetricsRead(BaseModel):
    analysis_jobs_total: int
    avg_score: float
    provider_distribution: dict[str, int]
    severity_distribution: dict[str, int]


class LlmUsageRead(BaseModel):
    total_calls: int
    total_prompt_tokens: int
    total_completion_tokens: int
    total_tokens: int
    avg_latency_ms: float
    provider_distribution: dict[str, int]
    model_distribution: dict[str, int]


class TrendPointRead(BaseModel):
    date: str
    collected_documents: int
    analysis_jobs: int
    review_actions: int


class BeatScheduleRead(BaseModel):
    name: str
    task: str
    schedule_seconds: float


class SourceScheduleRead(BaseModel):
    source_id: int
    name: str
    enabled: bool
    interval_minutes: int
    last_collected_at: str | None
    next_run_at: str | None
    status: str


class SchedulerOverviewRead(BaseModel):
    beat_jobs: list[BeatScheduleRead]
    sources: list[SourceScheduleRead]


class DeadLetterTaskRead(BaseModel):
    id: int
    task_type: str
    status: str
    attempt_count: int
    max_attempts: int
    dead_letter_reason: str | None
    current_stage: str | None
    error_message: str | None
    queue_name: str | None
    created_at: str
    updated_at: str


class PromptRegistryItemRead(BaseModel):
    key: str
    agent_name: str
    version: str
    required_keys: list[str]
    usage_count: int
    success_count: int
    failure_count: int
    avg_latency_ms: float


class EvalRunRead(BaseModel):
    file_name: str
    provider: str
    dataset_size: int
    triage_accuracy: float
    triage_precision: float
    triage_recall: float
    extraction_completeness: float
    merge_precision: float
    generated_at: str


class OpsMetricsRead(BaseModel):
    queue_metrics: QueueMetricsRead
    source_health: SourceHealthRead
    provider_metrics: ProviderMetricsRead
    llm_usage: LlmUsageRead
    daily_trends: list[TrendPointRead]
