import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


AI_KEYWORDS = [
    "llm",
    "large language model",
    "大模型",
    "模型",
    "prompt",
    "rag",
    "agent",
    "plugin",
    "embedding",
    "知识库",
    "langchain",
    "llamaindex",
    "autogen",
    "crewai",
    "retriever",
    "tool",
    "browser",
    "routing",
    "evaluation",
    "mcp",
]

VULN_KEYWORDS = [
    "漏洞",
    "泄露",
    "越权",
    "注入",
    "攻击",
    "绕过",
    "未授权",
    "bypass",
    "injection",
    "leak",
    "exploit",
    "exfiltration",
    "permission",
    "unauthorized",
    "privileged",
    "tenant",
    "exposure",
    "advisory",
    "security issue",
]

SECURITY_PATTERNS = [
    "untrusted",
    "unauthorized",
    "prompt leakage",
    "prompt leak",
    "hidden instruction",
    "tool output",
    "system prompt",
    "jailbreak",
    "permission bypass",
    "command execution",
    "privilege escalation",
    "data exposure",
    "malicious input",
    "cross-tenant",
    "supply chain",
    "ssrf",
    "sql injection",
    "path traversal",
    "rce",
]

NEGATIVE_PATTERNS = [
    "没有安全漏洞",
    "无安全漏洞",
    "没有漏洞",
    "未提及漏洞",
    "不涉及漏洞",
    "只是普通新闻",
    "产品介绍",
    "no security issue",
    "does not describe any exploit",
    "does not describe any exploit or bypass",
    "feature announcement",
    "general availability",
    "launch",
    "launches",
    "newsroom",
    "customer story",
    "release notes",
    "changelog",
    "tutorial",
    "getting started",
    "benchmark",
    "enterprise deployment",
]

NOISE_PATTERNS = [
    "release notes",
    "changelog",
    "launches",
    "announces",
    "newsroom",
    "tutorial",
    "getting started",
    "benchmark",
    "one click",
    "employees",
    "feature announcement",
    "spend controls",
    "partnership",
    "customer story",
    "case study",
    "webinar",
    "native-speed",
]


class LLMProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str | None
    base_url: str
    model: str


@dataclass(frozen=True)
class ProviderStatus:
    configured_provider: str
    active_provider: str
    model: str
    has_api_key: bool
    fallback_enabled: bool
    using_mock: bool
    can_call_remote: bool


class LLMClient:
    def __init__(self) -> None:
        self.settings = get_settings()

    @property
    def model_name(self) -> str:
        return self._provider_config().model if self.settings.llm_provider in {"openai", "deepseek"} else "mock-heuristic"

    def _provider_config(self) -> ProviderConfig:
        provider = self.settings.llm_provider.lower()
        if provider == "openai":
            return ProviderConfig("openai", self.settings.openai_api_key, self.settings.openai_base_url, self.settings.openai_model)
        if provider == "deepseek":
            return ProviderConfig("deepseek", self.settings.deepseek_api_key, self.settings.deepseek_base_url, self.settings.deepseek_model)
        return ProviderConfig("mock", None, "", "mock-heuristic")

    def provider_status(self) -> ProviderStatus:
        provider = self._provider_config()
        configured_provider = self.settings.llm_provider.lower()
        has_api_key = bool(provider.api_key)
        can_call_remote = provider.name != "mock" and has_api_key
        active_provider = provider.name if can_call_remote or provider.name == "mock" else ("mock" if self.settings.llm_fallback_to_mock else provider.name)
        model = provider.model if active_provider != "mock" else "mock-heuristic"
        return ProviderStatus(
            configured_provider=configured_provider,
            active_provider=active_provider,
            model=model,
            has_api_key=has_api_key,
            fallback_enabled=self.settings.llm_fallback_to_mock,
            using_mock=active_provider == "mock",
            can_call_remote=can_call_remote,
        )

    async def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        provider = self._provider_config()
        if provider.name != "mock" and provider.api_key:
            try:
                content = await self._chat_completion(
                    provider=provider,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    response_format={"type": "json_object"},
                )
                payload = self._parse_json_content(content)
                payload["_provider"] = {
                    "configured_provider": provider.name,
                    "active_provider": provider.name,
                    "model": provider.model,
                    "fallback_reason": None,
                }
                return payload
            except Exception as exc:
                if not self.settings.llm_fallback_to_mock:
                    raise
                payload = self._mock_json(system_prompt, user_prompt)
                payload["_provider"] = {
                    "configured_provider": provider.name,
                    "active_provider": "mock",
                    "model": "mock-heuristic",
                    "fallback_reason": str(exc),
                }
                return payload
        elif provider.name != "mock" and not provider.api_key and not self.settings.llm_fallback_to_mock:
            raise LLMProviderError(f"{provider.name} provider selected but API key is missing.")

        payload = self._mock_json(system_prompt, user_prompt)
        payload["_provider"] = {
            "configured_provider": provider.name,
            "active_provider": "mock",
            "model": "mock-heuristic",
            "fallback_reason": f"{provider.name} provider is not available or API key is missing." if provider.name != "mock" else None,
        }
        return payload

    async def chat_text(self, system_prompt: str, user_prompt: str) -> str:
        provider = self._provider_config()
        if provider.name != "mock" and provider.api_key:
            try:
                return await self._chat_completion(
                    provider=provider,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                )
            except Exception:
                if not self.settings.llm_fallback_to_mock:
                    raise
        elif provider.name != "mock" and not provider.api_key and not self.settings.llm_fallback_to_mock:
            raise LLMProviderError(f"{provider.name} provider selected but API key is missing.")

        return self._mock_text(user_prompt)

    async def _chat_completion(
        self,
        provider: ProviderConfig,
        messages: list[dict[str, str]],
        response_format: dict[str, str] | None = None,
    ) -> str:
        payload: dict[str, Any] = {
            "model": provider.model,
            "messages": messages,
            "temperature": self.settings.llm_temperature,
        }
        if response_format:
            payload["response_format"] = response_format

        last_error: Exception | None = None
        for attempt in range(1, self.settings.llm_max_retries + 1):
            try:
                async with httpx.AsyncClient(timeout=self.settings.llm_timeout_seconds) as client:
                    response = await client.post(
                        f"{provider.base_url.rstrip('/')}/chat/completions",
                        headers={"Authorization": f"Bearer {provider.api_key}", "Content-Type": "application/json"},
                        json=payload,
                    )
                    response.raise_for_status()
                    data = response.json()
                    content = data["choices"][0]["message"]["content"]
                    if isinstance(content, list):
                        content = "".join(part.get("text", "") if isinstance(part, dict) else str(part) for part in content)
                    return str(content)
            except Exception as exc:
                last_error = exc
                if attempt >= self.settings.llm_max_retries:
                    break

        raise LLMProviderError(f"{provider.name} completion failed after {self.settings.llm_max_retries} attempts: {last_error}")

    def _parse_json_content(self, content: str) -> dict[str, Any]:
        try:
            return json.loads(content)
        except json.JSONDecodeError:
            match = re.search(r"\{.*\}", content, re.DOTALL)
            if match:
                return json.loads(match.group(0))
            raise LLMProviderError("Model returned invalid JSON content.")

    def _candidate_text(self, prompt: str) -> str:
        for marker in ("Candidate text:", "Vulnerability text:", "漏洞文本：", "漏洞描述："):
            if marker in prompt:
                return prompt.split(marker, 1)[1].strip()
        return prompt.strip()

    def _mock_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        prompt_lower = user_prompt.lower()
        text = self._candidate_text(user_prompt).lower()

        if "is_ai_vulnerability" in user_prompt:
            has_negative = any(pattern in text for pattern in NEGATIVE_PATTERNS)
            ai_hit = any(keyword in text for keyword in AI_KEYWORDS)
            vuln_hit = any(keyword in text for keyword in VULN_KEYWORDS)
            security_hit = any(pattern in text for pattern in SECURITY_PATTERNS)
            advisory_hit = any(phrase in text for phrase in ["ghsa-", "cve-", "advisory", "security advisory"])
            noise_hit = any(phrase in text for phrase in NOISE_PATTERNS)
            strong_context_hit = any(
                phrase in text
                for phrase in [
                    "permission broker",
                    "knowledge base",
                    "evaluation artifact",
                    "support operators",
                    "per-user acl",
                    "third-party manifest",
                    "privileged tools",
                    "fallback model",
                    "debug traces",
                    "graphcypherqachain",
                    "retrieval pipeline",
                ]
            )
            hit = (not has_negative) and (not noise_hit) and ai_hit and (vuln_hit or security_hit or advisory_hit or strong_context_hit)

            if "prompt" in text or "注入" in text:
                area = "Prompt Injection"
            elif "rag" in text or "knowledge" in text or "知识库" in text:
                area = "RAG Data Leakage"
            elif "tool" in text or "browser" in text or "agent" in text:
                area = "Agent / Tool Abuse"
            elif "evaluation" in text or "trace" in text or "artifact" in text:
                area = "Training / Evaluation Data Exposure"
            elif "routing" in text or "fallback model" in text:
                area = "Model Routing Misconfiguration"
            else:
                area = "LLM Application Security"

            return {
                "is_ai_vulnerability": hit,
                "confidence": 0.95 if advisory_hit and hit else 0.92 if vuln_hit and hit else 0.84 if (security_hit or strong_context_hit) and hit else 0.08,
                "related_area": area if hit else "unknown",
                "reason": "The text contains AI-system context together with explicit security-impact or advisory language." if hit else "The text does not clearly describe an AI security vulnerability or advisory.",
            }

        if "risk_reason" in user_prompt and "priority" in user_prompt:
            severity = "严重" if "严重" in user_prompt else "高危" if "高危" in user_prompt else "中危"
            return {
                "risk_reason": f"该漏洞影响 AI 工作流中的关键执行链路，可能导致提示词泄露、未授权工具调用或敏感数据外泄，综合判断为{severity}。",
                "priority": "P1" if severity in {"严重", "高危"} else "P2",
                "analyst_notes": "优先验证外部输入边界、工具调用授权和输出隔离策略。",
            }

        if "publishable" in user_prompt and "review_status" in user_prompt:
            return {
                "publishable": False,
                "review_status": "needs_review",
                "review_summary": "结构化字段已经具备，但仍建议人工确认攻击前提、影响边界和修复建议后再发布。",
                "missing_fields": [],
            }

        if "candidate_ids" in user_prompt or "should_merge" in user_prompt:
            ids = [int(match) for match in re.findall(r"ID:\s*(\d+)", user_prompt)]
            return {
                "should_merge": False,
                "candidate_ids": ids[:1] if ids and "same vulnerability" in prompt_lower else [],
                "reason": "The candidate appears related, but should remain manual review unless the exploit path and affected component fully match.",
                "confidence": 0.45 if ids else 0.0,
            }

        if "supply chain" in text or "供应链" in text or "ssrf" in text:
            vuln_type = "Plugin Supply Chain Risk"
            severity = "严重"
            component = "Plugin Permission Broker"
        elif "prompt" in text or "注入" in text:
            vuln_type = "Prompt Injection"
            severity = "高危"
            component = "LLM Agent / Tool Calling"
        elif "rag" in text or "知识库" in text or "retriever" in text:
            vuln_type = "RAG Data Leakage"
            severity = "高危"
            component = "RAG Retriever / Document Store"
        elif any(word in text for word in ["trace", "telemetry", "routing", "debug", "evaluation"]):
            vuln_type = "Model Routing Misconfiguration"
            severity = "低危"
            component = "LLM Application"
        elif any(word in text for word in ["exposure", "export", "artifact", "dataset"]):
            vuln_type = "Training / Evaluation Data Exposure"
            severity = "中危"
            component = "Evaluation Artifact Pipeline"
        elif "agent" in text or "tool" in text or "browser" in text:
            vuln_type = "Agent Authorization Bypass"
            severity = "严重"
            component = "LLM Agent / Tool Calling"
        else:
            vuln_type = "LLM Application Security Risk"
            severity = "中危"
            component = "LLM Application"

        title = f"{component} {vuln_type} Vulnerability"
        return {
            "title": title,
            "vuln_type": vuln_type,
            "severity": severity,
            "affected_component": component,
            "description": text[:240] if text else "unknown",
            "attack_method": "The attacker injects malicious content through prompts, external documents, web pages, or tool output to manipulate model behavior.",
            "impact": "This may lead to prompt leakage, unauthorized tool execution, cross-tenant data access, or sensitive knowledge-base exposure.",
            "mitigation": "Isolate instructions from external content, enforce tool authorization, add retrieval filtering, and audit model outputs before action.",
            "tags": [vuln_type, component.split("/")[0].strip()],
        }

    def _mock_text(self, prompt: str) -> str:
        if "可用漏洞库记录" in prompt:
            title_matches = re.findall(r"\[(\d+)\] 标题：(.+)", prompt)
            mitigation_matches = re.findall(r"修复建议：(.+)", prompt)
            impact_matches = re.findall(r"影响：(.+)", prompt)
            titles = title_matches[:3]
            refs = "\n".join(f"- [{idx}] {title}" for idx, title in titles)
            mitigation = mitigation_matches[0] if mitigation_matches else "需要结合命中的漏洞记录补充隔离、权限校验、审计和输入过滤措施。"
            impact = impact_matches[0] if impact_matches else "命中记录显示该类问题可能影响 LLM / RAG / Agent 链路的安全边界。"
            return (
                f"结论：当前问题可以从漏洞库命中的记录中找到相关依据，重点风险是：{impact} [1]\n\n"
                f"可执行措施：\n"
                f"1. 优先按命中记录中的修复建议处理：{mitigation} [1]\n"
                f"2. 对外部输入、检索内容和工具调用结果做指令隔离，避免把不可信文本直接拼进高权限上下文。[1]\n"
                f"3. 检查 RAG 检索是否先做权限过滤，再做语义召回；对跨租户、内部知识库和调试 Trace 单独加访问控制。[1]\n"
                f"4. 对命中组件建立回归测试，覆盖恶意文档、特殊 token、越权查询和异常输入。\n\n"
                f"参考记录：\n{refs}"
            )
        if "漏洞库上下文" in prompt or "context" in prompt.lower():
            return "根据漏洞库上下文，风险主要集中在外部输入进入 Prompt、RAG 检索权限不足，以及 Agent 工具调用缺少边界控制。建议采用指令隔离、最小权限、检索过滤和工具审计。"
        return "该漏洞需要优先关注攻击入口、影响范围、敏感数据暴露和修复可行性，并在上线前补充权限校验与审计。"
