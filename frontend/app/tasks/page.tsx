"use client";

import { useEffect, useState } from "react";
import { Archive, RefreshCw, RotateCcw, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHero } from "@/components/page-hero";
import { Pagination } from "@/components/pagination";
import {
  api,
  AuthSession,
  DeadLetterTask,
  TaskListResponse,
  TaskRecord,
} from "@/lib/api";

type TaskSourceGroup = {
  source_id: number;
  source_name: string;
  task_count: number;
  active_count: number;
};

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
  const [deleting, setDeleting] = useState(false);
  const [message, setMessage] = useState("");
  const [canDeleteTasks, setCanDeleteTasks] = useState(false);
  const [sourceGroups, setSourceGroups] = useState<TaskSourceGroup[]>([]);
  const [deleteSourceId, setDeleteSourceId] = useState("");
  const [failedTasks, setFailedTasks] = useState<TaskRecord[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [taskStatus, setTaskStatus] = useState("");
  const [failedPage, setFailedPage] = useState(1);
  const [failedPageSize, setFailedPageSize] = useState(5);
  const [deadLetterPage, setDeadLetterPage] = useState(1);
  const [deadLetterPageSize, setDeadLetterPageSize] = useState(5);
  const [total, setTotal] = useState(0);
  const [stats, setStats] = useState<TaskListResponse["stats"]>({
    total: 0,
    queued: 0,
    running: 0,
    success: 0,
    failed: 0,
    dead_letter: 0,
  });

  async function load() {
    try {
      const taskQuery = new URLSearchParams({
        page: String(page),
        page_size: String(pageSize),
      });
      if (taskStatus) taskQuery.set("status", taskStatus);
      const [taskRes, failedRes, deadLetterRes] = await Promise.all([
        api<TaskListResponse>(`/tasks?${taskQuery}`),
        api<TaskListResponse>("/tasks?status=failed&page=1&page_size=100"),
        api<DeadLetterTask[]>("/ops/dead-letter"),
      ]);
      setTasks(taskRes.items);
      setTotal(taskRes.total);
      setStats(taskRes.stats);
      setFailedTasks(failedRes.items.filter((task) => !task.output_data.dead_letter));
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
  }, [page, pageSize, taskStatus]);

  useEffect(() => {
    api<AuthSession>("/auth/status")
      .then(async (session) => {
        const isAdmin = session.role === "admin";
        setCanDeleteTasks(isAdmin);
        setSourceGroups(isAdmin ? await api<TaskSourceGroup[]>("/tasks/source-groups") : []);
      })
      .catch(() => {
        setCanDeleteTasks(false);
        setSourceGroups([]);
      });
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

  async function markDeadLetter(taskId: number) {
    setMessage("");
    try {
      await api(`/ops/dead-letter/${taskId}/mark`, { method: "POST" });
      setMessage(`异常任务 #${taskId} 已转入死信队列。`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "转入死信队列失败。");
    }
  }

  async function deleteTask(task: TaskRecord | DeadLetterTask) {
    if (!canDeleteTasks || task.status === "pending" || task.status === "queued" || task.status === "running") return;
    if (!window.confirm(`确认删除任务 #${task.id}？该任务的执行记录和错误信息将无法恢复。`)) return;
    setDeleting(true);
    setMessage("");
    try {
      await api(`/tasks/${task.id}`, { method: "DELETE" });
      setMessage(`任务 #${task.id} 已删除。`);
      setSourceGroups(await api<TaskSourceGroup[]>("/tasks/source-groups"));
      if (tasks.length === 1 && page > 1) {
        setPage((current) => current - 1);
      } else {
        await load();
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除任务失败。");
    } finally {
      setDeleting(false);
    }
  }

  async function deleteTasksBySource() {
    if (!canDeleteTasks || !deleteSourceId) return;
    const source = sourceGroups.find((item) => item.source_id === Number(deleteSourceId));
    if (!source) return;
    if (!window.confirm(
      `确认删除采集源“${source.source_name}”关联的 ${source.task_count} 条已结束任务？多源采集任务只要包含该来源，也会被删除。`,
    )) return;
    setDeleting(true);
    setMessage("");
    try {
      const result = await api<{ deleted_count: number }>(`/tasks/by-source/${source.source_id}`, { method: "DELETE" });
      setMessage(`已删除采集源“${source.source_name}”关联的 ${result.deleted_count} 条任务。`);
      setPage(1);
      setDeleteSourceId("");
      setSourceGroups(await api<TaskSourceGroup[]>("/tasks/source-groups"));
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "按采集源删除任务失败。");
    } finally {
      setDeleting(false);
    }
  }

  const activeCount = stats.queued + stats.running;
  const selectedSourceGroup = sourceGroups.find((item) => item.source_id === Number(deleteSourceId));

  return (
    <div className="space-y-5">
      <PageHero
        title="任务中心"
        description="查看采集、分析、复核和通知任务的执行状态。"
        actions={<Button type="button" className="border border-white/20 bg-white/10 text-white hover:bg-white/20" onClick={load} disabled={loading}>
            <RefreshCw size={16} />
            刷新
          </Button>}
      />

      {message ? <div className="rounded-md border border-border bg-white p-3 text-sm">{message}</div> : null}

      <div className="grid gap-4 sm:grid-cols-2 xl:grid-cols-6">
        {([
          ["任务总数", stats.total],
          ["排队中", stats.queued],
          ["运行中", stats.running],
          ["已成功", stats.success],
          ["执行失败", stats.failed],
          ["死信任务", stats.dead_letter],
        ] as Array<[string, number]>).map(([label, value]) => (
          <Card key={label}>
            <div className="text-sm text-slate-500">{label}</div>
            <div className="mt-3 text-3xl font-semibold">{value}</div>
          </Card>
        ))}
      </div>

      <Card className="space-y-4">
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="text-lg font-semibold">失败与死信任务</h2>
            <p className="text-sm text-slate-500">失败任务可直接重试或转入死信队列；死信任务在排障后可重新入队。</p>
          </div>
          <div className="text-sm text-slate-500">异常 {failedTasks.length} · 死信 {deadLetters.length}</div>
        </div>

        <div className="space-y-3">
          <div className="text-sm font-medium text-slate-700">失败任务</div>
          {failedTasks
            .slice((failedPage - 1) * failedPageSize, failedPage * failedPageSize)
            .map((item) => (
            <div key={`failed-${item.id}`} className="rounded-md border border-amber-200 bg-amber-50/50 p-3">
              <div className="flex flex-wrap items-start justify-between gap-3">
                <div>
                  <div className="font-medium">异常任务 #{item.id} · {item.task_type}</div>
                  <div className="mt-1 text-sm text-slate-600">{item.error_message || item.output_data.last_message || "未记录异常原因。"}</div>
                  <div className="mt-2 text-xs text-slate-500">
                    阶段 {item.output_data.current_stage || "-"} · 更新时间 {new Date(item.updated_at).toLocaleString()}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button type="button" onClick={() => retryTask(item.id)}>
                    <RotateCcw size={16} />
                    重试
                  </Button>
                  <Button type="button" className="bg-slate-700" onClick={() => markDeadLetter(item.id)}>
                    <Archive size={16} />
                    转为死信
                  </Button>
                  {canDeleteTasks ? (
                    <Button
                      type="button"
                      className="border border-rose-200 bg-white text-rose-700 hover:bg-rose-50"
                      disabled={deleting}
                      onClick={() => deleteTask(item)}
                    >
                      <Trash2 size={16} />
                      删除
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
          <Pagination
            total={failedTasks.length}
            page={failedPage}
            pageSize={failedPageSize}
            onPageChange={setFailedPage}
            onPageSizeChange={(value) => {
              setFailedPage(1);
              setFailedPageSize(value);
            }}
          />

          <div className="pt-2 text-sm font-medium text-slate-700">死信任务</div>
          {deadLetters
            .slice((deadLetterPage - 1) * deadLetterPageSize, deadLetterPage * deadLetterPageSize)
            .map((item) => (
            <div key={item.id} className="rounded-md border border-border bg-slate-50 p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">任务 #{item.id} · {item.task_type}</div>
                  <div className="mt-1 text-sm text-slate-600">{item.dead_letter_reason || item.error_message || "No reason recorded."}</div>
                  <div className="mt-2 text-xs text-slate-500">
                    尝试 {item.attempt_count}/{item.max_attempts} · 阶段 {item.current_stage || "-"} · 队列 {item.queue_name || "-"} · 更新时间 {new Date(item.updated_at).toLocaleString()}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button type="button" onClick={() => requeueDeadLetter(item.id)}>
                    <RotateCcw size={16} />
                    重新入队
                  </Button>
                  {canDeleteTasks ? (
                    <Button
                      type="button"
                      className="border border-rose-200 bg-white text-rose-700 hover:bg-rose-50"
                      disabled={deleting}
                      onClick={() => deleteTask(item)}
                    >
                      <Trash2 size={16} />
                      删除
                    </Button>
                  ) : null}
                </div>
              </div>
            </div>
          ))}
          <Pagination
            total={deadLetters.length}
            page={deadLetterPage}
            pageSize={deadLetterPageSize}
            onPageChange={setDeadLetterPage}
            onPageSizeChange={(value) => {
              setDeadLetterPage(1);
              setDeadLetterPageSize(value);
            }}
          />
          {failedTasks.length === 0 && deadLetters.length === 0 ? <div className="text-sm text-slate-500">当前没有异常或死信任务。</div> : null}
        </div>
      </Card>

      <Card>
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <div className="font-semibold">任务列表</div>
            <div className="mt-1 text-sm text-slate-500">共 {total} 条任务记录</div>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            {canDeleteTasks ? (
              <div className="flex items-center gap-2">
                <select
                  className="h-10 min-w-44 rounded-md border border-border bg-white px-3 text-sm text-slate-700"
                  value={deleteSourceId}
                  onChange={(event) => setDeleteSourceId(event.target.value)}
                  aria-label="选择需要清理任务的采集源"
                >
                  <option value="">选择采集源</option>
                  {sourceGroups.map((source) => (
                    <option key={source.source_id} value={source.source_id}>
                      {source.source_name} · {source.task_count} 条
                      {source.active_count ? ` · ${source.active_count} 条活跃` : ""}
                    </option>
                  ))}
                </select>
                <Button
                  type="button"
                  className="border border-rose-200 bg-white text-rose-700 hover:bg-rose-50"
                  disabled={!deleteSourceId || deleting || Boolean(selectedSourceGroup?.active_count)}
                  title={selectedSourceGroup?.active_count ? "该来源仍有活跃任务，结束后才能批量删除" : "删除该来源任务集"}
                  onClick={deleteTasksBySource}
                >
                  <Trash2 size={16} />
                  删除该来源任务集
                </Button>
              </div>
            ) : null}
            <label className="flex items-center gap-2 text-sm text-slate-500">
              分类
              <select
                className="h-10 rounded-md border border-border bg-white px-3 text-sm text-slate-700"
                value={taskStatus}
                onChange={(event) => {
                  setPage(1);
                  setTaskStatus(event.target.value);
                }}
              >
                <option value="">全部任务</option>
                <option value="success">成功任务</option>
                <option value="failed">失败任务</option>
              </select>
            </label>
          </div>
        </div>
      </Card>

      <Pagination
        className="rounded-lg border border-border bg-white px-4 pb-3 shadow-soft"
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(value) => {
          setPage(1);
          setPageSize(value);
        }}
      />

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
                  运行方式 {task.output_data.execution_mode ?? "pending"} · 尝试次数 {task.output_data.attempt_count ?? 0}/{task.output_data.max_attempts ?? 0}
                  {task.output_data.elapsed_seconds != null ? ` · 耗时 ${task.output_data.elapsed_seconds}s` : ""}
                </p>
              </div>
              <div className="flex gap-2">
                {task.status === "failed" ? (
                  <Button type="button" onClick={() => retryTask(task.id)}>
                    <RotateCcw size={16} />
                    重试
                  </Button>
                ) : null}
                {canDeleteTasks ? (
                  <Button
                    type="button"
                    className="border border-rose-200 bg-white text-rose-700 hover:bg-rose-50"
                    disabled={deleting || task.status === "pending" || task.status === "queued" || task.status === "running"}
                    title={
                      task.status === "pending" || task.status === "queued" || task.status === "running"
                        ? "运行中的任务不能删除"
                        : "删除任务"
                    }
                    onClick={() => deleteTask(task)}
                  >
                    <Trash2 size={16} />
                    删除
                  </Button>
                ) : null}
              </div>
            </div>

            <MetricCards task={task} />

            <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
              <div className="rounded-md border border-border">
                <div className="border-b border-border px-4 py-3 text-sm font-semibold">执行记录</div>
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
                <div className="border-b border-border px-4 py-3 text-sm font-semibold">数据源执行明细</div>
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
      <Pagination
        className="rounded-lg border border-border bg-white px-4 pb-3 shadow-soft"
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(value) => {
          setPage(1);
          setPageSize(value);
        }}
      />
    </div>
  );
}
