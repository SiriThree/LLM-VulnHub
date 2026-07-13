from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity, require_role
from app.db.session import get_db
from app.schemas.intel import (
    BatchReviewDecisionRequest,
    BatchReviewDecisionResponse,
    IntelligenceItemRead,
    IntelligenceListResponse,
    IntelligenceStatsRead,
    MergeCandidateRead,
    MergeDecisionRequest,
    ReviewActionListResponse,
    ReviewDecisionRequest,
    ReviewStatsRead,
)
from app.services.intel_service import (
    approve_intelligence_item,
    approve_merge_candidate,
    batch_approve_intelligence_items,
    batch_reject_intelligence_items,
    export_review_actions_csv,
    get_intelligence_item,
    get_intelligence_stats,
    get_review_stats,
    list_intelligence_items,
    list_merge_candidates,
    list_review_actions,
    reject_intelligence_item,
)

router = APIRouter(prefix="/intel", tags=["intel"])


@router.get("/items", response_model=IntelligenceListResponse)
def list_items(status: str | None = Query(default=None), db: Session = Depends(get_db)):
    return {"items": list_intelligence_items(db, status=status)}


@router.get("/stats", response_model=IntelligenceStatsRead)
def get_stats(db: Session = Depends(get_db)):
    return get_intelligence_stats(db)


@router.get("/review-stats", response_model=ReviewStatsRead)
def get_review_metrics(db: Session = Depends(get_db)):
    return get_review_stats(db)


@router.get("/items/{intel_item_id}", response_model=IntelligenceItemRead)
def get_item(intel_item_id: int, db: Session = Depends(get_db)):
    item = get_intelligence_item(db, intel_item_id)
    if not item:
        raise HTTPException(404, "intelligence item not found")
    return item


@router.get("/items/{intel_item_id}/actions", response_model=ReviewActionListResponse)
def list_item_actions(intel_item_id: int, db: Session = Depends(get_db)):
    item = get_intelligence_item(db, intel_item_id)
    if not item:
        raise HTTPException(404, "intelligence item not found")
    return {"items": list_review_actions(db, target_type="intelligence_item", target_id=intel_item_id)}


@router.get("/review-actions", response_model=ReviewActionListResponse)
def list_all_review_actions(
    actor: str | None = Query(default=None),
    limit: int = Query(default=50, ge=1, le=200),
    db: Session = Depends(get_db),
):
    return {"items": list_review_actions(db, actor=actor, limit=limit)}


@router.get("/review-actions/export", response_class=PlainTextResponse)
def export_review_actions(
    actor: str | None = Query(default=None),
    limit: int = Query(default=500, ge=1, le=2000),
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("admin")),
):
    return export_review_actions_csv(db, actor=actor, limit=limit)


@router.post("/items/{intel_item_id}/approve", response_model=IntelligenceItemRead)
def approve_item(
    intel_item_id: int,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    item = approve_intelligence_item(db, intel_item_id, actor=payload.actor or identity.actor, notes=payload.notes)
    if not item:
        raise HTTPException(404, "intelligence item not found")
    return item


@router.post("/items/{intel_item_id}/reject", response_model=IntelligenceItemRead)
def reject_item(
    intel_item_id: int,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    item = reject_intelligence_item(db, intel_item_id, actor=payload.actor or identity.actor, notes=payload.notes)
    if not item:
        raise HTTPException(404, "intelligence item not found")
    return item


@router.post("/items/batch-approve", response_model=BatchReviewDecisionResponse)
def batch_approve_items(
    payload: BatchReviewDecisionRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    return {"items": batch_approve_intelligence_items(db, payload.item_ids, actor=payload.actor or identity.actor, notes=payload.notes)}


@router.post("/items/batch-reject", response_model=BatchReviewDecisionResponse)
def batch_reject_items(
    payload: BatchReviewDecisionRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    return {"items": batch_reject_intelligence_items(db, payload.item_ids, actor=payload.actor or identity.actor, notes=payload.notes)}


@router.get("/merge-candidates", response_model=list[MergeCandidateRead])
def get_merge_candidates(
    intel_item_id: int | None = Query(default=None),
    status: str | None = Query(default=None),
    db: Session = Depends(get_db),
):
    return list_merge_candidates(db, intel_item_id=intel_item_id, status=status)


@router.post("/merge-candidates/{merge_candidate_id}/approve", response_model=MergeCandidateRead)
def approve_merge(
    merge_candidate_id: int,
    payload: MergeDecisionRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    candidate = approve_merge_candidate(db, merge_candidate_id, actor=payload.actor or identity.actor, notes=payload.notes)
    if not candidate:
        raise HTTPException(404, "merge candidate not found")
    return candidate
