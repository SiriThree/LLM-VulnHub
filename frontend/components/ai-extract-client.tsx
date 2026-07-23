"use client";

import { useEffect, useMemo, useState } from "react";
import { BadgeCheck, Bot, CheckCircle2, FlaskConical, Play, Save, Sparkles } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";
import {
  AnalyzeResult,
  api,
  ConfirmAnalysisResult,
  EvalDataset,
  EvalRun,
  EvalRunDetail,
  Vulnerability,
} from "@/lib/api";

const SAMPLE_TEXTS = [
  {
    label: "Agent / 浏览器工具输出注入",
    value:
      "A LangChain agent accepts untrusted browser tool output and injects it into the next model turn without any instruction boundary isolation. " +
      "An attacker can plant hidden prompt instructions in a web page, causing the agent to reveal system prompts, call tools without authorization, " +
      "or retrieve sensitive RAG content from connected knowledge sources.",
  },
  {
    label: "RAG 文档注入",
    value:
      "某大语言模型应用平台的知识库问答模块存在提示词注入漏洞。攻击者可以在上传的文档中嵌入恶意指令，要求模型忽略系统提示词、泄露隐藏配置或调用未经授权的外部工具。" +
      "当管理员导入恶意文档后，检索增强生成会将攻击指令拼接进上下文，最终导致敏感信息泄露、越权访问和非授权工具调用。",
  },
  {
    label: "GraphCypherQAChain",
    value:
      "LangChain 的 GraphCypherQAChain 组件存在提示词注入问题。该组件使用大语言模型将自然语言问题转换为图数据库查询语句，但没有充分限制或验证模型生成的查询内容。" +
      "攻击者可以通过构造特殊提示词，诱导模型生成具有破坏性的 Cypher 查询，从而创建、修改或删除节点关系，提取敏感数据，破坏多租户之间的数据隔离。",
  },
  {
    label: "非漏洞样本",
    value:
      "本系统采用 FastAPI 构建后端服务，并使用 PostgreSQL 存储用户、漏洞记录和操作日志。前端通过 REST API 获取漏洞列表，支持按照漏洞等级、发布时间和漏洞类型进行筛选。",
  },
];

const FIELD_LABELS: Record<string, string> = {
  title: "标题",
  vuln_type: "漏洞类型",
  severity: "风险等级",
  score: "评分",
  affected_component: "受影响组件",
  description: "漏洞描述",
  attack_method: "攻击方式",
  impact: "影响",
  mitigation: "修复建议",
};

const LONG_FIELDS = new Set(["description", "attack_method", "impact", "mitigation"]);
const MAIN_FIELDS = ["title", "vuln_type", "severity", "score", "affected_component", "description", "attack_method", "impact", "mitigation"] as const;

type EditableExtract = Partial<Vulnerability> & {
  tags?: string[];
  risk_reason?: string;
  review_summary?: string;
  asset_impact_summary?: string;
  asset_impact_details?: Record<string, unknown>;
  similar?: Vulnerability[];
  merge_suggestions?: Record<string, unknown>;
};

function pct(value: number | undefined | null) {
  if (value == null) return "-";
  return `${Math.round(value * 100)}%`;
}

function statusTone(ok: boolean | undefined | null) {
  if (ok == null) return "bg-slate-100 text-slate-600";
  return ok ? "bg-emerald-100 text-emerald-700" : "bg-rose-100 text-rose-700";
}

function buildPayload(result: EditableExtract): Omit<Vulnerability, "id" | "created_at" | "updated_at"> {
  return {
    title: String(result.title ?? ""),
    vuln_type: String(result.vuln_type ?? "待确认"),
    severity: String(result.severity ?? "中危"),
    score: Number(result.score ?? 0),
    affected_component: String(result.affected_component ?? "待确认"),
    description: String(result.description ?? ""),
    attack_method: String(result.attack_method ?? "原文未提供，需人工补充。"),
    impact: String(result.impact ?? "原文未提供，需人工补充。"),
    mitigation: String(result.mitigation ?? "原文未提供，需人工补充。"),
    source: result.source ?? null,
    reference_url: result.reference_url ?? null,
    source_url: result.source_url ?? null,
    confidence: Number(result.confidence ?? 0),
    status: String(result.status ?? "待人工复核"),
    visibility: result.visibility ?? "internal",
    tags: result.tags ?? [],
  };
}

export function AiExtractClient() {
  const [mode, setMode] = useState<"workspace" | "quality">("workspace");
  const [raw, setRaw] = useState(SAMPLE_TEXTS[0].value);
  const [analysis, setAnalysis] = useState<AnalyzeResult | null>(null);
  const [originalResult, setOriginalResult] = useState<EditableExtract | null>(null);
  const [result, setResult] = useState<EditableExtract | null>(null);
  const [reviewNote, setReviewNote] = useState("");
  const [loading, setLoading] = useState(false);
  const [saving, setSaving] = useState(false);
  const [message, setMessage] = useState("");

  const [dataset, setDataset] = useState<EvalDataset | null>(null);
  const [evalRuns, setEvalRuns] = useState<EvalRun[]>([]);
  const [latestEval, setLatestEval] = useState<EvalRunDetail | null>(null);
  const [evalLoading, setEvalLoading] = useState(true);
  const [evalRunning, setEvalRunning] = useState(false);

  const modifiedFields = useMemo(() => {
    if (!originalResult || !result) return [];
    return MAIN_FIELDS.filter((key) => String(originalResult[key] ?? "") !== String(result[key] ?? ""));
  }, [originalResult, result]);

  useEffect(() => {
    loadEvaluation();
  }, []);

  async function loadEvaluation() {
    setEvalLoading(true);
    try {
      const [datasetRes, runsRes, latestRes] = await Promise.all([
        api<EvalDataset>("/ai/evaluation/dataset"),
        api<EvalRun[]>("/ai/evaluation/runs"),
        api<EvalRunDetail | null>("/ai/evaluation/runs/latest"),
      ]);
      setDataset(datasetRes);
      setEvalRuns(runsRes);
      setLatestEval(latestRes);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "加载评测信息失败。");
    } finally {
      setEvalLoading(false);
    }
  }

  async function handleExtract() {
    setLoading(true);
    setMessage("");
    try {
      const analyzed = await api<AnalyzeResult>("/ai/analyze", {
        method: "POST",
        body: JSON.stringify({ raw_text: raw, save: false }),
      });
      setAnalysis(analyzed);
      setOriginalResult(analyzed.extracted);
      setResult(analyzed.extracted);
      setReviewNote("");
      setMode("workspace");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "分析失败。");
    } finally {
      setLoading(false);
    }
  }

  async function handleConfirm() {
    if (!result || !analysis?.analysis_job) return;
    setSaving(true);
    setMessage("");
    try {
      const confirmed = await api<ConfirmAnalysisResult>("/ai/confirm", {
        method: "POST",
        body: JSON.stringify({
          analysis_job_id: analysis.analysis_job.id,
          vulnerability: buildPayload(result),
          review_note: reviewNote || "Analyst reviewed and confirmed the extracted record.",
        }),
      });
      setMessage(`已确认入库：#${confirmed.vulnerability.id} ${confirmed.vulnerability.title}`);
      setResult(confirmed.vulnerability);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "确认入库失败。");
    } finally {
      setSaving(false);
    }
  }

  async function handleRunEval() {
    setEvalRunning(true);
    setMessage("");
    try {
      const latest = await api<EvalRunDetail>("/ai/evaluation/run", { method: "POST" });
      setLatestEval(latest);
      setEvalRuns((current) => [latest, ...current.filter((item) => item.file_name !== latest.file_name)]);
      setMessage(`已完成回归评测：${latest.file_name}`);
      setMode("quality");
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "运行评测失败。");
    } finally {
      setEvalRunning(false);
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
      <div className="flex flex-wrap items-center justify-between gap-3">
        <div className="inline-flex rounded-md border border-border bg-white p-1">
          <button
            className={`rounded-md px-3 py-1.5 text-sm ${mode === "workspace" ? "bg-primary text-white" : "text-slate-600"}`}
            onClick={() => setMode("workspace")}
            type="button"
          >
            抽取工作台
          </button>
          <button
            className={`rounded-md px-3 py-1.5 text-sm ${mode === "quality" ? "bg-primary text-white" : "text-slate-600"}`}
            onClick={() => setMode("quality")}
            type="button"
          >
            质量评估
          </button>
        </div>

        <div className="flex flex-wrap gap-2">
          {SAMPLE_TEXTS.map((item) => (
            <button
              key={item.label}
              className="rounded-md border border-border px-3 py-1.5 text-sm text-slate-600 hover:border-primary hover:text-primary"
              onClick={() => setRaw(item.value)}
              type="button"
            >
              {item.label}
            </button>
          ))}
        </div>
      </div>

      {mode === "workspace" ? (
        <>
          <div className="grid gap-4 xl:grid-cols-[1.05fr_1.15fr]">
            <Card className="space-y-4">
              <div>
                <h2 className="font-semibold">原始漏洞文本</h2>
                <p className="mt-1 text-sm text-slate-500">输入原文后执行相关性判断、字段抽取、风险评分和相似记录比对。</p>
              </div>
              <Textarea
                className="min-h-[480px]"
                maxLength={12000}
                value={raw}
                onChange={(event) => setRaw(event.target.value)}
              />
              <div className="flex flex-wrap items-center gap-3">
                <Button disabled={loading} onClick={handleExtract} type="button">
                  <Bot size={16} />
                  {loading ? "分析中..." : "开始提取"}
                </Button>
                {analysis?.analysis_job ? (
                  <div className="text-sm text-slate-500">
                    Job #{analysis.analysis_job.id} · {analysis.analysis_job.pipeline_name} · {analysis.analysis_job.model_name}
                  </div>
                ) : null}
              </div>
            </Card>

            <Card className="space-y-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <h2 className="font-semibold">结构化审阅结果</h2>
                  <p className="mt-1 text-sm text-slate-500">系统保留模型原始结果；请逐字段核对，修订后再确认入库。</p>
                </div>
                {modifiedFields.length > 0 ? (
                  <div className="rounded-md bg-amber-100 px-2 py-1 text-xs text-amber-700">已修改 {modifiedFields.length} 个字段</div>
                ) : null}
              </div>

              {result ? (
                <>
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-md border border-border bg-slate-50 p-3">
                      <div className="text-xs text-slate-500">模型相关性判断</div>
                      <div className="mt-1 font-medium">
                        {analysis?.relevance.is_ai_vulnerability ? "识别为 AI 漏洞文本" : "未识别为 AI 漏洞文本"}
                      </div>
                      <div className="mt-1 text-sm text-slate-600">置信度 {pct(analysis?.relevance.confidence)}</div>
                    </div>
                    <div className="rounded-md border border-border bg-slate-50 p-3">
                      <div className="text-xs text-slate-500">领域分类</div>
                      <div className="mt-1 font-medium">{analysis?.relevance.related_area || "-"}</div>
                      <div className="mt-1 text-sm text-slate-600">{analysis?.relevance.reason || "-"}</div>
                    </div>
                  </div>

                  <div className="space-y-3">
                    {MAIN_FIELDS.map((key) => {
                      const changed = modifiedFields.includes(key);
                      return (
                        <label className="block" key={key}>
                          <div className="mb-1 flex items-center justify-between gap-3">
                            <span className="text-sm font-medium text-slate-700">{FIELD_LABELS[key]}</span>
                            {changed ? <span className="text-xs text-amber-700">人工已修订</span> : null}
                          </div>
                          {LONG_FIELDS.has(key) ? (
                            <Textarea
                              className={changed ? "border-amber-300" : ""}
                              maxLength={12000}
                              value={String(result[key] ?? "")}
                              onChange={(event) => updateField(key, event.target.value)}
                            />
                          ) : (
                            <Input
                              className={changed ? "border-amber-300" : ""}
                              maxLength={300}
                              value={String(result[key] ?? "")}
                              onChange={(event) => updateField(key, event.target.value)}
                            />
                          )}
                        </label>
                      );
                    })}
                  </div>

                  <div className="grid gap-3 xl:grid-cols-2">
                    <div className="rounded-md border border-border bg-slate-50 p-3 text-sm text-slate-700">
                      <div className="font-medium">Risk Explanation Agent</div>
                      <div className="mt-2 whitespace-pre-wrap">{result.risk_reason || "-"}</div>
                    </div>
                    <div className="rounded-md border border-border bg-slate-50 p-3 text-sm text-slate-700">
                      <div className="font-medium">Reviewer Agent</div>
                      <div className="mt-2 whitespace-pre-wrap">{result.review_summary || "-"}</div>
                    </div>
                  </div>

                  <div className="rounded-md border border-border bg-slate-50 p-3 text-sm text-slate-700">
                    <div className="font-medium">Asset Impact Agent</div>
                    <div className="mt-3 grid gap-3 md:grid-cols-2">
                      {Object.entries(result.asset_impact_details ?? {}).map(([key, value]) => (
                        <div key={key} className="rounded-md bg-white p-3">
                          <div className="text-xs uppercase text-slate-400">{key}</div>
                          <div className="mt-1 break-words">{String(value)}</div>
                        </div>
                      ))}
                    </div>
                    <div className="mt-3 rounded-md bg-white p-3">{result.asset_impact_summary || "-"}</div>
                  </div>

                  <div className="rounded-md border border-border bg-slate-50 p-3 text-sm text-slate-700">
                    <div className="font-medium">Merge Suggestions</div>
                    <div className="mt-2 whitespace-pre-wrap">
                      {String(result.merge_suggestions?.reason ?? "暂无合并建议。")}
                    </div>
                    {result.similar && result.similar.length > 0 ? (
                      <div className="mt-3 grid gap-2">
                        {result.similar.map((item) => (
                          <div key={item.id} className="rounded-md bg-white p-3">
                            <div className="font-medium">#{item.id} {item.title}</div>
                            <div className="mt-1 text-sm text-slate-600">
                              {item.vuln_type} · {item.severity} · {item.affected_component}
                            </div>
                          </div>
                        ))}
                      </div>
                    ) : null}
                  </div>

                  <div className="space-y-3 rounded-md border border-border p-3">
                    <div className="flex items-center gap-2">
                      <BadgeCheck size={16} />
                      <div className="font-medium">人工修订闭环</div>
                    </div>
                    <p className="text-sm text-slate-500">
                      模型原始结果保存在分析任务中，当前表单保存的是人工修订后的正式漏洞记录。
                    </p>
                    <Textarea
                      className="min-h-24"
                      maxLength={2000}
                      placeholder="填写人工复核说明，例如：补充修复建议、修正漏洞类型、确认是否入库。"
                      value={reviewNote}
                      onChange={(event) => setReviewNote(event.target.value)}
                    />
                    <Button disabled={saving || !analysis?.analysis_job} onClick={handleConfirm} type="button">
                      <Save size={16} />
                      {saving ? "确认中..." : "确认入库"}
                    </Button>
                  </div>
                </>
              ) : (
                <div className="rounded-md bg-muted p-4 text-sm text-slate-500">等待分析结果。</div>
              )}
            </Card>
          </div>

          {analysis?.analysis_job ? (
            <Card className="space-y-4">
              <div className="flex items-center gap-2">
                <Sparkles size={16} />
                <h2 className="font-semibold">分析执行轨迹</h2>
              </div>

              <div className="rounded-md border border-border bg-slate-50 p-3 text-sm text-slate-700">
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
                    <div className="mt-2 line-clamp-5 text-xs text-slate-700">{JSON.stringify(item.output_payload)}</div>
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
        </>
      ) : (
        <div className="space-y-4">
          <Card className="space-y-4">
            <div className="flex items-start justify-between gap-3">
              <div>
                <h2 className="font-semibold">抽取评测集与回归指标</h2>
                <p className="mt-1 text-sm text-slate-500">用标注样本验证相关性判断、字段完整率和合并候选质量。</p>
              </div>
              <Button disabled={evalRunning} onClick={handleRunEval} type="button">
                <Play size={16} />
                {evalRunning ? "运行中..." : "运行评测"}
              </Button>
            </div>

            <div className="grid gap-3 md:grid-cols-4">
              <div className="rounded-md border border-border bg-slate-50 p-3">
                <div className="text-xs text-slate-500">评测样本数</div>
                <div className="mt-1 text-2xl font-semibold">{dataset?.dataset_size ?? "-"}</div>
              </div>
              <div className="rounded-md border border-border bg-slate-50 p-3">
                <div className="text-xs text-slate-500">AI 漏洞样本</div>
                <div className="mt-1 text-2xl font-semibold">{dataset?.positive_samples ?? "-"}</div>
              </div>
              <div className="rounded-md border border-border bg-slate-50 p-3">
                <div className="text-xs text-slate-500">非漏洞 / 噪声样本</div>
                <div className="mt-1 text-2xl font-semibold">{dataset?.negative_samples ?? "-"}</div>
              </div>
              <div className="rounded-md border border-border bg-slate-50 p-3">
                <div className="text-xs text-slate-500">最近一次 Provider</div>
                <div className="mt-1 text-2xl font-semibold">{latestEval?.provider ?? "-"}</div>
              </div>
            </div>

            <div className="grid gap-3 xl:grid-cols-[0.9fr_1.1fr]">
              <div className="rounded-md border border-border bg-slate-50 p-3">
                <div className="mb-3 flex items-center gap-2 font-medium">
                  <FlaskConical size={16} />
                  数据集分布
                </div>
                <div className="space-y-2">
                  {Object.entries(dataset?.categories ?? {}).map(([key, value]) => (
                    <div key={key}>
                      <div className="mb-1 flex items-center justify-between text-sm">
                        <span>{key}</span>
                        <span>{value}</span>
                      </div>
                      <div className="h-2 rounded-full bg-slate-200">
                        <div
                          className="h-2 rounded-full bg-primary"
                          style={{ width: `${dataset ? (value / dataset.dataset_size) * 100 : 0}%` }}
                        />
                      </div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-md border border-border bg-slate-50 p-3">
                <div className="mb-3 font-medium">最近一次评测结果</div>
                {latestEval ? (
                  <div className="grid gap-3 md:grid-cols-2">
                    <div className="rounded-md bg-white p-3">
                      <div className="text-xs text-slate-500">Triage Accuracy</div>
                      <div className="mt-1 text-xl font-semibold">{pct(latestEval.triage_accuracy)}</div>
                    </div>
                    <div className="rounded-md bg-white p-3">
                      <div className="text-xs text-slate-500">Triage Precision / Recall</div>
                      <div className="mt-1 text-xl font-semibold">
                        {pct(latestEval.triage_precision)} / {pct(latestEval.triage_recall)}
                      </div>
                    </div>
                    <div className="rounded-md bg-white p-3">
                      <div className="text-xs text-slate-500">字段完整率</div>
                      <div className="mt-1 text-xl font-semibold">{pct(latestEval.extraction_completeness)}</div>
                    </div>
                    <div className="rounded-md bg-white p-3">
                      <div className="text-xs text-slate-500">Merge Precision</div>
                      <div className="mt-1 text-xl font-semibold">{pct(latestEval.merge_precision)}</div>
                    </div>
                  </div>
                ) : (
                  <div className="text-sm text-slate-500">{evalLoading ? "加载中..." : "还没有评测结果。"}</div>
                )}
              </div>
            </div>
          </Card>

          <Card className="space-y-4">
            <h2 className="font-semibold">按样本查看评测表现</h2>
            {latestEval ? (
              <div className="space-y-3">
                {latestEval.samples.slice(0, 12).map((item) => (
                  <div key={item.id} className="rounded-md border border-border p-3">
                    <div className="flex flex-wrap items-center gap-2">
                      <div className="font-medium">{item.id}</div>
                      <span className={`rounded px-2 py-0.5 text-xs ${statusTone(item.triage_correct)}`}>
                        {item.triage_correct ? "Triage 正确" : "Triage 失配"}
                      </span>
                      {item.merge_correct != null ? (
                        <span className={`rounded px-2 py-0.5 text-xs ${statusTone(item.merge_correct)}`}>
                          {item.merge_correct ? "Merge 正确" : "Merge 失配"}
                        </span>
                      ) : null}
                    </div>
                    <div className="mt-2 grid gap-2 text-sm text-slate-600 md:grid-cols-4">
                      <div>预期 AI：{item.expected_ai ? "是" : "否"}</div>
                      <div>预测 AI：{item.predicted_ai ? "是" : "否"}</div>
                      <div>置信度：{pct(item.confidence)}</div>
                      <div>完整率：{pct(item.extraction_completeness ?? undefined)}</div>
                    </div>
                    {Object.keys(item.extraction_exact ?? {}).length > 0 ? (
                      <div className="mt-3 flex flex-wrap gap-2">
                        {Object.entries(item.extraction_exact).map(([key, ok]) => (
                          <span key={key} className={`rounded px-2 py-1 text-xs ${statusTone(ok)}`}>
                            {key}: {ok ? "命中" : "失配"}
                          </span>
                        ))}
                      </div>
                    ) : null}
                    {item.errors.length > 0 ? <div className="mt-2 text-sm text-rose-600">{item.errors.join(" | ")}</div> : null}
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-slate-500">先运行一次评测，就能看到逐样本结果。</div>
            )}
          </Card>

          <Card className="space-y-4">
            <h2 className="font-semibold">历史评测记录</h2>
            <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
              {evalRuns.map((item) => (
                <div key={item.file_name} className="rounded-md border border-border p-3">
                  <div className="font-medium">{item.file_name}</div>
                  <div className="mt-1 text-xs text-slate-500">{item.provider} · {new Date(item.generated_at).toLocaleString()}</div>
                  <div className="mt-3 space-y-1 text-sm text-slate-600">
                    <div>样本数：{item.dataset_size}</div>
                    <div>准确率：{pct(item.triage_accuracy)}</div>
                    <div>完整率：{pct(item.extraction_completeness)}</div>
                    <div>Merge Precision：{pct(item.merge_precision)}</div>
                  </div>
                </div>
              ))}
              {!evalLoading && evalRuns.length === 0 ? <div className="text-sm text-slate-500">还没有评测记录。</div> : null}
            </div>
          </Card>
        </div>
      )}

      {message ? (
        <div className="rounded-md border border-border bg-white p-3 text-sm">
          <div className="flex items-start gap-2">
            <CheckCircle2 className="mt-0.5 text-primary" size={16} />
            <div>{message}</div>
          </div>
        </div>
      ) : null}
    </div>
  );
}
