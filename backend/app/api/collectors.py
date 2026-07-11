from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import CollectedDocument
from app.db.session import get_db
from app.schemas.collector import CollectedDocumentRead, CollectorRunRequest, CollectorRunResult
from app.services.collector_service import (
    approve_document,
    create_collection_task,
    dispatch_collection_task,
)

router = APIRouter(prefix="/collectors", tags=["collectors"])


@router.post("/run", response_model=CollectorRunResult)
def run_api(payload: CollectorRunRequest, db: Session = Depends(get_db)):
    task = create_collection_task(db, payload.source_id)
    dispatch_collection_task(task.id)
    output = task.output_data or {}
    return {
        "task_id": task.id,
        "status": task.status,
        "current_stage": output.get("current_stage", "queued"),
        "queued_at": task.created_at,
        "message": "Collection task queued.",
    }


@router.get("/documents", response_model=list[CollectedDocumentRead])
def documents_api(db: Session = Depends(get_db)):
    return db.scalars(select(CollectedDocument).order_by(CollectedDocument.collected_at.desc()).limit(100)).all()


@router.post("/documents/{doc_id}/approve", response_model=CollectedDocumentRead)
async def approve_api(doc_id: int, db: Session = Depends(get_db)):
    doc = await approve_document(db, doc_id)
    if not doc:
        raise HTTPException(404, "document not found")
    return doc
