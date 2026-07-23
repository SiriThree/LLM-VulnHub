from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy import select
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity, require_role
from app.db.models import Task
from app.db.session import get_db
from app.schemas.task import TaskListResponse, TaskRead
from app.services.collector_service import (
    dispatch_analysis_task,
    dispatch_collection_task,
    dispatch_notification_task,
    dispatch_review_task,
)

router = APIRouter(prefix="/tasks", tags=["tasks"])


@router.get("", response_model=TaskListResponse)
def list_tasks(
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    tasks = db.scalars(select(Task).order_by(Task.created_at.desc()).limit(100)).all()
    return {"items": tasks}


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


@router.post("/{task_id}/retry", response_model=TaskRead)
def retry_task(
    task_id: int,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    task = db.get(Task, task_id)
    if not task:
        raise HTTPException(404, "task not found")

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

    if task.task_type == "crawl":
        dispatch_collection_task(task.id)
    elif task.task_type == "analyze_document":
        dispatch_analysis_task(task.id)
    elif task.task_type == "review_helper":
        dispatch_review_task(task.id)
    elif task.task_type == "notification":
        dispatch_notification_task(task.id)

    return task
