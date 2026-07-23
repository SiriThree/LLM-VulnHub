import unittest
from unittest.mock import patch

import httpx
from fastapi import FastAPI, HTTPException
from sqlalchemy import create_engine, select
from sqlalchemy.orm import Session
from sqlalchemy.pool import StaticPool

from app.core.input_security import redact_sensitive_text
from app.core.security import AuthenticationMiddleware, RequestIdentity, allowed_visibilities, require_role
from app.db.models import DocumentChunk, RagQueryAudit, Vulnerability
from app.db.session import Base
from app.services.rag_service import record_rag_audit, search_similar
from app.services.security_model_service import get_security_model
from app.services.vulnerability_service import safe_legacy_external_url, serialize_vulnerability_for_role


class CriticalSecurityTests(unittest.IsolatedAsyncioTestCase):
    async def test_forged_role_headers_do_not_authenticate(self):
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware)

        @app.get("/api/v1/protected")
        def protected():
            return {"ok": True}

        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
            response = await client.get(
                "/api/v1/protected",
                headers={"X-Actor": "attacker", "X-Role": "admin"},
            )
        self.assertEqual(response.status_code, 401)

    async def test_mutation_requires_session_bound_csrf_token(self):
        app = FastAPI()
        app.add_middleware(AuthenticationMiddleware)

        @app.post("/api/v1/protected")
        def protected():
            return {"ok": True}

        identity = RequestIdentity(actor="analyst", role="analyst", session_key="stored", csrf_token="csrf-secret")
        transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
        with patch("app.core.security.load_identity", return_value=identity):
            async with httpx.AsyncClient(transport=transport, base_url="http://test") as client:
                missing = await client.post(
                    "/api/v1/protected",
                    cookies={"llm_vulnhub_session": "opaque-session"},
                )
                accepted = await client.post(
                    "/api/v1/protected",
                    cookies={
                        "llm_vulnhub_session": "opaque-session",
                        "llm_vulnhub_csrf": "csrf-secret",
                    },
                    headers={"X-CSRF-Token": "csrf-secret"},
                )
        self.assertEqual(missing.status_code, 403)
        self.assertEqual(accepted.status_code, 200)

    def test_model_context_redacts_common_credentials(self):
        raw = (
            "password=SuperSecret123 "
            "Authorization: Bearer abcdefghijklmnopqrstuvwxyz "
            "OPENAI_API_KEY=sk-abcdefghijklmnopqrstuvwxyz "
            "https://admin:private-pass@example.com/feed"
        )
        redacted = redact_sensitive_text(raw)
        self.assertNotIn("SuperSecret123", redacted)
        self.assertNotIn("abcdefghijklmnopqrstuvwxyz", redacted)
        self.assertNotIn("private-pass", redacted)
        self.assertGreaterEqual(redacted.count("[REDACTED_SECRET]"), 3)

    def test_legacy_invalid_url_is_not_returned(self):
        self.assertIsNone(safe_legacy_external_url("123"))
        self.assertIsNone(safe_legacy_external_url("file:///etc/passwd"))
        self.assertEqual(
            safe_legacy_external_url("https://example.com/advisory"),
            "https://example.com/advisory",
        )

    def test_guest_is_read_only_and_only_sees_public_visibility(self):
        guest = RequestIdentity(actor="guest", role="guest", session_key="stored", csrf_token="csrf")
        self.assertEqual(allowed_visibilities("guest"), ("public",))
        with self.assertRaises(HTTPException) as raised:
            require_role("viewer")(guest)
        self.assertEqual(raised.exception.status_code, 403)

    def test_rag_filters_records_before_scoring_and_audits_without_full_query(self):
        engine = create_engine(
            "sqlite://",
            connect_args={"check_same_thread": False},
            poolclass=StaticPool,
        )
        Base.metadata.create_all(engine)
        with Session(engine) as db:
            for index, visibility in enumerate(("public", "internal", "restricted"), start=1):
                vulnerability = Vulnerability(
                    title=f"{visibility} record",
                    vuln_type="Prompt Injection",
                    severity="高危",
                    score=80,
                    affected_component="RAG",
                    description="same searchable evidence",
                    attack_method="prompt",
                    impact="leak",
                    mitigation="filter",
                    confidence=0.9,
                    status="未修复",
                    visibility=visibility,
                )
                db.add(vulnerability)
                db.flush()
                db.add(DocumentChunk(vulnerability_id=vulnerability.id, chunk_text="same searchable evidence", embedding=[1.0]))
            db.commit()

            with (
                patch("app.services.rag_service.embed_text", return_value=[1.0]),
                patch("app.services.rag_service.cosine_similarity", return_value=1.0),
            ):
                viewer_hits = search_similar(db, "same evidence", 10, role="viewer")
                analyst_hits = search_similar(db, "same evidence", 10, role="analyst")
                admin_hits = search_similar(db, "same evidence", 10, role="admin")

            self.assertEqual({hit["vulnerability"].visibility for hit in viewer_hits}, {"public"})
            self.assertEqual({hit["vulnerability"].visibility for hit in analyst_hits}, {"public", "internal"})
            self.assertEqual(
                {hit["vulnerability"].visibility for hit in admin_hits},
                {"public", "internal", "restricted"},
            )

            public_record = db.scalar(select(Vulnerability).where(Vulnerability.visibility == "public"))
            guest_payload = serialize_vulnerability_for_role(public_record, "guest")
            self.assertEqual(guest_payload["attack_method"], "访客模式不展示攻击复现细节。")
            self.assertIsNone(guest_payload["source_url"])
            self.assertEqual(guest_payload["confidence"], 0.0)

            query = "password=SecretValue123 find prompt injection"
            record_rag_audit(
                db,
                actor="viewer",
                role="viewer",
                action="search",
                query=query,
                top_k=10,
                hits=viewer_hits,
            )
            audit = db.scalar(select(RagQueryAudit))
            self.assertIsNotNone(audit)
            self.assertNotEqual(audit.query_hash, query)
            self.assertNotIn("SecretValue123", audit.query_excerpt)
            self.assertEqual(audit.hit_ids, [hit["vulnerability"].id for hit in viewer_hits])

    def test_every_critical_threat_is_marked_implemented(self):
        critical = [item for item in get_security_model()["threats"] if item["priority"] == "严重"]
        self.assertGreater(len(critical), 0)
        self.assertTrue(all(item["status"] == "已实施" for item in critical))


if __name__ == "__main__":
    unittest.main()
