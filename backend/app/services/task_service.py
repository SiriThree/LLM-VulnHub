from sqlalchemy import select
from sqlalchemy.orm import Session

from app.db.models import DataSource, Task


ACTIVE_TASK_STATUSES = {"pending", "queued", "running"}


class ActiveTaskDeletionError(ValueError):
    pass


def task_references_source(task: Task, source_id: int) -> bool:
    input_data = task.input_data or {}
    output_data = task.output_data or {}
    if input_data.get("source_id") == source_id:
        return True
    if output_data.get("requested_source_id") == source_id:
        return True
    return any(
        run.get("source_id") == source_id
        for run in output_data.get("source_runs", [])
        if isinstance(run, dict)
    )


def list_task_source_groups(db: Session) -> list[dict]:
    source_names = {
        source.id: source.name
        for source in db.scalars(select(DataSource)).all()
    }
    groups: dict[int, dict] = {}
    for task in db.scalars(select(Task)).all():
        output_data = task.output_data or {}
        references: dict[int, str | None] = {}
        requested_source_id = (task.input_data or {}).get("source_id")
        if isinstance(requested_source_id, int) and not isinstance(requested_source_id, bool):
            references[requested_source_id] = None
        output_source_id = output_data.get("requested_source_id")
        if isinstance(output_source_id, int) and not isinstance(output_source_id, bool):
            references[output_source_id] = None
        for run in output_data.get("source_runs", []):
            if not isinstance(run, dict):
                continue
            run_source_id = run.get("source_id")
            if isinstance(run_source_id, int) and not isinstance(run_source_id, bool):
                references[run_source_id] = run.get("source_name")

        for source_id, run_name in references.items():
            group = groups.setdefault(
                source_id,
                {
                    "source_id": source_id,
                    "source_name": source_names.get(source_id) or run_name or f"已删除来源 #{source_id}",
                    "task_count": 0,
                    "active_count": 0,
                },
            )
            group["task_count"] += 1
            if task.status in ACTIVE_TASK_STATUSES:
                group["active_count"] += 1

    return sorted(
        groups.values(),
        key=lambda item: (item["source_name"].lower(), item["source_id"]),
    )


def delete_task_record(db: Session, task: Task) -> None:
    if task.status in ACTIVE_TASK_STATUSES:
        raise ActiveTaskDeletionError(f"task #{task.id} is still {task.status}")
    db.delete(task)
    db.commit()


def delete_tasks_for_source(db: Session, source_id: int) -> int:
    matched_tasks = [
        task
        for task in db.scalars(select(Task)).all()
        if task_references_source(task, source_id)
    ]
    active_tasks = [task for task in matched_tasks if task.status in ACTIVE_TASK_STATUSES]
    if active_tasks:
        task_ids = ", ".join(f"#{task.id}" for task in active_tasks[:10])
        raise ActiveTaskDeletionError(
            f"source #{source_id} still has active tasks: {task_ids}"
        )

    for task in matched_tasks:
        db.delete(task)
    db.commit()
    return len(matched_tasks)
