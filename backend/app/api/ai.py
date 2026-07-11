from fastapi import APIRouter, Depends
from sqlalchemy.orm import Session

from app.db.session import get_db
from app.schemas.ai import AnalyzeRequest, AnalyzeResult, ExtractRequest, ExtractResult, ReportRequest, ReportResult, ScoreRequest, ScoreResult
from app.schemas.vulnerability import VulnerabilityCreate
from app.services.scoring_service import calculate_risk, explain_risk
from app.services.vulnerability_service import serialize_vulnerability
from app.workflows.vuln_analysis_graph import analyze_text

router = APIRouter(prefix="/ai", tags=["ai"])


@router.post("/extract", response_model=ExtractResult)
async def extract_api(payload: ExtractRequest, db: Session = Depends(get_db)):
    state = await analyze_text(db, payload.raw_text, payload.source_url, save=False)
    extracted = dict(state["extracted_fields"])
    extracted["risk_reason"] = state.get("risk_reason", "")
    extracted["similar"] = [h["vulnerability"] for h in state.get("similar", [])]
    return extracted


@router.post("/analyze", response_model=AnalyzeResult)
async def analyze_api(payload: AnalyzeRequest, db: Session = Depends(get_db)):
    state = await analyze_text(db, payload.raw_text, payload.source_url, save=payload.save)
    vulnerability = None
    if state.get("vulnerability_id"):
        from app.db.models import Vulnerability

        vulnerability = serialize_vulnerability(db.get(Vulnerability, state["vulnerability_id"]))
    extracted = dict(state["extracted_fields"])
    extracted["risk_reason"] = state.get("risk_reason", "")
    extracted["similar"] = [h["vulnerability"] for h in state.get("similar", [])]
    return {"relevance": state["relevance"], "extracted": extracted, "vulnerability": vulnerability, "report": state["report"]}


@router.post("/score", response_model=ScoreResult)
def score_api(payload: ScoreRequest):
    score, severity, factors = calculate_risk(payload.vulnerability)
    return {"score": score, "severity": severity, "risk_reason": explain_risk(score, severity, factors), "key_risk_factors": factors, "suggested_priority": "立即修复" if score >= 81 else "高优先级" if score >= 61 else "常规排期"}


@router.post("/report", response_model=ReportResult)
def report_api(payload: ReportRequest):
    v: VulnerabilityCreate = payload.vulnerability
    report = f"# {v.title}\n\n## 风险概览\n- 类型：{v.vuln_type}\n- 等级：{v.severity}\n- 评分：{v.score}\n- 组件：{v.affected_component}\n\n## 描述\n{v.description}\n\n## 攻击方式\n{v.attack_method}\n\n## 影响\n{v.impact}\n\n## 修复建议\n{v.mitigation}\n\n## AI 分析\n{payload.risk_reason or '暂无补充分析。'}\n"
    return {"report": report}
