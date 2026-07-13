from __future__ import annotations

import argparse
import asyncio
import json
import os
from dataclasses import dataclass
from pathlib import Path
from typing import Any

from sqlalchemy import select

from app.db.models import Vulnerability
from app.db.runtime_schema import ensure_runtime_schema
from app.db.session import SessionLocal, engine
from app.schemas.vulnerability import VulnerabilityCreate
from app.services.scoring_service import calculate_risk, explain_risk
from app.services.vulnerability_service import create_vulnerability
from app.workflows.vuln_analysis_graph import analyze_text

DATASET_PATH = Path(__file__).with_name("agent_eval_dataset.json")
EXTRACTION_FIELDS = ("vuln_type", "severity", "affected_component")
COMPLETENESS_FIELDS = ("title", "vuln_type", "severity", "affected_component", "description", "attack_method", "impact", "mitigation")

CANONICAL_VULNS = [
    {
        "title": "Canonical Prompt Injection via Tool Output",
        "vuln_type": "Prompt Injection",
        "severity": "高危",
        "affected_component": "LLM Agent / Tool Calling",
        "description": "Untrusted tool output is injected into the next model turn without boundary isolation.",
        "attack_method": "Attacker controls browser or tool output to insert hidden instructions.",
        "impact": "Prompt leakage and unauthorized tool execution become possible.",
        "mitigation": "Treat tool output as untrusted data and separate it from system instructions.",
        "source_url": "eval://canonical/prompt-injection-tool-output",
    },
    {
        "title": "Canonical RAG Permission Bypass",
        "vuln_type": "RAG Data Leakage",
        "severity": "高危",
        "affected_component": "RAG Retriever / Document Store",
        "description": "Semantic retrieval happens before authorization checks are enforced.",
        "attack_method": "Low-privilege users craft queries that return protected chunks.",
        "impact": "Cross-tenant or protected document disclosure.",
        "mitigation": "Apply ACL filters before retrieval and bind search to user identity.",
        "source_url": "eval://canonical/rag-permission-bypass",
    },
    {
        "title": "Canonical Plugin Supply Chain Risk",
        "vuln_type": "Plugin Supply Chain Risk",
        "severity": "严重",
        "affected_component": "Plugin Permission Broker",
        "description": "Third-party capability updates are loaded without integrity verification.",
        "attack_method": "A malicious dependency or manifest update expands scope and exfiltrates data.",
        "impact": "Unauthorized capability expansion and data exfiltration.",
        "mitigation": "Pin versions, verify signatures, and review permission changes.",
        "source_url": "eval://canonical/plugin-supply-chain",
    },
    {
        "title": "Canonical Evaluation Artifact Exposure",
        "vuln_type": "Training / Evaluation Data Exposure",
        "severity": "中危",
        "affected_component": "Evaluation Artifact Pipeline",
        "description": "Benchmark prompts and model traces are exported without proper review.",
        "attack_method": "Operators share raw evaluation bundles containing private prompt content.",
        "impact": "Internal evaluation assets and prompts can leak.",
        "mitigation": "Redact trace bundles and review export permissions.",
        "source_url": "eval://canonical/eval-artifact-exposure",
    },
]


@dataclass
class SampleResult:
    sample_id: str
    expected_ai: bool
    predicted_ai: bool
    triage_correct: bool
    extraction_exact: dict[str, bool]
    extraction_completeness: float | None
    merge_correct: bool | None
    confidence: float
    errors: list[str]


def load_dataset(path: Path) -> list[dict[str, Any]]:
    return json.loads(path.read_text(encoding="utf-8"))


def is_meaningful(value: Any) -> bool:
    if value is None:
        return False
    if isinstance(value, str):
        normalized = value.strip().lower()
        return normalized not in {"", "unknown", "n/a", "none"}
    if isinstance(value, list):
        return len(value) > 0
    return True


def normalize_text(value: Any) -> str:
    return str(value or "").strip().lower()


def ensure_eval_canonical_vulnerabilities() -> None:
    with SessionLocal() as db:
        for item in CANONICAL_VULNS:
            exists = db.scalar(select(Vulnerability).where(Vulnerability.source_url == item["source_url"]))
            if exists:
                continue
            payload = VulnerabilityCreate(
                title=item["title"],
                vuln_type=item["vuln_type"],
                severity=item["severity"],
                score=0,
                affected_component=item["affected_component"],
                description=item["description"],
                attack_method=item["attack_method"],
                impact=item["impact"],
                mitigation=item["mitigation"],
                source="eval",
                reference_url=item["source_url"],
                source_url=item["source_url"],
                confidence=0.99,
                status="未修复",
                tags=[item["vuln_type"], "eval"],
            )
            score, severity, factors = calculate_risk(payload)
            payload.score = score
            payload.severity = severity
            create_vulnerability(db, payload, explain_risk(score, severity, factors))


async def evaluate_sample(sample: dict[str, Any]) -> SampleResult:
    with SessionLocal() as db:
        state = await analyze_text(db, sample["raw_text"], source_url=None, save=False)

    expected = sample["expected"]
    relevance = state.get("relevance", {})
    extracted = state.get("extracted_fields", {})
    merge_suggestions = state.get("merge_suggestions", {})

    predicted_ai = bool(relevance.get("is_ai_vulnerability")) and float(relevance.get("confidence", 0.0)) >= 0.45
    expected_ai = bool(expected["is_ai_vulnerability"])

    extraction_exact: dict[str, bool] = {}
    completeness = None

    if expected_ai:
        for field in EXTRACTION_FIELDS:
            extraction_exact[field] = normalize_text(extracted.get(field)) == normalize_text(expected.get(field))
        present_count = sum(1 for field in COMPLETENESS_FIELDS if is_meaningful(extracted.get(field)))
        completeness = present_count / len(COMPLETENESS_FIELDS)

    merge_expected = expected.get("merge_should_merge")
    merge_correct = None
    if merge_expected is not None:
        merge_correct = bool(merge_suggestions.get("should_merge")) == bool(merge_expected)

    return SampleResult(
        sample_id=sample["id"],
        expected_ai=expected_ai,
        predicted_ai=predicted_ai,
        triage_correct=predicted_ai == expected_ai,
        extraction_exact=extraction_exact,
        extraction_completeness=completeness,
        merge_correct=merge_correct,
        confidence=float(relevance.get("confidence", 0.0)),
        errors=list(state.get("errors", [])),
    )


def summarize(results: list[SampleResult]) -> dict[str, Any]:
    total = len(results)
    triage_correct = sum(1 for item in results if item.triage_correct)
    positives = [item for item in results if item.expected_ai]
    true_positive = sum(1 for item in results if item.expected_ai and item.predicted_ai)
    false_positive = sum(1 for item in results if (not item.expected_ai) and item.predicted_ai)
    false_negative = sum(1 for item in results if item.expected_ai and (not item.predicted_ai))

    precision = true_positive / (true_positive + false_positive) if (true_positive + false_positive) else 0.0
    recall = true_positive / (true_positive + false_negative) if (true_positive + false_negative) else 0.0

    field_scores: dict[str, float] = {}
    for field in EXTRACTION_FIELDS:
        field_scores[field] = sum(1 for item in positives if item.extraction_exact.get(field, False)) / len(positives) if positives else 0.0

    completeness_values = [item.extraction_completeness for item in positives if item.extraction_completeness is not None]
    avg_completeness = sum(completeness_values) / len(completeness_values) if completeness_values else 0.0

    merge_labeled = [item for item in results if item.merge_correct is not None]
    merge_precision = sum(1 for item in merge_labeled if item.merge_correct) / len(merge_labeled) if merge_labeled else 0.0

    return {
        "provider": os.getenv("LLM_PROVIDER", "mock"),
        "dataset_size": total,
        "positive_samples": len(positives),
        "triage_accuracy": triage_correct / total if total else 0.0,
        "triage_precision": precision,
        "triage_recall": recall,
        "extraction_field_exact_match": field_scores,
        "extraction_completeness": avg_completeness,
        "merge_precision": merge_precision,
    }


async def run_eval(dataset_path: Path, verbose: bool, output_path: Path | None) -> int:
    ensure_runtime_schema(engine)
    ensure_eval_canonical_vulnerabilities()
    dataset = load_dataset(dataset_path)
    results = [await evaluate_sample(sample) for sample in dataset]
    summary = summarize(results)

    print("== LLM-VulnHub Agent Evaluation ==")
    print(json.dumps(summary, ensure_ascii=False, indent=2))

    if verbose:
        print("\n== Per Sample ==")
        for item in results:
            print(
                json.dumps(
                    {
                        "id": item.sample_id,
                        "expected_ai": item.expected_ai,
                        "predicted_ai": item.predicted_ai,
                        "triage_correct": item.triage_correct,
                        "confidence": item.confidence,
                        "extraction_exact": item.extraction_exact,
                        "extraction_completeness": item.extraction_completeness,
                        "merge_correct": item.merge_correct,
                        "errors": item.errors,
                    },
                    ensure_ascii=False,
                )
            )

    if output_path is not None:
        payload = {
            "summary": summary,
            "samples": [
                {
                    "id": item.sample_id,
                    "expected_ai": item.expected_ai,
                    "predicted_ai": item.predicted_ai,
                    "triage_correct": item.triage_correct,
                    "confidence": item.confidence,
                    "extraction_exact": item.extraction_exact,
                    "extraction_completeness": item.extraction_completeness,
                    "merge_correct": item.merge_correct,
                    "errors": item.errors,
                }
                for item in results
            ],
        }
        output_path.parent.mkdir(parents=True, exist_ok=True)
        output_path.write_text(json.dumps(payload, ensure_ascii=False, indent=2), encoding="utf-8")

    return 0


def main() -> int:
    parser = argparse.ArgumentParser(description="Run labeled evaluation for the LLM-VulnHub multi-agent workflow.")
    parser.add_argument("--dataset", type=Path, default=DATASET_PATH, help="Path to the labeled evaluation dataset JSON file.")
    parser.add_argument("--verbose", action="store_true", help="Print per-sample evaluation details.")
    parser.add_argument("--output", type=Path, default=None, help="Optional path to save the evaluation result as JSON.")
    args = parser.parse_args()
    return asyncio.run(run_eval(args.dataset, args.verbose, args.output))


if __name__ == "__main__":
    raise SystemExit(main())
