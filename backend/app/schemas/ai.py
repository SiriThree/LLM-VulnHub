from pydantic import BaseModel, Field

from app.core.input_security import MAX_REVIEW_NOTE_CHARS, MAX_UNTRUSTED_TEXT_CHARS, MAX_URL_LENGTH
from app.schemas.vulnerability import VulnerabilityCreate, VulnerabilityRead


class ExtractRequest(BaseModel):
    raw_text: str = Field(min_length=10, max_length=MAX_UNTRUSTED_TEXT_CHARS)
    source_url: str | None = Field(default=None, max_length=MAX_URL_LENGTH)


class RelevanceResult(BaseModel):
    is_ai_vulnerability: bool
    confidence: float = Field(ge=0, le=1)
    related_area: str = "unknown"
    reason: str = ""


class ExtractResult(VulnerabilityCreate):
    risk_reason: str = ""
    similar: list[VulnerabilityRead] = []
    review_summary: str = ""
    asset_impact_summary: str = ""
    asset_impact_details: dict = {}
    merge_suggestions: dict = {}


class AgentExecutionRead(BaseModel):
    id: int
    agent_name: str
    stage_name: str
    status: str
    provider_name: str | None = None
    model_name: str | None = None
    prompt_version: str
    retry_count: int = 1
    latency_ms: int | None = None
    prompt_tokens: int | None = None
    completion_tokens: int | None = None
    total_tokens: int | None = None
    input_payload: dict = {}
    output_payload: dict = {}
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None


class AnalysisJobRead(BaseModel):
    id: int
    pipeline_name: str
    pipeline_version: str
    status: str
    source_url: str | None = None
    raw_text_hash: str
    raw_text_excerpt: str
    provider_name: str | None = None
    model_name: str | None = None
    relevance: dict = {}
    extracted_fields: dict = {}
    similar_snapshot: list[dict] = []
    asset_impact_summary: str = ""
    asset_impact_details: dict = {}
    score: int | None = None
    severity: str | None = None
    risk_reason: str = ""
    review_summary: str = ""
    report: str = ""
    error_message: str | None = None
    started_at: str | None = None
    finished_at: str | None = None
    agent_executions: list[AgentExecutionRead] = []


class AnalyzeRequest(ExtractRequest):
    save: bool = False


class AnalyzeResult(BaseModel):
    relevance: RelevanceResult
    extracted: ExtractResult
    vulnerability: VulnerabilityRead | None = None
    report: str
    analysis_job: AnalysisJobRead | None = None


class ScoreRequest(BaseModel):
    vulnerability: VulnerabilityCreate


class ScoreResult(BaseModel):
    score: int
    severity: str
    risk_reason: str
    key_risk_factors: list[str]
    suggested_priority: str


class ReportRequest(BaseModel):
    vulnerability: VulnerabilityCreate
    risk_reason: str | None = Field(default=None, max_length=MAX_REVIEW_NOTE_CHARS)


class ReportResult(BaseModel):
    report: str


class ProviderStatusRead(BaseModel):
    configured_provider: str
    active_provider: str
    model: str
    has_api_key: bool
    fallback_enabled: bool
    using_mock: bool
    can_call_remote: bool


class EvalSampleRead(BaseModel):
    id: str
    expected_ai: bool
    predicted_ai: bool | None = None
    triage_correct: bool | None = None
    confidence: float | None = None
    extraction_exact: dict[str, bool] = {}
    extraction_completeness: float | None = None
    merge_correct: bool | None = None
    errors: list[str] = []


class EvalDatasetRead(BaseModel):
    dataset_size: int
    positive_samples: int
    negative_samples: int
    categories: dict[str, int]
    samples: list[dict]


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


class EvalRunDetailRead(EvalRunRead):
    summary: dict = {}
    samples: list[EvalSampleRead] = []


class ConfirmAnalysisRequest(BaseModel):
    analysis_job_id: int
    vulnerability: VulnerabilityCreate
    review_note: str | None = Field(default=None, max_length=MAX_REVIEW_NOTE_CHARS)


class ConfirmAnalysisResult(BaseModel):
    vulnerability: VulnerabilityRead
    analysis_job: AnalysisJobRead
