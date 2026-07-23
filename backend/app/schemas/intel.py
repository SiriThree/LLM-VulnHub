from datetime import datetime

from pydantic import BaseModel, ConfigDict, Field

from app.core.input_security import MAX_REVIEW_NOTE_CHARS


class MergeCandidateRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    intelligence_item_id: int
    candidate_vulnerability_id: int
    merge_score: float
    merge_reason: str
    status: str
    created_at: datetime
    updated_at: datetime


class MergeCandidateExplanationRead(MergeCandidateRead):
    candidate_title: str | None = None
    candidate_severity: str | None = None
    candidate_score: int | None = None
    candidate_component: str | None = None
    quality: str = "weak"
    match_signals: list[str] = []
    review_hint: str = ""


class IntelligenceItemRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    source_id: int | None
    collected_document_id: int | None
    vulnerability_id: int | None
    title: str
    url: str | None
    raw_text: str
    normalized_text: str
    content_hash: str
    language: str
    triage_confidence: float
    triage_category: str
    triage_reason: str
    extracted_data: dict
    review_notes: str | None
    status: str
    collected_at: datetime
    created_at: datetime
    updated_at: datetime
    merge_candidates: list[MergeCandidateRead] = []


class IntelligenceListResponse(BaseModel):
    items: list[IntelligenceItemRead]
    total: int
    page: int
    page_size: int


class ReviewDecisionRequest(BaseModel):
    notes: str | None = Field(default=None, max_length=MAX_REVIEW_NOTE_CHARS)
    actor: str = Field(default="analyst", min_length=1, max_length=120)


class BatchReviewDecisionRequest(BaseModel):
    item_ids: list[int] = Field(min_length=1, max_length=100)
    notes: str | None = Field(default=None, max_length=MAX_REVIEW_NOTE_CHARS)
    actor: str = Field(default="analyst", min_length=1, max_length=120)


class MergeDecisionRequest(BaseModel):
    actor: str = Field(default="analyst", min_length=1, max_length=120)
    notes: str | None = Field(default=None, max_length=MAX_REVIEW_NOTE_CHARS)


class ReviewActionRead(BaseModel):
    model_config = ConfigDict(from_attributes=True)

    id: int
    actor: str
    target_type: str
    target_id: int
    action: str
    before_snapshot: dict
    after_snapshot: dict
    reason: str
    created_at: datetime


class ReviewActionListResponse(BaseModel):
    items: list[ReviewActionRead]


class ReviewStatsRead(BaseModel):
    total_actions: int
    approvals: int
    rejections: int
    merges: int
    undos: int
    unique_actors: int
    last_24h_actions: int
    top_actors: list[dict[str, int | str]]


class IntelligenceStatsRead(BaseModel):
    total: int
    reviewable: int
    pending_review: int
    ignored: int
    approved: int
    rejected: int
    triaged: int
    high_risk_pending_review: int
    merge_candidates_pending: int


class BatchReviewDecisionResponse(BaseModel):
    items: list[IntelligenceItemRead]


class LinkedSourceRead(BaseModel):
    id: int
    name: str
    source_type: str
    url: str
    enabled: bool
    interval_minutes: int
    last_collected_at: datetime | None = None
    trust_score: int
    trust_level: str
    status: str
    signals: list[str] = []


class LinkedCollectedDocumentRead(BaseModel):
    id: int
    title: str
    url: str | None = None
    status: str
    is_ai_related: bool
    confidence: float
    collected_at: datetime
    content_hash: str


class LinkedVulnerabilitySummaryRead(BaseModel):
    id: int
    title: str
    severity: str
    score: int
    status: str


class LineageTraceEventRead(BaseModel):
    stage: str
    title: str
    status: str
    timestamp: datetime | None = None
    detail: str


class IntelligenceLineageRead(BaseModel):
    intelligence_item_id: int
    title: str
    status: str
    triage_category: str
    triage_confidence: float
    source: LinkedSourceRead | None = None
    collected_document: LinkedCollectedDocumentRead | None = None
    linked_vulnerability: LinkedVulnerabilitySummaryRead | None = None
    merge_candidates: list[MergeCandidateExplanationRead] = []
    review_actions: list[ReviewActionRead] = []
    trace: list[LineageTraceEventRead] = []
