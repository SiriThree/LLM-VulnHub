import unittest
from types import SimpleNamespace
from unittest.mock import AsyncMock, Mock, patch

from pydantic import ValidationError

from app.schemas.vulnerability import VulnerabilityCreate, VulnerabilityUpdate
from app.services.embedding_service import cosine_similarity, embed_texts, tokenize
from app.services.rag_service import MIN_RAG_SIMILARITY, ask, validate_answer_citations


class EmbeddingServiceTests(unittest.TestCase):
    def test_numeric_only_vulnerability_titles_are_rejected(self):
        with self.assertRaises(ValidationError):
            VulnerabilityCreate(title="123")
        with self.assertRaises(ValidationError):
            VulnerabilityUpdate(title=" 456 ")

    def test_tokenize_supports_security_terms_and_chinese_text(self):
        self.assertEqual(
            tokenize("Prompt Injection 与 RAG-Access_Control"),
            ["prompt", "injection", "与", "rag-access_control"],
        )

    def test_hash_fallback_returns_normalized_vectors(self):
        with patch("app.services.embedding_service.get_embedding_model", return_value=None):
            vectors = embed_texts(["prompt injection", "RAG 数据泄露"])

        self.assertEqual(len(vectors), 2)
        self.assertTrue(all(len(vector) == 384 for vector in vectors))
        self.assertTrue(all(abs(sum(value * value for value in vector) - 1.0) < 1e-4 for vector in vectors))

    def test_cosine_similarity_rejects_mismatched_dimensions(self):
        self.assertEqual(cosine_similarity([1.0, 0.0], [1.0]), 0.0)


class RagAnswerTests(unittest.IsolatedAsyncioTestCase):
    def test_citation_validation_maps_valid_numbers_and_removes_unknown_numbers(self):
        hits = [
            {"vulnerability": SimpleNamespace(id=41)},
            {"vulnerability": SimpleNamespace(id=73)},
        ]

        answer, cited_ids = validate_answer_citations(
            "First finding [2], duplicate [2], invalid [9].",
            hits,
        )

        self.assertEqual(cited_ids, [73])
        self.assertEqual(answer, "First finding [2], duplicate [2], invalid .")

    async def test_low_relevance_hits_are_not_sent_to_the_llm(self):
        low_relevance_hit = {
            "similarity": MIN_RAG_SIMILARITY - 0.01,
            "vulnerability": SimpleNamespace(id=1, title="Unrelated record"),
            "chunk_text": "unrelated evidence",
        }

        with (
            patch("app.services.rag_service.search_similar", return_value=[low_relevance_hit]),
            patch("app.services.rag_service.record_rag_audit") as audit,
            patch("app.services.rag_service.LLMClient.chat_text", new_callable=AsyncMock) as chat_text,
        ):
            result = await ask(
                Mock(),
                "How should RAG access be protected?",
                5,
                actor="analyst",
                role="analyst",
            )

        self.assertEqual(result["references"], [])
        self.assertEqual(result["cited_reference_ids"], [])
        self.assertIn("没有足够相关的记录", result["answer"])
        chat_text.assert_not_awaited()
        audit.assert_called_once()
        self.assertEqual(audit.call_args.kwargs["hits"], [])


if __name__ == "__main__":
    unittest.main()
