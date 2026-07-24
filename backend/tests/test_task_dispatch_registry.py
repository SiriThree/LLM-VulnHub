import unittest
from unittest.mock import Mock, patch

from fastapi import HTTPException
from sqlalchemy import create_engine
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.api.tasks import retry_task
from app.core.security import RequestIdentity
from app.db.models import Task
from app.db.session import Base
from app.services.task_dispatch_registry import (
    TASK_DISPATCHERS,
    UnsupportedTaskTypeError,
    dispatch_registered_task,
    get_task_dispatcher,
)


class TaskDispatchRegistryTests(unittest.TestCase):
    def test_registered_dispatcher_is_called(self):
        dispatcher = Mock(return_value="queued")
        with patch.dict(TASK_DISPATCHERS, {"future_task": dispatcher}, clear=True):
            result = dispatch_registered_task("future_task", 42)

        self.assertEqual(result, "queued")
        dispatcher.assert_called_once_with(42)

    def test_unknown_task_type_is_rejected(self):
        with self.assertRaises(UnsupportedTaskTypeError):
            get_task_dispatcher("missing_executor")

    def test_retry_does_not_mark_unknown_task_as_queued(self):
        engine = create_engine(
            "sqlite+pysqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        identity = RequestIdentity(actor="analyst", role="analyst", session_key="session", csrf_token="csrf")

        with Session(engine) as db:
            task = Task(
                task_type="future_task",
                status="failed",
                input_data={},
                output_data={"dead_letter": True},
                error_message="no executor",
            )
            db.add(task)
            db.commit()
            db.refresh(task)

            with self.assertRaises(HTTPException) as raised:
                retry_task(task.id, db, identity)

            db.refresh(task)
            self.assertEqual(raised.exception.status_code, 409)
            self.assertEqual(task.status, "failed")
            self.assertEqual(task.error_message, "no executor")
            self.assertTrue(task.output_data["dead_letter"])

        engine.dispose()


if __name__ == "__main__":
    unittest.main()
