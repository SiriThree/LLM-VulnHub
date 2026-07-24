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
    Task,
    Vulnerability,
    VulnerabilityOccurrence,
)
from app.db.session import Base
from app.schemas.collector import DataSourceCreate
from app.services.collector_service import DuplicateSourceError, create_source, get_collector_overview
from app.services.intel_service import (
    approve_intelligence_item,
    approve_merge_candidate,
    count_review_actions,
    list_review_actions,
    undo_intelligence_review,
)
from app.services.notification_service import get_notification_stats
from app.services.prompt_registry import PROMPT_REGISTRY
from app.workflows.vuln_analysis_graph import report_node


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

    def test_analysis_prompts_and_report_require_simplified_chinese(self):
        self.assertTrue(
            all("Simplified Chinese" in prompt.system_prompt for prompt in PROMPT_REGISTRY.values())
        )
        state = {
            "extracted_fields": {
                "title": "测试漏洞",
                "vuln_type": "提示注入",
                "severity": "高危",
                "score": 80,
                "affected_component": "RAG",
                "description": "测试描述",
                "attack_method": "恶意文档",
                "impact": "数据泄露",
                "mitigation": "隔离不可信内容",
            },
            "similar": [],
            "asset_impact_details": {},
            "asset_impact_summary": "影响检索链路",
            "risk_reason": "可能导致越权访问",
            "review_summary": "需要人工复核",
            "risk_priority": "高",
            "score": 80,
            "severity": "高危",
        }

        report = report_node(state)["report"]

        self.assertIn("## 漏洞描述", report)
        self.assertIn("## 修复建议", report)
        self.assertIn("## 复核意见", report)
        self.assertNotIn("## Description", report)

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

    def test_collector_overview_lists_have_independent_pagination(self):
        for index in range(12):
            self.db.add(
                CollectedDocument(
                    title=f"Document {index}",
                    raw_text="evidence",
                    content_hash=f"{index:064d}",
                    status="pending_review",
                )
            )
            self.db.add(
                Task(
                    task_type="crawl",
                    status="success",
                    output_data={
                        "source_runs": [
                            {
                                "source_id": index + 1,
                                "source_name": f"Source {index}",
                                "source_type": "rss",
                                "status": "success",
                            }
                        ]
                    },
                )
            )
        self.db.commit()

        overview = get_collector_overview(
            self.db,
            pending_page=2,
            pending_page_size=5,
            recent_page=2,
            recent_page_size=5,
            runs_page=2,
            runs_page_size=5,
        )

        self.assertEqual(overview["pending_documents_total"], 12)
        self.assertEqual(len(overview["pending_documents"]), 5)
        self.assertEqual(overview["recent_documents_total"], 12)
        self.assertEqual(len(overview["recent_documents"]), 5)
        self.assertEqual(overview["recent_runs_total"], 12)
        self.assertEqual(len(overview["recent_runs"]), 5)

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

    def test_review_actions_support_category_pagination(self):
        for index, action in enumerate(["approve", "reject", "approve", "undo_review", "approve_merge", "approve"]):
            self.db.add(
                ReviewAction(
                    actor="analyst",
                    target_type="intelligence_item",
                    target_id=index + 1,
                    action=action,
                    before_snapshot={},
                    after_snapshot={},
                    reason=f"action {index}",
                )
            )
        self.db.commit()

        first_page = list_review_actions(self.db, action="approve", offset=0, limit=2)
        second_page = list_review_actions(self.db, action="approve", offset=2, limit=2)

        self.assertEqual(count_review_actions(self.db, action="approve"), 3)
        self.assertEqual(len(first_page), 2)
        self.assertEqual(len(second_page), 1)
        self.assertTrue(all(item.action == "approve" for item in first_page + second_page))

    def test_notification_stats_count_all_visible_and_unread_notifications(self):
        self.db.add_all(
            [
                Task(task_type="notification", status="success", output_data={"acknowledged": False}),
                Task(task_type="notification", status="success", output_data={"acknowledged": True}),
                Task(task_type="notification", status="success", output_data={"suppressed": True}),
                Task(task_type="crawl", status="success", output_data={}),
            ]
        )
        self.db.commit()

        self.assertEqual(get_notification_stats(self.db), {"total": 2, "unread": 1})

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
