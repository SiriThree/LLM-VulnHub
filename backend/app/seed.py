from itertools import product

from sqlalchemy import select

from app.db.models import DataSource, Vulnerability
from app.db.session import Base, SessionLocal, engine
from app.schemas.collector import DataSourceCreate
from app.schemas.vulnerability import VulnerabilityCreate, VulnerabilityUpdate
from app.services.collector_service import create_source
from app.services.scoring_service import calculate_risk, explain_risk
from app.services.vulnerability_service import create_vulnerability, update_vulnerability


SEED_VULNERABILITIES = [
    {
        "title": "Agent tool output prompt injection leads to hidden instruction execution",
        "vuln_type": "Prompt Injection",
        "severity": "高危",
        "affected_component": "LLM Agent / Tool Calling",
        "description": "The agent injects raw tool output into the next model turn without instruction boundary isolation.",
        "attack_method": "An attacker returns malicious hidden instructions from a search or browser tool to override the agent policy.",
        "impact": "System prompt leakage, unauthorized tool execution, and unintended external actions are possible.",
        "mitigation": "Sandbox tool output, add role separation, strip control instructions, and require allowlisted tool actions.",
        "source": "seed",
        "reference_url": "https://example.local/agent-tool-prompt-injection",
        "source_url": "https://example.local/agent-tool-prompt-injection",
        "confidence": 0.95,
        "status": "未修复",
        "tags": ["Prompt Injection", "Agent", "Tool Calling"],
    },
    {
        "title": "RAG retriever permission bypass leaks internal documents",
        "vuln_type": "RAG Data Leakage",
        "severity": "高危",
        "affected_component": "RAG Retriever / Document Store",
        "description": "The retriever executes semantic search before applying per-user document authorization checks.",
        "attack_method": "A low-privilege user crafts queries that recall protected chunks from internal documents.",
        "impact": "Knowledge base leakage, sensitive document exposure, and unauthorized business intelligence access may occur.",
        "mitigation": "Apply ACL filtering before recall, attach user-scoped filters to vector search, and log protected chunk access.",
        "source": "seed",
        "reference_url": "https://example.local/rag-permission-bypass",
        "source_url": "https://example.local/rag-permission-bypass",
        "confidence": 0.94,
        "status": "未修复",
        "tags": ["RAG", "Data Leakage", "Authorization"],
    },
]

GENERATED_PATTERNS = [
    {
        "slug": "prompt-injection",
        "vuln_type": "Prompt Injection",
        "severity": "高危",
        "attack_method": "An attacker injects hidden instructions through {entry}.",
        "impact": "The model may leak hidden prompts, bypass policy checks, or invoke tools without proper approval.",
        "mitigation": "Treat {entry} as untrusted input, isolate instructions by role, and filter control content before reuse.",
        "tags": ["Prompt Injection", "Input Boundary"],
    },
    {
        "slug": "rag-leakage",
        "vuln_type": "RAG Data Leakage",
        "severity": "高危",
        "attack_method": "A user crafts semantic queries that exploit weak authorization in {component}.",
        "impact": "Confidential chunks, internal documents, and tenant-isolated knowledge may become visible to unauthorized users.",
        "mitigation": "Apply ACL filters before retrieval, bind search to user identity, and add recall audit logs.",
        "tags": ["RAG", "Data Leakage"],
    },
    {
        "slug": "agent-bypass",
        "vuln_type": "Agent 越权",
        "severity": "严重",
        "attack_method": "A planner misclassifies a side-effecting action from {entry} as safe and skips approval.",
        "impact": "The agent may execute actions with higher privileges than intended or perform operations on behalf of the wrong user.",
        "mitigation": "Bind approval to tool class, verify actor identity, and require explicit authorization for privileged actions.",
        "tags": ["Agent", "Authorization"],
    },
    {
        "slug": "supply-chain",
        "vuln_type": "Plugin Supply Chain Risk",
        "severity": "严重",
        "attack_method": "A remote update or dependency in {component} expands capability scope without trust verification.",
        "impact": "Compromised dependencies may exfiltrate data, alter model behavior, or introduce unauthorized network access.",
        "mitigation": "Pin versions, verify signatures, review permission changes, and isolate third-party runtime boundaries.",
        "tags": ["Supply Chain", "Dependency"],
    },
    {
        "slug": "routing-misconfig",
        "vuln_type": "Model Routing Misconfiguration",
        "severity": "低危",
        "attack_method": "A low-impact routing rule mismatch in {component} sends benign traffic to the wrong prompt template.",
        "impact": "This may cause noisy responses or minor exposure of non-sensitive debug traces, but does not directly bypass authorization.",
        "mitigation": "Tighten routing conditions, remove debug trace exposure, and validate non-production templates before rollout.",
        "tags": ["Routing", "Config"],
    },
    {
        "slug": "trace-exposure",
        "vuln_type": "Training / Evaluation Data Exposure",
        "severity": "中危",
        "attack_method": "An operator exports {entry} into a shared trace bundle without downstream review.",
        "impact": "Limited internal data or evaluation artifacts may become visible outside the intended workflow.",
        "mitigation": "Redact trace bundles, scope export permissions, and require review before sharing evaluation assets.",
        "tags": ["Trace", "Evaluation"],
    },
]

GENERATED_COMPONENTS = [
    ("LangChain Agent Executor", "browser tool output"),
    ("LlamaIndex Query Engine", "retrieved private document chunks"),
    ("OpenAI-compatible Model Gateway", "fallback routing decisions"),
    ("RAG Vector Search Pipeline", "semantic recall requests"),
    ("Plugin Permission Broker", "third-party manifest updates"),
    ("Evaluation Artifact Pipeline", "benchmark prompt exports"),
    ("Conversation Memory Store", "persisted cross-session notes"),
    ("Document OCR Ingestion Service", "scanned PDF footer text"),
    ("Notebook Assistant Shared Kernel", "prior user notebook state"),
    ("Tool Schema Validator", "JSON tool parameters"),
    ("Moderation Trace Exporter", "support audit package exports"),
    ("Embedding Telemetry Service", "debug request traces"),
    ("Approval Workflow Planner", "natural language action descriptions"),
    ("Markdown Answer Viewer", "rendered retrieved snippets"),
]

DEFAULT_SOURCES = [
    {
        "name": "GitHub Global Advisories - pip",
        "source_type": "github",
        "url": "https://api.github.com/advisories?type=reviewed&ecosystem=pip&per_page=30",
        "interval_minutes": 180,
    },
    {
        "name": "GitHub Global Advisories - npm",
        "source_type": "github",
        "url": "https://api.github.com/advisories?type=reviewed&ecosystem=npm&per_page=30",
        "interval_minutes": 180,
    },
    {
        "name": "LangChain Releases Atom",
        "source_type": "rss",
        "url": "https://github.com/langchain-ai/langchain/releases.atom",
        "interval_minutes": 180,
    },
    {
        "name": "LangGraph Releases Atom",
        "source_type": "rss",
        "url": "https://github.com/langchain-ai/langgraph/releases.atom",
        "interval_minutes": 180,
    },
    {
        "name": "LlamaIndex Releases Atom",
        "source_type": "rss",
        "url": "https://github.com/run-llama/llama_index/releases.atom",
        "interval_minutes": 180,
    },
    {
        "name": "Transformers Releases Atom",
        "source_type": "rss",
        "url": "https://github.com/huggingface/transformers/releases.atom",
        "interval_minutes": 180,
    },
    {
        "name": "AutoGen Releases Atom",
        "source_type": "rss",
        "url": "https://github.com/microsoft/autogen/releases.atom",
        "interval_minutes": 180,
    },
    {
        "name": "CrewAI Releases Atom",
        "source_type": "rss",
        "url": "https://github.com/crewAIInc/crewAI/releases.atom",
        "interval_minutes": 180,
    },
    {
        "name": "Haystack Releases Atom",
        "source_type": "rss",
        "url": "https://github.com/deepset-ai/haystack/releases.atom",
        "interval_minutes": 180,
    },
    {
        "name": "OpenAI Security News",
        "source_type": "web",
        "url": "https://openai.com/news/security/",
        "interval_minutes": 240,
    },
    {
        "name": "OpenAI News RSS",
        "source_type": "rss",
        "url": "https://openai.com/news/rss.xml",
        "interval_minutes": 240,
    },
    {
        "name": "Anthropic News",
        "source_type": "web",
        "url": "https://www.anthropic.com/news",
        "interval_minutes": 240,
    },
    {
        "name": "Hugging Face Blog Feed",
        "source_type": "rss",
        "url": "https://huggingface.co/blog/feed.xml",
        "interval_minutes": 240,
    },
]


def build_generated_vulnerabilities() -> list[dict]:
    generated = []
    for pattern, (component, entry) in product(GENERATED_PATTERNS, GENERATED_COMPONENTS):
        slug = f"{pattern['slug']}-{component.lower().replace(' ', '-').replace('/', '-')}"
        generated.append(
            {
                "title": f"{component} {pattern['vuln_type']} risk via {entry}",
                "vuln_type": pattern["vuln_type"],
                "severity": pattern["severity"],
                "affected_component": component,
                "description": f"{component} trusts {entry} without enough isolation, authorization, or validation in a large-model workflow.",
                "attack_method": pattern["attack_method"].format(component=component, entry=entry),
                "impact": pattern["impact"],
                "mitigation": pattern["mitigation"].format(component=component, entry=entry),
                "source": "seed-generated",
                "reference_url": f"https://example.local/generated/{slug}",
                "source_url": f"https://example.local/generated/{slug}",
                "confidence": 0.82,
                "status": "未修复",
                "tags": pattern["tags"] + [component.split()[0]],
            }
        )
    return generated


def seed_vulnerabilities() -> None:
    db = SessionLocal()
    try:
        all_samples = SEED_VULNERABILITIES + build_generated_vulnerabilities()
        for item in all_samples:
            payload = VulnerabilityCreate(**item, score=0)
            score, severity, factors = calculate_risk(payload)
            payload.score = score
            payload.severity = severity
            exists = db.scalar(select(Vulnerability).where(Vulnerability.source_url == item["source_url"]))
            if exists:
                update_vulnerability(
                    db,
                    exists.id,
                    VulnerabilityUpdate(
                        title=payload.title,
                        vuln_type=payload.vuln_type,
                        severity=payload.severity,
                        score=payload.score,
                        affected_component=payload.affected_component,
                        description=payload.description,
                        attack_method=payload.attack_method,
                        impact=payload.impact,
                        mitigation=payload.mitigation,
                        source=payload.source,
                        reference_url=payload.reference_url,
                        source_url=payload.source_url,
                        confidence=payload.confidence,
                        status=payload.status,
                        tags=payload.tags,
                    ),
                )
                continue
            create_vulnerability(db, payload, explain_risk(score, severity, factors))
    finally:
        db.close()


def seed_sources() -> None:
    db = SessionLocal()
    try:
        demo_sources = db.scalars(
            select(DataSource).where(
                DataSource.source_type == "local_file",
                DataSource.url.in_(["../data/sample_sources.json", "data/sample_sources.json"]),
            )
        ).all()
        for source in demo_sources:
            db.delete(source)
        if demo_sources:
            db.commit()

        for source in DEFAULT_SOURCES:
            exists = db.scalar(select(DataSource).where(DataSource.url == source["url"]))
            if exists:
                continue
            create_source(
                db,
                DataSourceCreate(
                    name=source["name"],
                    source_type=source["source_type"],
                    url=source["url"],
                    enabled=True,
                    interval_minutes=source["interval_minutes"],
                ),
            )
    finally:
        db.close()


def run() -> None:
    Base.metadata.create_all(bind=engine)
    seed_vulnerabilities()
    seed_sources()


if __name__ == "__main__":
    run()
