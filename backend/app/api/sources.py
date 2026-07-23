from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity, require_role
from app.core.input_security import InputSecurityError
from app.db.models import DataSource
from app.db.session import get_db
from app.schemas.collector import DataSourceCreate, DataSourceRead, DataSourceUpdate
from app.services.collector_service import create_source, update_source

router = APIRouter(prefix="/sources", tags=["sources"])


@router.get("", response_model=list[DataSourceRead])
def list_sources(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    return db.scalars(select(DataSource).order_by(DataSource.created_at.desc())).all()


@router.post("", response_model=DataSourceRead)
def create_source_api(
    payload: DataSourceCreate,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("admin")),
):
    try:
        return create_source(db, payload)
    except InputSecurityError as exc:
        raise HTTPException(422, detail=str(exc)) from exc


@router.put("/{source_id}", response_model=DataSourceRead)
def update_source_api(
    source_id: int,
    payload: DataSourceUpdate,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("admin")),
):
    try:
        source = update_source(db, source_id, payload)
    except InputSecurityError as exc:
        raise HTTPException(422, detail=str(exc)) from exc
    if not source:
        raise HTTPException(404, "source not found")
    return source


@router.delete("/{source_id}")
def delete_source_api(
    source_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("admin")),
):
    source = db.get(DataSource, source_id)
    if not source:
        raise HTTPException(404, "source not found")
    db.delete(source)
    db.commit()
    return {"ok": True}
