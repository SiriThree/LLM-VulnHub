import asyncio
import hashlib
import json
import threading
import traceback
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

import feedparser
import httpx
from bs4 import BeautifulSoup
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.config import get_settings
from app.db.models import CollectedDocument, DataSource, IntelligenceItem, MergeCandidate, Task, Vulnerability
from app.db.session import SessionLocal
from app.schemas.collector import DataSourceCreate, DataSourceUpdate
from app.workflows.vuln_analysis_graph import analyze_text, get_analysis_job_snapshot

settings = get_settings()

TASK_STAGE_ORDER = [
    "queued",
    "fetching",
    "parsing",
    "ingesting",
    "queued_analysis",
    "filtering",
    "analyzing",
    "extracting",
    "deduplicating",
    "reviewing",
    "storing",
    "completed",
]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_source(db: Session, payload: DataSourceCreate) -> DataSource:
    source = DataSource(**payload.model_dump())
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def update_source(db: Session, source_id: int, payload: DataSourceUpdate) -> DataSource | None:
    source = db.get(DataSource, source_id)
    if not source:
        return None
    for key, value in payload.model_dump(exclude_unset=True).items():
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return source


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _intel_status(is_related: bool, confidence: float) -> str:
    if not is_related:
        return "rejected"
    if confidence >= 0.5:
        return "pending_review"
    return "triaged"


def _json_safe_vulnerability_snapshot(vulnerability: Vulnerability) -> dict[str, Any]:
    return {
        "id": vulnerability.id,
        "title": vulnerability.title,
        "vuln_type": vulnerability.vuln_type,
        "severity": vulnerability.severity,
        "score": vulnerability.score,
        "affected_component": vulnerability.affected_component,
        "description": vulnerability.description,
        "attack_method": vulnerability.attack_method,
        "impact": vulnerability.impact,
        "mitigation": vulnerability.mitigation,
        "source": vulnerability.source,
        "reference_url": vulnerability.reference_url,
        "source_url": vulnerability.source_url,
        "confidence": vulnerability.confidence,
        "status": vulnerability.status,
        "tags": [tag.name for tag in vulnerability.tags],
        "created_at": vulnerability.created_at.isoformat() if vulnerability.created_at else None,
        "updated_at": vulnerability.updated_at.isoformat() if vulnerability.updated_at else None,
    }


def _ensure_intelligence_item_for_document(
    db: Session,
    doc: CollectedDocument,
    *,
    source: DataSource | None = None,
    triage_category: str = "unknown",
    triage_reason: str = "",
    extracted_data: dict[str, Any] | None = None,
) -> IntelligenceItem:
    existing = db.scalar(select(IntelligenceItem).where(IntelligenceItem.collected_document_id == doc.id))
    if existing:
        return existing

    vulnerability_data: dict[str, Any] = {}
    if doc.vulnerability_id:
        vulnerability = db.get(Vulnerability, doc.vulnerability_id)
        if vulnerability:
            vulnerability_data = _json_safe_vulnerability_snapshot(vulnerability)

    item = IntelligenceItem(
        source_id=doc.source_id,
        collected_document_id=doc.id,
        vulnerability_id=doc.vulnerability_id,
        title=doc.title,
        url=doc.url,
        raw_text=doc.raw_text,
        normalized_text=doc.raw_text,
        content_hash=doc.content_hash,
        language="en" if doc.raw_text.isascii() else "unknown",
        triage_confidence=doc.confidence,
        triage_category=triage_category,
        triage_reason=triage_reason,
        extracted_data=extracted_data or vulnerability_data,
        status="approved" if doc.status == "stored" else "pending_review" if doc.is_ai_related else "rejected",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _empty_metrics() -> dict[str, int]:
    return {
        "discovered": 0,
        "processed": 0,
        "queued_analysis": 0,
        "analyzed": 0,
        "queued_review": 0,
        "notifications": 0,
        "saved": 0,
        "failed": 0,
        "duplicates": 0,
        "pending_review": 0,
        "ignored": 0,
    }


def _base_output(source_id: int | None, trigger: str) -> dict[str, Any]:
    return {
        "pipeline": "collector_v2",
        "trigger": trigger,
        "requested_source_id": source_id,
        "execution_mode": "pending",
        "queue_task_id": None,
        "attempt_count": 0,
        "max_attempts": 3,
        "dead_letter": False,
        "dead_letter_reason": None,
        "dead_letter_at": None,
        "started_at": None,
        "finished_at": None,
        "elapsed_seconds": None,
        "current_stage": "queued",
        "stage_history": [],
        "source_runs": [],
        "metrics": _empty_metrics(),
        "last_message": "Task queued.",
    }


def _base_analysis_output(document_id: int, source_id: int | None, trigger: str) -> dict[str, Any]:
    return {
        "pipeline": "analysis_v2",
        "trigger": trigger,
        "document_id": document_id,
        "source_id": source_id,
        "execution_mode": "pending",
        "queue_task_id": None,
        "attempt_count": 0,
        "max_attempts": 3,
        "dead_letter": False,
        "dead_letter_reason": None,
        "dead_letter_at": None,
        "started_at": None,
        "finished_at": None,
        "elapsed_seconds": None,
        "current_stage": "queued",
        "stage_history": [],
        "agent_summary": [],
        "last_message": "Analysis queued.",
    }


def _base_review_output(intel_item_id: int, analysis_job_id: int | None, trigger: str) -> dict[str, Any]:
    return {
        "pipeline": "review_helper_v1",
        "trigger": trigger,
        "intel_item_id": intel_item_id,
        "analysis_job_id": analysis_job_id,
        "execution_mode": "pending",
        "queue_task_id": None,
        "attempt_count": 0,
        "max_attempts": 3,
        "dead_letter": False,
        "dead_letter_reason": None,
        "dead_letter_at": None,
        "started_at": None,
        "finished_at": None,
        "elapsed_seconds": None,
        "current_stage": "queued",
        "stage_history": [],
        "review_packet": {},
        "last_message": "Review helper queued.",
    }


def _base_notification_output(event_type: str, trigger: str, payload: dict[str, Any]) -> dict[str, Any]:
    return {
        "pipeline": "notification_v1",
        "trigger": trigger,
        "event_type": event_type,
        "payload": payload,
        "execution_mode": "pending",
        "queue_task_id": None,
        "attempt_count": 0,
        "max_attempts": 3,
        "dead_letter": False,
        "dead_letter_reason": None,
        "dead_letter_at": None,
        "started_at": None,
        "finished_at": None,
        "elapsed_seconds": None,
        "current_stage": "queued",
        "stage_history": [],
        "notification": {},
        "last_message": "Notification queued.",
    }


def create_collection_task(db: Session, source_id: int | None, trigger: str = "manual") -> Task:
    task = Task(
        task_type="crawl",
        status="queued",
        input_data={"source_id": source_id, "trigger": trigger},
        output_data=_base_output(source_id, trigger),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def create_analysis_task(db: Session, document_id: int, source_id: int | None, trigger: str = "collector") -> Task:
    task = Task(
        task_type="analyze_document",
        status="queued",
        input_data={"document_id": document_id, "source_id": source_id, "trigger": trigger},
        output_data=_base_analysis_output(document_id, source_id, trigger),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def create_review_task(db: Session, intel_item_id: int, analysis_job_id: int | None, trigger: str = "analysis") -> Task:
    task = Task(
        task_type="review_helper",
        status="queued",
        input_data={"intel_item_id": intel_item_id, "analysis_job_id": analysis_job_id, "trigger": trigger},
        output_data=_base_review_output(intel_item_id, analysis_job_id, trigger),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def create_notification_task(db: Session, event_type: str, payload: dict[str, Any], trigger: str = "system") -> Task:
    task = Task(
        task_type="notification",
        status="queued",
        input_data={"event_type": event_type, "payload": payload, "trigger": trigger},
        output_data=_base_notification_output(event_type, trigger, payload),
    )
    db.add(task)
    db.commit()
    db.refresh(task)
    return task


def _merge_output(task: Task, db: Session, patch: dict[str, Any]) -> None:
    output = dict(task.output_data or {})
    output.update(patch)
    task.output_data = output
    db.add(task)
    db.commit()
    db.refresh(task)


def _mark_dead_letter_if_needed(task: Task, db: Session, reason: str | None = None) -> None:
    output = dict(task.output_data or {})
    attempt_count = int(output.get("attempt_count", 0) or 0)
    max_attempts = int(output.get("max_attempts", 0) or 0)
    if max_attempts > 0 and attempt_count >= max_attempts:
        output["dead_letter"] = True
        output["dead_letter_reason"] = reason or task.error_message or "Task reached the retry limit."
        output["dead_letter_at"] = utcnow().isoformat()
        task.output_data = output
        db.commit()
        db.refresh(task)


def _append_stage(task: Task, db: Session, stage: str, status: str, message: str, extra: dict[str, Any] | None = None) -> None:
    output = dict(task.output_data or {})
    history = list(output.get("stage_history", []))
    history.append(
        {
            "stage": stage,
            "status": status,
            "message": message,
            "timestamp": utcnow().isoformat(),
            **(extra or {}),
        }
    )
    output["stage_history"] = history
    output["current_stage"] = stage
    output["last_message"] = message
    task.output_data = output
    db.add(task)
    db.commit()
    db.refresh(task)


def _update_metrics(task: Task, db: Session, **delta: int) -> None:
    output = dict(task.output_data or {})
    metrics = {**_empty_metrics(), **output.get("metrics", {})}
    for key, value in delta.items():
        metrics[key] = metrics.get(key, 0) + value
    output["metrics"] = metrics
    task.output_data = output
    db.add(task)
    db.commit()
    db.refresh(task)


def _upsert_source_run(task: Task, db: Session, source: DataSource, patch: dict[str, Any]) -> None:
    output = dict(task.output_data or {})
    runs = list(output.get("source_runs", []))
    existing = next((item for item in runs if item.get("source_id") == source.id), None)
    if existing is None:
        existing = {
            "source_id": source.id,
            "source_name": source.name,
            "source_type": source.source_type,
            "url": source.url,
            "status": "queued",
            "stage": "queued",
            "discovered": 0,
            "processed": 0,
            "queued_analysis": 0,
            "saved": 0,
            "duplicates": 0,
            "pending_review": 0,
            "ignored": 0,
            "failed": 0,
            "events": [],
        }
        runs.append(existing)
    for key, value in patch.items():
        if key == "event":
            existing.setdefault("events", []).append(
                {
                    "timestamp": utcnow().isoformat(),
                    **value,
                }
            )
        else:
            existing[key] = value
    output["source_runs"] = runs
    task.output_data = output
    db.add(task)
    db.commit()
    db.refresh(task)


async def fetch_candidates(source: DataSource) -> list[dict[str, str]]:
    if source.source_type == "local_file":
        path = Path(source.url)
        if not path.exists() and source.url.startswith("../data/"):
            path = Path("../data") / Path(source.url).name
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("items", [])
        return [
            {
                "title": item.get("title", "local item"),
                "url": item.get("url", source.url),
                "raw_text": item.get("raw_text") or item.get("text", ""),
            }
            for item in data
        ]

    headers = {
        "User-Agent": "LLM-VulnHub/0.1",
        "Accept": "application/json, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, text/html;q=0.7",
    }
    if settings.github_token:
        headers["Authorization"] = f"Bearer {settings.github_token}"

    async with httpx.AsyncClient(timeout=30, follow_redirects=True, headers=headers) as client:
        resp = await client.get(source.url)
        if source.source_type == "github" and resp.status_code == 403:
            if not settings.github_token:
                raise RuntimeError("GitHub advisory source hit the anonymous rate limit. Set GITHUB_TOKEN to enable stable collection.")
            raise RuntimeError(f"GitHub advisory source request failed with status {resp.status_code}.")
        resp.raise_for_status()
        content_type = resp.headers.get("content-type", "")

        if source.source_type == "github" or "api.github.com" in source.url:
            advisories = resp.json()
            if isinstance(advisories, dict):
                advisories = advisories.get("items", [])
            candidates = []
            for item in advisories:
                summary = item.get("summary", "")
                description = item.get("description", "")
                severity = item.get("severity", "")
                identifier = item.get("cve_id") or item.get("ghsa_id") or ""
                title = f"{identifier} {summary}".strip() if identifier else summary or "github advisory"
                refs = " ".join(
                    ref.get("url", "") if isinstance(ref, dict) else str(ref)
                    for ref in item.get("references", [])[:5]
                )
                raw_text = " ".join(
                    part
                    for part in [summary, description, f"severity: {severity}" if severity else "", item.get("html_url", ""), refs]
                    if part
                )
                candidates.append(
                    {
                        "title": title[:300],
                        "url": item.get("html_url") or item.get("url") or source.url,
                        "raw_text": raw_text[:16000],
                    }
                )
            return candidates

        body = resp.text

    if source.source_type == "rss" or "atom" in content_type or source.url.endswith(".atom"):
        feed = feedparser.parse(body)
        return [
            {
                "title": entry.get("title", "rss item"),
                "url": entry.get("link", source.url),
                "raw_text": " ".join([entry.get("title", ""), entry.get("summary", "")]),
            }
            for entry in feed.entries[:30]
        ]

    soup = BeautifulSoup(body, "html.parser")
    for tag in soup(["script", "style", "nav", "footer"]):
        tag.decompose()
    title = soup.title.text.strip() if soup.title else source.name
    text = " ".join(soup.get_text(" ").split())
    return [{"title": title, "url": source.url, "raw_text": text[:12000]}]


def dispatch_collection_task(task_id: int) -> None:
    db = SessionLocal()
    try:
        from app.worker import collect_task

        async_result = collect_task.apply_async(args=[task_id], queue="ingestion")
        task = db.get(Task, task_id)
        if task:
            _merge_output(
                task,
                db,
                {
                    "execution_mode": "celery-worker",
                    "queue_name": "ingestion",
                    "queue_task_id": async_result.id,
                    "last_message": "Task dispatched to Celery worker.",
                },
            )
        return
    except Exception:
        task = db.get(Task, task_id)
        if task:
            _merge_output(
                task,
                db,
                {
                    "execution_mode": "thread-fallback",
                    "queue_name": "local-thread",
                    "queue_task_id": None,
                    "last_message": "Celery unavailable, running with local background worker.",
                },
            )
        thread = threading.Thread(target=lambda: asyncio.run(run_collection_task(task_id)), daemon=True)
        thread.start()
    finally:
        db.close()


def dispatch_analysis_task(task_id: int) -> None:
    db = SessionLocal()
    try:
        from app.worker import analyze_document_task

        async_result = analyze_document_task.apply_async(args=[task_id], queue="analysis")
        task = db.get(Task, task_id)
        if task:
            _merge_output(
                task,
                db,
                {
                    "execution_mode": "celery-worker",
                    "queue_name": "analysis",
                    "queue_task_id": async_result.id,
                    "last_message": "Analysis task dispatched to Celery worker.",
                },
            )
        return
    except Exception:
        task = db.get(Task, task_id)
        if task:
            _merge_output(
                task,
                db,
                {
                    "execution_mode": "thread-fallback",
                    "queue_name": "local-thread",
                    "queue_task_id": None,
                    "last_message": "Celery unavailable, running analysis with local background worker.",
                },
            )
        thread = threading.Thread(target=lambda: asyncio.run(run_analysis_task(task_id)), daemon=True)
        thread.start()
    finally:
        db.close()


def dispatch_review_task(task_id: int) -> None:
    db = SessionLocal()
    try:
        from app.worker import review_helper_task

        async_result = review_helper_task.apply_async(args=[task_id], queue="review")
        task = db.get(Task, task_id)
        if task:
            _merge_output(task, db, {"execution_mode": "celery-worker", "queue_name": "review", "queue_task_id": async_result.id, "last_message": "Review task dispatched to Celery worker."})
        return
    except Exception:
        task = db.get(Task, task_id)
        if task:
            _merge_output(task, db, {"execution_mode": "thread-fallback", "queue_name": "local-thread", "queue_task_id": None, "last_message": "Celery unavailable, running review helper locally."})
        thread = threading.Thread(target=lambda: asyncio.run(run_review_task(task_id)), daemon=True)
        thread.start()
    finally:
        db.close()


def dispatch_notification_task(task_id: int) -> None:
    db = SessionLocal()
    try:
        from app.worker import notification_task

        async_result = notification_task.apply_async(args=[task_id], queue="notification")
        task = db.get(Task, task_id)
        if task:
            _merge_output(task, db, {"execution_mode": "celery-worker", "queue_name": "notification", "queue_task_id": async_result.id, "last_message": "Notification task dispatched to Celery worker."})
        return
    except Exception:
        task = db.get(Task, task_id)
        if task:
            _merge_output(task, db, {"execution_mode": "thread-fallback", "queue_name": "local-thread", "queue_task_id": None, "last_message": "Celery unavailable, running notification locally."})
        thread = threading.Thread(target=lambda: asyncio.run(run_notification_task(task_id)), daemon=True)
        thread.start()
    finally:
        db.close()


async def run_collection_task(task_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if not task:
            return {"task_id": task_id, "status": "missing"}
        return await _run_collection(db, task)
    finally:
        db.close()


async def run_analysis_task(task_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if not task:
            return {"task_id": task_id, "status": "missing"}
        return await _run_analysis(db, task)
    finally:
        db.close()


async def run_review_task(task_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if not task:
            return {"task_id": task_id, "status": "missing"}
        return await _run_review(db, task)
    finally:
        db.close()


async def run_notification_task(task_id: int) -> dict[str, Any]:
    db = SessionLocal()
    try:
        task = db.get(Task, task_id)
        if not task:
            return {"task_id": task_id, "status": "missing"}
        return await _run_notification(db, task)
    finally:
        db.close()


async def _run_collection(db: Session, task: Task) -> dict[str, Any]:
    source_id = (task.input_data or {}).get("source_id")
    output = dict(task.output_data or {})
    attempt_count = int(output.get("attempt_count", 0)) + 1
    started_at = utcnow()
    task.status = "running"
    task.error_message = None
    output["attempt_count"] = attempt_count
    output["started_at"] = started_at.isoformat()
    output["finished_at"] = None
    output["elapsed_seconds"] = None
    task.output_data = output
    db.commit()
    db.refresh(task)
    _append_stage(task, db, "fetching", "running", "Starting source discovery.")

    try:
        stmt = select(DataSource).where(DataSource.enabled.is_(True))
        if source_id:
            stmt = stmt.where(DataSource.id == source_id)
        sources = db.scalars(stmt).all()
        _merge_output(task, db, {"source_total": len(sources)})

        for source in sources:
            await _process_source(db, task, source)

        task.status = "success"
        _append_stage(task, db, "completed", "success", "Collection pipeline completed.")
    except Exception as exc:
        task.status = "failed"
        task.error_message = str(exc)
        _append_stage(task, db, "completed", "failed", f"Collection pipeline failed: {exc}", {"traceback": traceback.format_exc(limit=3)})
        _mark_dead_letter_if_needed(task, db, str(exc))
    finally:
        finished_at = utcnow()
        _merge_output(
            task,
            db,
            {
                "finished_at": finished_at.isoformat(),
                "elapsed_seconds": round((finished_at - started_at).total_seconds(), 2),
            },
        )
        db.commit()
        db.refresh(task)

    return {
        "task_id": task.id,
        "status": task.status,
        "metrics": (task.output_data or {}).get("metrics", {}),
        "current_stage": (task.output_data or {}).get("current_stage", "completed"),
    }


async def _run_analysis(db: Session, task: Task) -> dict[str, Any]:
    output = dict(task.output_data or {})
    attempt_count = int(output.get("attempt_count", 0)) + 1
    started_at = utcnow()
    task.status = "running"
    task.error_message = None
    output["attempt_count"] = attempt_count
    output["started_at"] = started_at.isoformat()
    output["finished_at"] = None
    output["elapsed_seconds"] = None
    output["current_stage"] = "analyzing"
    task.output_data = output
    db.commit()
    db.refresh(task)

    document_id = int((task.input_data or {}).get("document_id"))
    doc = db.get(CollectedDocument, document_id)
    if not doc:
        task.status = "failed"
        task.error_message = "document not found"
        _mark_dead_letter_if_needed(task, db, "document not found")
        db.commit()
        return {"task_id": task.id, "status": task.status}

    _append_stage(task, db, "analyzing", "running", f"Analyzing document #{doc.id}.", {"document_id": doc.id})

    try:
        state = await analyze_text(db, doc.raw_text, doc.url, save=False)
        rel = state.get("relevance", {})
        is_related = bool(rel.get("is_ai_vulnerability"))
        confidence = float(rel.get("confidence", 0.0))

        status = "ignored"
        if not is_related:
            status = "ignored"
        elif confidence < 0.7:
            status = "pending_review"
        else:
            status = "pending_review"

        doc.is_ai_related = is_related
        doc.confidence = confidence
        doc.status = status
        db.commit()
        db.refresh(doc)

        intel_item = db.scalar(select(IntelligenceItem).where(IntelligenceItem.collected_document_id == doc.id))
        if not intel_item:
            intel_item = IntelligenceItem(
                source_id=doc.source_id,
                collected_document_id=doc.id,
                vulnerability_id=doc.vulnerability_id,
                title=doc.title,
                url=doc.url,
                raw_text=doc.raw_text,
                normalized_text=state.get("cleaned_text", doc.raw_text),
                content_hash=doc.content_hash,
                language="en" if doc.raw_text.isascii() else "unknown",
                triage_confidence=confidence,
                triage_category=str(rel.get("related_area", "unknown")),
                triage_reason=str(rel.get("reason", "")),
                extracted_data=dict(state.get("extracted_fields", {})),
                status=_intel_status(is_related, confidence),
            )
            db.add(intel_item)
            db.commit()
            db.refresh(intel_item)
        else:
            intel_item.triage_confidence = confidence
            intel_item.triage_category = str(rel.get("related_area", "unknown"))
            intel_item.triage_reason = str(rel.get("reason", ""))
            intel_item.normalized_text = state.get("cleaned_text", doc.raw_text)
            intel_item.extracted_data = dict(state.get("extracted_fields", {}))
            intel_item.status = _intel_status(is_related, confidence)
            db.commit()
            db.refresh(intel_item)

        existing_candidates = db.scalars(select(MergeCandidate).where(MergeCandidate.intelligence_item_id == intel_item.id)).all()
        for candidate in existing_candidates:
            db.delete(candidate)
        db.commit()

        for match in state.get("similar", [])[:3]:
            vulnerability_payload = match.get("vulnerability")
            score = float(match.get("similarity", match.get("score", 0.0)))
            if not vulnerability_payload or not vulnerability_payload.get("id"):
                continue
            db.add(
                MergeCandidate(
                    intelligence_item_id=intel_item.id,
                    candidate_vulnerability_id=int(vulnerability_payload["id"]),
                    merge_score=score,
                    merge_reason=(
                        "Similarity candidate based on semantic retrieval. "
                        f"Matched {vulnerability_payload.get('title', 'existing vulnerability')}."
                    ),
                    status="pending",
                )
            )
        db.commit()

        output = dict(task.output_data or {})
        output["agent_summary"] = [
            {
                "agent_name": item.get("agent_name"),
                "stage_name": item.get("stage_name"),
                "status": item.get("status"),
                "retry_count": item.get("retry_count"),
                "latency_ms": item.get("latency_ms"),
            }
            for item in (get_analysis_job_snapshot(db, state["analysis_job_id"]) or {}).get("agent_executions", [])
        ]
        output["analysis_job_id"] = state.get("analysis_job_id")
        output["intel_item_id"] = intel_item.id
        output["document_status"] = doc.status
        task.output_data = output
        task.status = "success"
        _append_stage(task, db, "completed", "success", f"Analysis completed for document #{doc.id}.", {"document_id": doc.id, "intel_item_id": intel_item.id})

        if doc.status == "pending_review":
            review_task = create_review_task(db, intel_item.id, state.get("analysis_job_id"), trigger="analysis")
            dispatch_review_task(review_task.id)
            _update_metrics(task, db, queued_review=1)
            if state.get("severity") in {"高危", "严重"}:
                notification_task = create_notification_task(
                    db,
                    "high_risk_pending_review",
                    {
                        "document_id": doc.id,
                        "intel_item_id": intel_item.id,
                        "analysis_job_id": state.get("analysis_job_id"),
                        "title": intel_item.title,
                        "severity": state.get("severity"),
                        "score": state.get("score"),
                    },
                    trigger="analysis",
                )
                dispatch_notification_task(notification_task.id)
                _update_metrics(task, db, notifications=1)
    except Exception as exc:
        task.status = "failed"
        task.error_message = str(exc)
        _append_stage(task, db, "completed", "failed", f"Analysis failed: {exc}", {"document_id": doc.id, "traceback": traceback.format_exc(limit=3)})
        _mark_dead_letter_if_needed(task, db, str(exc))
    finally:
        finished_at = utcnow()
        _merge_output(
            task,
            db,
            {
                "finished_at": finished_at.isoformat(),
                "elapsed_seconds": round((finished_at - started_at).total_seconds(), 2),
            },
        )
        db.commit()
        db.refresh(task)

    return {
        "task_id": task.id,
        "status": task.status,
        "current_stage": (task.output_data or {}).get("current_stage", "completed"),
    }


async def _run_review(db: Session, task: Task) -> dict[str, Any]:
    output = dict(task.output_data or {})
    attempt_count = int(output.get("attempt_count", 0)) + 1
    started_at = utcnow()
    task.status = "running"
    task.error_message = None
    output["attempt_count"] = attempt_count
    output["started_at"] = started_at.isoformat()
    output["current_stage"] = "reviewing"
    task.output_data = output
    db.commit()
    db.refresh(task)

    intel_item_id = int((task.input_data or {}).get("intel_item_id"))
    intel_item = db.get(IntelligenceItem, intel_item_id)
    if not intel_item:
        task.status = "failed"
        task.error_message = "intel item not found"
        _mark_dead_letter_if_needed(task, db, "intel item not found")
        db.commit()
        return {"task_id": task.id, "status": task.status}

    merge_candidates = db.scalars(select(MergeCandidate).where(MergeCandidate.intelligence_item_id == intel_item.id)).all()
    review_packet = {
        "intel_item_id": intel_item.id,
        "title": intel_item.title,
        "status": intel_item.status,
        "triage_confidence": intel_item.triage_confidence,
        "triage_category": intel_item.triage_category,
        "triage_reason": intel_item.triage_reason,
        "merge_candidate_count": len(merge_candidates),
        "top_merge_scores": [candidate.merge_score for candidate in merge_candidates[:3]],
        "suggested_action": "merge_or_publish" if merge_candidates else "manual_publish_review",
    }

    _append_stage(task, db, "reviewing", "running", f"Preparing review packet for intelligence item #{intel_item.id}.", {"intel_item_id": intel_item.id})
    task.status = "success"
    _merge_output(task, db, {"review_packet": review_packet, "current_stage": "completed", "last_message": "Review helper completed."})
    _append_stage(task, db, "completed", "success", f"Review packet ready for intelligence item #{intel_item.id}.", {"intel_item_id": intel_item.id})
    finished_at = utcnow()
    _merge_output(task, db, {"finished_at": finished_at.isoformat(), "elapsed_seconds": round((finished_at - started_at).total_seconds(), 2)})
    task.status = "success"
    db.commit()
    db.refresh(task)
    return {"task_id": task.id, "status": task.status, "review_packet": review_packet}


async def _run_notification(db: Session, task: Task) -> dict[str, Any]:
    output = dict(task.output_data or {})
    attempt_count = int(output.get("attempt_count", 0)) + 1
    started_at = utcnow()
    task.status = "running"
    task.error_message = None
    output["attempt_count"] = attempt_count
    output["started_at"] = started_at.isoformat()
    output["current_stage"] = "notifying"
    task.output_data = output
    db.commit()
    db.refresh(task)

    payload = dict((task.input_data or {}).get("payload", {}))
    event_type = str((task.input_data or {}).get("event_type", "generic"))
    notification = {
        "event_type": event_type,
        "channel": "task-center",
        "severity": payload.get("severity", "info"),
        "title": payload.get("title") or event_type,
        "message": payload.get("message") or f"Notification generated for {event_type}.",
        "payload": payload,
        "notified_at": utcnow().isoformat(),
    }

    _append_stage(task, db, "notifying", "running", f"Creating notification for {event_type}.", {"event_type": event_type})
    task.status = "success"
    _merge_output(task, db, {"notification": notification, "current_stage": "completed", "last_message": "Notification generated."})
    _append_stage(task, db, "completed", "success", f"Notification completed for {event_type}.", {"event_type": event_type})
    finished_at = utcnow()
    _merge_output(task, db, {"finished_at": finished_at.isoformat(), "elapsed_seconds": round((finished_at - started_at).total_seconds(), 2)})
    db.commit()
    db.refresh(task)
    return {"task_id": task.id, "status": task.status, "notification": notification}


async def _process_source(db: Session, task: Task, source: DataSource) -> None:
    started_at = utcnow()
    _upsert_source_run(
        task,
        db,
        source,
        {
            "status": "running",
            "stage": "fetching",
            "started_at": utcnow().isoformat(),
            "event": {"stage": "fetching", "message": "Fetching source content."},
        },
    )
    try:
        candidates = await fetch_candidates(source)
        _update_metrics(task, db, discovered=len(candidates))
        _upsert_source_run(
            task,
            db,
            source,
            {
                "discovered": len(candidates),
                "stage": "parsing",
                "event": {"stage": "parsing", "message": f"Loaded {len(candidates)} candidate items."},
            },
        )
        _append_stage(task, db, "parsing", "running", f"Parsing {source.name}.", {"source_id": source.id})

        for item in candidates:
            await _process_candidate(db, task, source, item)

        source.last_collected_at = utcnow()
        db.commit()
        db.refresh(source)
        source_run = next(
            (
                run
                for run in (task.output_data or {}).get("source_runs", [])
                if run.get("source_id") == source.id
            ),
            None,
        )
        _upsert_source_run(
            task,
            db,
            source,
            {
                "status": "success",
                "stage": "completed",
                "finished_at": utcnow().isoformat(),
                "elapsed_seconds": round((utcnow() - started_at).total_seconds(), 2),
                "event": {
                    "stage": "completed",
                    "message": f"Source finished with {source_run.get('saved', 0) if source_run else 0} stored items.",
                },
            },
        )
    except Exception as exc:
        _update_metrics(task, db, failed=1)
        _update_metrics(task, db, notifications=1)
        notification_task = create_notification_task(
            db,
            "source_failure",
            {
                "source_id": source.id,
                "title": source.name,
                "severity": "warning",
                "message": str(exc),
                "url": source.url,
            },
            trigger="collector",
        )
        dispatch_notification_task(notification_task.id)
        _upsert_source_run(
            task,
            db,
            source,
            {
                "status": "failed",
                "stage": "failed",
                "failed": 1,
                "finished_at": utcnow().isoformat(),
                "elapsed_seconds": round((utcnow() - started_at).total_seconds(), 2),
                "error": str(exc),
                "event": {"stage": "failed", "message": str(exc)},
            },
        )


async def _process_candidate(db: Session, task: Task, source: DataSource, item: dict[str, str]) -> None:
    raw_text = item.get("raw_text", "").strip()
    if not raw_text:
        return

    title = item.get("title", "untitled")[:300]
    doc_hash = content_hash(raw_text)

    _append_stage(task, db, "ingesting", "running", f"Ingesting {title}.", {"source_id": source.id})
    existing = db.scalar(select(CollectedDocument).where(CollectedDocument.content_hash == doc_hash))
    if existing:
        _ensure_intelligence_item_for_document(db, existing, source=source)
        _update_metrics(task, db, duplicates=1)
        _upsert_source_run(
            task,
            db,
            source,
            {
                "duplicates": next(
                    (run.get("duplicates", 0) + 1 for run in (task.output_data or {}).get("source_runs", []) if run.get("source_id") == source.id),
                    1,
                ),
                "stage": "deduplicating",
                "event": {"stage": "deduplicating", "message": f"Duplicate skipped: {title}"},
            },
        )
        return

    doc = CollectedDocument(
        source_id=source.id,
        title=title,
        url=item.get("url"),
        raw_text=raw_text,
        content_hash=doc_hash,
        is_ai_related=False,
        confidence=0.0,
        status="queued_analysis",
        vulnerability_id=None,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    analysis_task = create_analysis_task(db, doc.id, source.id, trigger="collector")
    dispatch_analysis_task(analysis_task.id)
    _update_metrics(db=db, task=task, processed=1, queued_analysis=1)

    current_run = next(
        (run for run in (task.output_data or {}).get("source_runs", []) if run.get("source_id") == source.id),
        None,
    )
    _upsert_source_run(
        task,
        db,
        source,
        {
            "processed": (current_run or {}).get("processed", 0) + 1,
            "queued_analysis": (current_run or {}).get("queued_analysis", 0) + 1,
            "stage": "queued_analysis",
            "event": {
                "stage": "queued_analysis",
                "message": f"{title} queued for analysis",
                "document_id": doc.id,
                "analysis_task_id": analysis_task.id,
            },
        },
    )


async def approve_document(db: Session, doc_id: int) -> CollectedDocument | None:
    doc = db.get(CollectedDocument, doc_id)
    if not doc:
        return None
    state = await analyze_text(db, doc.raw_text, doc.url, save=True)
    doc.vulnerability_id = state.get("vulnerability_id")
    doc.status = "stored"
    doc.is_ai_related = True
    intel_items = db.scalars(select(IntelligenceItem).where(IntelligenceItem.collected_document_id == doc.id)).all()
    for intel_item in intel_items:
        intel_item.vulnerability_id = doc.vulnerability_id
        intel_item.status = "approved"
    db.commit()
    db.refresh(doc)
    return doc
