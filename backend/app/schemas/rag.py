from pydantic import BaseModel, Field

from app.schemas.vulnerability import VulnerabilityRead


class RagAskRequest(BaseModel):
    question: str = Field(min_length=2)
    top_k: int = Field(default=5, ge=1, le=10)


class RagSearchRequest(BaseModel):
    query: str = Field(min_length=2)
    top_k: int = Field(default=5, ge=1, le=10)


class SearchHit(BaseModel):
    vulnerability: VulnerabilityRead
    similarity: float
    chunk_text: str


class RagAskResponse(BaseModel):
    answer: str
    references: list[SearchHit]
