from datetime import datetime
from typing import Any

from app.db.models import CollectedDocument, DataSource, Task


def to_naive(dt: datetime | None) -> datetime | None:
    if dt is None:
        return None
    return dt.replace(tzinfo=None) if dt.tzinfo else dt


def source_runtime_status(source: DataSource) -> str:
    now = datetime.utcnow()
    last_collected_at = to_naive(source.last_collected_at)
    if not source.enabled:
        return "disabled"
    if last_collected_at is None:
        return "never_run"
    due_at = last_collected_at.timestamp() + source.interval_minutes * 60
    if due_at <= now.timestamp():
        return "due"
    return "healthy"


def build_source_health(
    source: DataSource,
    docs: list[CollectedDocument],
    tasks: list[Task],
) -> dict[str, Any]:
    now = datetime.utcnow()
    last_collected_at = to_naive(source.last_collected_at)
    related_docs = [doc for doc in docs if doc.source_id == source.id]
    crawl_runs: list[dict[str, Any]] = []
    for task in tasks:
        if task.task_type != "crawl":
            continue
        for run in (task.output_data or {}).get("source_runs", []):
            if run.get("source_id") == source.id:
                crawl_runs.append(run)

    recent_runs = crawl_runs[:10]
    success_runs = sum(1 for run in recent_runs if str(run.get("status")) in {"success", "completed"})
    failure_runs = sum(1 for run in recent_runs if str(run.get("status")) == "failed")
    run_count = len(recent_runs)
    success_rate = round(success_runs / run_count, 2) if run_count else 0.0
    freshness_minutes = int((now - last_collected_at).total_seconds() // 60) if last_collected_at else None

    ai_related = sum(1 for doc in related_docs if doc.is_ai_related)
    pending_review = sum(1 for doc in related_docs if doc.status == "pending_review")
    stored = sum(1 for doc in related_docs if doc.status == "stored")
    duplicates = sum(int(run.get("duplicates", 0) or 0) for run in recent_runs)

    score = 35
    signals: list[str] = []
    if source.enabled:
        score += 10
        signals.append("source enabled")
    else:
        signals.append("source disabled")

    if last_collected_at is not None:
        if freshness_minutes is not None and freshness_minutes <= source.interval_minutes * 3:
            score += 20
            signals.append("freshly collected")
        else:
            signals.append("collection may be stale")
    else:
        signals.append("never collected")

    if run_count:
        score += round(success_rate * 20)
        signals.append(f"recent success rate {int(success_rate * 100)}%")
    else:
        signals.append("no recent runs")

    if ai_related > 0:
        score += 8
        signals.append(f"{ai_related} AI-related hits")
    if stored > 0:
        score += 7
        signals.append(f"{stored} items reached library")
    if pending_review > 0:
        score += 4
        signals.append(f"{pending_review} items pending analyst review")
    if duplicates > 0:
        score += 3
        signals.append(f"{duplicates} duplicates matched historical corpus")
    if failure_runs > 0:
        score -= min(12, failure_runs * 4)
        signals.append(f"{failure_runs} recent failed runs")

    score = max(0, min(100, score))
    if score >= 80:
        trust_level = "high"
    elif score >= 60:
        trust_level = "medium"
    else:
        trust_level = "low"

    return {
        "source_id": source.id,
        "name": source.name,
        "source_type": source.source_type,
        "enabled": source.enabled,
        "interval_minutes": source.interval_minutes,
        "last_collected_at": source.last_collected_at,
        "status": source_runtime_status(source),
        "trust_score": score,
        "trust_level": trust_level,
        "documents_total": len(related_docs),
        "ai_related_documents": ai_related,
        "pending_review_documents": pending_review,
        "stored_documents": stored,
        "duplicate_documents": duplicates,
        "recent_run_count": run_count,
        "recent_failure_count": failure_runs,
        "success_rate": success_rate,
        "freshness_minutes": freshness_minutes,
        "signals": signals[:6],
    }
