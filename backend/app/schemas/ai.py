from pydantic import BaseModel, Field

from app.schemas.vulnerability import VulnerabilityCreate, VulnerabilityRead


class ExtractRequest(BaseModel):
    raw_text: str = Field(min_length=10)
    source_url: str | None = None


class RelevanceResult(BaseModel):
    is_ai_vulnerability: bool
    confidence: float = Field(ge=0, le=1)
    related_area: str = "unknown"
    reason: str = ""


class ExtractResult(VulnerabilityCreate):
    risk_reason: str = ""
    similar: list[VulnerabilityRead] = []


class AnalyzeRequest(ExtractRequest):
    save: bool = False


class AnalyzeResult(BaseModel):
    relevance: RelevanceResult
    extracted: ExtractResult
    vulnerability: VulnerabilityRead | None = None
    report: str


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
    risk_reason: str | None = None


class ReportResult(BaseModel):
    report: str
