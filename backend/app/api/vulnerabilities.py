from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy.orm import Session, selectinload

from app.db.models import Vulnerability
from app.db.session import get_db
from app.schemas.vulnerability import DashboardStats, VulnerabilityCreate, VulnerabilityList, VulnerabilityRead, VulnerabilityUpdate
from app.services.vulnerability_service import create_vulnerability, dashboard_stats, list_vulnerabilities, serialize_vulnerability, update_vulnerability

router = APIRouter(prefix="/vulnerabilities", tags=["vulnerabilities"])


@router.get("", response_model=VulnerabilityList)
def list_api(
    q: str | None = None,
    severity: str | None = None,
    vuln_type: str | None = None,
    component: str | None = None,
    status: str | None = None,
    page: int = Query(1, ge=1),
    page_size: int = Query(20, ge=1, le=100),
    db: Session = Depends(get_db),
):
    items, total = list_vulnerabilities(db, q, severity, vuln_type, component, status, page, page_size)
    return {"items": [serialize_vulnerability(v) for v in items], "total": total, "page": page, "page_size": page_size}


@router.get("/dashboard", response_model=DashboardStats)
def dashboard_api(db: Session = Depends(get_db)):
    return dashboard_stats(db)


@router.get("/{vuln_id}", response_model=VulnerabilityRead)
def get_api(vuln_id: int, db: Session = Depends(get_db)):
    vuln = db.query(Vulnerability).options(selectinload(Vulnerability.tags)).filter(Vulnerability.id == vuln_id).first()
    if not vuln:
        raise HTTPException(404, "vulnerability not found")
    return serialize_vulnerability(vuln)


@router.post("", response_model=VulnerabilityRead)
def create_api(payload: VulnerabilityCreate, db: Session = Depends(get_db)):
    return serialize_vulnerability(create_vulnerability(db, payload))


@router.put("/{vuln_id}", response_model=VulnerabilityRead)
def update_api(vuln_id: int, payload: VulnerabilityUpdate, db: Session = Depends(get_db)):
    vuln = update_vulnerability(db, vuln_id, payload)
    if not vuln:
        raise HTTPException(404, "vulnerability not found")
    return serialize_vulnerability(vuln)


@router.delete("/{vuln_id}")
def delete_api(vuln_id: int, db: Session = Depends(get_db)):
    vuln = db.get(Vulnerability, vuln_id)
    if not vuln:
        raise HTTPException(404, "vulnerability not found")
    db.delete(vuln)
    db.commit()
    return {"ok": True}
