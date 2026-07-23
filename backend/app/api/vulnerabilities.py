from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.core.security import RequestIdentity, allowed_visibilities, can_access_visibility, require_role
from app.db.models import IntelligenceItem, Vulnerability, VulnerabilityOccurrence
from app.db.session import get_db
from app.schemas.vulnerability import (
    DashboardStats,
    VulnerabilityCreate,
    VulnerabilityDetailRead,
    VulnerabilityLineageRead,
    VulnerabilityList,
    VulnerabilityRead,
    VulnerabilityUpdate,
)
from app.services.vulnerability_service import (
    create_vulnerability,
    dashboard_stats,
    list_vulnerabilities,
    serialize_vulnerability_lineage,
    serialize_vulnerability,
    serialize_vulnerability_for_role,
    serialize_vulnerability_detail,
    update_vulnerability,
)

router = APIRouter(prefix="/vulnerabilities", tags=["vulnerabilities"])


@router.get("", response_model=VulnerabilityList)
def list_api(
    q: str | None = Query(default=None, max_length=300),
    severity: str | None = Query(default=None, max_length=20),
    vuln_type: str | None = Query(default=None, max_length=120),
    component: str | None = Query(default=None, max_length=200),
    status: str | None = Query(default=None, max_length=40),
    page: int = Query(1, ge=1),
    page_size: int = Query(5, ge=1, le=100),
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("guest")),
):
    items, total = list_vulnerabilities(db, q, severity, vuln_type, component, status, page, page_size, identity.role)
    return {
        "items": [serialize_vulnerability_for_role(v, identity.role) for v in items],
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/dashboard", response_model=DashboardStats)
def dashboard_api(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("guest")),
):
    return dashboard_stats(db, identity.role)


@router.get("/{vuln_id}", response_model=VulnerabilityDetailRead)
def get_api(
    vuln_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("guest")),
):
    vuln = (
        db.query(Vulnerability)
        .options(
            selectinload(Vulnerability.tags),
            selectinload(Vulnerability.occurrences)
            .selectinload(VulnerabilityOccurrence.intelligence_item)
            .selectinload(IntelligenceItem.source),
            selectinload(Vulnerability.occurrences)
            .selectinload(VulnerabilityOccurrence.intelligence_item)
            .selectinload(IntelligenceItem.collected_document),
            selectinload(Vulnerability.analyses),
        )
        .filter(Vulnerability.id == vuln_id, Vulnerability.visibility.in_(allowed_visibilities(identity.role)))
        .first()
    )
    if not vuln:
        raise HTTPException(404, "vulnerability not found")
    return serialize_vulnerability_detail(vuln, identity.role)


@router.get("/{vuln_id}/lineage", response_model=VulnerabilityLineageRead)
def get_lineage_api(
    vuln_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("viewer")),
):
    vuln = (
        db.query(Vulnerability)
        .options(
            selectinload(Vulnerability.occurrences)
            .selectinload(VulnerabilityOccurrence.intelligence_item)
            .selectinload(IntelligenceItem.source),
            selectinload(Vulnerability.occurrences)
            .selectinload(VulnerabilityOccurrence.intelligence_item)
            .selectinload(IntelligenceItem.collected_document),
        )
        .filter(Vulnerability.id == vuln_id, Vulnerability.visibility.in_(allowed_visibilities(identity.role)))
        .first()
    )
    if not vuln:
        raise HTTPException(404, "vulnerability not found")
    return serialize_vulnerability_lineage(db, vuln)


@router.post("", response_model=VulnerabilityRead)
def create_api(
    payload: VulnerabilityCreate,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    if payload.visibility == "restricted" and identity.role != "admin":
        raise HTTPException(403, "only admins can create restricted records")
    return serialize_vulnerability(create_vulnerability(db, payload))


@router.put("/{vuln_id}", response_model=VulnerabilityRead)
def update_api(
    vuln_id: int,
    payload: VulnerabilityUpdate,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    existing = db.get(Vulnerability, vuln_id)
    if not existing or not can_access_visibility(identity.role, existing.visibility):
        raise HTTPException(404, "vulnerability not found")
    if payload.visibility == "restricted" and identity.role != "admin":
        raise HTTPException(403, "only admins can mark records as restricted")
    vuln = update_vulnerability(db, vuln_id, payload)
    if not vuln:
        raise HTTPException(404, "vulnerability not found")
    return serialize_vulnerability(vuln)


@router.delete("/{vuln_id}")
def delete_api(
    vuln_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("admin")),
):
    vuln = db.get(Vulnerability, vuln_id)
    if not vuln:
        raise HTTPException(404, "vulnerability not found")
    db.delete(vuln)
    db.commit()
    return {"ok": True}
