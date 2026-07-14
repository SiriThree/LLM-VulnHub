from datetime import datetime, timedelta
from pathlib import Path
import asyncio
import json

from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.db.models import AgentExecution, AnalysisJob, CollectedDocument, DataSource, ReviewAction, Task
from app.evals.run_agent_eval import DATASET_PATH, run_eval
from app.services.prompt_registry import PROMPT_REGISTRY


def _naive(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    return value.replace(tzinfo=None) if value.tzinfo else value


def _iso(value: datetime | None) -> str | None:
    normalized = _naive(value)
    return normalized.isoformat() if normalized else None


def is_dead_letter_task(task: Task) -> bool:
    output = dict(task.output_data or {})
    attempt_count = int(output.get("attempt_count", 0) or 0)
    max_attempts = int(output.get("max_attempts", 0) or 0)
    return bool(output.get("dead_letter")) or (task.status == "failed" and max_attempts > 0 and attempt_count >= max_attempts)


def mark_task_dead_letter(db: Session, task: Task, reason: str | None = None) -> Task:
    output = dict(task.output_data or {})
    output["dead_letter"] = True
    output["dead_letter_reason"] = reason or task.error_message or "Task reached the retry limit."
    output["dead_letter_at"] = datetime.utcnow().isoformat()
    task.output_data = output
    db.commit()
    db.refresh(task)
    return task


def get_ops_metrics(db: Session) -> dict:
    mock_providers = {"mock"}
    mock_models = {"mock-heuristic", "mock"}

    queue_metrics = {
        "queued": db.scalar(select(func.count()).select_from(Task).where(Task.status == "queued")) or 0,
        "running": db.scalar(select(func.count()).select_from(Task).where(Task.status == "running")) or 0,
        "success": db.scalar(select(func.count()).select_from(Task).where(Task.status == "success")) or 0,
        "failed": db.scalar(select(func.count()).select_from(Task).where(Task.status == "failed")) or 0,
    }

    total_sources = db.scalar(select(func.count()).select_from(DataSource)) or 0
    enabled_sources = db.scalar(select(func.count()).select_from(DataSource).where(DataSource.enabled.is_(True))) or 0

    notification_failures = 0
    for task in db.scalars(select(Task).where(Task.task_type == "notification")).all():
        output = dict(task.output_data or {})
        if str(output.get("event_type")) == "source_failure":
            notification_failures += 1

    jobs = list(db.scalars(select(AnalysisJob)).all())
    provider_distribution: dict[str, int] = {}
    severity_distribution: dict[str, int] = {}
    scores: list[int] = []
    for job in jobs:
        provider = job.provider_name or "unknown"
        if provider not in mock_providers:
            provider_distribution[provider] = provider_distribution.get(provider, 0) + 1
        if job.severity:
            severity_distribution[job.severity] = severity_distribution.get(job.severity, 0) + 1
        if job.score is not None:
            scores.append(job.score)

    agent_executions = list(db.scalars(select(AgentExecution)).all())
    llm_provider_distribution: dict[str, int] = {}
    model_distribution: dict[str, int] = {}
    total_prompt_tokens = 0
    total_completion_tokens = 0
    total_tokens = 0
    latency_samples: list[int] = []
    for execution in agent_executions:
        provider = execution.provider_name or "unknown"
        model = execution.model_name or "unknown"
        if provider not in mock_providers:
            llm_provider_distribution[provider] = llm_provider_distribution.get(provider, 0) + 1
        if model not in mock_models:
            model_distribution[model] = model_distribution.get(model, 0) + 1
        total_prompt_tokens += execution.prompt_tokens or 0
        total_completion_tokens += execution.completion_tokens or 0
        total_tokens += execution.total_tokens or 0
        if execution.latency_ms is not None:
            latency_samples.append(execution.latency_ms)

    today = datetime.utcnow().date()
    trend_days = [today - timedelta(days=offset) for offset in range(6, -1, -1)]
    trend_map: dict[str, dict[str, int]] = {
        day.isoformat(): {
            "date": day.isoformat(),
            "collected_documents": 0,
            "analysis_jobs": 0,
            "review_actions": 0,
        }
        for day in trend_days
    }

    for document in db.scalars(select(CollectedDocument)).all():
        collected_at = _naive(document.collected_at)
        if collected_at is None:
            continue
        key = collected_at.date().isoformat()
        if key in trend_map:
            trend_map[key]["collected_documents"] += 1

    for job in jobs:
        created_at = _naive(job.created_at)
        if created_at is None:
            continue
        key = created_at.date().isoformat()
        if key in trend_map:
            trend_map[key]["analysis_jobs"] += 1

    for action in db.scalars(select(ReviewAction)).all():
        created_at = _naive(action.created_at)
        if created_at is None:
            continue
        key = created_at.date().isoformat()
        if key in trend_map:
            trend_map[key]["review_actions"] += 1

    return {
        "queue_metrics": queue_metrics,
        "source_health": {
            "total_sources": total_sources,
            "enabled_sources": enabled_sources,
            "disabled_sources": max(total_sources - enabled_sources, 0),
            "recently_failed_notifications": notification_failures,
        },
        "provider_metrics": {
            "analysis_jobs_total": len(jobs),
            "avg_score": round(sum(scores) / len(scores), 2) if scores else 0.0,
            "provider_distribution": provider_distribution,
            "severity_distribution": severity_distribution,
        },
        "llm_usage": {
            "total_calls": len(agent_executions),
            "total_prompt_tokens": total_prompt_tokens,
            "total_completion_tokens": total_completion_tokens,
            "total_tokens": total_tokens,
            "avg_latency_ms": round(sum(latency_samples) / len(latency_samples), 2) if latency_samples else 0.0,
            "provider_distribution": llm_provider_distribution,
            "model_distribution": model_distribution,
        },
        "daily_trends": [trend_map[day.isoformat()] for day in trend_days],
    }


def get_scheduler_overview(db: Session) -> dict:
    from app.worker import celery_app

    beat_jobs = []
    for name, config in dict(celery_app.conf.beat_schedule or {}).items():
        schedule = config.get("schedule")
        schedule_seconds = float(getattr(schedule, "run_every", schedule).total_seconds()) if hasattr(getattr(schedule, "run_every", schedule), "total_seconds") else float(schedule)
        beat_jobs.append(
            {
                "name": name,
                "task": str(config.get("task")),
                "schedule_seconds": schedule_seconds,
            }
        )

    sources = []
    now = datetime.utcnow()
    for source in db.scalars(select(DataSource).order_by(DataSource.enabled.desc(), DataSource.id.asc())).all():
        last_collected_at = _naive(source.last_collected_at)
        next_run_at = None
        if source.enabled:
            if last_collected_at is None:
                next_run_at = now
            else:
                next_run_at = last_collected_at + timedelta(minutes=source.interval_minutes)

        if not source.enabled:
            status = "disabled"
        elif last_collected_at is None:
            status = "never-run"
        elif next_run_at and next_run_at <= now:
            status = "due"
        else:
            status = "scheduled"

        sources.append(
            {
                "source_id": source.id,
                "name": source.name,
                "enabled": source.enabled,
                "interval_minutes": source.interval_minutes,
                "last_collected_at": _iso(source.last_collected_at),
                "next_run_at": next_run_at.isoformat() if next_run_at else None,
                "status": status,
            }
        )

    return {"beat_jobs": beat_jobs, "sources": sources}


def list_dead_letter_tasks(db: Session) -> list[dict]:
    tasks = db.scalars(select(Task).order_by(Task.updated_at.desc(), Task.id.desc()).limit(200)).all()
    items = []
    for task in tasks:
        if not is_dead_letter_task(task):
            continue
        output = dict(task.output_data or {})
        items.append(
            {
                "id": task.id,
                "task_type": task.task_type,
                "status": task.status,
                "attempt_count": int(output.get("attempt_count", 0) or 0),
                "max_attempts": int(output.get("max_attempts", 0) or 0),
                "dead_letter_reason": output.get("dead_letter_reason"),
                "current_stage": output.get("current_stage"),
                "error_message": task.error_message,
                "queue_name": output.get("queue_name"),
                "created_at": task.created_at.isoformat(),
                "updated_at": task.updated_at.isoformat(),
            }
        )
    return items


def list_prompt_registry_items(db: Session) -> list[dict]:
    executions = list(db.scalars(select(AgentExecution)).all())
    usage_map: dict[str, dict[str, float]] = {}
    for execution in executions:
        prompt_key = str((execution.input_payload or {}).get("prompt_key") or "")
        if not prompt_key:
            continue
        stats = usage_map.setdefault(
            prompt_key,
            {"usage_count": 0, "success_count": 0, "failure_count": 0, "latency_total": 0.0, "latency_count": 0},
        )
        stats["usage_count"] += 1
        if execution.status == "completed":
            stats["success_count"] += 1
        else:
            stats["failure_count"] += 1
        if execution.latency_ms is not None:
            stats["latency_total"] += execution.latency_ms
            stats["latency_count"] += 1

    items = []
    for key, spec in PROMPT_REGISTRY.items():
        stats = usage_map.get(key, {})
        latency_count = int(stats.get("latency_count", 0))
        items.append(
            {
                "key": spec.key,
                "agent_name": spec.agent_name,
                "version": spec.version,
                "required_keys": list(spec.required_keys),
                "usage_count": int(stats.get("usage_count", 0)),
                "success_count": int(stats.get("success_count", 0)),
                "failure_count": int(stats.get("failure_count", 0)),
                "avg_latency_ms": round(float(stats.get("latency_total", 0.0)) / latency_count, 2) if latency_count else 0.0,
            }
        )

    return sorted(items, key=lambda item: (item["usage_count"], item["key"]), reverse=True)


def _eval_output_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "artifacts" / "evals"


def list_eval_runs() -> list[dict]:
    output_dir = _eval_output_dir()
    if not output_dir.exists():
        return []

    items = []
    for path in sorted(output_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True):
        try:
            payload = json.loads(path.read_text(encoding="utf-8"))
        except Exception:
            continue
        summary = dict(payload.get("summary") or {})
        generated_at = datetime.fromtimestamp(path.stat().st_mtime).isoformat()
        items.append(
            {
                "file_name": path.name,
                "provider": str(summary.get("provider", "unknown")),
                "dataset_size": int(summary.get("dataset_size", 0) or 0),
                "triage_accuracy": float(summary.get("triage_accuracy", 0.0) or 0.0),
                "triage_precision": float(summary.get("triage_precision", 0.0) or 0.0),
                "triage_recall": float(summary.get("triage_recall", 0.0) or 0.0),
                "extraction_completeness": float(summary.get("extraction_completeness", 0.0) or 0.0),
                "merge_precision": float(summary.get("merge_precision", 0.0) or 0.0),
                "generated_at": generated_at,
            }
        )
    return items


def run_eval_and_collect() -> dict:
    output_dir = _eval_output_dir()
    timestamp = datetime.utcnow().strftime("%Y%m%d-%H%M%S")
    output_path = output_dir / f"eval-{timestamp}.json"
    asyncio.run(run_eval(DATASET_PATH, verbose=False, output_path=output_path))
    runs = list_eval_runs()
    return runs[0] if runs else {
        "file_name": output_path.name,
        "provider": "unknown",
        "dataset_size": 0,
        "triage_accuracy": 0.0,
        "triage_precision": 0.0,
        "triage_recall": 0.0,
        "extraction_completeness": 0.0,
        "merge_precision": 0.0,
        "generated_at": datetime.utcnow().isoformat(),
    }
