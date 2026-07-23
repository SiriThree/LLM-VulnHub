from dataclasses import dataclass

from app.core.input_security import UNTRUSTED_INPUT_POLICY, wrap_untrusted_content


UNTRUSTED_FIELDS = {"text", "intel", "candidates", "vulnerability", "factors", "merge", "risk_reason"}


def guarded_system_prompt(role: str) -> str:
    return f"{role}\n\nSecurity policy: {UNTRUSTED_INPUT_POLICY}"


@dataclass(frozen=True)
class PromptSpec:
    key: str
    agent_name: str
    version: str
    system_prompt: str
    user_template: str
    required_keys: tuple[str, ...]

    def render(self, **kwargs: str) -> str:
        secured = {
            key: wrap_untrusted_content(key, str(value)) if key in UNTRUSTED_FIELDS else value
            for key, value in kwargs.items()
        }
        return self.user_template.format(**secured)


PROMPT_REGISTRY: dict[str, PromptSpec] = {
    "triage_v2": PromptSpec(
        key="triage_v2",
        agent_name="Triage Agent",
        version="v2",
        system_prompt=guarded_system_prompt("You are an AI security triage analyst. Be conservative, avoid invention, and return valid JSON only."),
        user_template=(
            "Determine whether the text describes an AI or LLM-related security vulnerability or security advisory. "
            "Do not classify general AI news, product launches, feature announcements, benchmark posts, tutorials, changelogs, release notes, or enterprise adoption stories as vulnerabilities. "
            "Only return is_ai_vulnerability=true when the text clearly describes a security weakness, exploit path, unauthorized access, data leakage, prompt injection, advisory, CVE, GHSA, or concrete security impact in an AI/LLM/agent/RAG system. "
            "Return JSON with keys: is_ai_vulnerability, confidence, related_area, reason. "
            "confidence must be a number between 0 and 1, not a word like high or medium.\n\n"
            "Candidate text:\n{text}"
        ),
        required_keys=("is_ai_vulnerability", "confidence", "related_area", "reason"),
    ),
    "extraction_v2": PromptSpec(
        key="extraction_v2",
        agent_name="Extraction Agent",
        version="v2",
        system_prompt=guarded_system_prompt("You are a vulnerability structuring agent for AI security reports. Return valid JSON only."),
        user_template=(
            "Extract structured vulnerability fields from the text. "
            "Return JSON with keys: title, vuln_type, affected_component, severity, description, attack_method, impact, mitigation, tags. "
            "Severity must be one of: 低危, 中危, 高危, 严重. If a field is unknown, use unknown.\n\n"
            "Vulnerability text:\n{text}"
        ),
        required_keys=("title", "vuln_type", "affected_component", "severity", "description", "attack_method", "impact", "mitigation", "tags"),
    ),
    "merge_v2": PromptSpec(
        key="merge_v2",
        agent_name="Merge Agent",
        version="v2",
        system_prompt=guarded_system_prompt("You compare candidate vulnerabilities and return merge decisions as JSON only."),
        user_template=(
            "Decide whether the new intelligence item should merge into an existing canonical vulnerability. "
            "Return JSON with keys: should_merge, candidate_ids, reason, confidence.\n\n"
            "New intelligence:\n{intel}\n\n"
            "Candidate vulnerabilities:\n{candidates}"
        ),
        required_keys=("should_merge", "candidate_ids", "reason", "confidence"),
    ),
    "risk_v2": PromptSpec(
        key="risk_v2",
        agent_name="Risk Explanation Agent",
        version="v2",
        system_prompt=guarded_system_prompt("You explain AI vulnerability risk to a security analyst. Return JSON only."),
        user_template=(
            "Given the structured fields and rule-based score, explain the risk in concise analyst language. "
            "Return JSON with keys: risk_reason, priority, analyst_notes.\n\n"
            "Structured vulnerability:\n{vulnerability}\n\n"
            "Rule factors:\n{factors}\n"
            "Rule score: {score}\n"
            "Rule severity: {severity}"
        ),
        required_keys=("risk_reason", "priority", "analyst_notes"),
    ),
    "reviewer_v2": PromptSpec(
        key="reviewer_v2",
        agent_name="Reviewer Agent",
        version="v2",
        system_prompt=guarded_system_prompt("You are a security review assistant. Return JSON only."),
        user_template=(
            "Assess whether the extracted record is publishable or still needs manual review. "
            "Return JSON with keys: publishable, review_status, review_summary, missing_fields.\n\n"
            "Structured vulnerability:\n{vulnerability}\n\n"
            "Merge suggestions:\n{merge}\n\n"
            "Risk explanation:\n{risk_reason}"
        ),
        required_keys=("publishable", "review_status", "review_summary", "missing_fields"),
    ),
    "asset_impact_v2": PromptSpec(
        key="asset_impact_v2",
        agent_name="Asset Impact Agent",
        version="v2",
        system_prompt=guarded_system_prompt("You assess asset and blast-radius impact for AI security issues. Return JSON only."),
        user_template=(
            "Assess which assets or platform layers would be impacted by this AI vulnerability. "
            "Return JSON with keys: impacted_assets, tenant_scope, blast_radius, operational_risk, asset_summary.\n\n"
            "Structured vulnerability:\n{vulnerability}\n\n"
            "Risk explanation:\n{risk_reason}"
        ),
        required_keys=("impacted_assets", "tenant_scope", "blast_radius", "operational_risk", "asset_summary"),
    ),
}


def get_prompt_spec(key: str) -> PromptSpec:
    return PROMPT_REGISTRY[key]
