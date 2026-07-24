import unittest

from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import Task
from app.db.session import Base
from app.services.task_service import (
    ActiveTaskDeletionError,
    delete_task_record,
    delete_tasks_for_source,
    list_task_source_groups,
)


class TaskDeletionTests(unittest.TestCase):
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

    def add_task(
        self,
        *,
        status: str,
        source_id: int | None = None,
        source_runs: list[dict] | None = None,
    ) -> Task:
        task = Task(
            task_type="crawl",
            status=status,
            input_data={"source_id": source_id},
            output_data={
                "requested_source_id": source_id,
                "source_runs": source_runs or [],
            },
        )
        self.db.add(task)
        self.db.commit()
        self.db.refresh(task)
        return task

    def test_deletes_finished_task(self):
        task = self.add_task(status="success", source_id=3)

        delete_task_record(self.db, task)

        self.assertIsNone(self.db.get(Task, task.id))

    def test_rejects_deleting_active_task(self):
        task = self.add_task(status="running", source_id=3)

        with self.assertRaises(ActiveTaskDeletionError):
            delete_task_record(self.db, task)

        self.assertIsNotNone(self.db.get(Task, task.id))

    def test_deletes_all_finished_tasks_referencing_source(self):
        direct = self.add_task(status="success", source_id=7)
        multi_source = self.add_task(
            status="failed",
            source_runs=[{"source_id": 7}, {"source_id": 8}],
        )
        unrelated = self.add_task(status="success", source_id=9)

        deleted_count = delete_tasks_for_source(self.db, 7)

        self.assertEqual(deleted_count, 2)
        self.assertIsNone(self.db.get(Task, direct.id))
        self.assertIsNone(self.db.get(Task, multi_source.id))
        self.assertIsNotNone(self.db.get(Task, unrelated.id))

    def test_source_batch_is_atomic_when_active_task_exists(self):
        finished = self.add_task(status="failed", source_id=11)
        active = self.add_task(status="queued", source_id=11)

        with self.assertRaises(ActiveTaskDeletionError):
            delete_tasks_for_source(self.db, 11)

        self.assertIsNotNone(self.db.get(Task, finished.id))
        self.assertIsNotNone(self.db.get(Task, active.id))

    def test_source_groups_include_deleted_sources_and_active_counts(self):
        self.add_task(
            status="success",
            source_runs=[{"source_id": 21, "source_name": "Historical source"}],
        )
        self.add_task(status="running", source_id=21)

        groups = list_task_source_groups(self.db)

        self.assertEqual(groups, [{
            "source_id": 21,
            "source_name": "Historical source",
            "task_count": 2,
            "active_count": 1,
        }])


if __name__ == "__main__":
    unittest.main()
