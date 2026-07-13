from app.schemas.vulnerability import VulnerabilityCreate


SEVERITY_BASE = {"低危": 10, "中危": 25, "高危": 40, "严重": 55}
SENSITIVE_TERMS = [
    "泄露",
    "敏感",
    "secret",
    "token",
    "key",
    "credential",
    "knowledge",
    "system prompt",
    "prompt",
]
REMOTE_TERMS = ["remote", "web", "browser", "external", "retriever", "api", "plugin", "public"]
POC_TERMS = ["poc", "exploit", "payload", "attacker can", "reproduce"]
CORE_TERMS = ["agent", "rag", "tool", "plugin", "gateway", "retriever", "document store", "model routing"]
FIX_UNKNOWN_TERMS = ["unknown", "not provided", "unclear", "n/a"]
CRITICAL_TERMS = ["supply chain", "ssrf", "system prompt exposure", "authorization bypass", "越权"]
LOW_RISK_TERMS = ["telemetry", "routing", "trace", "debug", "benchmark", "evaluation", "viewer", "render"]


def severity_from_score(score: int) -> str:
    if score <= 30:
        return "低危"
    if score <= 60:
        return "中危"
    if score <= 80:
        return "高危"
    return "严重"


def calculate_risk(vuln: VulnerabilityCreate | dict) -> tuple[int, str, list[str]]:
    data = vuln.model_dump() if hasattr(vuln, "model_dump") else dict(vuln)
    text = " ".join(
        str(data.get(key, ""))
        for key in ["title", "vuln_type", "affected_component", "description", "attack_method", "impact", "mitigation"]
    ).lower()

    score = SEVERITY_BASE.get(str(data.get("severity", "中危")), 25)
    factors = [f"基础等级 {data.get('severity', '中危')}"]

    if any(term in text for term in REMOTE_TERMS):
        score += 15
        factors.append("存在外部输入、网页、API 或插件链路入口")
    if any(term in text for term in SENSITIVE_TERMS):
        score += 15
        factors.append("涉及提示词、知识库、密钥或敏感数据暴露")
    if any(term in text for term in POC_TERMS):
        score += 10
        factors.append("存在可复现攻击方式或 payload 线索")
    if any(term in text for term in CORE_TERMS):
        score += 10
        factors.append("影响 Agent、RAG、工具调用或模型网关等关键组件")
    if any(term in text for term in CRITICAL_TERMS):
        score += 15
        factors.append("命中高破坏性关键字，存在越权或供应链风险")
    if any(term in text for term in LOW_RISK_TERMS):
        score -= 10
        factors.append("更偏向调试、观测或配置侧问题，直接利用面较弱")

    mitigation = str(data.get("mitigation", "")).lower()
    if any(term in mitigation for term in FIX_UNKNOWN_TERMS):
        score += 10
        factors.append("修复方案不明确")
    elif len(mitigation) > 15:
        score -= 10
        factors.append("已有较明确的缓解或修复措施")

    score = max(0, min(100, score))
    return score, severity_from_score(score), factors


def explain_risk(score: int, severity: str, factors: list[str]) -> str:
    joined = "；".join(factors)
    return f"规则评分为 {score} 分，对应 {severity}。主要依据：{joined}。建议优先检查输入边界、权限控制、日志审计与修复可执行性。"
