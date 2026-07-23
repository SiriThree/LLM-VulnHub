from typing import Literal

from pydantic import BaseModel


class ArchitectureNodeRead(BaseModel):
    id: str
    label: str
    layer: str
    description: str


class ArchitectureEdgeRead(BaseModel):
    source: str
    target: str
    label: str


class TrustBoundaryRead(BaseModel):
    id: str
    title: str
    trust_level: Literal["untrusted", "controlled", "third_party"]
    description: str
    assets: list[str]


class ThreatRead(BaseModel):
    id: str
    category: str
    title: str
    scenario: str
    impact: str
    current_controls: list[str]
    recommended_controls: list[str]
    priority: Literal["严重", "高", "中", "低"]
    status: Literal["已实施", "部分实施", "规划中"]


class SecurityModelRead(BaseModel):
    version: str
    scope: str
    business_flow: list[str]
    architecture_nodes: list[ArchitectureNodeRead]
    architecture_edges: list[ArchitectureEdgeRead]
    trust_boundaries: list[TrustBoundaryRead]
    threats: list[ThreatRead]
    rag_controls: list[str]
    release_baseline: list[str]
