from fastapi import APIRouter, Depends, HTTPException, Query
from sqlalchemy import func, select
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity, require_role
from app.db.models import Task
from app.db.session import get_db
from app.schemas.task import TaskListResponse, TaskRead
from app.services.task_dispatch_registry import UnsupportedTaskTypeError, get_task_dispatcher
from app.services.task_service import (
    ActiveTaskDeletionError,
    delete_task_record,
    delete_tasks_for_source,
    list_task_source_groups,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=TaskListResponse)
def list_tasks(
    status: str | None = Query(default=None, max_length=40),
    page: int = Query(default=1, ge=1),
    page_size: int = Query(default=5, ge=1, le=100),
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    stmt = select(Task)
    if status:
        stmt = stmt.where(Task.status == status)
    total = db.scalar(select(func.count()).select_from(stmt.subquery())) or 0
    tasks = db.scalars(
        stmt.order_by(Task.created_at.desc(), Task.id.desc())
        .offset((page - 1) * page_size)
        .limit(page_size)
    ).all()
    status_counts = dict(
        db.execute(select(Task.status, func.count(Task.id)).group_by(Task.status)).all()
    )
    all_outputs = db.scalars(select(Task.output_data)).all()
    return {
        "items": tasks,
        "total": total,
        "page": page,
        "page_size": page_size,
        "stats": {
            "total": sum(status_counts.values()),
            "queued": status_counts.get("queued", 0),
            "running": status_counts.get("running", 0),
            "success": status_counts.get("success", 0),
            "failed": status_counts.get("failed", 0),
            "dead_letter": sum(1 for output in all_outputs if bool((output or {}).get("dead_letter"))),
        },
    }


@router.get("/source-groups")
def get_task_source_groups(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("admin")),
):
    return list_task_source_groups(db)


@router.get("/{task_id}", response_model=TaskRead)
def get_task(
    task_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    return task


@router.delete("/by-source/{source_id}")
def delete_tasks_by_source(
    source_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("admin")),
):
    try:
        deleted_count = delete_tasks_for_source(db, source_id)
    except ActiveTaskDeletionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True, "source_id": source_id, "deleted_count": deleted_count}


@router.delete("/{task_id}")
def delete_task(
    task_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("admin")),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "task not found")
    try:
        delete_task_record(db, task)
    except ActiveTaskDeletionError as exc:
        raise HTTPException(409, str(exc)) from exc
    return {"ok": True, "task_id": task_id}


@router.post("/{task_id}/retry", response_model=TaskRead)
def retry_task(
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

    task.status = "queued"
    task.error_message = None
    task.output_data = {
        **(task.output_data or {}),
        "dead_letter": False,
        "dead_letter_reason": None,
        "dead_letter_at": None,
        "execution_mode": "pending",
        "queue_task_id": None,
        "current_stage": "queued",
        "stage_history": [],
        "source_runs": [],
        "started_at": None,
        "finished_at": None,
        "elapsed_seconds": None,
        "metrics": {
            "discovered": 0,
            "processed": 0,
            "saved": 0,
            "failed": 0,
            "duplicates": 0,
            "pending_review": 0,
            "ignored": 0,
        },
    }
    db.commit()
    db.refresh(task)

    dispatcher(task.id)

    return task
