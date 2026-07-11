from typing import Any, Literal, TypedDict

from langgraph.graph import END, START, StateGraph
from sqlalchemy.orm import Session

from app.schemas.vulnerability import VulnerabilityCreate
from app.services.llm_service import LLMClient
from app.services.rag_service import search_similar
from app.services.scoring_service import calculate_risk, explain_risk
from app.services.vulnerability_service import create_vulnerability


class VulnerabilityAnalysisState(TypedDict, total=False):
    source_url: str | None
    raw_text: str
    cleaned_text: str
    relevance: dict[str, Any]
    extracted_fields: dict[str, Any]
    score: int
    severity: str
    risk_reason: str
    similar: list[dict[str, Any]]
    report: str
    vulnerability_id: int | None
    errors: list[str]


def clean_text(text: str) -> str:
    return " ".join((text or "").replace("\r", " ").replace("\n", " ").split())[:12000]


def preprocess_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
    state["cleaned_text"] = clean_text(state["raw_text"])
    return state


async def relevance_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
    client = LLMClient()
    prompt = (
        "请判断下面的文本是否描述了与 AI 大模型、LLM 应用、Agent、RAG、模型插件、模型供应链或模型服务相关的安全漏洞。"
        "只输出 JSON，字段为：is_ai_vulnerability, confidence, related_area, reason。\n\n"
        f"候选文本：{state['cleaned_text']}"
    )
    state["relevance"] = await client.chat_json("你是一个 AI 安全情报筛选助手。", prompt)
    return state


def route_after_relevance(state: VulnerabilityAnalysisState) -> Literal["field_extract", "reject_non_vuln"]:
    relevance = state.get("relevance", {})
    if bool(relevance.get("is_ai_vulnerability")) and float(relevance.get("confidence", 0.0)) >= 0.5:
        return "field_extract"
    return "reject_non_vuln"


async def extract_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
    client = LLMClient()
    prompt = (
        "请从下面的漏洞描述中抽取结构化信息，只输出 JSON。"
        "不要编造原文中没有的信息，无法判断时填写 unknown。"
        '风险等级只能从 ["低危","中危","高危","严重"] 中选择。'
        "输出字段：title, vuln_type, affected_component, severity, description, attack_method, impact, mitigation, tags。\n\n"
        f"漏洞描述：{state['cleaned_text']}"
    )
    data = await client.chat_json("你是一个 AI 应用安全分析助手。", prompt)
    data.setdefault("source", None)
    data.setdefault("source_url", state.get("source_url"))
    data.setdefault("reference_url", state.get("source_url"))
    data.setdefault("confidence", state.get("relevance", {}).get("confidence", 0.0))
    data.setdefault("status", "未修复")
    data.setdefault("tags", [])
    state["extracted_fields"] = data
    return state


def reject_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
    relevance = state.get("relevance", {})
    reason = relevance.get("reason", "文本未体现明确的 AI 漏洞语义。")
    state["score"] = 0
    state["severity"] = "低危"
    state["risk_reason"] = reason
    state["extracted_fields"] = {
        "title": "未识别为 AI 漏洞",
        "vuln_type": "unknown",
        "severity": "低危",
        "score": 0,
        "affected_component": "unknown",
        "description": state.get("cleaned_text", ""),
        "attack_method": "unknown",
        "impact": "当前文本未被识别为 AI 漏洞情报，建议补充更多上下文后重试。",
        "mitigation": "请提供更完整的漏洞描述、攻击路径、影响组件或参考链接。",
        "source": None,
        "reference_url": state.get("source_url"),
        "source_url": state.get("source_url"),
        "confidence": float(relevance.get("confidence", 0.0)),
        "status": "待确认",
        "tags": ["needs-review"],
    }
    return state


def score_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
    score, severity, factors = calculate_risk(state["extracted_fields"])
    state["score"] = score
    state["severity"] = severity
    state["risk_reason"] = explain_risk(score, severity, factors)
    state["extracted_fields"]["score"] = score
    state["extracted_fields"]["severity"] = severity
    return state


def report_node(state: VulnerabilityAnalysisState) -> VulnerabilityAnalysisState:
    fields = state["extracted_fields"]
    state["report"] = f"""# {fields.get("title", "unknown")}

- 漏洞类型：{fields.get("vuln_type", "unknown")}
- 风险等级：{fields.get("severity", "unknown")}
- 风险评分：{fields.get("score", 0)}
- 影响组件：{fields.get("affected_component", "unknown")}

## 漏洞描述
{fields.get("description", "unknown")}

## 攻击方式
{fields.get("attack_method", "unknown")}

## 影响范围
{fields.get("impact", "unknown")}

## 修复建议
{fields.get("mitigation", "unknown")}

## AI 分析结论
{state.get("risk_reason", "")}
"""
    return state


def build_analysis_graph():
    graph = StateGraph(VulnerabilityAnalysisState)
    graph.add_node("preprocess", preprocess_node)
    graph.add_node("relevance_check", relevance_node)
    graph.add_node("field_extract", extract_node)
    graph.add_node("reject_non_vuln", reject_node)
    graph.add_node("risk_score", score_node)
    graph.add_node("report_generate", report_node)

    graph.add_edge(START, "preprocess")
    graph.add_edge("preprocess", "relevance_check")
    graph.add_conditional_edges(
        "relevance_check",
        route_after_relevance,
        {
            "field_extract": "field_extract",
            "reject_non_vuln": "reject_non_vuln",
        },
    )
    graph.add_edge("field_extract", "risk_score")
    graph.add_edge("risk_score", "report_generate")
    graph.add_edge("reject_non_vuln", "report_generate")
    graph.add_edge("report_generate", END)
    return graph.compile()


ANALYSIS_GRAPH = build_analysis_graph()


async def analyze_text(
    db: Session,
    raw_text: str,
    source_url: str | None = None,
    save: bool = False,
) -> VulnerabilityAnalysisState:
    state: VulnerabilityAnalysisState = {"raw_text": raw_text, "source_url": source_url, "errors": []}
    state = await ANALYSIS_GRAPH.ainvoke(state)
    state["similar"] = search_similar(db, state.get("cleaned_text", ""), 3)

    relevance = state.get("relevance", {})
    is_relevant = bool(relevance.get("is_ai_vulnerability")) and float(relevance.get("confidence", 0.0)) >= 0.5
    if save and is_relevant:
        payload = VulnerabilityCreate(**state["extracted_fields"])
        vuln = create_vulnerability(db, payload, state.get("risk_reason", ""))
        state["vulnerability_id"] = vuln.id

    return state
