"use client";

import { useEffect, useState } from "react";
import { FlaskConical, Play, ScrollText } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, EvalRun, PromptRegistryItem } from "@/lib/api";

function pct(value: number) {
  return `${Math.round(value * 100)}%`;
}

export function PromptEvalPanel() {
  const [prompts, setPrompts] = useState<PromptRegistryItem[]>([]);
  const [evals, setEvals] = useState<EvalRun[]>([]);
  const [loading, setLoading] = useState(true);
  const [running, setRunning] = useState(false);
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const [promptItems, evalRuns] = await Promise.all([
        api<PromptRegistryItem[]>("/ops/prompts"),
        api<EvalRun[]>("/ops/evals"),
      ]);
      setPrompts(promptItems);
      setEvals(evalRuns);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "加载 Prompt / Eval 信息失败。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
  }, []);

  async function runEval() {
    setRunning(true);
    setMessage("");
    try {
      const latest = await api<EvalRun>("/ops/evals/run", { method: "POST" });
      setEvals((current) => [latest, ...current.filter((item) => item.file_name !== latest.file_name)]);
      setMessage(`已完成一次评测：${latest.file_name}`);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "触发评测失败。");
    } finally {
      setRunning(false);
    }
  }

  return (
    <div className="grid gap-4 xl:grid-cols-2">
      <Card className="space-y-4">
        <div className="flex items-start gap-3">
          <div className="rounded-md bg-muted p-2 text-primary">
            <ScrollText size={18} />
          </div>
          <div>
            <h2 className="font-semibold">Prompt Registry</h2>
            <p className="text-sm text-slate-500">查看各 Agent Prompt 的版本、必填字段和历史调用情况。</p>
          </div>
        </div>

        <div className="space-y-3">
          {prompts.map((item) => (
            <div key={item.key} className="rounded-md border border-border bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium">{item.key}</div>
                  <div className="text-xs text-slate-500">{item.agent_name} · {item.version}</div>
                </div>
                <div className="text-right text-xs text-slate-500">
                  <div>调用 {item.usage_count}</div>
                  <div>成功 {item.success_count} / 失败 {item.failure_count}</div>
                </div>
              </div>
              <div className="mt-3 text-sm text-slate-600">平均延迟 {item.avg_latency_ms} ms</div>
              <div className="mt-2 flex flex-wrap gap-2">
                {item.required_keys.map((key) => (
                  <span key={key} className="rounded bg-white px-2 py-1 text-xs text-slate-600">
                    {key}
                  </span>
                ))}
              </div>
            </div>
          ))}
          {!loading && prompts.length === 0 ? <div className="text-sm text-slate-500">暂无 Prompt 统计。</div> : null}
        </div>
      </Card>

      <Card className="space-y-4">
        <div className="flex items-start justify-between gap-3">
          <div className="flex items-start gap-3">
            <div className="rounded-md bg-muted p-2 text-primary">
              <FlaskConical size={18} />
            </div>
            <div>
              <h2 className="font-semibold">评测结果</h2>
              <p className="text-sm text-slate-500">展示离线标注集的最近评测记录，可直接触发一次回归。</p>
            </div>
          </div>
          <Button type="button" onClick={runEval} disabled={running}>
            <Play size={16} />
            {running ? "运行中" : "运行评测"}
          </Button>
        </div>

        {message ? <div className="rounded-md bg-muted px-3 py-2 text-sm text-slate-600">{message}</div> : null}

        <div className="space-y-3">
          {evals.map((item) => (
            <div key={item.file_name} className="rounded-md border border-border bg-slate-50 p-3">
              <div className="flex items-center justify-between gap-3">
                <div>
                  <div className="font-medium">{item.file_name}</div>
                  <div className="text-xs text-slate-500">{item.provider} · {new Date(item.generated_at).toLocaleString()}</div>
                </div>
                <div className="text-sm text-slate-500">样本 {item.dataset_size}</div>
              </div>
              <div className="mt-3 grid gap-2 text-sm text-slate-600 md:grid-cols-2">
                <div>准确率 {pct(item.triage_accuracy)}</div>
                <div>精确率 {pct(item.triage_precision)}</div>
                <div>召回率 {pct(item.triage_recall)}</div>
                <div>抽取完整度 {pct(item.extraction_completeness)}</div>
                <div>合并精度 {pct(item.merge_precision)}</div>
              </div>
            </div>
          ))}
          {!loading && evals.length === 0 ? <div className="text-sm text-slate-500">还没有评测结果文件。</div> : null}
        </div>
      </Card>
    </div>
  );
}
