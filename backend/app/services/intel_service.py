from collections import Counter
from datetime import datetime, timedelta, timezone
import csv
import io

from sqlalchemy import func, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import CollectedDocument, IntelligenceItem, MergeCandidate, ReviewAction, Vulnerability, VulnerabilityOccurrence
from app.schemas.vulnerability import VulnerabilityCreate
from app.services.collector_service import _ensure_intelligence_item_for_document
from app.services.vulnerability_service import create_vulnerability, serialize_vulnerability


def _json_safe_vulnerability_snapshot(vulnerability: Vulnerability) -> dict:
    snapshot = serialize_vulnerability(vulnerability)
    for field in ("created_at", "updated_at"):
        value = snapshot.get(field)
        if value is not None:
            snapshot[field] = value.isoformat()
    return snapshot


def list_intelligence_items(db: Session, status: str | None = None) -> list[IntelligenceItem]:
    for doc in db.scalars(select(CollectedDocument)).all():
        _ensure_intelligence_item_for_document(db, doc)
    stmt = select(IntelligenceItem).options(selectinload(IntelligenceItem.merge_candidates)).order_by(
        IntelligenceItem.collected_at.desc(),
        IntelligenceItem.id.desc(),
    )
    if status:
        stmt = stmt.where(IntelligenceItem.status == status)
    return list(db.scalars(stmt).all())


def get_intelligence_item(db: Session, intel_item_id: int) -> IntelligenceItem | None:
    stmt = (
        select(IntelligenceItem)
        .options(selectinload(IntelligenceItem.merge_candidates))
        .where(IntelligenceItem.id == intel_item_id)
    )
    return db.scalar(stmt)


def list_merge_candidates(db: Session, intel_item_id: int | None = None, status: str | None = None) -> list[MergeCandidate]:
    stmt = select(MergeCandidate).order_by(MergeCandidate.created_at.desc())
    if intel_item_id is not None:
        stmt = stmt.where(MergeCandidate.intelligence_item_id == intel_item_id)
    if status:
        stmt = stmt.where(MergeCandidate.status == status)
    return list(db.scalars(stmt).all())


def _record_review_action(
    db: Session,
    *,
    actor: str,
    target_type: str,
    target_id: int,
    action: str,
    before_snapshot: dict,
    after_snapshot: dict,
    reason: str = "",
) -> None:
    db.add(
        ReviewAction(
            actor=actor,
            target_type=target_type,
            target_id=target_id,
            action=action,
            before_snapshot=before_snapshot,
            after_snapshot=after_snapshot,
            reason=reason,
        )
    )
    db.commit()


def approve_intelligence_item(db: Session, intel_item_id: int, actor: str, notes: str | None = None) -> IntelligenceItem | None:
    intel_item = get_intelligence_item(db, intel_item_id)
    if not intel_item:
        return None

    before = {
        "status": intel_item.status,
        "vulnerability_id": intel_item.vulnerability_id,
        "review_notes": intel_item.review_notes,
    }
    intel_item.review_notes = notes

    if intel_item.vulnerability_id:
        intel_item.status = "approved"
        db.commit()
        db.refresh(intel_item)
    else:
        extracted = dict(intel_item.extracted_data or {})
        payload = VulnerabilityCreate(**extracted)
        vuln = create_vulnerability(db, payload, extracted.get("risk_reason", ""))
        intel_item.vulnerability_id = vuln.id
        intel_item.status = "approved"
        db.add(
            VulnerabilityOccurrence(
                vulnerability_id=vuln.id,
                intelligence_item_id=intel_item.id,
                source_url=intel_item.url,
                published_at=datetime.now(timezone.utc),
                evidence_excerpt=intel_item.raw_text[:400],
                confidence=intel_item.triage_confidence,
            )
        )
        db.commit()
        db.refresh(intel_item)

    _record_review_action(
        db,
        actor=actor,
        target_type="intelligence_item",
        target_id=intel_item.id,
        action="approve",
        before_snapshot=before,
        after_snapshot={
            "status": intel_item.status,
            "vulnerability_id": intel_item.vulnerability_id,
            "review_notes": intel_item.review_notes,
        },
        reason=notes or "",
    )
    return intel_item


def reject_intelligence_item(db: Session, intel_item_id: int, actor: str, notes: str | None = None) -> IntelligenceItem | None:
    intel_item = get_intelligence_item(db, intel_item_id)
    if not intel_item:
        return None

    before = {
        "status": intel_item.status,
        "review_notes": intel_item.review_notes,
    }
    intel_item.status = "rejected"
    intel_item.review_notes = notes
    db.commit()
    db.refresh(intel_item)

    _record_review_action(
        db,
        actor=actor,
        target_type="intelligence_item",
        target_id=intel_item.id,
        action="reject",
        before_snapshot=before,
        after_snapshot={"status": intel_item.status, "review_notes": intel_item.review_notes},
        reason=notes or "",
    )
    return intel_item


def approve_merge_candidate(db: Session, merge_candidate_id: int, actor: str, notes: str | None = None) -> MergeCandidate | None:
    candidate = db.get(MergeCandidate, merge_candidate_id)
    if not candidate:
        return None

    intel_item = get_intelligence_item(db, candidate.intelligence_item_id)
    target_vuln = db.get(Vulnerability, candidate.candidate_vulnerability_id)
    if not intel_item or not target_vuln:
        return None

    before = {
        "candidate_status": candidate.status,
        "intel_status": intel_item.status,
        "vulnerability_id": intel_item.vulnerability_id,
    }

    candidate.status = "approved"
    intel_item.vulnerability_id = target_vuln.id
    intel_item.status = "approved"
    intel_item.review_notes = notes

    db.add(
        VulnerabilityOccurrence(
            vulnerability_id=target_vuln.id,
            intelligence_item_id=intel_item.id,
            source_url=intel_item.url,
            published_at=datetime.now(timezone.utc),
            evidence_excerpt=intel_item.raw_text[:400],
            confidence=intel_item.triage_confidence,
        )
    )
    db.commit()
    db.refresh(candidate)

    _record_review_action(
        db,
        actor=actor,
        target_type="merge_candidate",
        target_id=candidate.id,
        action="approve_merge",
        before_snapshot=before,
        after_snapshot={
            "candidate_status": candidate.status,
            "intel_status": intel_item.status,
            "vulnerability_id": intel_item.vulnerability_id,
            "merged_into": _json_safe_vulnerability_snapshot(target_vuln),
        },
        reason=notes or candidate.merge_reason,
    )
    return candidate


def batch_approve_intelligence_items(db: Session, item_ids: list[int], actor: str, notes: str | None = None) -> list[IntelligenceItem]:
    items: list[IntelligenceItem] = []
    for item_id in item_ids:
        item = approve_intelligence_item(db, item_id, actor=actor, notes=notes)
        if item:
            items.append(item)
    return items


def batch_reject_intelligence_items(db: Session, item_ids: list[int], actor: str, notes: str | None = None) -> list[IntelligenceItem]:
    items: list[IntelligenceItem] = []
    for item_id in item_ids:
        item = reject_intelligence_item(db, item_id, actor=actor, notes=notes)
        if item:
            items.append(item)
    return items


def list_review_actions(
    db: Session,
    *,
    target_type: str | None = None,
    target_id: int | None = None,
    actor: str | None = None,
    limit: int = 50,
) -> list[ReviewAction]:
    stmt = select(ReviewAction).order_by(ReviewAction.created_at.desc(), ReviewAction.id.desc())
    if target_type:
        stmt = stmt.where(ReviewAction.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(ReviewAction.target_id == target_id)
    if actor:
        stmt = stmt.where(ReviewAction.actor == actor)
    stmt = stmt.limit(limit)
    return list(db.scalars(stmt).all())


def get_review_stats(db: Session) -> dict:
    actions = list(db.scalars(select(ReviewAction).order_by(ReviewAction.created_at.desc())).all())
    actor_counter = Counter(action.actor for action in actions if action.actor)
    since = datetime.utcnow() - timedelta(hours=24)

    def _naive(dt: datetime | None) -> datetime | None:
        if dt is None:
            return None
        return dt.replace(tzinfo=None) if dt.tzinfo else dt

    return {
        "total_actions": len(actions),
        "approvals": sum(1 for action in actions if action.action == "approve"),
        "rejections": sum(1 for action in actions if action.action == "reject"),
        "merges": sum(1 for action in actions if action.action == "approve_merge"),
        "unique_actors": len(actor_counter),
        "last_24h_actions": sum(1 for action in actions if _naive(action.created_at) and _naive(action.created_at) >= since),
        "top_actors": [{"actor": actor, "count": count} for actor, count in actor_counter.most_common(5)],
    }


def export_review_actions_csv(db: Session, *, actor: str | None = None, limit: int = 500) -> str:
    actions = list_review_actions(db, actor=actor, limit=limit)
    buffer = io.StringIO()
    writer = csv.writer(buffer)
    writer.writerow(["id", "actor", "target_type", "target_id", "action", "reason", "created_at"])
    for action in actions:
        writer.writerow(
            [
                action.id,
                action.actor,
                action.target_type,
                action.target_id,
                action.action,
                action.reason,
                action.created_at.isoformat() if action.created_at else "",
            ]
        )
    return buffer.getvalue()


def get_intelligence_stats(db: Session) -> dict:
    for doc in db.scalars(select(CollectedDocument)).all():
        _ensure_intelligence_item_for_document(db, doc)

    total = db.scalar(select(func.count()).select_from(IntelligenceItem)) or 0
    pending_review = db.scalar(select(func.count()).select_from(IntelligenceItem).where(IntelligenceItem.status == "pending_review")) or 0
    approved = db.scalar(select(func.count()).select_from(IntelligenceItem).where(IntelligenceItem.status == "approved")) or 0
    rejected = db.scalar(select(func.count()).select_from(IntelligenceItem).where(IntelligenceItem.status == "rejected")) or 0
    triaged = db.scalar(select(func.count()).select_from(IntelligenceItem).where(IntelligenceItem.status == "triaged")) or 0
    merge_candidates_pending = db.scalar(select(func.count()).select_from(MergeCandidate).where(MergeCandidate.status == "pending")) or 0

    high_risk_pending_review = 0
    pending_items = db.scalars(select(IntelligenceItem).where(IntelligenceItem.status == "pending_review")).all()
    for item in pending_items:
        severity = str((item.extracted_data or {}).get("severity", ""))
        score = int((item.extracted_data or {}).get("score", 0) or 0)
        if severity in {"高危", "严重"} or score >= 80:
            high_risk_pending_review += 1

    return {
        "total": total,
        "pending_review": pending_review,
        "approved": approved,
        "rejected": rejected,
        "triaged": triaged,
        "high_risk_pending_review": high_risk_pending_review,
        "merge_candidates_pending": merge_candidates_pending,
    }
