import asyncio
from copy import deepcopy
import hashlib
import json
import threading
import traceback
from datetime import datetime, timezone
from typing import Any

import feedparser
import httpx
from sqlalchemy import select
from sqlalchemy.orm import Session
from sqlalchemy.orm.attributes import flag_modified

from app.core.config import get_settings
from app.core.input_security import (
    MAX_SOURCE_RESPONSE_BYTES,
    MAX_UNTRUSTED_TEXT_CHARS,
    InputSecurityError,
    resolve_local_source_path,
    safe_http_get,
    sanitize_html_text,
    sanitize_plain_text,
    validate_source_location,
)
from app.db.models import CollectedDocument, DataSource, IntelligenceItem, MergeCandidate, Task, Vulnerability
from app.db.session import SessionLocal
from app.schemas.collector import DataSourceCreate, DataSourceUpdate
from app.schemas.vulnerability import normalize_confidence_value
from app.services.provenance_service import build_source_health
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

AI_CONTEXT_TERMS = {
    "llm",
    "large language model",
    "large-language-model",
    "prompt",
    "prompt injection",
    "rag",
    "agent",
    "ai agent",
    "langchain",
    "llamaindex",
    "llama-index",
    "autogen",
    "crewai",
    "haystack",
    "mcp",
    "model context protocol",
    "tool calling",
    "function calling",
    "model context",
    "embedding",
    "vector database",
    "vector store",
    "inference",
    "transformers",
    "hugging face",
    "huggingface",
    "vllm",
    "ollama",
    "open-webui",
    "gradio",
    "ray serve",
    "chroma",
    "chromadb",
    "milvus",
    "weaviate",
    "qdrant",
}

SECURITY_SIGNAL_TERMS = {
    "cve-",
    "ghsa-",
    "vulnerability",
    "advisory",
    "security issue",
    "security advisory",
    "prompt injection",
    "indirect prompt injection",
    "jailbreak",
    "system prompt leakage",
    "data leakage",
    "data exposure",
    "secret leakage",
    "unauthorized",
    "permission bypass",
    "authorization bypass",
    "supply chain",
    "ssrf",
    "rce",
    "sql injection",
    "path traversal",
    "cross-tenant",
    "privilege escalation",
    "tool abuse",
    "model poisoning",
    "cypher injection",
}

LLM_COMPONENT_TERMS = {
    "langchain",
    "llamaindex",
    "llama-index",
    "llama_index",
    "autogen",
    "crewai",
    "haystack",
    "transformers",
    "huggingface",
    "hugging face",
    "vllm",
    "ollama",
    "open-webui",
    "gradio",
    "ray",
    "ray serve",
    "mcp",
    "model context protocol",
    "chroma",
    "chromadb",
    "milvus",
    "weaviate",
    "qdrant",
    "n8n-mcp",
}

NOISE_SIGNAL_TERMS = {
    "release notes",
    "release v",
    "changelog",
    "launches",
    "brings",
    "announces",
    "newsroom",
    "news",
    "improving",
    "getting started",
    "one click",
    "analytics",
    "spend controls",
    "partnership",
    "case study",
    "customer story",
    "webinar",
    "documentation",
    "docs",
    "how to",
    "tutorial",
    "benchmark",
    "profiling",
    "evaluation",
    "conference",
    "native-speed",
    "foundation managed compute",
    "sagemaker studio",
    "employees",
}


def _normalize_for_match(value: str) -> str:
    return " ".join((value or "").replace("\r", " ").replace("\n", " ").lower().split())


def _prefilter_candidate(source: DataSource, item: dict[str, str]) -> tuple[bool, str]:
    title = _normalize_for_match(item.get("title", ""))
    raw_text = _normalize_for_match(item.get("raw_text", ""))
    combined = f"{title}\n{raw_text[:4000]}"

    ai_hit = any(term in combined for term in AI_CONTEXT_TERMS)
    component_hit = any(term in combined for term in LLM_COMPONENT_TERMS)
    security_hit = any(term in combined for term in SECURITY_SIGNAL_TERMS)
    noise_hit = any(term in title for term in NOISE_SIGNAL_TERMS)

    if not ai_hit and not component_hit:
        return False, "Missing LLM/RAG/Agent security context."
    if source.source_type == "github" and not component_hit and not ai_hit:
        return False, "Generic GitHub advisory without LLM component signal."
    if not security_hit:
        return False, "Missing explicit security or vulnerability signal."
    if noise_hit and "security" not in title and "advisory" not in title and "vulnerability" not in title:
        return False, "Looks like product/news/release content rather than vulnerability intelligence."
    return True, "passed"


def get_collector_overview(db: Session) -> dict[str, Any]:
    sources = db.scalars(select(DataSource).order_by(DataSource.created_at.desc())).all()
    docs = db.scalars(select(CollectedDocument).order_by(CollectedDocument.collected_at.desc())).all()
    tasks = db.scalars(select(Task).order_by(Task.created_at.desc())).all()

    source_metrics = {
        "total": len(sources),
        "enabled": sum(1 for source in sources if source.enabled),
        "rss": sum(1 for source in sources if source.source_type == "rss"),
        "github": sum(1 for source in sources if source.source_type == "github"),
        "web": sum(1 for source in sources if source.source_type == "web"),
        "local_file": sum(1 for source in sources if source.source_type == "local_file"),
    }

    document_metrics = {
        "total": len(docs),
        "queued_analysis": sum(1 for doc in docs if doc.status == "queued_analysis"),
        "pending_review": sum(1 for doc in docs if doc.status == "pending_review"),
        "stored": sum(1 for doc in docs if doc.status == "stored"),
        "ignored": sum(1 for doc in docs if doc.status == "ignored"),
        "ai_related": sum(1 for doc in docs if doc.is_ai_related),
    }

    queue_metrics = {
        "crawl_running": sum(1 for task in tasks if task.task_type == "crawl" and task.status in {"queued", "running"}),
        "analysis_running": sum(1 for task in tasks if task.task_type == "analyze_document" and task.status in {"queued", "running"}),
        "review_running": sum(1 for task in tasks if task.task_type == "review_helper" and task.status in {"queued", "running"}),
        "crawl_failed": sum(1 for task in tasks if task.task_type == "crawl" and task.status == "failed"),
    }

    recent_runs: list[dict[str, Any]] = []
    crawl_tasks = [task for task in tasks if task.task_type == "crawl"]
    for task in crawl_tasks[:12]:
        for run in list((task.output_data or {}).get("source_runs", []))[:4]:
            recent_runs.append(
                {
                    "task_id": task.id,
                    "source_id": run.get("source_id"),
                    "source_name": str(run.get("source_name") or "unknown source"),
                    "source_type": str(run.get("source_type") or "unknown"),
                    "status": str(run.get("status") or task.status),
                    "stage": str(run.get("stage") or (task.output_data or {}).get("current_stage") or "queued"),
                    "discovered": int(run.get("discovered", 0) or 0),
                    "prefilter_passed": int(run.get("prefilter_passed", 0) or 0),
                    "processed": int(run.get("processed", 0) or 0),
                    "queued_analysis": int(run.get("queued_analysis", 0) or 0),
                    "analyzed": int(run.get("analyzed", 0) or 0),
                    "ai_related": int(run.get("ai_related", 0) or 0),
                    "saved": int(run.get("saved", 0) or 0),
                    "duplicates": int(run.get("duplicates", 0) or 0),
                    "pending_review": int(run.get("pending_review", 0) or 0),
                    "ignored": int(run.get("ignored", 0) or 0),
                    "failed": int(run.get("failed", 0) or 0),
                    "started_at": run.get("started_at"),
                    "finished_at": run.get("finished_at"),
                    "elapsed_seconds": run.get("elapsed_seconds"),
                    "error": run.get("error"),
                }
            )
    recent_runs = recent_runs[:12]

    pending_documents = [
        doc
        for doc in docs
        if doc.status in {"queued_analysis", "pending_review"}
    ][:10]
    recent_documents = docs[:10]
    source_health = [build_source_health(source, docs, tasks) for source in sources]
    source_health.sort(key=lambda item: (item["trust_score"], item["documents_total"], item["source_id"]), reverse=True)

    return {
        "source_metrics": source_metrics,
        "document_metrics": document_metrics,
        "queue_metrics": queue_metrics,
        "source_health": source_health,
        "recent_runs": recent_runs,
        "pending_documents": pending_documents,
        "recent_documents": recent_documents,
    }


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def create_source(db: Session, payload: DataSourceCreate) -> DataSource:
    data = payload.model_dump()
    data["url"] = validate_source_location(data["source_type"], data["url"])
    source = DataSource(**data)
    db.add(source)
    db.commit()
    db.refresh(source)
    return source


def update_source(db: Session, source_id: int, payload: DataSourceUpdate) -> DataSource | None:
    source = db.get(DataSource, source_id)
    if not source:
        return None
    data = payload.model_dump(exclude_unset=True)
    source_type = data.get("source_type", source.source_type)
    source_url = data.get("url", source.url)
    data["url"] = validate_source_location(source_type, source_url)
    for key, value in data.items():
        setattr(source, key, value)
    db.commit()
    db.refresh(source)
    return source


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def _intel_status(is_related: bool, confidence: float) -> str:
    if not is_related:
        return "ignored"
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
        status="approved" if doc.status == "stored" else "pending_review" if doc.is_ai_related else "ignored",
    )
    db.add(item)
    db.commit()
    db.refresh(item)
    return item


def _empty_metrics() -> dict[str, int]:
    return {
        "discovered": 0,
        "prefilter_passed": 0,
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


def _get_required_task_int(task: Task, field_name: str) -> int | None:
    raw_value = (task.input_data or {}).get(field_name)
    if raw_value in (None, ""):
        return None
    try:
        return int(raw_value)
    except (TypeError, ValueError):
        return None


def _format_exception_message(exc: Exception) -> str:
    message = str(exc).strip()
    return message or exc.__class__.__name__


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
    output = deepcopy(task.output_data or {})
    output.update(patch)
    task.output_data = output
    flag_modified(task, "output_data")
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
    output = deepcopy(task.output_data or {})
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
    flag_modified(task, "output_data")
    db.add(task)
    db.commit()
    db.refresh(task)


def _update_metrics(task: Task, db: Session, **delta: int) -> None:
    output = deepcopy(task.output_data or {})
    metrics = {**_empty_metrics(), **output.get("metrics", {})}
    for key, value in delta.items():
        metrics[key] = metrics.get(key, 0) + value
    output["metrics"] = metrics
    task.output_data = output
    flag_modified(task, "output_data")
    db.add(task)
    db.commit()
    db.refresh(task)


def _upsert_source_run(task: Task, db: Session, source: DataSource, patch: dict[str, Any]) -> None:
    output = deepcopy(task.output_data or {})
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
            "prefilter_passed": 0,
            "processed": 0,
            "queued_analysis": 0,
            "analyzed": 0,
            "ai_related": 0,
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
    flag_modified(task, "output_data")
    db.add(task)
    db.commit()
    db.refresh(task)


def _record_source_analysis_result(db: Session, source_id: int | None, *, is_related: bool, document_status: str) -> None:
    if source_id is None:
        return
    source = db.get(DataSource, source_id)
    if not source:
        return
    crawl_tasks = db.scalars(select(Task).where(Task.task_type == "crawl").order_by(Task.created_at.desc())).all()
    for crawl_task in crawl_tasks:
        source_run = next(
            (run for run in (crawl_task.output_data or {}).get("source_runs", []) if run.get("source_id") == source_id),
            None,
        )
        if not source_run:
            continue
        patch: dict[str, Any] = {
            "analyzed": int(source_run.get("analyzed", 0) or 0) + 1,
            "event": {
                "stage": "analysis_result",
                "message": f"Analysis result recorded: {document_status}",
                "is_ai_related": is_related,
            },
        }
        if is_related:
            patch["ai_related"] = int(source_run.get("ai_related", 0) or 0) + 1
        if document_status == "pending_review":
            patch["pending_review"] = int(source_run.get("pending_review", 0) or 0) + 1
        if document_status == "stored":
            patch["saved"] = int(source_run.get("saved", 0) or 0) + 1
        _upsert_source_run(crawl_task, db, source, patch)
        return


async def fetch_candidates(source: DataSource) -> list[dict[str, str]]:
    if source.source_type == "local_file":
        path = resolve_local_source_path(source.url)
        if not path.exists() or not path.is_file():
            raise InputSecurityError("local source file does not exist")
        if path.stat().st_size > MAX_SOURCE_RESPONSE_BYTES:
            raise InputSecurityError("local source file exceeds the configured byte limit")
        data = json.loads(path.read_text(encoding="utf-8"))
        if isinstance(data, dict):
            data = data.get("items", [])
        return [
            {
                "title": sanitize_plain_text(item.get("title", "local item"), max_chars=300),
                "url": item.get("url", source.url),
                "raw_text": sanitize_plain_text(item.get("raw_text") or item.get("text", "")),
            }
            for item in data[:100]
        ]

    headers = {
        "User-Agent": "LLM-VulnHub/0.1",
        "Accept": "application/json, application/atom+xml, application/xml;q=0.9, text/xml;q=0.8, text/html;q=0.7",
    }
    if settings.github_token and (source.source_type == "github" or "api.github.com" in source.url):
        headers["Authorization"] = f"Bearer {settings.github_token}"

    async with httpx.AsyncClient(timeout=45, follow_redirects=False, headers=headers, trust_env=False) as client:
        async def get_with_retry(url: str) -> httpx.Response:
            last_exc: Exception | None = None
            for attempt in range(3):
                try:
                    response = await safe_http_get(client, url, max_bytes=MAX_SOURCE_RESPONSE_BYTES)
                    if response.status_code < 500:
                        return response
                    last_exc = RuntimeError(f"HTTP {response.status_code}")
                except (httpx.TimeoutException, httpx.NetworkError) as exc:
                    last_exc = exc
                if attempt < 2:
                    await asyncio.sleep(0.8 * (attempt + 1))
            if last_exc:
                raise last_exc
            raise RuntimeError("source request failed")

        resp = await get_with_retry(source.url)
        if resp.status_code == 404 and source.source_type == "rss" and "github.com/" in source.url and source.url.endswith("/releases.atom"):
            fallback_url = source.url.removesuffix("/releases.atom") + "/tags.atom"
            resp = await get_with_retry(fallback_url)
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
                summary = sanitize_plain_text(item.get("summary", ""), max_chars=4_000)
                description = sanitize_plain_text(item.get("description", ""), max_chars=12_000)
                severity = item.get("severity", "")
                identifier = item.get("cve_id") or item.get("ghsa_id") or ""
                title = f"{identifier} {summary}".strip() if identifier else summary or "github advisory"
                refs = " ".join(
                    ref.get("url", "") if isinstance(ref, dict) else str(ref)
                    for ref in item.get("references", [])[:5]
                )
                raw_text = sanitize_plain_text(" ".join(
                    part
                    for part in [summary, description, f"severity: {severity}" if severity else "", item.get("html_url", ""), refs]
                    if part
                ), max_chars=16_000)
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
                "title": sanitize_plain_text(entry.get("title", "rss item"), max_chars=300),
                "url": entry.get("link", source.url),
                "raw_text": sanitize_html_text(" ".join([entry.get("title", ""), entry.get("summary", "")])),
            }
            for entry in feed.entries[:30]
        ]

    text = sanitize_html_text(body, max_chars=MAX_UNTRUSTED_TEXT_CHARS)
    return [{"title": sanitize_plain_text(source.name, max_chars=300), "url": source.url, "raw_text": text}]


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
        output = dict(task.output_data or {})
        if task.status == "success" and output.get("current_stage") == "completed":
            return {"task_id": task.id, "status": task.status, "notification": output.get("notification", {})}
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

    document_id = _get_required_task_int(task, "document_id")
    if document_id is None:
        task.status = "failed"
        task.error_message = "invalid task payload: missing document_id"
        _append_stage(
            task,
            db,
            "completed",
            "failed",
            "Analysis task payload is invalid: missing document_id.",
            {"task_input": dict(task.input_data or {})},
        )
        _mark_dead_letter_if_needed(task, db, "invalid task payload: missing document_id")
        return {"task_id": task.id, "status": task.status}

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
        confidence = normalize_confidence_value(rel.get("confidence", 0.0))

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

        # Collected content is untrusted and must never publish itself into the
        # canonical vulnerability library or RAG index. Publication is only
        # reachable through an authenticated analyst review action.
        auto_published = False

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
        output["auto_published"] = auto_published
        task.output_data = output
        task.status = "success"
        _update_metrics(task, db, analyzed=1, saved=1 if doc.status == "stored" else 0, pending_review=1 if doc.status == "pending_review" else 0, ignored=1 if doc.status == "ignored" else 0)
        _record_source_analysis_result(db, doc.source_id, is_related=is_related, document_status=doc.status)
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
        elif auto_published:
            _append_stage(
                task,
                db,
                "storing",
                "success",
                f"High-confidence intelligence auto-published as vulnerability #{intel_item.vulnerability_id}.",
                {"document_id": doc.id, "intel_item_id": intel_item.id, "vulnerability_id": intel_item.vulnerability_id},
            )
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

    intel_item_id = _get_required_task_int(task, "intel_item_id")
    if intel_item_id is None:
        task.status = "failed"
        task.error_message = "invalid task payload: missing intel_item_id"
        _append_stage(
            task,
            db,
            "completed",
            "failed",
            "Review task payload is invalid: missing intel_item_id.",
            {"task_input": dict(task.input_data or {})},
        )
        _mark_dead_letter_if_needed(task, db, "invalid task payload: missing intel_item_id")
        return {"task_id": task.id, "status": task.status}

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
        error_message = _format_exception_message(exc)
        _update_metrics(task, db, failed=1)
        _update_metrics(task, db, notifications=1)
        notification_task = create_notification_task(
            db,
            "source_failure",
            {
                "source_id": source.id,
                "title": source.name,
                "severity": "warning",
                "message": error_message,
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
                "error": error_message,
                "event": {"stage": "failed", "message": error_message},
            },
        )


async def _process_candidate(db: Session, task: Task, source: DataSource, item: dict[str, str]) -> None:
    raw_text = sanitize_plain_text(item.get("raw_text", ""), max_chars=MAX_UNTRUSTED_TEXT_CHARS)
    if not raw_text:
        return

    title = item.get("title", "untitled")[:300]
    passed_prefilter, prefilter_reason = _prefilter_candidate(source, item)
    if not passed_prefilter:
        _update_metrics(task, db, ignored=1)
        current_run = next(
            (run for run in (task.output_data or {}).get("source_runs", []) if run.get("source_id") == source.id),
            None,
        )
        _upsert_source_run(
            task,
            db,
            source,
            {
                "ignored": (current_run or {}).get("ignored", 0) + 1,
                "stage": "filtering",
                "event": {
                    "stage": "filtering",
                    "message": f"Prefilter ignored: {title}",
                    "reason": prefilter_reason,
                },
            },
        )
        return

    _update_metrics(task, db, prefilter_passed=1)
    current_run = next(
        (run for run in (task.output_data or {}).get("source_runs", []) if run.get("source_id") == source.id),
        None,
    )
    _upsert_source_run(
        task,
        db,
        source,
        {
            "prefilter_passed": (current_run or {}).get("prefilter_passed", 0) + 1,
            "stage": "deduplicating",
            "event": {
                "stage": "prefilter",
                "message": f"Prefilter passed: {title}",
                "reason": prefilter_reason,
            },
        },
    )

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
