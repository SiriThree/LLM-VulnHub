from collections.abc import Callable
from typing import Any

from app.services.collector_service import (
    dispatch_analysis_task,
    dispatch_collection_task,
    dispatch_notification_task,
    dispatch_review_task,
)

TaskDispatcher = Callable[[int], Any]


class UnsupportedTaskTypeError(ValueError):
    pass


TASK_DISPATCHERS: dict[str, TaskDispatcher] = {
    "crawl": dispatch_collection_task,
    "analyze_document": dispatch_analysis_task,
    "review_helper": dispatch_review_task,
    "notification": dispatch_notification_task,
}


def get_task_dispatcher(task_type: str) -> TaskDispatcher:
    dispatcher = TASK_DISPATCHERS.get(task_type)
    if dispatcher is None:
        raise UnsupportedTaskTypeError(f"no executor is registered for task type: {task_type}")
    return dispatcher


def dispatch_registered_task(task_type: str, task_id: int) -> Any:
    return get_task_dispatcher(task_type)(task_id)
