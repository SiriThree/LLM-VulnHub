from app.schemas.vulnerability import (
    SEVERITY_SCORE_DEFAULTS,
    VulnerabilityCreate,
    normalize_score_value,
    normalize_severity_value,
)


SEVERITY_BASE = {"低危": 10, "中危": 30, "高危": 55, "严重": 75}
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
    "多租户",
]
REMOTE_TERMS = [
    "remote",
    "web",
    "browser",
    "external",
    "retriever",
    "api",
    "plugin",
    "public",
    "上传",
    "导入",
]
POC_TERMS = [
    "poc",
    "exploit",
    "payload",
    "attacker can",
    "攻击者可以",
    "诱导",
    "构造特殊提示词",
]
CORE_TERMS = [
    "agent",
    "rag",
    "tool",
    "plugin",
    "gateway",
    "retriever",
    "document store",
    "model routing",
    "langchain",
    "llm",
]
CRITICAL_TERMS = [
    "supply chain",
    "ssrf",
    "system prompt exposure",
    "authorization bypass",
    "越权",
    "注入",
    "删除数据库",
    "拒绝服务",
]
LOW_RISK_TERMS = [
    "telemetry",
    "routing",
    "trace",
    "debug",
    "benchmark",
    "evaluation",
    "viewer",
    "render",
]
FIX_UNKNOWN_TERMS = ["unknown", "not provided", "unclear", "n/a", "未提供", "待补充", "人工补充"]


def severity_from_score(score: int) -> str:
    if score <= 30:
        return "低危"
    if score <= 60:
        return "中危"
    if score <= 80:
        return "高危"
    return "严重"


def priority_from_score(score: int) -> str:
    if score >= 85:
        return "紧急"
    if score >= 70:
        return "高"
    if score >= 40:
        return "中"
    return "低"


def calculate_risk(vuln: VulnerabilityCreate | dict) -> tuple[int, str, list[str]]:
    data = vuln.model_dump() if hasattr(vuln, "model_dump") else dict(vuln)
    text = " ".join(
        str(data.get(key, ""))
        for key in ["title", "vuln_type", "affected_component", "description", "attack_method", "impact", "mitigation"]
    ).lower()

    declared_severity = normalize_severity_value(data.get("severity", "中危"))
    score = SEVERITY_BASE.get(declared_severity, SEVERITY_SCORE_DEFAULTS.get(declared_severity, 30))
    factors = [f"基础等级 {declared_severity}"]

    if any(term in text for term in REMOTE_TERMS):
        score += 10
        factors.append("存在外部输入或公开入口，攻击面更大")
    if any(term in text for term in SENSITIVE_TERMS):
        score += 10
        factors.append("涉及敏感数据、提示词或知识库内容")
    if any(term in text for term in POC_TERMS):
        score += 8
        factors.append("文本包含较明确的攻击路径或利用方式")
    if any(term in text for term in CORE_TERMS):
        score += 8
        factors.append("影响 Agent、RAG、工具调用或模型执行链路")
    if any(term in text for term in CRITICAL_TERMS):
        score += 12
        factors.append("存在越权、注入、供应链或破坏性操作风险")
    if any(term in text for term in LOW_RISK_TERMS):
        score -= 12
        factors.append("更偏向调试、观测或配置问题，直接利用性较弱")

    mitigation = str(data.get("mitigation", "")).lower()
    if any(term in mitigation for term in FIX_UNKNOWN_TERMS):
        score += 5
        factors.append("修复方案暂不明确，需要人工补充")
    elif len(mitigation.strip()) > 15:
        score -= 5
        factors.append("已给出较清晰的缓解或修复措施")

    score = normalize_score_value(score, declared_severity, default=0)
    return score, severity_from_score(score), factors


def explain_risk(score: int, severity: str, factors: list[str]) -> str:
    joined = "；".join(factors)
    return f"规则评分为 {score} 分，对应 {severity}。主要依据：{joined}。建议优先检查输入边界、权限控制、日志审计与修复可执行性。"
