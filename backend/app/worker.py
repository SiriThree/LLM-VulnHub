from celery import Celery

from app.core.config import get_settings

settings = get_settings()
celery_app = Celery("llm_vulnhub", broker=settings.redis_url, backend=settings.redis_url)
celery_app.conf.timezone = "Asia/Shanghai"
celery_app.conf.beat_schedule = {
    "collect-enabled-sources-every-5-minutes": {
        "task": "app.worker.collect_enabled_sources",
        "schedule": 300.0,
    }
}


@celery_app.task(name="app.worker.collect_task")
def collect_task(task_id: int) -> dict:
    import asyncio

    from app.services.collector_service import run_collection_task

    return asyncio.run(run_collection_task(task_id))


@celery_app.task(name="app.worker.collect_enabled_sources")
def collect_enabled_sources() -> dict:
    from app.services.collector_service import create_collection_task
    from app.db.session import SessionLocal

    db = SessionLocal()
    try:
        task = create_collection_task(db, None, trigger="scheduler")
        return collect_task.run(task.id)
    finally:
        db.close()
