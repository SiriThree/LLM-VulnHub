"use client";

import { useState } from "react";
import { Bot, Save, Sparkles } from "lucide-react";
import { AnalyzeResult, api, Vulnerability } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";

const sample =
  "A LangChain agent accepts untrusted browser tool output and injects it into the next model turn without any instruction boundary isolation. " +
  "An attacker can plant hidden prompt instructions in a web page, causing the agent to reveal system prompts, call tools without authorization, " +
  "or retrieve sensitive RAG content from connected knowledge sources.";

type EditableExtract = Partial<Vulnerability> & {
  tags?: string[];
  risk_reason?: string;
  review_summary?: string;
  asset_impact_summary?: string;
  asset_impact_details?: Record<string, unknown>;
  similar?: Vulnerability[];
};

const mainFields = [
  "title",
  "vuln_type",
  "severity",
  "score",
  "affected_component",
  "description",
  "attack_method",
  "impact",
  "mitigation",
] as const;

export function AiExtractClient() {
  const [raw, setRaw] = useState(sample);
  const [result, setResult] = useState<EditableExtract | null>(null);
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  async function handleExtract() {
    setLoading(true);
    setMessage("");
    try {
      const analyzed = await api<AnalyzeResult>("/ai/analyze", {
        method: "POST",
        body: JSON.stringify({ raw_text: raw, save: false }),
      });
      setAnalysis(analyzed);
      setResult(analyzed.extracted);
    } catch (error) {
      setMessage(String(error));
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!result) return;
    setSaving(true);
    setMessage("");
    try {
      const saved = await api<Vulnerability>("/vulnerabilities", {
        method: "POST",
        body: JSON.stringify(result),
      });
      setMessage(`已入库：#${saved.id} ${saved.title}`);
    } catch (error) {
      setMessage(String(error));
    } finally {
      setSaving(false);
    }
  }

  function updateField(key: string, value: string) {
    setResult((current) => ({
      ...(current ?? {}),
      [key]: key === "score" ? Number(value) : value,
    }));
  }

  return (
    <div className="space-y-5">
      <div className="grid gap-4 xl:grid-cols-[1.2fr_1fr]">
        <Card>
          <h2 className="mb-3 font-semibold">原始漏洞文本</h2>
          <Textarea className="min-h-96" value={raw} onChange={(event) => setRaw(event.target.value)} />
          <div className="mt-3 flex items-center gap-3">
            <Button type="button" onClick={handleExtract} disabled={loading}>
              <Bot size={16} />
              {loading ? "分析中..." : "AI 解析"}
            </Button>
            {analysis?.analysis_job ? (
              <div className="text-sm text-slate-500">
                Job #{analysis.analysis_job.id} · {analysis.analysis_job.pipeline_name} · {analysis.analysis_job.model_name}
              </div>
            ) : null}
          </div>
        </Card>

        <Card>
          <h2 className="mb-3 font-semibold">抽取结果预览</h2>
          {result ? (
            <div className="space-y-3">
              {mainFields.map((key) => (
                <label className="block" key={key}>
                  <span className="mb-1 block text-xs text-slate-500">{key}</span>
                  {["description", "attack_method", "impact", "mitigation"].includes(key) ? (
                    <Textarea
                      value={String((result as Record<string, unknown>)[key] ?? "")}
                      onChange={(event) => updateField(key, event.target.value)}
                    />
                  ) : (
                    <Input
                      value={String((result as Record<string, unknown>)[key] ?? "")}
                      onChange={(event) => updateField(key, event.target.value)}
                    />
                  )}
                </label>
              ))}

              <div className="rounded-md border border-border bg-slate-50 p-3 text-sm text-slate-700">
                <div className="font-medium">Risk Explanation Agent</div>
                <div className="mt-1 whitespace-pre-wrap">{result.risk_reason || "-"}</div>
              </div>

              <div className="rounded-md border border-border bg-slate-50 p-3 text-sm text-slate-700">
                <div className="font-medium">Asset Impact Agent</div>
                <div className="mt-1 whitespace-pre-wrap">{result.asset_impact_summary || "-"}</div>
              </div>

              <div className="rounded-md border border-border bg-slate-50 p-3 text-sm text-slate-700">
                <div className="font-medium">Reviewer Agent</div>
                <div className="mt-1 whitespace-pre-wrap">{result.review_summary || "-"}</div>
              </div>

              {result.similar && result.similar.length > 0 ? (
                <div className="rounded-md border border-border bg-slate-50 p-3 text-sm text-slate-700">
                  <div className="font-medium">相似漏洞候选</div>
                  <div className="mt-1">{result.similar.map((item) => `#${item.id} ${item.title}`).join(" | ")}</div>
                </div>
              ) : null}

              <Button type="button" onClick={handleSave} disabled={saving}>
                <Save size={16} />
                {saving ? "入库中..." : "确认入库"}
              </Button>
            </div>
          ) : (
            <div className="rounded-md bg-muted p-4 text-sm text-slate-500">等待分析结果</div>
          )}
        </Card>
      </div>

      {analysis?.analysis_job ? (
        <Card>
          <div className="mb-3 flex items-center gap-2">
            <Sparkles size={16} />
            <h2 className="font-semibold">Phase 2 Agent 执行轨迹</h2>
          </div>

          <div className="mb-4 rounded-md border border-border bg-slate-50 p-3 text-sm text-slate-700">
            <div className="font-medium">资产影响摘要</div>
            <div className="mt-1 whitespace-pre-wrap">{analysis.analysis_job.asset_impact_summary || "-"}</div>
          </div>

          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-6">
            {analysis.analysis_job.agent_executions.map((item) => (
              <div key={item.id} className="rounded-md border border-border p-3">
                <div className="text-sm font-medium">{item.agent_name}</div>
                <div className="mt-1 text-xs text-slate-500">
                  {item.stage_name} · {item.status}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  {item.model_name || item.provider_name || "local"} · {item.latency_ms ?? 0} ms
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  prompt {String((item.output_payload?._meta as { prompt_key?: string } | undefined)?.prompt_key ?? "-")} · attempts{" "}
                  {String((item.output_payload?._meta as { attempt_count?: number } | undefined)?.attempt_count ?? item.retry_count ?? 1)}
                </div>
                <div className="mt-2 text-xs text-slate-600">tokens ~ {item.total_tokens ?? 0}</div>
                <div className="mt-2 line-clamp-4 text-xs text-slate-700">{JSON.stringify(item.output_payload)}</div>
              </div>
            ))}
          </div>
        </Card>
      ) : null}

      {analysis?.report ? (
        <Card>
          <h2 className="mb-3 font-semibold">分析报告</h2>
          <pre className="whitespace-pre-wrap text-sm text-slate-700">{analysis.report}</pre>
        </Card>
      ) : null}

      {message ? <div className="rounded-md border border-border bg-white p-3 text-sm">{message}</div> : null}
    </div>
  );
}
