import json
from datetime import datetime
from pathlib import Path

from fastapi import APIRouter, Depends, HTTPException
from sqlalchemy.orm import Session

from app.core.security import RequestIdentity, require_role
from app.db.models import AnalysisJob, ReviewAction, Vulnerability
from app.db.session import get_db
from app.evals.run_agent_eval import DATASET_PATH
from app.schemas.ai import (
    AnalyzeRequest,
    AnalyzeResult,
    AnalysisJobRead,
    ConfirmAnalysisRequest,
    ConfirmAnalysisResult,
    EvalDatasetRead,
    EvalRunDetailRead,
    EvalRunRead,
    ExtractRequest,
    ExtractResult,
    ProviderStatusRead,
    ReportRequest,
    ReportResult,
    ScoreRequest,
    ScoreResult,
)
from app.schemas.vulnerability import VulnerabilityCreate
from app.services.llm_service import LLMClient
from app.services.ops_service import list_eval_runs, run_eval_and_collect
from app.services.scoring_service import calculate_risk, explain_risk
from app.services.vulnerability_service import create_vulnerability, serialize_vulnerability
from app.workflows.vuln_analysis_graph import analyze_text, get_analysis_job_snapshot

router = APIRouter(prefix="/ai", tags=["ai"])


def _eval_output_dir() -> Path:
    return Path(__file__).resolve().parents[2] / "artifacts" / "evals"


def _load_eval_dataset() -> dict:
    samples = json.loads(DATASET_PATH.read_text(encoding="utf-8"))
    categories: dict[str, int] = {}
    positive = 0
    negative = 0
    for item in samples:
        expected = item.get("expected", {})
        if expected.get("is_ai_vulnerability"):
            positive += 1
            vuln_type = str(expected.get("vuln_type") or "Unlabeled Positive")
            categories[vuln_type] = categories.get(vuln_type, 0) + 1
        else:
            negative += 1
            categories["Negative / Noise"] = categories.get("Negative / Noise", 0) + 1
    return {
        "dataset_size": len(samples),
        "positive_samples": positive,
        "negative_samples": negative,
        "categories": categories,
        "samples": samples,
    }


def _load_eval_run_detail(file_name: str | None = None) -> dict | None:
    output_dir = _eval_output_dir()
    if not output_dir.exists():
        return None

    target_path = output_dir / file_name if file_name else None
    if file_name and not target_path.exists():
        return None

    if target_path is None:
        files = sorted(output_dir.glob("*.json"), key=lambda item: item.stat().st_mtime, reverse=True)
        if not files:
            return None
        target_path = files[0]

    payload = json.loads(target_path.read_text(encoding="utf-8"))
    summary = dict(payload.get("summary") or {})
    generated_at = datetime.fromtimestamp(target_path.stat().st_mtime).isoformat()
    return {
        "file_name": target_path.name,
        "provider": str(summary.get("provider", "unknown")),
        "dataset_size": int(summary.get("dataset_size", 0) or 0),
        "triage_accuracy": float(summary.get("triage_accuracy", 0.0) or 0.0),
        "triage_precision": float(summary.get("triage_precision", 0.0) or 0.0),
        "triage_recall": float(summary.get("triage_recall", 0.0) or 0.0),
        "extraction_completeness": float(summary.get("extraction_completeness", 0.0) or 0.0),
        "merge_precision": float(summary.get("merge_precision", 0.0) or 0.0),
        "generated_at": generated_at,
        "summary": summary,
        "samples": payload.get("samples", []),
    }


def _jsonable_snapshot(value):
    return json.loads(json.dumps(value, ensure_ascii=False, default=str))


@router.get("/provider-status", response_model=ProviderStatusRead)
def provider_status():
    return LLMClient().provider_status()


@router.post("/extract", response_model=ExtractResult)
async def extract_api(payload: ExtractRequest, db: Session = Depends(get_db)):
    state = await analyze_text(db, payload.raw_text, payload.source_url, save=False)
    extracted = dict(state["extracted_fields"])
    extracted["risk_reason"] = state.get("risk_reason", "")
    extracted["review_summary"] = state.get("review_summary", "")
    extracted["similar"] = [item["vulnerability"] for item in state.get("similar", [])]
    extracted["asset_impact_summary"] = state.get("asset_impact_summary", "")
    extracted["asset_impact_details"] = state.get("asset_impact_details", {})
    extracted["merge_suggestions"] = state.get("merge_suggestions", {})
    return extracted


@router.post("/analyze", response_model=AnalyzeResult)
async def analyze_api(payload: AnalyzeRequest, db: Session = Depends(get_db)):
    state = await analyze_text(db, payload.raw_text, payload.source_url, save=payload.save)
    vulnerability = None
    if state.get("vulnerability_id"):
        vulnerability = serialize_vulnerability(db.get(Vulnerability, state["vulnerability_id"]))

    extracted = dict(state["extracted_fields"])
    extracted["risk_reason"] = state.get("risk_reason", "")
    extracted["review_summary"] = state.get("review_summary", "")
    extracted["similar"] = [item["vulnerability"] for item in state.get("similar", [])]
    extracted["asset_impact_summary"] = state.get("asset_impact_summary", "")
    extracted["asset_impact_details"] = state.get("asset_impact_details", {})
    extracted["merge_suggestions"] = state.get("merge_suggestions", {})

    return {
        "relevance": state["relevance"],
        "extracted": extracted,
        "vulnerability": vulnerability,
        "report": state["report"],
        "analysis_job": get_analysis_job_snapshot(db, state["analysis_job_id"]),
    }


@router.post("/confirm", response_model=ConfirmAnalysisResult)
def confirm_analysis_api(
    payload: ConfirmAnalysisRequest,
    db: Session = Depends(get_db),
    identity: RequestIdentity = Depends(require_role("analyst")),
):
    job = db.get(AnalysisJob, payload.analysis_job_id)
    if not job:
        raise HTTPException(404, "analysis job not found")

    before_snapshot = dict(job.extracted_fields or {})
    vuln = create_vulnerability(db, payload.vulnerability, risk_reason=job.risk_reason or "")
    job.vulnerability_id = vuln.id
    db.add(
        ReviewAction(
            actor=identity.actor,
            target_type="analysis_job",
            target_id=job.id,
            action="confirm_to_vulnerability",
            before_snapshot=_jsonable_snapshot(before_snapshot),
            after_snapshot=_jsonable_snapshot(serialize_vulnerability(vuln)),
            reason=payload.review_note or "Confirmed after analyst review.",
        )
    )
    db.commit()
    db.refresh(job)

    return {
        "vulnerability": serialize_vulnerability(vuln),
        "analysis_job": get_analysis_job_snapshot(db, job.id),
    }


@router.get("/jobs/{analysis_job_id}", response_model=AnalysisJobRead)
def get_analysis_job(analysis_job_id: int, db: Session = Depends(get_db)):
    job = get_analysis_job_snapshot(db, analysis_job_id)
    if not job:
        raise HTTPException(404, "analysis job not found")
    return job


@router.get("/evaluation/dataset", response_model=EvalDatasetRead)
def evaluation_dataset(
    identity: RequestIdentity = Depends(require_role("viewer")),
):
    return _load_eval_dataset()


@router.get("/evaluation/runs", response_model=list[EvalRunRead])
def evaluation_runs(
    identity: RequestIdentity = Depends(require_role("viewer")),
):
    return list_eval_runs()


@router.get("/evaluation/runs/latest", response_model=EvalRunDetailRead | None)
def evaluation_latest_run(
    identity: RequestIdentity = Depends(require_role("viewer")),
):
    return _load_eval_run_detail()


@router.post("/evaluation/run", response_model=EvalRunDetailRead)
def evaluation_run_now(
    identity: RequestIdentity = Depends(require_role("admin")),
):
    run_eval_and_collect()
    detail = _load_eval_run_detail()
    if detail is None:
        raise HTTPException(500, "evaluation run did not produce an output file")
    return detail


@router.post("/score", response_model=ScoreResult)
def score_api(payload: ScoreRequest):
    score, severity, factors = calculate_risk(payload.vulnerability)
    return {
        "score": score,
        "severity": severity,
        "risk_reason": explain_risk(score, severity, factors),
        "key_risk_factors": factors,
        "suggested_priority": "立即修复" if score >= 81 else "高优先级" if score >= 61 else "常规排期",
    }


@router.post("/report", response_model=ReportResult)
def report_api(payload: ReportRequest):
    vulnerability: VulnerabilityCreate = payload.vulnerability
    report = (
        f"# {vulnerability.title}\n\n"
        f"## 风险概览\n- 类型：{vulnerability.vuln_type}\n- 等级：{vulnerability.severity}\n"
        f"- 评分：{vulnerability.score}\n- 组件：{vulnerability.affected_component}\n\n"
        f"## 描述\n{vulnerability.description}\n\n"
        f"## 攻击方式\n{vulnerability.attack_method}\n\n"
        f"## 影响\n{vulnerability.impact}\n\n"
        f"## 修复建议\n{vulnerability.mitigation}\n\n"
        f"## AI 分析\n{payload.risk_reason or '暂无补充分析。'}\n"
    )
    return {"report": report}
