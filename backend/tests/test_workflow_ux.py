import unittest

from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.db.models import (
    CollectedDocument,
    DataSource,
    IntelligenceItem,
    MergeCandidate,
    ReviewAction,
    Vulnerability,
    VulnerabilityOccurrence,
)
from app.db.session import Base
from app.schemas.collector import DataSourceCreate
from app.services.collector_service import DuplicateSourceError, create_source
from app.services.intel_service import (
    approve_intelligence_item,
    approve_merge_candidate,
    undo_intelligence_review,
)


class WorkflowUxTests(unittest.TestCase):
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

    def test_duplicate_source_url_and_type_are_rejected(self):
        payload = DataSourceCreate(
            name="Primary feed",
            source_type="rss",
            url="https://example.com/security.xml",
            interval_minutes=30,
        )
        create_source(self.db, payload)
        with self.assertRaises(DuplicateSourceError):
            create_source(
                self.db,
                payload.model_copy(update={"name": "Duplicate name"}),
            )

    def test_reviewed_items_and_merge_candidates_cannot_be_approved_twice(self):
        vulnerability = Vulnerability(title="Existing vulnerability")
        item = IntelligenceItem(
            title="Reviewed intelligence",
            raw_text="evidence",
            content_hash="a" * 64,
            status="approved",
            vulnerability=vulnerability,
        )
        candidate = MergeCandidate(
            intelligence_item=item,
            candidate_vulnerability=vulnerability,
            merge_score=0.95,
            status="approved",
        )
        self.db.add_all([vulnerability, item, candidate])
        self.db.commit()

        with self.assertRaises(ValueError):
            approve_intelligence_item(self.db, item.id, actor="analyst")
        with self.assertRaises(ValueError):
            approve_merge_candidate(self.db, candidate.id, actor="analyst")

    def test_undo_merge_restores_review_state_and_records_history(self):
        source = DataSource(name="Source", source_type="rss", url="https://example.com/feed.xml")
        document = CollectedDocument(
            source=source,
            title="Collected document",
            raw_text="evidence",
            content_hash="b" * 64,
            status="stored",
        )
        vulnerability = Vulnerability(title="Shared vulnerability")
        item = IntelligenceItem(
            source=source,
            collected_document=document,
            vulnerability=vulnerability,
            title="Merged intelligence",
            raw_text="evidence",
            content_hash="c" * 64,
            status="approved",
        )
        candidate = MergeCandidate(
            intelligence_item=item,
            candidate_vulnerability=vulnerability,
            merge_score=0.91,
            status="approved",
        )
        occurrence = VulnerabilityOccurrence(
            intelligence_item=item,
            vulnerability=vulnerability,
            evidence_excerpt="evidence",
        )
        document.vulnerability_id = vulnerability.id
        self.db.add_all([source, document, vulnerability, item, candidate, occurrence])
        self.db.commit()

        updated = undo_intelligence_review(self.db, item.id, actor="analyst", notes="重新审核")

        self.assertEqual(updated.status, "pending_review")
        self.assertIsNone(updated.vulnerability_id)
        self.assertEqual(document.status, "pending_review")
        self.assertIsNone(document.vulnerability_id)
        self.assertEqual(candidate.status, "pending")
        self.assertIsNotNone(self.db.get(Vulnerability, vulnerability.id))
        self.assertIsNone(
            self.db.scalar(
                select(VulnerabilityOccurrence).where(
                    VulnerabilityOccurrence.intelligence_item_id == item.id
                )
            )
        )
        action = self.db.scalar(
            select(ReviewAction).where(
                ReviewAction.target_type == "intelligence_item",
                ReviewAction.target_id == item.id,
                ReviewAction.action == "undo_review",
            )
        )
        self.assertIsNotNone(action)
        self.assertEqual(action.reason, "重新审核")


if __name__ == "__main__":
    unittest.main()
