from __future__ import annotations

import hashlib
import json
from datetime import datetime, timezone
from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session, selectinload

from app.core.config import get_settings
from app.db.models import AgentExecution, AnalysisJob
from app.schemas.vulnerability import VulnerabilityCreate
from app.services.llm_service import LLMClient
from app.services.prompt_registry import PromptSpec, get_prompt_spec
from app.services.rag_service import search_similar
from app.services.scoring_service import calculate_risk
from app.services.vulnerability_service import create_vulnerability

PIPELINE_NAME = "vuln_analysis_v2"
PIPELINE_VERSION = "v2"


class VulnerabilityAnalysisState(TypedDict, total=False):
    analysis_job_id: int
    source_url: str | None
    raw_text: str
    cleaned_text: str
    relevance: dict[str, Any]
    extracted_fields: dict[str, Any]
    score: int
    severity: str
    risk_reason: str
    review_summary: str
    risk_priority: str
    similar: list[dict[str, Any]]
    merge_suggestions: dict[str, Any]
    asset_impact_summary: str
    asset_impact_details: dict[str, Any]
    report: str
    vulnerability_id: int | None
    errors: list[str]


def utcnow() -> datetime:
    return datetime.now(timezone.utc)


def ensure_aware(value: datetime | None) -> datetime | None:
    if value is None:
        return None
    if value.tzinfo is None:
        return value.replace(tzinfo=timezone.utc)
    return value


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\r", " ").replace("\n", " ").split())[:12000]


def content_hash(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def estimate_tokens(value: Any) -> int:
    if value is None:
        return 0
    text = value if isinstance(value, str) else json.dumps(value, ensure_ascii=False, default=str)
    return max(1, len(text) // 4)


def safe_similar_hits(db: Session, query: str, top_k: int = 3) -> list[dict[str, Any]]:
    hits = search_similar(db, query, top_k)
    result: list[dict[str, Any]] = []
    for hit in hits:
        vulnerability = hit["vulnerability"]
        vulnerability_data = vulnerability.model_dump(mode="json") if hasattr(vulnerability, "model_dump") else dict(vulnerability)
        result.append(
            {
                "vulnerability": vulnerability_data,
                "similarity": float(hit.get("similarity", 0.0)),
                "chunk_text": hit.get("chunk_text", "")[:400],
            }
        )
    return result


def create_analysis_job(db: Session, raw_text: str, source_url: str | None) -> AnalysisJob:
    client = LLMClient()
    provider = client._provider_config()  # noqa: SLF001
    job = AnalysisJob(
        pipeline_name=PIPELINE_NAME,
        pipeline_version=PIPELINE_VERSION,
        status="running",
        source_url=source_url,
        raw_text_hash=content_hash(raw_text),
        raw_text_excerpt=clean_text(raw_text)[:1200],
        provider_name=provider.name,
        model_name=client.model_name,
        started_at=utcnow(),
    )
    db.add(job)
    db.commit()
    db.refresh(job)
    return job


def finalize_analysis_job(db: Session, state: VulnerabilityAnalysisState, status: str, error_message: str | None = None) -> None:
    job = db.get(AnalysisJob, state["analysis_job_id"])
    if not job:
        return
    job.status = status
    job.relevance = state.get("relevance", {})
    job.extracted_fields = state.get("extracted_fields", {})
    job.similar_snapshot = state.get("similar", [])
    job.asset_impact_summary = state.get("asset_impact_summary", "")
    job.asset_impact_details = state.get("asset_impact_details", {})
    job.score = state.get("score")
    job.severity = state.get("severity")
    job.risk_reason = state.get("risk_reason", "")
    job.review_summary = state.get("review_summary", "")
    job.report = state.get("report", "")
    job.vulnerability_id = state.get("vulnerability_id")
    job.error_message = error_message
    job.finished_at = utcnow()
    db.commit()


def create_agent_execution(
    db: Session,
    state: VulnerabilityAnalysisState,
    *,
    agent_name: str,
    stage_name: str,
    provider_name: str | None,
    model_name: str | None,
    prompt_version: str,
    input_payload: dict[str, Any],
) -> AgentExecution:
    execution = AgentExecution(
        analysis_job_id=state["analysis_job_id"],
        agent_name=agent_name,
        stage_name=stage_name,
        status="running",
        provider_name=provider_name,
        model_name=model_name,
        prompt_version=prompt_version,
        input_payload=input_payload,
        started_at=utcnow(),
    )
    db.add(execution)
    db.commit()
    db.refresh(execution)
    return execution


def complete_agent_execution(
    db: Session,
    execution: AgentExecution,
    *,
    output_payload: dict[str, Any],
    retry_count: int,
    error_message: str | None = None,
) -> None:
    execution.status = "failed" if error_message else "completed"
    execution.output_payload = output_payload
    execution.retry_count = retry_count
    execution.error_message = error_message
    execution.finished_at = utcnow()
    started_at = ensure_aware(execution.started_at)
    finished_at = ensure_aware(execution.finished_at)
    execution.latency_ms = int((finished_at - started_at).total_seconds() * 1000) if started_at and finished_at else 0
    execution.prompt_tokens = estimate_tokens(execution.input_payload)
    execution.completion_tokens = estimate_tokens(output_payload)
    execution.total_tokens = (execution.prompt_tokens or 0) + (execution.completion_tokens or 0)
    db.commit()


def missing_required_keys(payload: dict[str, Any], required_keys: tuple[str, ...]) -> list[str]:
    missing: list[str] = []
    for key in required_keys:
        value = payload.get(key)
        if value is None:
            missing.append(key)
        elif isinstance(value, str) and not value.strip():
            missing.append(key)
    return missing


async def run_json_agent(
    db: Session,
    state: VulnerabilityAnalysisState,
    *,
    stage_name: str,
    prompt_spec: PromptSpec,
    user_prompt: str,
    fallback_output: dict[str, Any],
) -> dict[str, Any]:
    settings = get_settings()
    client = LLMClient()
    provider = client._provider_config()  # noqa: SLF001
    input_payload = {
        "prompt_key": prompt_spec.key,
        "system_prompt": prompt_spec.system_prompt,
        "user_prompt": user_prompt,
        "required_keys": list(prompt_spec.required_keys),
        "max_attempts": settings.agent_max_attempts,
    }
    execution = create_agent_execution(
        db,
        state,
        agent_name=prompt_spec.agent_name,
        stage_name=stage_name,
        provider_name=provider.name,
        model_name=client.model_name,
        prompt_version=prompt_spec.version,
        input_payload=input_payload,
    )

    last_error = ""
    validation_errors: list[dict[str, Any]] = []

    for attempt in range(1, settings.agent_max_attempts + 1):
        try:
            output = await client.chat_json(prompt_spec.system_prompt, user_prompt)
            missing = missing_required_keys(output, prompt_spec.required_keys)
            if missing:
                last_error = f"Missing required keys: {', '.join(missing)}"
                validation_errors.append({"attempt": attempt, "error": last_error, "output": output})
                continue
            output["_meta"] = {
                "attempt_count": attempt,
                "prompt_key": prompt_spec.key,
                "prompt_version": prompt_spec.version,
            }
            complete_agent_execution(db, execution, output_payload=output, retry_count=attempt)
            return output
        except Exception as exc:
            last_error = str(exc)
            validation_errors.append({"attempt": attempt, "error": last_error})

    fallback = {
        **fallback_output,
        "_meta": {
            "attempt_count": settings.agent_max_attempts,
            "prompt_key": prompt_spec.key,
            "prompt_version": prompt_spec.version,
            "fallback": True,
        },
        "fallback_reason": last_error or "agent validation failed",
        "validation_errors": validation_errors,
    }
    state.setdefault("errors", []).append(f"{prompt_spec.agent_name}: {fallback['fallback_reason']}")
    complete_agent_execution(
        db,
        execution,
        output_payload=fallback,
        retry_count=settings.agent_max_attempts,
        error_message=fallback["fallback_reason"],
    )
    return fallback


def preprocess_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
    state["cleaned_text"] = clean_text(state["raw_text"])
    return state


def route_after_triage(state: VulnerabilityAnalysisState) -> Literal["extract_agent", "reject_non_vuln"]:
    relevance = state.get("relevance", {})
    if bool(relevance.get("is_ai_vulnerability")) and float(relevance.get("confidence", 0.0)) >= 0.45:
        return "extract_agent"
    return "reject_non_vuln"


def reject_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
    reason = state.get("relevance", {}).get("reason", "The text does not contain enough evidence of AI vulnerability intelligence.")
    state["score"] = 0
    state["severity"] = "低危"
    state["risk_reason"] = reason
    state["review_summary"] = "Reviewer Agent was skipped because triage did not classify this text as an AI vulnerability."
    state["asset_impact_summary"] = "No asset impact analysis was produced because the text was not classified as AI vulnerability intelligence."
    state["asset_impact_details"] = {
        "impacted_assets": [],
        "tenant_scope": "none",
        "blast_radius": "none",
        "operational_risk": "low",
        "asset_summary": state["asset_impact_summary"],
    }
    state["extracted_fields"] = {
        "title": "未识别为 AI 漏洞",
        "vuln_type": "unknown",
        "severity": "低危",
        "score": 0,
        "affected_component": "unknown",
        "description": state.get("cleaned_text", ""),
        "attack_method": "unknown",
        "impact": "当前文本未被识别为 AI 漏洞情报，建议补充更多上下文后重试。",
        "mitigation": "补充漏洞触发条件、攻击路径、受影响组件或参考链接。",
        "source": None,
        "reference_url": state.get("source_url"),
        "source_url": state.get("source_url"),
        "confidence": float(state.get("relevance", {}).get("confidence", 0.0)),
        "status": "待确认",
        "tags": ["needs-review"],
    }
    state["similar"] = []
    state["merge_suggestions"] = {"should_merge": False, "candidate_ids": [], "reason": "Not applicable for non-vulnerability text."}
    return state


def report_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
    fields = state["extracted_fields"]
    similar_lines = [
        f"- #{item.get('vulnerability', {}).get('id')} {item.get('vulnerability', {}).get('title')} (similarity {item.get('similarity', 0)})"
        for item in state.get("similar", [])
    ]
    similar_text = "\n".join(similar_lines) if similar_lines else "- No strong canonical match found."
    state["report"] = (
        f"# {fields.get('title', 'unknown')}\n\n"
        f"- Type: {fields.get('vuln_type', 'unknown')}\n"
        f"- Severity: {state.get('severity', fields.get('severity', 'unknown'))}\n"
        f"- Score: {state.get('score', fields.get('score', 0))}\n"
        f"- Affected component: {fields.get('affected_component', 'unknown')}\n"
        f"- Priority: {state.get('risk_priority', 'P2')}\n\n"
        f"## Description\n{fields.get('description', 'unknown')}\n\n"
        f"## Attack Method\n{fields.get('attack_method', 'unknown')}\n\n"
        f"## Impact\n{fields.get('impact', 'unknown')}\n\n"
        f"## Mitigation\n{fields.get('mitigation', 'unknown')}\n\n"
        f"## Merge Suggestions\n{similar_text}\n\n"
        f"## Risk Explanation Agent\n{state.get('risk_reason', '')}\n\n"
        f"## Asset Impact Agent\n{state.get('asset_impact_summary', '')}\n\n"
        f"## Reviewer Agent\n{state.get('review_summary', '')}\n"
    )
    return state


def build_analysis_graph(db: Session):
    triage_prompt = get_prompt_spec("triage_v2")
    extraction_prompt = get_prompt_spec("extraction_v2")
    merge_prompt = get_prompt_spec("merge_v2")
    risk_prompt = get_prompt_spec("risk_v2")
    asset_prompt = get_prompt_spec("asset_impact_v2")
    reviewer_prompt = get_prompt_spec("reviewer_v2")

    async def triage_agent_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
        user_prompt = triage_prompt.render(text=state["cleaned_text"])
        fallback = {
            "is_ai_vulnerability": False,
            "confidence": 0.0,
            "related_area": "unknown",
            "reason": "The triage agent could not confirm that this text is AI vulnerability intelligence.",
        }
        state["relevance"] = await run_json_agent(db, state, stage_name="triage", prompt_spec=triage_prompt, user_prompt=user_prompt, fallback_output=fallback)
        return state

    async def extraction_agent_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
        user_prompt = extraction_prompt.render(text=state["cleaned_text"])
        fallback = {
            "title": "AI vulnerability pending review",
            "vuln_type": state.get("relevance", {}).get("related_area", "unknown"),
            "affected_component": "unknown",
            "severity": "中危",
            "description": state["cleaned_text"][:500],
            "attack_method": "unknown",
            "impact": "unknown",
            "mitigation": "unknown",
            "tags": ["needs-review"],
        }
        data = await run_json_agent(db, state, stage_name="extract", prompt_spec=extraction_prompt, user_prompt=user_prompt, fallback_output=fallback)
        data.setdefault("source", None)
        data.setdefault("source_url", state.get("source_url"))
        data.setdefault("reference_url", state.get("source_url"))
        data.setdefault("confidence", float(state.get("relevance", {}).get("confidence", 0.0)))
        data.setdefault("status", "待确认")
        data.setdefault("tags", [])
        state["extracted_fields"] = data
        return state

    async def merge_agent_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
        hits = safe_similar_hits(db, state.get("cleaned_text", ""), 3)
        state["similar"] = hits
        if not hits:
            state["merge_suggestions"] = {
                "should_merge": False,
                "candidate_ids": [],
                "reason": "No similar published vulnerabilities were found.",
                "confidence": 0.0,
            }
            return state

        candidates_summary = "\n\n".join(
            f"ID: {item['vulnerability']['id']}\nTitle: {item['vulnerability']['title']}\nType: {item['vulnerability']['vuln_type']}\nSimilarity: {item['similarity']}\nEvidence: {item['chunk_text']}"
            for item in hits
        )
        user_prompt = merge_prompt.render(
            intel=json.dumps(state.get("extracted_fields", {}), ensure_ascii=False, default=str),
            candidates=candidates_summary,
        )
        fallback = {
            "should_merge": False,
            "candidate_ids": [],
            "reason": "Similar items were found, but the merge agent could not confirm a canonical match.",
            "confidence": 0.0,
        }
        state["merge_suggestions"] = await run_json_agent(db, state, stage_name="merge", prompt_spec=merge_prompt, user_prompt=user_prompt, fallback_output=fallback)
        return state

    async def risk_agent_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
        score, severity, factors = calculate_risk(state["extracted_fields"])
        state["score"] = score
        state["severity"] = severity
        state["extracted_fields"]["score"] = score
        state["extracted_fields"]["severity"] = severity
        user_prompt = risk_prompt.render(
            vulnerability=json.dumps(state["extracted_fields"], ensure_ascii=False, default=str),
            factors=json.dumps(factors, ensure_ascii=False),
            score=str(score),
            severity=severity,
        )
        fallback = {
            "risk_reason": f"Rule-based score is {score}, mapped to {severity}. Key factors: {'; '.join(factors)}.",
            "priority": "P0" if score >= 85 else "P1" if score >= 70 else "P2" if score >= 40 else "P3",
            "analyst_notes": "Generated by the fallback rule engine.",
        }
        risk_result = await run_json_agent(db, state, stage_name="risk", prompt_spec=risk_prompt, user_prompt=user_prompt, fallback_output=fallback)
        state["risk_reason"] = str(risk_result.get("risk_reason", fallback["risk_reason"]))
        state["risk_priority"] = str(risk_result.get("priority", fallback["priority"]))
        return state

    async def asset_impact_agent_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
        user_prompt = asset_prompt.render(
            vulnerability=json.dumps(state.get("extracted_fields", {}), ensure_ascii=False, default=str),
            risk_reason=state.get("risk_reason", ""),
        )
        fallback = {
            "impacted_assets": ["LLM application runtime", "retrieval pipeline", "tool execution boundary"],
            "tenant_scope": "single-tenant or cross-tenant depending on deployment isolation",
            "blast_radius": "application-level",
            "operational_risk": "medium",
            "asset_summary": "The issue primarily affects the AI application layer, its retrieval path, and tool execution boundary. Blast radius depends on tenant isolation and permission design.",
        }
        asset_result = await run_json_agent(db, state, stage_name="asset_impact", prompt_spec=asset_prompt, user_prompt=user_prompt, fallback_output=fallback)
        state["asset_impact_summary"] = str(asset_result.get("asset_summary", fallback["asset_summary"]))
        state["asset_impact_details"] = {
            "impacted_assets": asset_result.get("impacted_assets", fallback["impacted_assets"]),
            "tenant_scope": asset_result.get("tenant_scope", fallback["tenant_scope"]),
            "blast_radius": asset_result.get("blast_radius", fallback["blast_radius"]),
            "operational_risk": asset_result.get("operational_risk", fallback["operational_risk"]),
            "asset_summary": state["asset_impact_summary"],
        }
        return state

    async def reviewer_agent_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
        if state.get("extracted_fields", {}).get("title") == "未识别为 AI 漏洞":
            return state
        user_prompt = reviewer_prompt.render(
            vulnerability=json.dumps(state.get("extracted_fields", {}), ensure_ascii=False, default=str),
            merge=json.dumps(state.get("merge_suggestions", {}), ensure_ascii=False, default=str),
            risk_reason=state.get("risk_reason", ""),
        )
        fallback = {
            "publishable": False,
            "review_status": "needs_review",
            "review_summary": "The record is structurally complete enough for triage, but should remain in manual review before publishing.",
            "missing_fields": [],
        }
        review_result = await run_json_agent(db, state, stage_name="review", prompt_spec=reviewer_prompt, user_prompt=user_prompt, fallback_output=fallback)
        state["review_summary"] = str(review_result.get("review_summary", fallback["review_summary"]))
        state["extracted_fields"]["status"] = "已分析" if review_result.get("publishable") else "待人工复核"
        return state

    graph = StateGraph(VulnerabilityAnalysisState)
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("triage_agent", triage_agent_node)
    graph.add_node("extract_agent", extraction_agent_node)
    graph.add_node("reject_non_vuln", reject_node)
    graph.add_node("merge_agent", merge_agent_node)
    graph.add_node("risk_agent", risk_agent_node)
    graph.add_node("asset_impact_agent", asset_impact_agent_node)
    graph.add_node("reviewer_agent", reviewer_agent_node)
    graph.add_node("report_generate", report_node)

    graph.add_edge(START, "preprocess")
    graph.add_edge("preprocess", "triage_agent")
    graph.add_conditional_edges("triage_agent", route_after_triage, {"extract_agent": "extract_agent", "reject_non_vuln": "reject_non_vuln"})
    graph.add_edge("extract_agent", "merge_agent")
    graph.add_edge("merge_agent", "risk_agent")
    graph.add_edge("risk_agent", "asset_impact_agent")
    graph.add_edge("asset_impact_agent", "reviewer_agent")
    graph.add_edge("reviewer_agent", "report_generate")
    graph.add_edge("reject_non_vuln", "report_generate")
    graph.add_edge("report_generate", END)
    return graph.compile()


def get_analysis_job_snapshot(db: Session, analysis_job_id: int) -> dict[str, Any] | None:
    job = db.query(AnalysisJob).options(selectinload(AnalysisJob.agent_executions)).filter(AnalysisJob.id == analysis_job_id).first()
    if not job:
        return None
    return {
        "id": job.id,
        "pipeline_name": job.pipeline_name,
        "pipeline_version": job.pipeline_version,
        "status": job.status,
        "source_url": job.source_url,
        "raw_text_hash": job.raw_text_hash,
        "raw_text_excerpt": job.raw_text_excerpt,
        "provider_name": job.provider_name,
        "model_name": job.model_name,
        "relevance": job.relevance or {},
        "extracted_fields": job.extracted_fields or {},
        "similar_snapshot": job.similar_snapshot or [],
        "asset_impact_summary": job.asset_impact_summary or "",
        "asset_impact_details": job.asset_impact_details or {},
        "score": job.score,
        "severity": job.severity,
        "risk_reason": job.risk_reason or "",
        "review_summary": job.review_summary or "",
        "report": job.report or "",
        "error_message": job.error_message,
        "started_at": job.started_at.isoformat() if job.started_at else None,
        "finished_at": job.finished_at.isoformat() if job.finished_at else None,
        "agent_executions": [
            {
                "id": execution.id,
                "agent_name": execution.agent_name,
                "stage_name": execution.stage_name,
                "status": execution.status,
                "provider_name": execution.provider_name,
                "model_name": execution.model_name,
                "prompt_version": execution.prompt_version,
                "retry_count": execution.retry_count,
                "latency_ms": execution.latency_ms,
                "prompt_tokens": execution.prompt_tokens,
                "completion_tokens": execution.completion_tokens,
                "total_tokens": execution.total_tokens,
                "input_payload": execution.input_payload or {},
                "output_payload": execution.output_payload or {},
                "error_message": execution.error_message,
                "started_at": execution.started_at.isoformat() if execution.started_at else None,
                "finished_at": execution.finished_at.isoformat() if execution.finished_at else None,
            }
            for execution in sorted(job.agent_executions, key=lambda item: item.id)
        ],
    }


async def analyze_text(db: Session, raw_text: str, source_url: str | None = None, save: bool = False) -> VulnerabilityAnalysisState:
    job = create_analysis_job(db, raw_text, source_url)
    state: VulnerabilityAnalysisState = {
        "analysis_job_id": job.id,
        "raw_text": raw_text,
        "source_url": source_url,
        "errors": [],
    }
    analysis_graph = build_analysis_graph(db)

    try:
        state = await analysis_graph.ainvoke(state)
        relevance = state.get("relevance", {})
        is_relevant = bool(relevance.get("is_ai_vulnerability")) and float(relevance.get("confidence", 0.0)) >= 0.45
        if save and is_relevant:
            payload = VulnerabilityCreate(**state["extracted_fields"])
            vulnerability = create_vulnerability(db, payload, state.get("risk_reason", ""))
            state["vulnerability_id"] = vulnerability.id
            persisted_job = db.get(AnalysisJob, job.id)
            if persisted_job:
                persisted_job.vulnerability_id = vulnerability.id
                db.commit()
        finalize_analysis_job(db, state, "completed")
    except Exception as exc:
        state.setdefault("errors", []).append(str(exc))
        finalize_analysis_job(db, state, "failed", str(exc))
        raise

    return state
