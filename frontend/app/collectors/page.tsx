"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, Pencil, Play, Plus, RefreshCw, ShieldAlert, Trash2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { PageHero } from "@/components/page-hero";
import {
  api,
  AuthSession,
  CollectedDocument,
  CollectorOverview,
  DataSource,
  DataSourceListResponse,
  SourceHealth,
  TaskListResponse,
  TaskRecord,
} from "@/lib/api";
import { useSessionDraft } from "@/lib/use-session-draft";

type RunResponse = {
  task_id: number;
  status: string;
  current_stage: string;
  queued_at: string;
  message: string;
};

type SourceEditForm = Pick<DataSource, "name" | "source_type" | "url" | "enabled" | "interval_minutes">;

const DEFAULT_SOURCE_FORM = {
  name: "OpenAI Security News",
  source_type: "web",
  url: "https://openai.com/news/security/",
  interval_minutes: 240,
};

const DOC_STATUS_LABELS: Record<string, string> = {
  queued_analysis: "等待 AI 分析",
  pending_review: "待人工复核",
  stored: "已入库",
  ignored: "已忽略",
};

const SOURCE_TYPE_LABELS: Record<string, string> = {
  rss: "RSS / Blog",
  web: "Web 页面",
  github: "GitHub Advisory",
  local_file: "本地文件",
};

const SOURCE_STATUS_LABELS: Record<string, string> = {
  healthy: "健康",
  due: "待调度",
  never_run: "未采集",
  disabled: "已停用",
};

function TrustBadge({ source }: { source: SourceHealth }) {
  const tone =
    source.trust_level === "high"
      ? "bg-emerald-100 text-emerald-700"
      : source.trust_level === "medium"
        ? "bg-amber-100 text-amber-700"
        : "bg-slate-100 text-slate-700";

  return <span className={`rounded px-2 py-1 text-xs font-medium ${tone}`}>可信度 {source.trust_score}</span>;
}

function ListPager({
  total,
  page,
  pageSize,
  onPageChange,
  onPageSizeChange,
}: {
  total: number;
  page: number;
  pageSize: number;
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
}) {
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  return (
    <div className="flex flex-wrap items-center justify-between gap-3 border-t border-border pt-3 text-sm">
      <span className="text-slate-500">共 {total} 条 · 第 {page} / {pageCount} 页</span>
      <div className="flex flex-wrap items-center gap-2">
        <label className="flex items-center gap-2 text-slate-500">
          每页
          <select
            className="h-8 rounded-md border border-border bg-white px-2 text-slate-700"
            value={pageSize}
            onChange={(event) => onPageSizeChange(Number(event.target.value))}
          >
            <option value={5}>5 条</option>
            <option value={10}>10 条</option>
          </select>
        </label>
        <Button
          type="button"
          className="h-8 border border-border bg-white text-slate-700"
          disabled={page <= 1}
          onClick={() => onPageChange(page - 1)}
        >
          上一页
        </Button>
        <Button
          type="button"
          className="h-8 border border-border bg-white text-slate-700"
          disabled={page >= pageCount}
          onClick={() => onPageChange(page + 1)}
        >
          下一页
        </Button>
      </div>
    </div>
  );
}

export default function CollectorsPage() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [overview, setOverview] = useState<CollectorOverview | null>(null);
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [canManageSources, setCanManageSources] = useState(false);
  const [sourcePage, setSourcePage] = useState(1);
  const [sourcePageSize, setSourcePageSize] = useState(10);
  const [sourceTotal, setSourceTotal] = useState(0);
  const [pendingPage, setPendingPage] = useState(1);
  const [pendingPageSize, setPendingPageSize] = useState(5);
  const [recentPage, setRecentPage] = useState(1);
  const [recentPageSize, setRecentPageSize] = useState(5);
  const [runsPage, setRunsPage] = useState(1);
  const [runsPageSize, setRunsPageSize] = useState(5);
  const [editingSourceId, setEditingSourceId] = useState<number | null>(null);
  const [editForm, setEditForm] = useState<SourceEditForm | null>(null);
  const [form, setForm, { clearDraft: clearSourceDraft }] = useSessionDraft(
    "llm-vulnhub:collector-source-draft:v1",
    DEFAULT_SOURCE_FORM,
  );

  async function load() {
    const overviewQuery = new URLSearchParams({
      pending_page: String(pendingPage),
      pending_page_size: String(pendingPageSize),
      recent_page: String(recentPage),
      recent_page_size: String(recentPageSize),
      runs_page: String(runsPage),
      runs_page_size: String(runsPageSize),
    });
    const [sourceList, overviewRes, taskList] = await Promise.all([
      api<DataSourceListResponse>(`/sources?page=${sourcePage}&page_size=${sourcePageSize}`).catch(() => ({
        items: [],
        total: 0,
        page: sourcePage,
        page_size: sourcePageSize,
      })),
      api<CollectorOverview>(`/collectors/overview?${overviewQuery}`).catch(() => null),
      api<TaskListResponse>("/tasks?page_size=50").catch(() => ({
        items: [],
        total: 0,
        page: 1,
        page_size: 50,
        stats: { total: 0, queued: 0, running: 0, success: 0, failed: 0, dead_letter: 0 },
      })),
    ]);
    setSources(sourceList.items);
    setSourceTotal(sourceList.total);
    setOverview(overviewRes);
    if (overviewRes) {
      setPendingPage((current) => Math.min(current, Math.max(1, Math.ceil(overviewRes.pending_documents_total / pendingPageSize))));
      setRecentPage((current) => Math.min(current, Math.max(1, Math.ceil(overviewRes.recent_documents_total / recentPageSize))));
      setRunsPage((current) => Math.min(current, Math.max(1, Math.ceil(overviewRes.recent_runs_total / runsPageSize))));
    }
    setTasks(taskList.items.filter((task) => task.task_type === "crawl").slice(0, 8));
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
  }, [sourcePage, sourcePageSize, pendingPage, pendingPageSize, recentPage, recentPageSize, runsPage, runsPageSize]);

  useEffect(() => {
    api<AuthSession>("/auth/status")
      .then((session) => setCanManageSources(session.role === "admin"))
      .catch(() => setCanManageSources(false));
  }, []);

  async function createSource() {
    setSubmitting(true);
    setMessage("");
    try {
      await api("/sources", {
        method: "POST",
        body: JSON.stringify({ ...form, enabled: true }),
      });
      clearSourceDraft();
      setMessage("数据源已添加。");
      if (sourcePage !== 1) {
        setSourcePage(1);
      } else {
        await load();
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "添加数据源失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function deleteSource(source: DataSource) {
    if (!canManageSources || !window.confirm(`确认删除数据源“${source.name}”？历史采集文档会保留。`)) return;
    setSubmitting(true);
    setMessage("");
    try {
      await api(`/sources/${source.id}`, { method: "DELETE" });
      if (editingSourceId === source.id) {
        setEditingSourceId(null);
        setEditForm(null);
      }
      setMessage(`数据源“${source.name}”已删除，历史采集记录仍保留。`);
      if (sources.length === 1 && sourcePage > 1) {
        setSourcePage((current) => current - 1);
      } else {
        await load();
      }
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "删除数据源失败。");
    } finally {
      setSubmitting(false);
    }
  }

  function startEditingSource(source: DataSource) {
    setMessage("");
    setEditingSourceId(source.id);
    setEditForm({
      name: source.name,
      source_type: source.source_type,
      url: source.url,
      enabled: source.enabled,
      interval_minutes: source.interval_minutes,
    });
  }

  function cancelEditingSource() {
    setEditingSourceId(null);
    setEditForm(null);
  }

  async function saveSource() {
    if (!canManageSources || editingSourceId === null || !editForm) return;
    setSubmitting(true);
    setMessage("");
    try {
      const updated = await api<DataSource>(`/sources/${editingSourceId}`, {
        method: "PUT",
        body: JSON.stringify(editForm),
      });
      setMessage(`采集源“${updated.name}”已更新。`);
      cancelEditingSource();
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "更新采集源失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function run(sourceId?: number) {
    setSubmitting(true);
    setMessage("");
    try {
      const res = await api<RunResponse>("/collectors/run", {
        method: "POST",
        body: JSON.stringify({ source_id: sourceId }),
      });
      setMessage(`任务 #${res.task_id} 已进入队列，当前阶段：${res.current_stage}`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "触发采集失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function approve(docId: number) {
    setSubmitting(true);
    setMessage("");
    try {
      await api(`/collectors/documents/${docId}/approve`, { method: "POST" });
      setMessage(`文档 #${docId} 已确认入库。`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "确认入库失败。");
    } finally {
      setSubmitting(false);
    }
  }

  const activeTasks = useMemo(
    () => tasks.filter((task) => task.status === "queued" || task.status === "running"),
    [tasks],
  );

  const pendingDocs = overview?.pending_documents ?? [];
  const recentDocs = overview?.recent_documents ?? [];
  const recentRuns = overview?.recent_runs ?? [];
  const sourceHealth = overview?.source_health ?? [];

  return (
    <div className="space-y-5">
      <PageHero
        title="动态采集控制台"
        description="展示采集链路运行状态，以及每条情报从数据源到复核入库的可信度信号。"
        eyebrow="外部情报接入"
        actions={<Button type="button" className="border border-white/20 bg-white/10 text-white hover:bg-white/20" onClick={load}>
          <RefreshCw size={16} />
          刷新
        </Button>}
      />

      {message ? <div className="rounded-md border border-border bg-white p-3 text-sm">{message}</div> : null}

      {overview ? (
        <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
          <Card><div className="text-sm text-slate-500">数据源总数</div><div className="mt-3 text-3xl font-semibold">{overview.source_metrics.total}</div></Card>
          <Card><div className="text-sm text-slate-500">启用中来源</div><div className="mt-3 text-3xl font-semibold">{overview.source_metrics.enabled}</div></Card>
          <Card><div className="text-sm text-slate-500">采集文档总量</div><div className="mt-3 text-3xl font-semibold">{overview.document_metrics.total}</div></Card>
          <Card><div className="text-sm text-slate-500">AI 相关命中</div><div className="mt-3 text-3xl font-semibold">{overview.document_metrics.ai_related}</div></Card>
          <Card><div className="text-sm text-slate-500">待人工复核</div><div className="mt-3 text-3xl font-semibold">{overview.document_metrics.pending_review}</div></Card>
          <Card><div className="text-sm text-slate-500">运行中采集任务</div><div className="mt-3 text-3xl font-semibold">{overview.queue_metrics.crawl_running}</div></Card>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1.15fr_0.85fr]">
        <Card className="space-y-4">
          <div>
            <h2 className="font-semibold">新增数据源</h2>
            <p className="mt-1 text-sm text-slate-500">支持 RSS、安全博客页面、官方公告页和 GitHub Advisory。</p>
          </div>
          <div className="grid gap-3 md:grid-cols-5">
            <Input maxLength={160} value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="数据源名称" />
            <select
              className="h-10 rounded-md border border-border bg-background px-3 text-sm"
              value={form.source_type}
              onChange={(e) => setForm({ ...form, source_type: e.target.value })}
            >
              <option value="rss">rss</option>
              <option value="web">web</option>
              <option value="github">github</option>
              <option value="local_file">local_file</option>
            </select>
            <Input
              className="md:col-span-2"
              maxLength={800}
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
              placeholder="URL / 文件路径"
            />
            <Button onClick={createSource} disabled={submitting || !canManageSources}>
              <Plus size={16} />
              添加
            </Button>
          </div>
        </Card>

        <Card className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold">实时流水线状态</h2>
              <p className="mt-1 text-sm text-slate-500">当前排队和运行中的采集任务。</p>
            </div>
            <span className="rounded-md bg-slate-100 px-2 py-1 text-xs text-slate-600">{activeTasks.length} 个活跃任务</span>
          </div>

          {activeTasks.length > 0 ? (
            <div className="space-y-3">
              {activeTasks.map((task) => (
                <div key={task.id} className="rounded-md border border-border bg-slate-50 p-3">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">任务 #{task.id}</div>
                    <span className="rounded bg-white px-2 py-1 text-xs">{task.status}</span>
                  </div>
                  <div className="mt-2 text-sm text-slate-600">{task.output_data.last_message || "任务排队中"}</div>
                  <div className="mt-2 text-xs text-slate-400">
                    阶段 {task.output_data.current_stage ?? "queued"} | 尝试 {task.output_data.attempt_count ?? 0} / {task.output_data.max_attempts ?? 0}
                  </div>
                </div>
              ))}
            </div>
          ) : (
            <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">当前没有运行中的采集任务。</div>
          )}
        </Card>
      </div>

      <Card className="space-y-4">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">采集源</h2>
            <p className="mt-1 text-sm text-slate-500">
              共 {sourceTotal} 个来源，集中查看来源配置、运行状态、可信度与产出质量。
            </p>
          </div>
          <div className="flex flex-wrap items-center gap-3">
            <label className="flex items-center gap-2 text-sm text-slate-500">
              每页
              <select
                className="h-9 rounded-md border border-border bg-white px-2 text-slate-700"
                value={sourcePageSize}
                onChange={(event) => {
                  setSourcePage(1);
                  setSourcePageSize(Number(event.target.value));
                }}
              >
                {[5, 10, 20, 50].map((value) => <option key={value} value={value}>{value} 条</option>)}
              </select>
            </label>
            <Button onClick={() => run()} disabled={submitting}>
              <Play size={16} />
              采集全部启用源
            </Button>
          </div>
        </div>

        {editingSourceId !== null && editForm ? (
          <div className="rounded-lg border border-blue-200 bg-blue-50/40 p-4">
            <div>
              <h3 className="font-semibold text-slate-900">编辑采集源 #{editingSourceId}</h3>
              <p className="mt-1 text-sm text-slate-500">修改后会在下次调度或手动采集时生效。</p>
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-6">
              <label className="space-y-1 xl:col-span-2">
                <span className="text-xs text-slate-500">来源名称</span>
                <Input
                  maxLength={160}
                  value={editForm.name}
                  onChange={(event) => setEditForm({ ...editForm, name: event.target.value })}
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-slate-500">来源类型</span>
                <select
                  className="h-10 w-full rounded-md border border-border bg-white px-3 text-sm"
                  value={editForm.source_type}
                  onChange={(event) => setEditForm({ ...editForm, source_type: event.target.value })}
                >
                  <option value="rss">rss</option>
                  <option value="web">web</option>
                  <option value="github">github</option>
                  <option value="local_file">local_file</option>
                </select>
              </label>
              <label className="space-y-1 xl:col-span-2">
                <span className="text-xs text-slate-500">URL / 文件路径</span>
                <Input
                  maxLength={800}
                  value={editForm.url}
                  onChange={(event) => setEditForm({ ...editForm, url: event.target.value })}
                />
              </label>
              <label className="space-y-1">
                <span className="text-xs text-slate-500">采集周期（分钟）</span>
                <Input
                  type="number"
                  min={1}
                  max={10080}
                  value={editForm.interval_minutes}
                  onChange={(event) => setEditForm({ ...editForm, interval_minutes: Number(event.target.value) })}
                />
              </label>
            </div>
            <div className="mt-4 flex flex-wrap items-center justify-between gap-3">
              <label className="flex items-center gap-2 text-sm text-slate-700">
                <input
                  type="checkbox"
                  checked={editForm.enabled}
                  onChange={(event) => setEditForm({ ...editForm, enabled: event.target.checked })}
                />
                启用该采集源
              </label>
              <div className="flex gap-2">
                <Button
                  type="button"
                  className="border border-border bg-white text-slate-700"
                  disabled={submitting}
                  onClick={cancelEditingSource}
                >
                  取消
                </Button>
                <Button
                  type="button"
                  disabled={submitting || !editForm.name.trim() || !editForm.url.trim() || editForm.interval_minutes < 1}
                  onClick={saveSource}
                >
                  保存修改
                </Button>
              </div>
            </div>
          </div>
        ) : null}

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {sources.map((source) => {
            const health = sourceHealth.find((item) => item.source_id === source.id);
            return (
              <div key={source.id} className="flex h-full flex-col rounded-md border border-border p-4">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="font-medium">{source.name}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type}
                      {" · "}
                      {health ? SOURCE_STATUS_LABELS[health.status] ?? health.status : source.enabled ? "已启用" : "已停用"}
                    </div>
                  </div>
                  {health ? (
                    <TrustBadge source={health} />
                  ) : (
                    <span className={`shrink-0 rounded px-2 py-1 text-xs ${source.enabled ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                      {source.enabled ? "已启用" : "已停用"}
                    </span>
                  )}
                </div>

                <div className="mt-3 break-all rounded-md bg-slate-50 p-3 text-xs leading-5 text-slate-600">{source.url}</div>

                {health ? (
                  <>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-slate-600">
                      <div>总文档 {health.documents_total}</div>
                      <div>AI 命中 {health.ai_related_documents}</div>
                      <div>待复核 {health.pending_review_documents}</div>
                      <div>已入库 {health.stored_documents}</div>
                      <div>去重命中 {health.duplicate_documents}</div>
                      <div>成功率 {Math.round(health.success_rate * 100)}%</div>
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 rounded-md bg-slate-50 p-3 text-xs text-slate-600">
                      <div>请求成功 {Math.round(health.request_success_rate * 100)}%</div>
                      <div>初筛通过 {Math.round(health.prefilter_pass_rate * 100)}%</div>
                      <div>LLM 命中 {Math.round(health.llm_hit_rate * 100)}%</div>
                      <div>入库转化 {Math.round(health.library_conversion_rate * 100)}%</div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {health.signals.map((signal) => (
                        <span key={signal} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                          {signal}
                        </span>
                      ))}
                    </div>
                  </>
                ) : (
                  <div className="mt-3 rounded-md bg-slate-50 p-3 text-sm text-slate-500">暂时没有该来源的运行质量数据。</div>
                )}

                <div className="mt-3 text-xs text-slate-400">
                  周期 {source.interval_minutes} min · 最近采集 {source.last_collected_at ? new Date(source.last_collected_at).toLocaleString() : "尚未采集"}
                  {health?.freshness_minutes != null ? ` · 距今 ${health.freshness_minutes} min` : ""}
                </div>
                <div className={`mt-auto grid gap-2 pt-4 ${canManageSources ? "grid-cols-3" : "grid-cols-1"}`}>
                  <Button className="h-8 w-full gap-1 px-2 text-xs" onClick={() => run(source.id)} disabled={submitting || !source.enabled}>
                    <Play size={14} />
                    立即采集
                  </Button>
                  {canManageSources ? (
                    <>
                      <Button
                        type="button"
                        className="h-8 w-full gap-1 border border-border bg-white px-2 text-xs text-slate-700"
                        disabled={submitting}
                        onClick={() => startEditingSource(source)}
                      >
                        <Pencil size={14} />
                        编辑
                      </Button>
                      <Button
                        type="button"
                        className="h-8 w-full gap-1 border border-rose-200 bg-white px-2 text-xs text-rose-700 hover:bg-rose-50"
                        disabled={submitting}
                        onClick={() => deleteSource(source)}
                      >
                        <Trash2 size={14} />
                        删除来源
                      </Button>
                    </>
                  ) : null}
                </div>
              </div>
            );
          })}
        </div>
        {sources.length === 0 ? <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">当前没有采集源。</div> : null}
        <div className="flex items-center justify-between border-t border-border pt-4 text-sm">
          <span className="text-slate-500">
            第 {sourcePage} / {Math.max(1, Math.ceil(sourceTotal / sourcePageSize))} 页
          </span>
          <div className="flex gap-2">
            <Button
              type="button"
              className="border border-border bg-white text-slate-700"
              disabled={sourcePage <= 1}
              onClick={() => setSourcePage((current) => Math.max(1, current - 1))}
            >
              上一页
            </Button>
            <Button
              type="button"
              className="border border-border bg-white text-slate-700"
              disabled={sourcePage >= Math.max(1, Math.ceil(sourceTotal / sourcePageSize))}
              onClick={() => setSourcePage((current) => current + 1)}
            >
              下一页
            </Button>
          </div>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-[1fr_1fr]">
        <Card className="space-y-4">
          <div className="flex items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold">待处理队列</h2>
              <p className="mt-1 text-sm text-slate-500">优先处理等待 AI 分析或等待人工复核的候选文档。</p>
            </div>
            <Link className="text-sm text-primary hover:underline" href="/intel-pool?status=pending_review">
              进入情报池
            </Link>
          </div>

          <div className="space-y-3">
            {pendingDocs.map((doc: CollectedDocument) => (
              <div key={doc.id} className="rounded-md border border-border p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="line-clamp-2 font-medium">{doc.title}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      #{doc.id} | 置信度 {Math.round(doc.confidence * 100)}% | {DOC_STATUS_LABELS[doc.status] ?? doc.status}
                    </div>
                  </div>
                  {doc.status === "pending_review" ? (
                    <div className="flex w-[192px] shrink-0 items-center justify-end gap-2">
                      <Button className="h-8" onClick={() => approve(doc.id)} disabled={submitting}>
                        确认入库
                      </Button>
                      <Link
                        className="inline-flex h-8 items-center whitespace-nowrap rounded-md border border-border px-3 text-sm text-slate-700"
                        href={`/intel-pool?selected=${doc.id}&status=pending_review`}
                      >
                        去复核
                      </Link>
                    </div>
                  ) : (
                    <Link className="inline-flex h-8 shrink-0 items-center whitespace-nowrap rounded-md border border-border px-3 text-sm text-slate-700" href="/tasks">
                      看任务
                    </Link>
                  )}
                </div>
              </div>
            ))}
            {pendingDocs.length === 0 ? <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">当前没有待处理文档。</div> : null}
          </div>
          <ListPager
            total={overview?.pending_documents_total ?? 0}
            page={pendingPage}
            pageSize={pendingPageSize}
            onPageChange={setPendingPage}
            onPageSizeChange={(value) => {
              setPendingPage(1);
              setPendingPageSize(value);
            }}
          />
        </Card>

        <Card className="space-y-4">
          <div>
            <h2 className="font-semibold">最近采集结果</h2>
            <p className="mt-1 text-sm text-slate-500">展示最新进入系统的候选文本，可快速跳转到分析或复核环节。</p>
          </div>
          <div className="space-y-3">
            {recentDocs.map((doc: CollectedDocument) => (
              <div key={doc.id} className="rounded-md border border-border p-3">
                <div className="flex items-start justify-between gap-3">
                  <div className="min-w-0">
                    <div className="line-clamp-2 font-medium">{doc.title}</div>
                    <div className="mt-1 text-xs text-slate-500">
                      {doc.is_ai_related ? "AI 相关" : "未判定 AI 相关"} | {DOC_STATUS_LABELS[doc.status] ?? doc.status}
                    </div>
                  </div>
                  <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">{Math.round(doc.confidence * 100)}%</span>
                </div>
              </div>
            ))}
            {recentDocs.length === 0 ? <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">当前没有采集结果。</div> : null}
          </div>
          <ListPager
            total={overview?.recent_documents_total ?? 0}
            page={recentPage}
            pageSize={recentPageSize}
            onPageChange={setRecentPage}
            onPageSizeChange={(value) => {
              setRecentPage(1);
              setRecentPageSize(value);
            }}
          />
        </Card>
      </div>

      <Card className="space-y-4">
        <div className="flex items-center gap-2">
          <Activity size={16} />
          <h2 className="font-semibold">最近运行轨迹</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {recentRuns.map((run) => (
            <div key={`${run.task_id}-${run.source_id}-${run.source_name}`} className="rounded-md border border-border p-3">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">{run.source_name}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    任务 #{run.task_id} | {SOURCE_TYPE_LABELS[run.source_type] ?? run.source_type}
                  </div>
                </div>
                <span className={`rounded px-2 py-1 text-xs ${run.status === "failed" ? "bg-rose-100 text-rose-700" : run.status === "success" ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                  {run.status}
                </span>
              </div>
              <div className="mt-3 grid grid-cols-3 gap-2 text-xs text-slate-600">
                <div>发现 {run.discovered}</div>
                <div>处理 {run.processed}</div>
                <div>待分析 {run.queued_analysis}</div>
                <div>待复核 {run.pending_review}</div>
                <div>重复 {run.duplicates}</div>
                <div>失败 {run.failed}</div>
              </div>
              <div className="mt-3 text-xs text-slate-400">
                阶段 {run.stage}
                {run.elapsed_seconds != null ? ` | ${run.elapsed_seconds}s` : ""}
              </div>
              {run.error ? (
                <div className="mt-2 flex items-start gap-2 rounded-md bg-rose-50 p-2 text-xs text-rose-700">
                  <ShieldAlert size={14} className="mt-0.5" />
                  <span>{run.error}</span>
                </div>
              ) : (
                <div className="mt-2">
                  <Link className="inline-flex items-center gap-1 text-xs text-primary hover:underline" href="/tasks">
                    去任务中心查看完整轨迹
                    <ArrowRight size={12} />
                  </Link>
                </div>
              )}
            </div>
          ))}
          {recentRuns.length === 0 ? <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">当前没有运行轨迹。</div> : null}
        </div>
        <ListPager
          total={overview?.recent_runs_total ?? 0}
          page={runsPage}
          pageSize={runsPageSize}
          onPageChange={setRunsPage}
          onPageSizeChange={(value) => {
            setRunsPage(1);
            setRunsPageSize(value);
          }}
        />
      </Card>

    </div>
  );
}
