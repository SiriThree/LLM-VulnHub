"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Activity, ArrowRight, Play, Plus, RefreshCw, ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, CollectedDocument, CollectorOverview, DataSource, SourceHealth, TaskListResponse, TaskRecord } from "@/lib/api";
import { useSessionDraft } from "@/lib/use-session-draft";

type RunResponse = {
  task_id: number;
  status: string;
  current_stage: string;
  queued_at: string;
  message: string;
};

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

export default function CollectorsPage() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [overview, setOverview] = useState<CollectorOverview | null>(null);
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm, { clearDraft: clearSourceDraft }] = useSessionDraft(
    "llm-vulnhub:collector-source-draft:v1",
    DEFAULT_SOURCE_FORM,
  );

  async function load() {
    const [sourceList, overviewRes, taskList] = await Promise.all([
      api<DataSource[]>("/sources").catch(() => []),
      api<CollectorOverview>("/collectors/overview").catch(() => null),
      api<TaskListResponse>("/tasks").catch(() => ({ items: [] })),
    ]);
    setSources(sourceList);
    setOverview(overviewRes);
    setTasks(taskList.items.filter((task) => task.task_type === "crawl").slice(0, 8));
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 5000);
    return () => window.clearInterval(timer);
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
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "添加数据源失败。");
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
  const sourceHealth = overview?.source_health ?? [];

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">动态采集控制台</h1>
          <p className="text-sm text-slate-500">
            这里展示真实采集链路的运行状态，以及每条情报从数据源到复核入库的可信度信号。
          </p>
        </div>
        <Button type="button" className="border border-border bg-white text-slate-700" onClick={load}>
          <RefreshCw size={16} />
          刷新
        </Button>
      </div>

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
            <Input value={form.name} onChange={(e) => setForm({ ...form, name: e.target.value })} placeholder="数据源名称" />
            <select
              className="h-10 rounded-md border border-border bg-background px-3 text-sm"
              value={form.source_type}
              onChange={(e) => setForm({ ...form, source_type: e.target.value })}
            >
              <option value="rss">rss</option>
              <option value="web">web</option>
              <option value="github">github</option>
            </select>
            <Input
              className="md:col-span-2"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
              placeholder="URL / 文件路径"
            />
            <Button onClick={createSource} disabled={submitting}>
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
        <div className="flex items-center justify-between gap-3">
          <div>
            <h2 className="font-semibold">来源可信度与产出质量</h2>
            <p className="mt-1 text-sm text-slate-500">不是只看“有没有跑”，而是看这个源是否稳定、是否持续产出 AI 相关有效情报。</p>
          </div>
          <Button onClick={() => run()} disabled={submitting}>
            <Play size={16} />
            采集全部启用源
          </Button>
        </div>

        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {sourceHealth.map((source) => (
            <div key={source.source_id} className="rounded-md border border-border p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">{source.name}</div>
                  <div className="mt-1 text-xs text-slate-500">
                    {SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type} | {SOURCE_STATUS_LABELS[source.status] ?? source.status}
                  </div>
                </div>
                <TrustBadge source={source} />
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 text-sm text-slate-600">
                <div>总文档 {source.documents_total}</div>
                <div>AI 命中 {source.ai_related_documents}</div>
                <div>待复核 {source.pending_review_documents}</div>
                <div>已入库 {source.stored_documents}</div>
                <div>去重命中 {source.duplicate_documents}</div>
                <div>成功率 {Math.round(source.success_rate * 100)}%</div>
              </div>
              <div className="mt-3 grid grid-cols-2 gap-2 rounded-md bg-slate-50 p-3 text-xs text-slate-600">
                <div>请求成功 {Math.round(source.request_success_rate * 100)}%</div>
                <div>初筛通过 {Math.round(source.prefilter_pass_rate * 100)}%</div>
                <div>LLM 命中 {Math.round(source.llm_hit_rate * 100)}%</div>
                <div>入库转化 {Math.round(source.library_conversion_rate * 100)}%</div>
              </div>
              <div className="mt-2 grid grid-cols-3 gap-2 text-xs text-slate-500">
                <div>候选 {source.recent_discovered}</div>
                <div>初筛 {source.recent_prefilter_passed}</div>
                <div>入库 {source.recent_saved}</div>
              </div>
              <div className="mt-3 text-xs text-slate-400">
                最近采集 {source.last_collected_at ? new Date(source.last_collected_at).toLocaleString() : "尚未采集"}
                {source.freshness_minutes != null ? ` | 距今 ${source.freshness_minutes} min` : ""}
              </div>
              <div className="mt-3 flex flex-wrap gap-2">
                {source.signals.map((signal) => (
                  <span key={signal} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                    {signal}
                  </span>
                ))}
              </div>
              <div className="mt-4">
                <Button className="h-8" onClick={() => run(source.source_id)} disabled={submitting || !source.enabled}>
                  <Play size={14} />
                  立即采集
                </Button>
              </div>
            </div>
          ))}
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
                    <div className="flex gap-2">
                      <Button className="h-8" onClick={() => approve(doc.id)} disabled={submitting}>
                        确认入库
                      </Button>
                      <Link className="inline-flex h-8 items-center rounded-md border border-border px-3 text-sm text-slate-700" href={`/intel-pool?selected=${doc.id}&status=pending_review`}>
                        去复核
                      </Link>
                    </div>
                  ) : (
                    <Link className="inline-flex h-8 items-center rounded-md border border-border px-3 text-sm text-slate-700" href="/tasks">
                      看任务
                    </Link>
                  )}
                </div>
              </div>
            ))}
            {pendingDocs.length === 0 ? <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">当前没有待处理文档。</div> : null}
          </div>
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
          </div>
        </Card>
      </div>

      <Card className="space-y-4">
        <div className="flex items-center gap-2">
          <Activity size={16} />
          <h2 className="font-semibold">最近运行轨迹</h2>
        </div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {(overview?.recent_runs ?? []).map((run) => (
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
        </div>
      </Card>

      <Card className="space-y-4">
        <div className="font-semibold">原始来源清单</div>
        <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
          {sources.map((source) => (
            <div key={source.id} className="rounded-md border border-border p-4">
              <div className="flex items-start justify-between gap-3">
                <div>
                  <div className="font-medium">{source.name}</div>
                  <div className="mt-1 text-xs text-slate-500">{SOURCE_TYPE_LABELS[source.source_type] ?? source.source_type}</div>
                </div>
                <span className={`rounded px-2 py-1 text-xs ${source.enabled ? "bg-emerald-100 text-emerald-700" : "bg-slate-100 text-slate-600"}`}>
                  {source.enabled ? "enabled" : "disabled"}
                </span>
              </div>
              <div className="mt-3 break-all text-sm text-slate-600">{source.url}</div>
              <div className="mt-3 text-xs text-slate-400">
                周期 {source.interval_minutes} min | 最近采集 {source.last_collected_at ? new Date(source.last_collected_at).toLocaleString() : "尚未采集"}
              </div>
            </div>
          ))}
        </div>
      </Card>
    </div>
  );
}
