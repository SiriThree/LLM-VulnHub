from datetime import datetime

from pydantic import BaseModel, ConfigDict


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


class ReviewDecisionRequest(BaseModel):
    notes: str | None = None
    actor: str = "analyst"


class BatchReviewDecisionRequest(BaseModel):
    item_ids: list[int]
    notes: str | None = None
    actor: str = "analyst"


class MergeDecisionRequest(BaseModel):
    actor: str = "analyst"
    notes: str | None = None


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
    unique_actors: int
    last_24h_actions: int
    top_actors: list[dict[str, int | str]]


class IntelligenceStatsRead(BaseModel):
    total: int
    pending_review: int
    approved: int
    rejected: int
    triaged: int
    high_risk_pending_review: int
    merge_candidates_pending: int


class BatchReviewDecisionResponse(BaseModel):
    items: list[IntelligenceItemRead]
