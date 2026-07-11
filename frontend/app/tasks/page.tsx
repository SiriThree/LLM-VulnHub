"use client";

import { useEffect, useMemo, useState } from "react";
import { RefreshCw, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { api, TaskListResponse, TaskRecord } from "@/lib/api";

const STAGE_LABELS: Record<string, string> = {
  queued: "排队中",
  fetching: "抓取源内容",
  parsing: "解析候选内容",
  filtering: "AI 相关性筛选",
  extracting: "结构化抽取",
  deduplicating: "相似去重",
  reviewing: "待人工复核",
  storing: "标准化入库",
  completed: "完成",
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
    ["已入库", metrics.saved],
    ["待复核", metrics.pending_review],
    ["重复跳过", metrics.duplicates],
    ["忽略", metrics.ignored],
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
  const [loading, setLoading] = useState(true);
  const [message, setMessage] = useState("");

  async function load() {
    try {
      const res = await api<TaskListResponse>("/tasks");
      setTasks(res.items);
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

  const activeCount = useMemo(
    () => tasks.filter((task) => task.status === "queued" || task.status === "running").length,
    [tasks],
  );

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">任务中心</h1>
          <p className="text-sm text-slate-500">
            观察采集任务从排队、抓取、筛选、抽取、去重到审核入库的完整流水线。
          </p>
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

      <div className="space-y-4">
        {tasks.map((task) => (
          <Card key={task.id} className="space-y-4">
            <div className="flex items-start justify-between gap-4">
              <div>
                <div className="flex items-center gap-3">
                  <h2 className="text-lg font-semibold">任务 #{task.id}</h2>
                  <span className="rounded bg-slate-100 px-2 py-1 text-xs font-medium text-slate-700">
                    {task.task_type}
                  </span>
                  <span className="rounded bg-primary/10 px-2 py-1 text-xs font-medium text-primary">
                    {task.status}
                  </span>
                  <StageBadge value={task.output_data.current_stage} />
                </div>
                <p className="mt-2 text-sm text-slate-500">{task.output_data.last_message ?? "暂无消息"}</p>
                <p className="mt-1 text-xs text-slate-400">
                  创建时间 {new Date(task.created_at).toLocaleString()} · 更新时间{" "}
                  {new Date(task.updated_at).toLocaleString()}
                </p>
                <p className="mt-1 text-xs text-slate-400">
                  执行模式 {task.output_data.execution_mode ?? "pending"} · 尝试次数{" "}
                  {task.output_data.attempt_count ?? 0}/{task.output_data.max_attempts ?? 0}
                  {task.output_data.elapsed_seconds != null
                    ? ` · 耗时 ${task.output_data.elapsed_seconds}s`
                    : ""}
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
                <div className="border-b border-border px-4 py-3 text-sm font-semibold">源执行明细</div>
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
                        <div>入库 {run.saved}</div>
                        <div>待复核 {run.pending_review}</div>
                        <div>重复 {run.duplicates}</div>
                        <div>忽略 {run.ignored}</div>
                      </div>
                      {run.elapsed_seconds != null ? (
                        <div className="mt-2 text-xs text-slate-500">源耗时 {run.elapsed_seconds}s</div>
                      ) : null}
                      {run.error ? <div className="mt-2 text-xs text-danger">{run.error}</div> : null}
                    </div>
                  ))}
                </div>
              </div>
            </div>

            {task.error_message ? (
              <div className="rounded-md border border-danger/30 bg-red-50 p-3 text-sm text-danger">
                {task.error_message}
              </div>
            ) : null}
          </Card>
        ))}
      </div>
    </div>
  );
}
