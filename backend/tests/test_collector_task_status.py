import unittest
from unittest.mock import AsyncMock, patch

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import DataSource, Task
from app.db.session import Base
from app.services.collector_service import _base_output, _run_collection
from app.services.provenance_service import build_source_health


class CollectorTaskStatusTests(unittest.IsolatedAsyncioTestCase):
    def setUp(self):
        self.engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(self.engine)
        self.db = Session(self.engine)

    def tearDown(self):
        self.db.close()
        self.engine.dispose()

    def create_source(self, name: str) -> DataSource:
        source = DataSource(
            name=name,
            source_type="rss",
            url=f"https://example.com/{name}.xml",
            enabled=True,
            interval_minutes=30,
        )
        self.db.add(source)
        self.db.commit()
        self.db.refresh(source)
        return source

    def create_task(self, source_id: int | None = None) -> Task:
        task = Task(
            task_type="crawl",
            status="queued",
            input_data={"source_id": source_id},
            output_data=_base_output(source_id, "manual"),
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    async def test_source_failure_marks_parent_task_failed_and_updates_health(self):
        source = self.create_source("failing-feed")
        task = self.create_task(source.id)

        with (
            patch(
                "app.services.collector_service.fetch_candidates",
                new=AsyncMock(side_effect=RuntimeError("upstream unavailable")),
            ),
            patch("app.services.collector_service.dispatch_notification_task"),
        ):
            result = await _run_collection(self.db, task)

        self.db.refresh(task)
        health = build_source_health(source, [], [task])

        self.assertEqual(result["status"], "failed")
        self.assertEqual(task.status, "failed")
        self.assertEqual(task.output_data["source_failure_count"], 1)
        self.assertEqual(task.output_data["source_success_count"], 0)
        self.assertIn("failing-feed", task.error_message)
        self.assertIsNotNone(health["last_attempted_at"])
        self.assertEqual(health["last_run_status"], "failed")
        self.assertIn("upstream unavailable", health["last_run_error"])
        self.assertIsNone(source.last_collected_at)

    async def test_any_source_failure_makes_multi_source_task_failed(self):
        successful_source = self.create_source("working-feed")
        failing_source = self.create_source("broken-feed")
        task = self.create_task()

        with (
            patch(
                "app.services.collector_service.fetch_candidates",
                new=AsyncMock(side_effect=[[], RuntimeError("invalid response")]),
            ),
            patch("app.services.collector_service.dispatch_notification_task"),
        ):
            await _run_collection(self.db, task)

        self.db.refresh(task)
        self.db.refresh(successful_source)
        self.db.refresh(failing_source)

        self.assertEqual(task.status, "failed")
        self.assertTrue(task.output_data["partial_success"])
        self.assertEqual(task.output_data["source_success_count"], 1)
        self.assertEqual(task.output_data["source_failure_count"], 1)
        self.assertIsNotNone(successful_source.last_collected_at)
        self.assertIsNone(failing_source.last_collected_at)

    async def test_successful_source_keeps_parent_task_successful(self):
        source = self.create_source("working-feed")
        task = self.create_task(source.id)

        with patch(
            "app.services.collector_service.fetch_candidates",
            new=AsyncMock(return_value=[]),
        ):
            result = await _run_collection(self.db, task)

        self.db.refresh(task)
        self.db.refresh(source)

        self.assertEqual(result["status"], "success")
        self.assertEqual(task.output_data["source_failure_count"], 0)
        self.assertEqual(task.output_data["source_success_count"], 1)
        self.assertIsNotNone(source.last_collected_at)

