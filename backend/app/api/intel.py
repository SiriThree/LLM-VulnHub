from fastapi import APIRouter, Depends, HTTPException, Query
from fastapi.responses import PlainTextResponse
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity, can_access_visibility, require_role
from app.db.models import MergeCandidate, Vulnerability
from app.db.session import get_db
from app.schemas.intel import (
    BatchReviewDecisionRequest,
    BatchReviewDecisionResponse,
    IntelligenceLineageRead,
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
    batch_undo_intelligence_reviews,
    count_review_actions,
    export_review_actions_csv,
    get_intelligence_item,
    get_intelligence_lineage,
    get_intelligence_stats,
    get_review_stats,
    list_intelligence_items,
    list_intelligence_review_actions,
    list_merge_candidates,
    list_review_actions,
    reject_intelligence_item,
    undo_intelligence_review,
)

router = APIRouter(prefix="/intel", tags=["intel"])


@router.get("/items", response_model=IntelligenceListResponse)
def list_items(
    status: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=100),
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    items, total = list_intelligence_items(db, status=status, page=page, page_size=page_size)
    return {"items": items, "total": total, "page": page, "page_size": page_size}


@router.get("/stats", response_model=IntelligenceStatsRead)
def get_stats(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    return get_intelligence_stats(db)


@router.get("/review-stats", response_model=ReviewStatsRead)
def get_review_metrics(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    return get_review_stats(db)


@router.get("/items/{intel_item_id}", response_model=IntelligenceItemRead)
def get_item(
    intel_item_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    item = get_intelligence_item(db, intel_item_id)
    if not item:
        raise HTTPException(404, "intelligence item not found")
    return item


@router.get("/items/{intel_item_id}/lineage", response_model=IntelligenceLineageRead)
def get_item_lineage(
    intel_item_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    payload = get_intelligence_lineage(db, intel_item_id)
    if not payload:
        raise HTTPException(404, "intelligence item not found")
    return payload


@router.get("/items/{intel_item_id}/actions", response_model=ReviewActionListResponse)
def list_item_actions(
    intel_item_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    item = get_intelligence_item(db, intel_item_id)
    if not item:
        raise HTTPException(404, "intelligence item not found")
    items = list_intelligence_review_actions(db, intel_item_id)
    return {"items": items, "total": len(items), "page": 1, "page_size": max(1, len(items))}


@router.get("/review-actions", response_model=ReviewActionListResponse)
def list_all_review_actions(
    actor: str | None = Query(default=None, max_length=120),
    action: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=100),
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    total = count_review_actions(db, actor=actor, action=action)
    return {
        "items": list_review_actions(
            db,
            actor=actor,
            action=action,
            offset=(page - 1) * page_size,
            limit=page_size,
        ),
        "total": total,
        "page": page,
        "page_size": page_size,
    }


@router.get("/review-actions/export", response_class=PlainTextResponse)
def export_review_actions(
    actor: str | None = Query(default=None, max_length=120),
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
    try:
        item = approve_intelligence_item(db, intel_item_id, actor=identity.actor, notes=payload.notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
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
    try:
        item = reject_intelligence_item(db, intel_item_id, actor=identity.actor, notes=payload.notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not item:
        raise HTTPException(404, "intelligence item not found")
    return item


@router.post("/items/{intel_item_id}/undo", response_model=IntelligenceItemRead)
def undo_item_review(
    intel_item_id: int,
    payload: ReviewDecisionRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    try:
        item = undo_intelligence_review(db, intel_item_id, actor=identity.actor, notes=payload.notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not item:
        raise HTTPException(404, "intelligence item not found")
    return item


@router.post("/items/batch-approve", response_model=BatchReviewDecisionResponse)
def batch_approve_items(
    payload: BatchReviewDecisionRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    try:
        items = batch_approve_intelligence_items(db, payload.item_ids, actor=identity.actor, notes=payload.notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"items": items}


@router.post("/items/batch-reject", response_model=BatchReviewDecisionResponse)
def batch_reject_items(
    payload: BatchReviewDecisionRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    try:
        items = batch_reject_intelligence_items(db, payload.item_ids, actor=identity.actor, notes=payload.notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"items": items}


@router.post("/items/batch-undo", response_model=BatchReviewDecisionResponse)
def batch_undo_items(
    payload: BatchReviewDecisionRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    try:
        items = batch_undo_intelligence_reviews(db, payload.item_ids, actor=identity.actor, notes=payload.notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    return {"items": items}


@router.get("/merge-candidates", response_model=list[MergeCandidateRead])
def get_merge_candidates(
    intel_item_id: int | None = Query(default=None),
    status: str | None = Query(default=None, max_length=40),
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    return list_merge_candidates(db, intel_item_id=intel_item_id, status=status)


@router.post("/merge-candidates/{merge_candidate_id}/approve", response_model=MergeCandidateRead)
def approve_merge(
    merge_candidate_id: int,
    payload: MergeDecisionRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    candidate_record = db.get(MergeCandidate, merge_candidate_id)
    target = db.get(Vulnerability, candidate_record.candidate_vulnerability_id) if candidate_record else None
    if not candidate_record or not target or not can_access_visibility(identity.role, target.visibility):
        raise HTTPException(404, "merge candidate not found")
    try:
        candidate = approve_merge_candidate(db, merge_candidate_id, actor=identity.actor, notes=payload.notes)
    except ValueError as exc:
        raise HTTPException(400, str(exc)) from exc
    if not candidate:
        raise HTTPException(404, "merge candidate not found")
    return candidate
