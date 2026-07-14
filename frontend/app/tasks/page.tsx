"use client";

import { useEffect, useMemo, useState } from "react";
import { RefreshCw, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, DeadLetterTask, TaskListResponse, TaskRecord } from "@/lib/api";

const STAGE_LABELS: Record<string, string> = {
  queued: "排队中",
  fetching: "抓取来源内容",
  parsing: "解析候选内容",
  ingesting: "原始入池",
  queued_analysis: "等待分析",
  analyzing: "AI 分析",
  filtering: "AI 相关性判断",
  extracting: "结构化抽取",
  deduplicating: "相似去重",
  reviewing: "审阅辅助",
  notifying: "发送通知",
  storing: "标准化入库",
  completed: "完成",
  failed: "失败",
};

function StageBadge({ value }: { value?: string }) {
  const label = value ? STAGE_LABELS[value] ?? value : "-";
  return <span className="rounded bg-muted px-2 py-1 text-xs font-medium text-slate-700">{label}</span>;
}

function MetricCards({ task }: { task: TaskRecord }) {
  const metrics = task.output_data.metrics;
  if (!metrics) return null;

  const items = [
    ["发现候选", metrics.discovered],
    ["已处理", metrics.processed],
    ["等待分析", metrics.queued_analysis],
    ["等待复核", metrics.queued_review],
    ["通知", metrics.notifications],
    ["重复跳过", metrics.duplicates],
  ];

  return (
    <div className="grid grid-cols-2 gap-3 xl:grid-cols-6">
      {items.map(([label, value]) => (
        <div key={String(label)} className="rounded-md border border-border bg-white p-3">
          <div className="text-xs text-slate-500">{label}</div>
          <div className="mt-1 text-xl font-semibold">{value}</div>
        </div>
      ))}
    </div>
  );
}

export default function TasksPage() {
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [deadLetters, setDeadLetters] = useState<DeadLetterTask[]>([]);
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const [taskRes, deadLetterRes] = await Promise.all([
        api<TaskListResponse>("/tasks"),
        api<DeadLetterTask[]>("/ops/dead-letter"),
      ]);
      setTasks(taskRes.items);
      setDeadLetters(deadLetterRes);
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "加载任务失败。");
    } finally {
      setLoading(false);
    }
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 4000);
    return () => window.clearInterval(timer);
  }, []);

  async function retryTask(taskId: number) {
    setMessage("");
    try {
      await api(`/tasks/${taskId}/retry`, { method: "POST" });
      setMessage(`任务 #${taskId} 已重新排队。`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "任务重试失败。");
    }
  }

  async function requeueDeadLetter(taskId: number) {
    setMessage("");
    try {
      await api(`/ops/dead-letter/${taskId}/requeue`, { method: "POST" });
      setMessage(`死信任务 #${taskId} 已重新入队。`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "死信任务恢复失败。");
    }
  }

  const activeCount = useMemo(() => tasks.filter((task) => task.status === "queued" || task.status === "running").length, [tasks]);

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">任务中心</h1>
          <p className="text-sm text-slate-500">统一观察 ingestion、analysis、review、notification 四段异步流水线。</p>
        </div>
        <div className="flex items-center gap-3">
          <span className="text-sm text-slate-500">活跃任务 {activeCount}</span>
          <Button type="button" onClick={load} disabled={loading}>
            <RefreshCw size={16} />
            刷新
          </Button>
        </div>
      </div>

      {message ? <div className="rounded-md border border-border bg-white p-3 text-sm">{message}</div> : null}

      <Card className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">Dead Letter Queue</h2>
            <p className="text-sm text-slate-500">达到最大重试次数的任务会停留在这里，等待人工排障与恢复。</p>
          </div>
          <div className="text-sm text-slate-500">当前 {deadLetters.length} 条</div>
        </div>

        <div className="space-y-3">
          {deadLetters.map((item) => (
            <div key={item.id} className="rounded-md border border-border bg-slate-50 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">任务 #{item.id} · {item.task_type}</div>
                  <div className="mt-1 text-sm text-slate-600">{item.dead_letter_reason || item.error_message || "No reason recorded."}</div>
                  <div className="mt-2 text-xs text-slate-500">
                    尝试 {item.attempt_count}/{item.max_attempts} · 阶段 {item.current_stage || "-"} · 队列 {item.queue_name || "-"} · 更新时间 {new Date(item.updated_at).toLocaleString()}
                  </div>
                </div>
                <Button type="button" onClick={() => requeueDeadLetter(item.id)}>
                  <RotateCcw size={16} />
                  重新入队
                </Button>
              </div>
            </div>
          ))}
          {deadLetters.length === 0 ? <div className="text-sm text-slate-500">当前没有死信任务。</div> : null}
        </div>
      </Card>

      <div className="space-y-4">
        {tasks.map((task) => (
          <Card key={task.id} className="space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-semibold">任务 #{task.id}</h2>
                  <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">{task.task_type}</span>
                  <span className="rounded bg-primary/10 px-2 py-1 text-xs font-medium text-primary">{task.status}</span>
                  <StageBadge value={task.output_data.current_stage} />
                  {task.output_data.dead_letter ? <span className="rounded bg-red-100 px-2 py-1 text-xs font-medium text-red-700">dead-letter</span> : null}
                </div>
                <p className="mt-2 text-sm text-slate-500">{task.output_data.last_message ?? "暂无消息"}</p>
                <p className="mt-1 text-xs text-slate-400">
                  创建时间 {new Date(task.created_at).toLocaleString()} · 更新时间 {new Date(task.updated_at).toLocaleString()}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  执行模式 {task.output_data.execution_mode ?? "pending"} · 尝试次数 {task.output_data.attempt_count ?? 0}/{task.output_data.max_attempts ?? 0}
                  {task.output_data.elapsed_seconds != null ? ` · 耗时 ${task.output_data.elapsed_seconds}s` : ""}
                </p>
              </div>
              {task.status === "failed" ? (
                <Button type="button" onClick={() => retryTask(task.id)}>
                  <RotateCcw size={16} />
                  重试
                </Button>
              ) : null}
            </div>

            <MetricCards task={task} />

            <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-md border border-border">
                <div className="border-b border-border px-4 py-3 text-sm font-semibold">阶段轨迹</div>
                <div className="max-h-72 space-y-3 overflow-auto p-4">
                  {(task.output_data.stage_history ?? []).map((item, index) => (
                    <div key={`${item.timestamp}-${index}`} className="rounded-md bg-slate-50 p-3">
                      <div className="flex items-center justify-between text-sm">
                        <span className="font-medium">{STAGE_LABELS[item.stage] ?? item.stage}</span>
                        <span className="text-slate-400">{new Date(item.timestamp).toLocaleTimeString()}</span>
                      </div>
                      <div className="mt-1 text-sm text-slate-600">{item.message}</div>
                    </div>
                  ))}
                </div>
              </div>

              <div className="rounded-md border border-border">
                <div className="border-b border-border px-4 py-3 text-sm font-semibold">来源执行明细</div>
                <div className="max-h-72 space-y-3 overflow-auto p-4">
                  {(task.output_data.source_runs ?? []).map((run) => (
                    <div key={run.source_id} className="rounded-md bg-slate-50 p-3">
                      <div className="flex items-center justify-between gap-3">
                        <div>
                          <div className="font-medium">{run.source_name}</div>
                          <div className="text-xs text-slate-500">{run.source_type}</div>
                        </div>
                        <div className="flex items-center gap-2">
                          <span className="rounded bg-white px-2 py-1 text-xs">{run.status}</span>
                          <StageBadge value={run.stage} />
                        </div>
                      </div>
                      <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-600">
                        <div>发现 {run.discovered}</div>
                        <div>处理 {run.processed}</div>
                        <div>待分析 {run.queued_analysis ?? 0}</div>
                        <div>待复核 {run.pending_review}</div>
                        <div>重复 {run.duplicates}</div>
                        <div>忽略 {run.ignored}</div>
                      </div>
                      {run.elapsed_seconds != null ? <div className="mt-2 text-xs text-slate-500">来源耗时 {run.elapsed_seconds}s</div> : null}
                      {run.error ? <div className="mt-2 text-xs text-red-600">{run.error}</div> : null}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {task.error_message ? <div className="rounded-md border border-red-200 bg-red-50 p-3 text-sm text-red-700">{task.error_message}</div> : null}
          </Card>
        ))}
      </div>
    </div>
  );
}
