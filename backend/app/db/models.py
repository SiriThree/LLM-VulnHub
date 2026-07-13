from datetime import datetime

from sqlalchemy import Boolean, Column, DateTime, Float, ForeignKey, Integer, JSON, String, Table, Text, func
from sqlalchemy.orm import Mapped, mapped_column, relationship

from app.db.session import Base


vulnerability_tags = Table(
    "vulnerability_tags",
    Base.metadata,
    Column("vulnerability_id", ForeignKey("vulnerabilities.id", ondelete="CASCADE"), primary_key=True),
    Column("tag_id", ForeignKey("tags.id", ondelete="CASCADE"), primary_key=True),
)


class TimestampMixin:
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())
    updated_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now(), onupdate=func.now())


class Vulnerability(TimestampMixin, Base):
    __tablename__ = "vulnerabilities"

    id: Mapped[int] = mapped_column(Integer, primary_key=True, index=True)
    title: Mapped[str] = mapped_column(String(300), index=True)
    vuln_type: Mapped[str] = mapped_column(String(120), index=True, default="unknown")
    severity: Mapped[str] = mapped_column(String(20), index=True, default="中危")
    score: Mapped[int] = mapped_column(Integer, index=True, default=0)
    affected_component: Mapped[str] = mapped_column(String(200), index=True, default="unknown")
    description: Mapped[str] = mapped_column(Text, default="")
    attack_method: Mapped[str] = mapped_column(Text, default="unknown")
    impact: Mapped[str] = mapped_column(Text, default="unknown")
    mitigation: Mapped[str] = mapped_column(Text, default="unknown")
    source: Mapped[str | None] = mapped_column(String(160), nullable=True)
    reference_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(600), nullable=True)
    collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    confidence: Mapped[float] = mapped_column(Float, default=0.0)
    status: Mapped[str] = mapped_column(String(40), index=True, default="未修复")

    tags: Mapped[list["Tag"]] = relationship(secondary=vulnerability_tags, back_populates="vulnerabilities")
    analyses: Mapped[list["AnalysisRecord"]] = relationship(back_populates="vulnerability", cascade="all, delete-orphan")
    chunks: Mapped[list["DocumentChunk"]] = relationship(back_populates="vulnerability", cascade="all, delete-orphan")
    occurrences: Mapped[list["VulnerabilityOccurrence"]] = relationship(back_populates="vulnerability", cascade="all, delete-orphan")
    intelligence_items: Mapped[list["IntelligenceItem"]] = relationship(back_populates="vulnerability")
    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="vulnerability")


class Tag(Base):
    __tablename__ = "tags"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(80), unique=True, index=True)
    vulnerabilities: Mapped[list[Vulnerability]] = relationship(secondary=vulnerability_tags, back_populates="tags")


class AnalysisRecord(Base):
    __tablename__ = "analysis_records"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vulnerability_id: Mapped[int] = mapped_column(ForeignKey("vulnerabilities.id", ondelete="CASCADE"), index=True)
    summary: Mapped[str] = mapped_column(Text, default="")
    risk_reason: Mapped[str] = mapped_column(Text, default="")
    suggested_fix: Mapped[str] = mapped_column(Text, default="")
    model_name: Mapped[str] = mapped_column(String(120), default="mock")
    prompt_version: Mapped[str] = mapped_column(String(40), default="v1")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vulnerability: Mapped[Vulnerability] = relationship(back_populates="analyses")


class DocumentChunk(Base):
    __tablename__ = "document_chunks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vulnerability_id: Mapped[int] = mapped_column(ForeignKey("vulnerabilities.id", ondelete="CASCADE"), index=True)
    chunk_text: Mapped[str] = mapped_column(Text)
    embedding: Mapped[list[float]] = mapped_column(JSON, default=list)
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    vulnerability: Mapped[Vulnerability] = relationship(back_populates="chunks")


class VulnerabilityOccurrence(TimestampMixin, Base):
    __tablename__ = "vulnerability_occurrences"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    vulnerability_id: Mapped[int] = mapped_column(ForeignKey("vulnerabilities.id", ondelete="CASCADE"), index=True)
    intelligence_item_id: Mapped[int | None] = mapped_column(ForeignKey("intelligence_items.id", ondelete="SET NULL"), nullable=True)
    source_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    published_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    evidence_excerpt: Mapped[str] = mapped_column(Text, default="")
    confidence: Mapped[float] = mapped_column(Float, default=0.0)

    vulnerability: Mapped[Vulnerability] = relationship(back_populates="occurrences")
    intelligence_item: Mapped["IntelligenceItem | None"] = relationship(back_populates="occurrences")


class Task(TimestampMixin, Base):
    __tablename__ = "tasks"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    task_type: Mapped[str] = mapped_column(String(40), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True, default="pending")
    input_data: Mapped[dict] = mapped_column(JSON, default=dict)
    output_data: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)


class DataSource(TimestampMixin, Base):
    __tablename__ = "data_sources"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    name: Mapped[str] = mapped_column(String(160), index=True)
    source_type: Mapped[str] = mapped_column(String(40), default="local_file")
    url: Mapped[str] = mapped_column(String(800))
    enabled: Mapped[bool] = mapped_column(Boolean, default=True)
    interval_minutes: Mapped[int] = mapped_column(Integer, default=30)
    last_collected_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    documents: Mapped[list["CollectedDocument"]] = relationship(back_populates="source")
    intelligence_items: Mapped[list["IntelligenceItem"]] = relationship(back_populates="source")


class CollectedDocument(Base):
    __tablename__ = "collected_documents"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    is_ai_related: Mapped[bool] = mapped_column(Boolean, default=False)
    confidence: Mapped[float] = mapped_column(Float, default=0)
    status: Mapped[str] = mapped_column(String(40), index=True, default="pending")
    vulnerability_id: Mapped[int | None] = mapped_column(ForeignKey("vulnerabilities.id", ondelete="SET NULL"), nullable=True)
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[DataSource | None] = relationship(back_populates="documents")
    intelligence_items: Mapped[list["IntelligenceItem"]] = relationship(back_populates="collected_document")
    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="collected_document")


class IntelligenceItem(TimestampMixin, Base):
    __tablename__ = "intelligence_items"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    source_id: Mapped[int | None] = mapped_column(ForeignKey("data_sources.id", ondelete="SET NULL"), nullable=True)
    collected_document_id: Mapped[int | None] = mapped_column(ForeignKey("collected_documents.id", ondelete="SET NULL"), nullable=True)
    vulnerability_id: Mapped[int | None] = mapped_column(ForeignKey("vulnerabilities.id", ondelete="SET NULL"), nullable=True)
    title: Mapped[str] = mapped_column(String(300))
    url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    raw_text: Mapped[str] = mapped_column(Text)
    normalized_text: Mapped[str] = mapped_column(Text, default="")
    content_hash: Mapped[str] = mapped_column(String(64), index=True)
    language: Mapped[str] = mapped_column(String(20), default="unknown")
    triage_confidence: Mapped[float] = mapped_column(Float, default=0.0)
    triage_category: Mapped[str] = mapped_column(String(120), default="unknown")
    triage_reason: Mapped[str] = mapped_column(Text, default="")
    extracted_data: Mapped[dict] = mapped_column(JSON, default=dict)
    review_notes: Mapped[str | None] = mapped_column(Text, nullable=True)
    status: Mapped[str] = mapped_column(String(40), index=True, default="new")
    collected_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())

    source: Mapped[DataSource | None] = relationship(back_populates="intelligence_items")
    collected_document: Mapped[CollectedDocument | None] = relationship(back_populates="intelligence_items")
    vulnerability: Mapped[Vulnerability | None] = relationship(back_populates="intelligence_items")
    merge_candidates: Mapped[list["MergeCandidate"]] = relationship(back_populates="intelligence_item", cascade="all, delete-orphan")
    occurrences: Mapped[list[VulnerabilityOccurrence]] = relationship(back_populates="intelligence_item")
    analysis_jobs: Mapped[list["AnalysisJob"]] = relationship(back_populates="intelligence_item")


class MergeCandidate(TimestampMixin, Base):
    __tablename__ = "merge_candidates"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    intelligence_item_id: Mapped[int] = mapped_column(ForeignKey("intelligence_items.id", ondelete="CASCADE"), index=True)
    candidate_vulnerability_id: Mapped[int] = mapped_column(ForeignKey("vulnerabilities.id", ondelete="CASCADE"), index=True)
    merge_score: Mapped[float] = mapped_column(Float, default=0.0)
    merge_reason: Mapped[str] = mapped_column(Text, default="")
    status: Mapped[str] = mapped_column(String(40), index=True, default="pending")

    intelligence_item: Mapped[IntelligenceItem] = relationship(back_populates="merge_candidates")
    candidate_vulnerability: Mapped[Vulnerability] = relationship()


class ReviewAction(Base):
    __tablename__ = "review_actions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    actor: Mapped[str] = mapped_column(String(120), default="system")
    target_type: Mapped[str] = mapped_column(String(40), index=True)
    target_id: Mapped[int] = mapped_column(Integer, index=True)
    action: Mapped[str] = mapped_column(String(40), index=True)
    before_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    after_snapshot: Mapped[dict] = mapped_column(JSON, default=dict)
    reason: Mapped[str] = mapped_column(Text, default="")
    created_at: Mapped[datetime] = mapped_column(DateTime(timezone=True), server_default=func.now())


class AnalysisJob(TimestampMixin, Base):
    __tablename__ = "analysis_jobs"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    pipeline_name: Mapped[str] = mapped_column(String(120), default="vuln_analysis_v2")
    pipeline_version: Mapped[str] = mapped_column(String(40), default="v2")
    status: Mapped[str] = mapped_column(String(40), index=True, default="pending")
    source_url: Mapped[str | None] = mapped_column(String(800), nullable=True)
    raw_text_hash: Mapped[str] = mapped_column(String(64), index=True)
    raw_text_excerpt: Mapped[str] = mapped_column(Text, default="")
    vulnerability_id: Mapped[int | None] = mapped_column(ForeignKey("vulnerabilities.id", ondelete="SET NULL"), nullable=True)
    intelligence_item_id: Mapped[int | None] = mapped_column(ForeignKey("intelligence_items.id", ondelete="SET NULL"), nullable=True)
    collected_document_id: Mapped[int | None] = mapped_column(ForeignKey("collected_documents.id", ondelete="SET NULL"), nullable=True)
    provider_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    relevance: Mapped[dict] = mapped_column(JSON, default=dict)
    extracted_fields: Mapped[dict] = mapped_column(JSON, default=dict)
    similar_snapshot: Mapped[list] = mapped_column(JSON, default=list)
    asset_impact_summary: Mapped[str] = mapped_column(Text, default="")
    asset_impact_details: Mapped[dict] = mapped_column(JSON, default=dict)
    score: Mapped[int | None] = mapped_column(Integer, nullable=True)
    severity: Mapped[str | None] = mapped_column(String(20), nullable=True)
    risk_reason: Mapped[str] = mapped_column(Text, default="")
    review_summary: Mapped[str] = mapped_column(Text, default="")
    report: Mapped[str] = mapped_column(Text, default="")
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    vulnerability: Mapped[Vulnerability | None] = relationship(back_populates="analysis_jobs")
    intelligence_item: Mapped[IntelligenceItem | None] = relationship(back_populates="analysis_jobs")
    collected_document: Mapped[CollectedDocument | None] = relationship(back_populates="analysis_jobs")
    agent_executions: Mapped[list["AgentExecution"]] = relationship(back_populates="analysis_job", cascade="all, delete-orphan")


class AgentExecution(Base):
    __tablename__ = "agent_executions"

    id: Mapped[int] = mapped_column(Integer, primary_key=True)
    analysis_job_id: Mapped[int] = mapped_column(ForeignKey("analysis_jobs.id", ondelete="CASCADE"), index=True)
    agent_name: Mapped[str] = mapped_column(String(80), index=True)
    stage_name: Mapped[str] = mapped_column(String(80), index=True)
    status: Mapped[str] = mapped_column(String(40), index=True, default="pending")
    provider_name: Mapped[str | None] = mapped_column(String(40), nullable=True)
    model_name: Mapped[str | None] = mapped_column(String(120), nullable=True)
    prompt_version: Mapped[str] = mapped_column(String(40), default="v2")
    retry_count: Mapped[int] = mapped_column(Integer, default=1)
    latency_ms: Mapped[int | None] = mapped_column(Integer, nullable=True)
    prompt_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    completion_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    total_tokens: Mapped[int | None] = mapped_column(Integer, nullable=True)
    input_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    output_payload: Mapped[dict] = mapped_column(JSON, default=dict)
    error_message: Mapped[str | None] = mapped_column(Text, nullable=True)
    started_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)
    finished_at: Mapped[datetime | None] = mapped_column(DateTime(timezone=True), nullable=True)

    analysis_job: Mapped[AnalysisJob] = relationship(back_populates="agent_executions")
