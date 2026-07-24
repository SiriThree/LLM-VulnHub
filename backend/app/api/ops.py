from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity, require_role
from app.db.session import get_db
from app.schemas.ops import (
    DeadLetterTaskRead,
    EvalRunRead,
    OpsMetricsRead,
    PromptRegistryItemRead,
    SchedulerOverviewRead,
)
from app.services.task_dispatch_registry import UnsupportedTaskTypeError, get_task_dispatcher
from app.services.ops_service import (
    get_ops_metrics,
    get_scheduler_overview,
    list_dead_letter_tasks,
    list_eval_runs,
    list_prompt_registry_items,
    mark_task_dead_letter,
    run_eval_and_collect,
)
from app.db.models import Task

router = APIRouter(prefix="/ops", tags=["ops"])


@router.get("/metrics", response_model=OpsMetricsRead)
def metrics(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("viewer")),
):
    return get_ops_metrics(db)


@router.get("/scheduler", response_model=SchedulerOverviewRead)
def scheduler(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    return get_scheduler_overview(db)


@router.get("/dead-letter", response_model=list[DeadLetterTaskRead])
def dead_letter(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    return list_dead_letter_tasks(db)


@router.post("/dead-letter/{task_id}/requeue", response_model=DeadLetterTaskRead)
def requeue_dead_letter(
    task_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    try:
        dispatcher = get_task_dispatcher(task.task_type)
    except UnsupportedTaskTypeError as exc:
        raise HTTPException(409, str(exc)) from exc

    output = dict(task.output_data or {})
    output["dead_letter"] = False
    output["dead_letter_reason"] = None
    output["dead_letter_at"] = None
    output["execution_mode"] = "pending"
    output["queue_task_id"] = None
    output["current_stage"] = "queued"
    output["stage_history"] = []
    output["source_runs"] = [] if task.task_type == "crawl" else output.get("source_runs", [])
    output["started_at"] = None
    output["finished_at"] = None
    output["elapsed_seconds"] = None
    task.output_data = output
    task.status = "queued"
    task.error_message = None
    db.commit()
    db.refresh(task)

    dispatcher(task.id)

    return next((item for item in list_dead_letter_tasks(db) if item["id"] == task.id), {
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
    })


@router.post("/dead-letter/{task_id}/mark", response_model=DeadLetterTaskRead)
def force_mark_dead_letter(
    task_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    mark_task_dead_letter(db, task)
    return next(item for item in list_dead_letter_tasks(db) if item["id"] == task.id)


@router.get("/prompts", response_model=list[PromptRegistryItemRead])
def prompts(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("viewer")),
):
    return list_prompt_registry_items(db)


@router.get("/evals", response_model=list[EvalRunRead])
def evals(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("viewer")),
):
    return list_eval_runs()


@router.post("/evals/run", response_model=EvalRunRead)
def run_eval_now(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("admin")),
):
    return run_eval_and_collect()
