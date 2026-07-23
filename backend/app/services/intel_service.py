from collections import Counter
from datetime import datetime, timedelta, timezone
import csv
import io

from sqlalchemy import func, or_, select
from sqlalchemy.orm import Session, selectinload

from app.db.models import (
    AnalysisJob,
    CollectedDocument,
    IntelligenceItem,
    MergeCandidate,
    ReviewAction,
    Task,
    Vulnerability,
    VulnerabilityOccurrence,
)
from app.schemas.vulnerability import (
    VulnerabilityCreate,
    normalize_confidence_value,
    normalize_score_value,
    normalize_severity_value,
    normalize_tags_value,
)
from app.services.collector_service import _ensure_intelligence_item_for_document
from app.services.provenance_service import build_source_health
from app.services.vulnerability_service import create_vulnerability, serialize_vulnerability

PUBLISHABLE_STATUSES = {"pending_review", "triaged"}
MISSING_TEXT = "原文未提供，需人工补充。"


def _json_safe_vulnerability_snapshot(vulnerability: Vulnerability) -> dict:
    snapshot = serialize_vulnerability(vulnerability)
    for field in ("created_at", "updated_at"):
        value = snapshot.get(field)
        if value is not None:
            snapshot[field] = value.isoformat()
    return snapshot


def _normalize_extracted_payload(extracted: dict) -> dict:
    payload = dict(extracted or {})
    payload["severity"] = normalize_severity_value(payload.get("severity"))
    payload["score"] = normalize_score_value(payload.get("score"), payload.get("severity"), default=0)
    payload["confidence"] = normalize_confidence_value(payload.get("confidence", 0.0))
    payload["tags"] = normalize_tags_value(payload.get("tags"))
    return payload


def _repair_legacy_intelligence_statuses(db: Session) -> None:
    items = db.scalars(
        select(IntelligenceItem)
        .options(selectinload(IntelligenceItem.collected_document))
        .where(IntelligenceItem.status == "rejected", IntelligenceItem.vulnerability_id.is_(None))
    ).all()
    if not items:
        return

    rejected_ids = {
        target_id
        for target_id, action in db.execute(
            select(ReviewAction.target_id, ReviewAction.action).where(
                ReviewAction.target_type == "intelligence_item",
                ReviewAction.action == "reject",
            )
        ).all()
    }

    changed = False
    for item in items:
        if item.id in rejected_ids:
            continue
        if item.collected_document and item.collected_document.status == "ignored":
            item.status = "ignored"
            changed = True
    if changed:
        db.commit()


def _build_publishable_extracted_payload(intel_item: IntelligenceItem) -> dict:
    payload = _normalize_extracted_payload(dict(intel_item.extracted_data or {}))
    title = str(payload.get("title") or "").strip() or intel_item.title.strip() or f"情报 #{intel_item.id}"
    vuln_type = str(payload.get("vuln_type") or "").strip() or str(intel_item.triage_category or "").strip() or "unknown"
    affected_component = str(payload.get("affected_component") or "").strip() or "待确认"
    description = str(payload.get("description") or "").strip() or intel_item.raw_text[:1200]
    attack_method = str(payload.get("attack_method") or "").strip() or MISSING_TEXT
    impact = str(payload.get("impact") or "").strip() or MISSING_TEXT
    mitigation = str(payload.get("mitigation") or "").strip() or MISSING_TEXT

    payload.update(
        {
            "title": title,
            "vuln_type": vuln_type,
            "affected_component": affected_component,
            "description": description,
            "attack_method": attack_method,
            "impact": impact,
            "mitigation": mitigation,
            "source_url": payload.get("source_url") or intel_item.url,
            "reference_url": payload.get("reference_url") or intel_item.url,
            "status": payload.get("status") or "待确认",
        }
    )
    payload["severity"] = normalize_severity_value(payload.get("severity"))
    payload["score"] = normalize_score_value(payload.get("score"), payload.get("severity"), default=0)
    payload["confidence"] = normalize_confidence_value(payload.get("confidence", intel_item.triage_confidence))
    payload["tags"] = normalize_tags_value(payload.get("tags"))
    return payload


def list_intelligence_items(
    db: Session,
    status: str | None = None,
    *,
    page: int = 1,
    page_size: int = 10,
) -> tuple[list[IntelligenceItem], int]:
    _repair_legacy_intelligence_statuses(db)
    for doc in db.scalars(select(CollectedDocument)).all():
        _ensure_intelligence_item_for_document(db, doc)
    stmt = select(IntelligenceItem).options(selectinload(IntelligenceItem.merge_candidates)).order_by(
        IntelligenceItem.collected_at.desc(),
        IntelligenceItem.id.desc(),
    )
    if status:
        if status == "reviewable":
            stmt = stmt.where(IntelligenceItem.status.in_(PUBLISHABLE_STATUSES))
        else:
            stmt = stmt.where(IntelligenceItem.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.order_by(None).subquery())) or 0
    stmt = stmt.offset((page - 1) * page_size).limit(page_size)
    return list(db.scalars(stmt).all()), total


def get_intelligence_item(db: Session, intel_item_id: int) -> IntelligenceItem | None:
    stmt = (
        select(IntelligenceItem)
        .options(
            selectinload(IntelligenceItem.merge_candidates).selectinload(MergeCandidate.candidate_vulnerability),
            selectinload(IntelligenceItem.source),
            selectinload(IntelligenceItem.collected_document),
            selectinload(IntelligenceItem.vulnerability),
        )
        .where(IntelligenceItem.id == intel_item_id)
    )
    return db.scalar(stmt)


def list_merge_candidates(db: Session, intel_item_id: int | None = None, status: str | None = None) -> list[MergeCandidate]:
    stmt = select(MergeCandidate).options(selectinload(MergeCandidate.candidate_vulnerability)).order_by(MergeCandidate.created_at.desc())
    if intel_item_id is not None:
        stmt = stmt.where(MergeCandidate.intelligence_item_id == intel_item_id)
    if status:
        stmt = stmt.where(MergeCandidate.status == status)
    return list(db.scalars(stmt).all())


def _merge_quality(score: float) -> str:
    if score >= 0.72:
        return "strong"
    if score >= 0.5:
        return "medium"
    return "weak"


def _match_signals(item: IntelligenceItem, candidate: MergeCandidate) -> list[str]:
    signals: list[str] = []
    extracted = dict(item.extracted_data or {})
    vuln = candidate.candidate_vulnerability
    if not vuln:
        return signals

    item_type = str(extracted.get("vuln_type") or "").strip().lower()
    vuln_type = str(vuln.vuln_type or "").strip().lower()
    if item_type and vuln_type and item_type == vuln_type:
        signals.append("same vulnerability type")

    item_component = str(extracted.get("affected_component") or "").strip().lower()
    vuln_component = str(vuln.affected_component or "").strip().lower()
    if item_component and vuln_component and (item_component in vuln_component or vuln_component in item_component):
        signals.append("same affected component")

    item_title = item.title.strip().lower()
    vuln_title = str(vuln.title or "").strip().lower()
    if item_title and vuln_title:
        title_tokens = {token for token in item_title.replace("/", " ").split() if len(token) >= 4}
        if title_tokens and any(token in vuln_title for token in title_tokens):
            signals.append("title keyword overlap")

    if candidate.merge_score >= 0.72:
        signals.append("high semantic similarity")
    elif candidate.merge_score >= 0.5:
        signals.append("moderate semantic similarity")

    return signals


def serialize_merge_candidate_explanation(item: IntelligenceItem, candidate: MergeCandidate) -> dict:
    target = candidate.candidate_vulnerability
    quality = _merge_quality(candidate.merge_score)
    match_signals = _match_signals(item, candidate)
    review_hint = {
        "strong": "High-confidence duplicate candidate; usually safe to merge after checking source and timeline.",
        "medium": "Potential duplicate; compare affected component, exploit path, and source evidence before merging.",
        "weak": "Low-confidence candidate; keep separate unless analyst confirms the same root issue.",
    }[quality]
    return {
        "id": candidate.id,
        "intelligence_item_id": candidate.intelligence_item_id,
        "candidate_vulnerability_id": candidate.candidate_vulnerability_id,
        "merge_score": candidate.merge_score,
        "merge_reason": candidate.merge_reason,
        "status": candidate.status,
        "created_at": candidate.created_at,
        "updated_at": candidate.updated_at,
        "candidate_title": target.title if target else None,
        "candidate_severity": target.severity if target else None,
        "candidate_score": target.score if target else None,
        "candidate_component": target.affected_component if target else None,
        "quality": quality,
        "match_signals": match_signals,
        "review_hint": review_hint,
    }


def _is_candidate_displayable(candidate: dict) -> bool:
    if candidate["merge_score"] >= 0.5:
        return True
    return len(candidate["match_signals"]) >= 2


def get_intelligence_lineage(db: Session, intel_item_id: int) -> dict | None:
    item = get_intelligence_item(db, intel_item_id)
    if not item:
        return None

    source = item.source
    doc = item.collected_document
    vulnerability = item.vulnerability
    docs = db.scalars(select(CollectedDocument).order_by(CollectedDocument.collected_at.desc())).all()
    tasks = db.scalars(select(Task).order_by(Task.created_at.desc())).all()

    source_payload = None
    if source:
        health = build_source_health(source, docs, tasks)
        source_payload = {
            "id": source.id,
            "name": source.name,
            "source_type": source.source_type,
            "url": source.url,
            "enabled": source.enabled,
            "interval_minutes": source.interval_minutes,
            "last_collected_at": source.last_collected_at,
            "trust_score": health["trust_score"],
            "trust_level": health["trust_level"],
            "status": health["status"],
            "signals": health["signals"],
        }

    merge_candidates = [
        serialize_merge_candidate_explanation(item, candidate)
        for candidate in item.merge_candidates
    ]
    merge_candidates = [candidate for candidate in merge_candidates if _is_candidate_displayable(candidate)]
    merge_candidates.sort(key=lambda candidate: candidate["merge_score"], reverse=True)
    review_actions = list_review_actions(db, target_type="intelligence_item", target_id=item.id, limit=20)

    trace = []
    if source:
        trace.append(
            {
                "stage": "collect",
                "title": "Source collected",
                "status": source_payload["status"] if source_payload else "unknown",
                "timestamp": doc.collected_at if doc else item.collected_at,
                "detail": f"{source.name} ({source.source_type}) discovered this document.",
            }
        )
    if doc:
        trace.append(
            {
                "stage": "ingest",
                "title": "Document ingested",
                "status": doc.status,
                "timestamp": doc.collected_at,
                "detail": f"Document #{doc.id} stored with hash {doc.content_hash[:12]} and AI confidence {round(doc.confidence * 100)}%.",
            }
        )
    trace.append(
        {
            "stage": "triage",
            "title": "AI triage",
            "status": item.status,
            "timestamp": item.updated_at,
            "detail": item.triage_reason or "Triage completed without additional notes.",
        }
    )
    if merge_candidates:
        top_candidate = merge_candidates[0]
        trace.append(
            {
                "stage": "deduplicate",
                "title": "Duplicate check",
                "status": top_candidate["quality"],
                "timestamp": top_candidate["updated_at"],
                "detail": f"Top candidate vulnerability #{top_candidate['candidate_vulnerability_id']} scored {top_candidate['merge_score']:.2f}.",
            }
        )
    if vulnerability:
        trace.append(
            {
                "stage": "publish",
                "title": "Published to vulnerability library",
                "status": vulnerability.status,
                "timestamp": item.updated_at,
                "detail": f"Linked to vulnerability #{vulnerability.id}: {vulnerability.title}.",
            }
        )

    return {
        "intelligence_item_id": item.id,
        "title": item.title,
        "status": item.status,
        "triage_category": item.triage_category,
        "triage_confidence": item.triage_confidence,
        "source": source_payload,
        "collected_document": (
            {
                "id": doc.id,
                "title": doc.title,
                "url": doc.url,
                "status": doc.status,
                "is_ai_related": doc.is_ai_related,
                "confidence": doc.confidence,
                "collected_at": doc.collected_at,
                "content_hash": doc.content_hash,
            }
            if doc
            else None
        ),
        "linked_vulnerability": (
            {
                "id": vulnerability.id,
                "title": vulnerability.title,
                "severity": vulnerability.severity,
                "score": vulnerability.score,
                "status": vulnerability.status,
            }
            if vulnerability
            else None
        ),
        "merge_candidates": merge_candidates,
        "review_actions": review_actions,
        "trace": trace,
    }


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


def _ensure_occurrence(
    db: Session,
    *,
    intel_item: IntelligenceItem,
    vulnerability_id: int,
) -> None:
    existing = db.scalar(
        select(VulnerabilityOccurrence).where(
            VulnerabilityOccurrence.intelligence_item_id == intel_item.id,
            VulnerabilityOccurrence.vulnerability_id == vulnerability_id,
        )
    )
    if existing:
        return

    db.add(
        VulnerabilityOccurrence(
            vulnerability_id=vulnerability_id,
            intelligence_item_id=intel_item.id,
            source_url=intel_item.url,
            published_at=datetime.now(timezone.utc),
            evidence_excerpt=intel_item.raw_text[:400],
            confidence=intel_item.triage_confidence,
        )
    )


def publish_intelligence_item(
    db: Session,
    intel_item: IntelligenceItem,
    *,
    notes: str | None = None,
    vulnerability: Vulnerability | None = None,
) -> IntelligenceItem:
    target_vuln = vulnerability
    if target_vuln is None:
        extracted = _build_publishable_extracted_payload(intel_item)
        intel_item.extracted_data = extracted
        payload = VulnerabilityCreate(**extracted)
        target_vuln = create_vulnerability(db, payload, extracted.get("risk_reason", ""))

    intel_item.vulnerability_id = target_vuln.id
    intel_item.status = "approved"
    intel_item.review_notes = notes

    if intel_item.collected_document:
        intel_item.collected_document.vulnerability_id = target_vuln.id
        intel_item.collected_document.status = "stored"
        intel_item.collected_document.is_ai_related = True
        intel_item.collected_document.confidence = intel_item.triage_confidence

    related_jobs = intel_item.analysis_jobs or []
    for job in related_jobs:
        job.vulnerability_id = target_vuln.id
        job.intelligence_item_id = intel_item.id
        if intel_item.collected_document_id:
            job.collected_document_id = intel_item.collected_document_id

    _ensure_occurrence(db, intel_item=intel_item, vulnerability_id=target_vuln.id)
    db.commit()
    db.refresh(intel_item)
    return intel_item


def approve_intelligence_item(db: Session, intel_item_id: int, actor: str, notes: str | None = None) -> IntelligenceItem | None:
    intel_item = get_intelligence_item(db, intel_item_id)
    if not intel_item:
        return None
    if intel_item.status not in PUBLISHABLE_STATUSES:
        raise ValueError("Only reviewable intelligence items can be approved into the vulnerability library.")

    before = {
        "status": intel_item.status,
        "vulnerability_id": intel_item.vulnerability_id,
        "review_notes": intel_item.review_notes,
    }
    linked_vulnerability = db.get(Vulnerability, intel_item.vulnerability_id) if intel_item.vulnerability_id else None
    intel_item = publish_intelligence_item(db, intel_item, notes=notes, vulnerability=linked_vulnerability)

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
    if intel_item.status not in PUBLISHABLE_STATUSES:
        raise ValueError("Only reviewable intelligence items can be rejected.")

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
    if candidate.status != "pending":
        raise ValueError("Only pending merge candidates can be approved.")

    intel_item = get_intelligence_item(db, candidate.intelligence_item_id)
    target_vuln = db.get(Vulnerability, candidate.candidate_vulnerability_id)
    if not intel_item or not target_vuln:
        return None
    if intel_item.status not in PUBLISHABLE_STATUSES:
        raise ValueError("Only reviewable intelligence items can be merged.")

    before = {
        "candidate_status": candidate.status,
        "intel_status": intel_item.status,
        "vulnerability_id": intel_item.vulnerability_id,
    }

    candidate.status = "approved"
    intel_item = publish_intelligence_item(db, intel_item, notes=notes, vulnerability=target_vuln)
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


def _latest_direct_approval(db: Session, intel_item_id: int) -> ReviewAction | None:
    return db.scalar(
        select(ReviewAction)
        .where(
            ReviewAction.target_type == "intelligence_item",
            ReviewAction.target_id == intel_item_id,
            ReviewAction.action == "approve",
        )
        .order_by(ReviewAction.created_at.desc(), ReviewAction.id.desc())
        .limit(1)
    )


def undo_intelligence_review(
    db: Session,
    intel_item_id: int,
    actor: str,
    notes: str | None = None,
) -> IntelligenceItem | None:
    intel_item = get_intelligence_item(db, intel_item_id)
    if not intel_item:
        return None
    if intel_item.status in PUBLISHABLE_STATUSES and not intel_item.vulnerability_id:
        raise ValueError("This intelligence item is already waiting for review.")

    previous_vulnerability_id = intel_item.vulnerability_id
    before = {
        "status": intel_item.status,
        "vulnerability_id": previous_vulnerability_id,
        "review_notes": intel_item.review_notes,
    }

    if previous_vulnerability_id:
        occurrences = db.scalars(
            select(VulnerabilityOccurrence).where(
                VulnerabilityOccurrence.intelligence_item_id == intel_item.id,
                VulnerabilityOccurrence.vulnerability_id == previous_vulnerability_id,
            )
        ).all()
        for occurrence in occurrences:
            db.delete(occurrence)

    if intel_item.collected_document:
        intel_item.collected_document.vulnerability_id = None
        intel_item.collected_document.status = "pending_review"

    for job in intel_item.analysis_jobs or []:
        if job.vulnerability_id == previous_vulnerability_id:
            job.vulnerability_id = None

    for candidate in intel_item.merge_candidates:
        if candidate.status == "approved":
            candidate.status = "pending"

    intel_item.vulnerability_id = None
    intel_item.status = "pending_review"
    intel_item.review_notes = notes
    db.flush()

    deleted_orphan_vulnerability_id: int | None = None
    if previous_vulnerability_id:
        latest_approval = _latest_direct_approval(db, intel_item.id)
        created_by_direct_approval = bool(
            latest_approval
            and latest_approval.before_snapshot.get("vulnerability_id") is None
            and latest_approval.after_snapshot.get("vulnerability_id") == previous_vulnerability_id
        )
        other_intel_count = db.scalar(
            select(func.count())
            .select_from(IntelligenceItem)
            .where(
                IntelligenceItem.vulnerability_id == previous_vulnerability_id,
                IntelligenceItem.id != intel_item.id,
            )
        ) or 0
        other_occurrence_count = db.scalar(
            select(func.count())
            .select_from(VulnerabilityOccurrence)
            .where(VulnerabilityOccurrence.vulnerability_id == previous_vulnerability_id)
        ) or 0
        other_document_count = db.scalar(
            select(func.count())
            .select_from(CollectedDocument)
            .where(CollectedDocument.vulnerability_id == previous_vulnerability_id)
        ) or 0
        other_job_count = db.scalar(
            select(func.count())
            .select_from(AnalysisJob)
            .where(AnalysisJob.vulnerability_id == previous_vulnerability_id)
        ) or 0
        candidate_reference_count = db.scalar(
            select(func.count())
            .select_from(MergeCandidate)
            .where(MergeCandidate.candidate_vulnerability_id == previous_vulnerability_id)
        ) or 0
        if (
            created_by_direct_approval
            and other_intel_count == 0
            and other_occurrence_count == 0
            and other_document_count == 0
            and other_job_count == 0
            and candidate_reference_count == 0
        ):
            vulnerability = db.get(Vulnerability, previous_vulnerability_id)
            if vulnerability:
                db.delete(vulnerability)
                deleted_orphan_vulnerability_id = previous_vulnerability_id

    db.commit()
    db.refresh(intel_item)
    _record_review_action(
        db,
        actor=actor,
        target_type="intelligence_item",
        target_id=intel_item.id,
        action="undo_review",
        before_snapshot=before,
        after_snapshot={
            "status": intel_item.status,
            "vulnerability_id": intel_item.vulnerability_id,
            "review_notes": intel_item.review_notes,
            "deleted_orphan_vulnerability_id": deleted_orphan_vulnerability_id,
        },
        reason=notes or "",
    )
    return intel_item


def batch_approve_intelligence_items(db: Session, item_ids: list[int], actor: str, notes: str | None = None) -> list[IntelligenceItem]:
    existing = {
        item.id: item
        for item in db.scalars(select(IntelligenceItem).where(IntelligenceItem.id.in_(item_ids))).all()
    }
    invalid_ids = [item_id for item_id in item_ids if item_id not in existing or existing[item_id].status not in PUBLISHABLE_STATUSES]
    if invalid_ids:
        raise ValueError(f"Items are missing or not reviewable: {invalid_ids}")
    items: list[IntelligenceItem] = []
    for item_id in item_ids:
        item = approve_intelligence_item(db, item_id, actor=actor, notes=notes)
        if item:
            items.append(item)
    return items


def batch_reject_intelligence_items(db: Session, item_ids: list[int], actor: str, notes: str | None = None) -> list[IntelligenceItem]:
    existing = {
        item.id: item
        for item in db.scalars(select(IntelligenceItem).where(IntelligenceItem.id.in_(item_ids))).all()
    }
    invalid_ids = [item_id for item_id in item_ids if item_id not in existing or existing[item_id].status not in PUBLISHABLE_STATUSES]
    if invalid_ids:
        raise ValueError(f"Items are missing or not reviewable: {invalid_ids}")
    items: list[IntelligenceItem] = []
    for item_id in item_ids:
        item = reject_intelligence_item(db, item_id, actor=actor, notes=notes)
        if item:
            items.append(item)
    return items


def batch_undo_intelligence_reviews(db: Session, item_ids: list[int], actor: str, notes: str | None = None) -> list[IntelligenceItem]:
    existing = {
        item.id: item
        for item in db.scalars(select(IntelligenceItem).where(IntelligenceItem.id.in_(item_ids))).all()
    }
    invalid_ids = [
        item_id
        for item_id in item_ids
        if item_id not in existing
        or (existing[item_id].status in PUBLISHABLE_STATUSES and not existing[item_id].vulnerability_id)
    ]
    if invalid_ids:
        raise ValueError(f"Items are missing or already waiting for review: {invalid_ids}")
    items: list[IntelligenceItem] = []
    for item_id in item_ids:
        item = undo_intelligence_review(db, item_id, actor=actor, notes=notes)
        if item:
            items.append(item)
    return items


def list_review_actions(
    db: Session,
    *,
    target_type: str | None = None,
    target_id: int | None = None,
    actor: str | None = None,
    action: str | None = None,
    offset: int = 0,
    limit: int = 50,
) -> list[ReviewAction]:
    stmt = select(ReviewAction).order_by(ReviewAction.created_at.desc(), ReviewAction.id.desc())
    if target_type:
        stmt = stmt.where(ReviewAction.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(ReviewAction.target_id == target_id)
    if actor:
        stmt = stmt.where(ReviewAction.actor == actor)
    if action:
        stmt = stmt.where(ReviewAction.action == action)
    stmt = stmt.offset(offset).limit(limit)
    return list(db.scalars(stmt).all())


def count_review_actions(
    db: Session,
    *,
    target_type: str | None = None,
    target_id: int | None = None,
    actor: str | None = None,
    action: str | None = None,
) -> int:
    stmt = select(func.count(ReviewAction.id))
    if target_type:
        stmt = stmt.where(ReviewAction.target_type == target_type)
    if target_id is not None:
        stmt = stmt.where(ReviewAction.target_id == target_id)
    if actor:
        stmt = stmt.where(ReviewAction.actor == actor)
    if action:
        stmt = stmt.where(ReviewAction.action == action)
    return db.scalar(stmt) or 0


def list_intelligence_review_actions(db: Session, intel_item_id: int, limit: int = 50) -> list[ReviewAction]:
    candidate_ids = select(MergeCandidate.id).where(MergeCandidate.intelligence_item_id == intel_item_id)
    stmt = (
        select(ReviewAction)
        .where(
            or_(
                (
                    (ReviewAction.target_type == "intelligence_item")
                    & (ReviewAction.target_id == intel_item_id)
                ),
                (
                    (ReviewAction.target_type == "merge_candidate")
                    & ReviewAction.target_id.in_(candidate_ids)
                ),
            )
        )
        .order_by(ReviewAction.created_at.desc(), ReviewAction.id.desc())
        .limit(limit)
    )
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
        "undos": sum(1 for action in actions if action.action == "undo_review"),
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
    _repair_legacy_intelligence_statuses(db)
    for doc in db.scalars(select(CollectedDocument)).all():
        _ensure_intelligence_item_for_document(db, doc)

    total = db.scalar(select(func.count()).select_from(IntelligenceItem)) or 0
    reviewable = db.scalar(select(func.count()).select_from(IntelligenceItem).where(IntelligenceItem.status.in_(PUBLISHABLE_STATUSES))) or 0
    pending_review = db.scalar(select(func.count()).select_from(IntelligenceItem).where(IntelligenceItem.status == "pending_review")) or 0
    ignored = db.scalar(select(func.count()).select_from(IntelligenceItem).where(IntelligenceItem.status == "ignored")) or 0
    approved = db.scalar(select(func.count()).select_from(IntelligenceItem).where(IntelligenceItem.status == "approved")) or 0
    rejected = db.scalar(select(func.count()).select_from(IntelligenceItem).where(IntelligenceItem.status == "rejected")) or 0
    triaged = db.scalar(select(func.count()).select_from(IntelligenceItem).where(IntelligenceItem.status == "triaged")) or 0
    merge_candidates_pending = db.scalar(select(func.count()).select_from(MergeCandidate).where(MergeCandidate.status == "pending")) or 0

    high_risk_pending_review = 0
    pending_items = db.scalars(select(IntelligenceItem).where(IntelligenceItem.status == "pending_review")).all()
    for item in pending_items:
        extracted = _normalize_extracted_payload(dict(item.extracted_data or {}))
        severity = extracted.get("severity", "")
        score = extracted.get("score", 0)
        if severity in {"高危", "严重"} or score >= 80:
            high_risk_pending_review += 1

    return {
        "total": total,
        "reviewable": reviewable,
        "pending_review": pending_review,
        "ignored": ignored,
        "approved": approved,
        "rejected": rejected,
        "triaged": triaged,
        "high_risk_pending_review": high_risk_pending_review,
        "merge_candidates_pending": merge_candidates_pending,
    }
