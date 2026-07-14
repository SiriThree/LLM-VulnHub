import os

from celery import Celery
from kombu import Queue

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("llm_vulnhub", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.timezone = "Asia/Shanghai"
celery_app.conf.task_default_queue = "default"
celery_app.conf.broker_connection_retry_on_startup = True
celery_app.conf.task_queues = (
    Queue("default"),
    Queue("ingestion"),
    Queue("analysis"),
    Queue("review"),
    Queue("notification"),
)
celery_app.conf.task_routes = {
    "app.worker.collect_task": {"queue": "ingestion"},
    "app.worker.analyze_document_task": {"queue": "analysis"},
    "app.worker.review_helper_task": {"queue": "review"},
    "app.worker.notification_task": {"queue": "notification"},
    "app.worker.collect_enabled_sources": {"queue": "ingestion"},
}
celery_app.conf.beat_schedule = {
    "collect-enabled-sources-every-5-minutes": {
        "task": "app.worker.collect_enabled_sources",
        "schedule": 300.0,
    }
}

if os.name == "nt":
    celery_app.conf.worker_pool = "solo"
    celery_app.conf.worker_concurrency = 1


@celery_app.task(
    bind=True,
    name="app.worker.collect_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def collect_task(self, task_id: int) -> dict:
    import asyncio

    from app.services.collector_service import run_collection_task

    return asyncio.run(run_collection_task(task_id))


@celery_app.task(
    bind=True,
    name="app.worker.analyze_document_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def analyze_document_task(self, task_id: int) -> dict:
    import asyncio

    from app.services.collector_service import run_analysis_task

    return asyncio.run(run_analysis_task(task_id))


@celery_app.task(
    bind=True,
    name="app.worker.review_helper_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def review_helper_task(self, task_id: int) -> dict:
    import asyncio

    from app.services.collector_service import run_review_task

    return asyncio.run(run_review_task(task_id))


@celery_app.task(
    bind=True,
    name="app.worker.notification_task",
    autoretry_for=(Exception,),
    retry_backoff=True,
    retry_kwargs={"max_retries": 3},
)
def notification_task(self, task_id: int) -> dict:
    import asyncio

    from app.services.collector_service import run_notification_task

    return asyncio.run(run_notification_task(task_id))


@celery_app.task(name="app.worker.collect_enabled_sources")
def collect_enabled_sources() -> dict:
    from app.services.collector_service import create_collection_task, dispatch_collection_task
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        task = create_collection_task(db, None, trigger="scheduler")
        dispatch_collection_task(task.id)
        return {"task_id": task.id, "status": "queued"}
    finally:
        db.close()
