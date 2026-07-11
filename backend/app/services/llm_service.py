import json
import re
from dataclasses import dataclass
from typing import Any

import httpx

from app.core.config import get_settings


AI_KEYWORDS = ["llm", "大模型", "prompt", "rag", "agent", "插件", "plugin", "embedding", "模型", "知识库", "langchain", "llamaindex"]
VULN_KEYWORDS = ["漏洞", "泄露", "越权", "注入", "攻击", "绕过", "未授权", "bypass", "injection", "leak", "exploit"]
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
]
NEGATIVE_PATTERNS = ["没有安全漏洞", "无安全漏洞", "没有漏洞", "未提及漏洞", "不涉及漏洞", "只是普通新闻", "产品介绍"]


class LLMProviderError(RuntimeError):
    pass


@dataclass(frozen=True)
class ProviderConfig:
    name: str
    api_key: str | None
    base_url: str
    model: str


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

    async def chat_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        provider = self._provider_config()
        if provider.name != "mock" and provider.api_key:
            try:
                content = await self._chat_completion(
                    provider=provider,
                    messages=[{"role": "system", "content": system_prompt}, {"role": "user", "content": user_prompt}],
                    response_format={"type": "json_object"},
                )
                return self._parse_json_content(content)
            except Exception:
                if not self.settings.llm_fallback_to_mock:
                    raise
        elif provider.name != "mock" and not provider.api_key and not self.settings.llm_fallback_to_mock:
            raise LLMProviderError(f"{provider.name} provider selected but API key is missing.")

        return self._mock_json(system_prompt, user_prompt)

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

    def _extract_candidate_text(self, prompt: str, marker: str) -> str:
        if marker in prompt:
            return prompt.split(marker, 1)[1].strip()
        return prompt.strip()

    def _mock_json(self, system_prompt: str, user_prompt: str) -> dict[str, Any]:
        if "is_ai_vulnerability" in user_prompt:
            text = self._extract_candidate_text(user_prompt, "候选文本：").lower()
            has_negative = any(pattern in text for pattern in NEGATIVE_PATTERNS)
            ai_hit = any(keyword in text for keyword in AI_KEYWORDS)
            vuln_hit = any(keyword in text for keyword in VULN_KEYWORDS)
            security_hit = any(pattern in text for pattern in SECURITY_PATTERNS)
            hit = (not has_negative) and ai_hit and (vuln_hit or security_hit)
            if "prompt" in text or "注入" in text:
                area = "Prompt Injection"
            elif "rag" in text or "知识库" in text:
                area = "RAG Data Leakage"
            else:
                area = "Agent / LLM Security"
            return {
                "is_ai_vulnerability": hit,
                "confidence": 0.9 if vuln_hit and hit else 0.78 if security_hit and hit else 0.15,
                "related_area": area if hit else "unknown",
                "reason": "关键词和语义线索显示该文本与 AI 应用安全风险相关。" if hit else "文本中未发现明确的 AI 漏洞语义线索。",
            }

        text = self._extract_candidate_text(user_prompt, "漏洞描述：").lower()

        if "supply chain" in text or "供应链" in text or "ssrf" in text:
            vuln_type = "Plugin Supply Chain Risk"
            severity = "严重"
            component = "Plugin Permission Broker"
        elif "prompt" in text or "注入" in text:
            vuln_type = "Prompt Injection"
            severity = "高危"
            component = "LLM Agent / Tool Calling"
        elif "rag" in text or "知识库" in text:
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
        elif "agent" in text or "工具" in text:
            vuln_type = "Agent 越权"
            severity = "严重"
            component = "LLM Agent / Tool Calling"
        else:
            vuln_type = "LLM 应用安全风险"
            severity = "中危"
            component = "LLM Application"

        return {
            "title": f"{component} {vuln_type} 漏洞",
            "vuln_type": vuln_type,
            "severity": severity,
            "affected_component": component,
            "description": text[:240] if text else "unknown",
            "attack_method": "攻击者通过构造恶意输入、外部文档或工具返回内容影响模型行为。",
            "impact": "可能造成系统提示词泄露、知识库越权访问、敏感数据暴露或未授权工具调用。",
            "mitigation": "隔离外部内容与指令，增加权限校验、检索过滤、工具调用审计和输出安全策略。",
            "tags": [vuln_type, component.split("/")[0].strip()],
        }

    def _mock_text(self, prompt: str) -> str:
        if "漏洞库上下文" in prompt:
            return "根据漏洞库上下文，相关风险主要集中在外部输入进入 Prompt、RAG 检索权限不足、Agent 工具调用缺少边界控制。建议采用指令隔离、最小权限、检索权限过滤、工具调用审批和日志审计。"
        return "该漏洞需要优先关注攻击入口、影响范围、敏感数据暴露和修复可行性，并在上线前补充权限校验与审计。"
