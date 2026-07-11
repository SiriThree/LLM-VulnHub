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
from app.db.models import CollectedDocument, DataSource, Task
from app.db.session import SessionLocal
from app.schemas.collector import DataSourceCreate, DataSourceUpdate
from app.workflows.vuln_analysis_graph import analyze_text

settings = get_settings()

TASK_STAGE_ORDER = [
    "queued",
    "fetching",
    "parsing",
    "filtering",
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


def _empty_metrics() -> dict[str, int]:
    return {
        "discovered": 0,
        "processed": 0,
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
        "started_at": None,
        "finished_at": None,
        "elapsed_seconds": None,
        "current_stage": "queued",
        "stage_history": [],
        "source_runs": [],
        "metrics": _empty_metrics(),
        "last_message": "Task queued.",
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


def _merge_output(task: Task, db: Session, patch: dict[str, Any]) -> None:
    output = dict(task.output_data or {})
    output.update(patch)
    task.output_data = output
    db.add(task)
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

        async_result = collect_task.delay(task_id)
        task = db.get(Task, task_id)
        if task:
            _merge_output(
                task,
                db,
                {
                    "execution_mode": "celery-worker",
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
                    "queue_task_id": None,
                    "last_message": "Celery unavailable, running with local background worker.",
                },
            )
        thread = threading.Thread(target=lambda: asyncio.run(run_collection_task(task_id)), daemon=True)
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

    _append_stage(task, db, "filtering", "running", f"Filtering {title}.", {"source_id": source.id})
    existing = db.scalar(select(CollectedDocument).where(CollectedDocument.content_hash == doc_hash))
    if existing:
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

    state = await analyze_text(db, raw_text, item.get("url"), save=False)
    rel = state.get("relevance", {})
    is_related = bool(rel.get("is_ai_vulnerability"))
    confidence = float(rel.get("confidence", 0.0))

    _append_stage(task, db, "extracting", "running", f"Extracting structured fields from {title}.", {"source_id": source.id})

    status = "ignored"
    vulnerability_id = None
    metric_delta = {"processed": 1}
    if not is_related:
        metric_delta["ignored"] = 1
        status = "ignored"
    elif confidence < 0.7:
        metric_delta["pending_review"] = 1
        status = "pending_review"
    else:
        _append_stage(task, db, "storing", "running", f"Storing validated vulnerability for {title}.", {"source_id": source.id})
        stored_state = await analyze_text(db, raw_text, item.get("url"), save=True)
        vulnerability_id = stored_state.get("vulnerability_id")
        metric_delta["saved"] = 1
        status = "stored"

    doc = CollectedDocument(
        source_id=source.id,
        title=title,
        url=item.get("url"),
        raw_text=raw_text,
        content_hash=doc_hash,
        is_ai_related=is_related,
        confidence=confidence,
        status=status,
        vulnerability_id=vulnerability_id,
    )
    db.add(doc)
    db.commit()
    db.refresh(doc)
    _update_metrics(db=db, task=task, **metric_delta)

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
            "saved": (current_run or {}).get("saved", 0) + (1 if status == "stored" else 0),
            "pending_review": (current_run or {}).get("pending_review", 0) + (1 if status == "pending_review" else 0),
            "ignored": (current_run or {}).get("ignored", 0) + (1 if status == "ignored" else 0),
            "stage": "reviewing" if status == "pending_review" else "storing" if status == "stored" else "filtering",
            "event": {
                "stage": status,
                "message": f"{title} -> {status}",
                "document_id": doc.id,
                "confidence": confidence,
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
    db.commit()
    db.refresh(doc)
    return doc
