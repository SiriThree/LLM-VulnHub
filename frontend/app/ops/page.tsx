import { Activity, AlertTriangle, Clock3, Database, ListChecks, RadioTower, ServerCog, Zap } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { PageHero } from "@/components/page-hero";
import { api, OpsMetrics, SchedulerOverview } from "@/lib/api";

function formatDate(value?: string | null) {
  return value ? new Date(value).toLocaleString() : "-";
}

function formatSeconds(value: number) {
  if (value < 60) return `${value} 秒`;
  const minutes = Math.round(value / 60);
  if (minutes < 60) return `${minutes} 分钟`;
  return `${Math.round(minutes / 60)} 小时`;
}

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string;
  value: string | number;
  hint?: string;
  icon: typeof Activity;
}) {
  return (
    <Card className="p-4">
      <div className="flex items-center justify-between gap-3">
        <div className="text-sm text-slate-500">{label}</div>
        <Icon size={17} className="text-slate-400" />
      </div>
      <div className="mt-3 text-3xl font-semibold text-slate-950">{value}</div>
      {hint ? <div className="mt-2 text-xs text-slate-400">{hint}</div> : null}
    </Card>
  );
}

function Bars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data).sort((a, b) => b[1] - a[1]);
  const max = Math.max(1, ...entries.map(([, value]) => value));

  if (entries.length === 0) {
    return <div className="rounded-md border border-dashed border-border p-4 text-sm text-slate-500">暂无数据</div>;
  }

  return (
    <div className="space-y-3">
      {entries.map(([key, value]) => (
        <div key={key}>
          <div className="mb-1 flex items-center justify-between gap-3 text-sm">
            <span className="truncate text-slate-600">{key}</span>
            <span className="shrink-0 font-medium text-slate-900">{value}</span>
          </div>
          <div className="h-2 rounded bg-muted">
            <div className="h-2 rounded bg-primary" style={{ width: `${(value / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default async function OpsPage() {
  const empty: OpsMetrics = {
    queue_metrics: { queued: 0, running: 0, success: 0, failed: 0 },
    source_health: { total_sources: 0, enabled_sources: 0, disabled_sources: 0, recently_failed_notifications: 0 },
    provider_metrics: { analysis_jobs_total: 0, avg_score: 0, provider_distribution: {}, severity_distribution: {} },
    llm_usage: {
      total_calls: 0,
      total_prompt_tokens: 0,
      total_completion_tokens: 0,
      total_tokens: 0,
      avg_latency_ms: 0,
      provider_distribution: {},
      model_distribution: {},
    },
    daily_trends: [],
  };

  const metrics = await api<OpsMetrics>("/ops/metrics").catch(() => empty);
  const scheduler = await api<SchedulerOverview>("/ops/scheduler").catch(() => ({ beat_jobs: [], sources: [] }));
  const failed = metrics.queue_metrics.failed + metrics.source_health.recently_failed_notifications;

  return (
    <div className="space-y-5">
      <PageHero
        title="运行运营"
        description="集中查看采集调度、任务队列、数据源健康度和模型调用状态。"
        eyebrow="运行态势"
        actions={<div className="flex items-center gap-2 text-sm text-slate-300">
          <Clock3 size={16} />
          <span>调度源 {scheduler.sources.length} 个，Beat 任务 {scheduler.beat_jobs.length} 个</span>
        </div>}
      />

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="队列中" value={metrics.queue_metrics.queued} hint="等待 worker 消费" icon={ListChecks} />
        <StatCard label="运行中" value={metrics.queue_metrics.running} hint="当前执行任务" icon={Activity} />
        <StatCard label="成功任务" value={metrics.queue_metrics.success} hint="历史成功完成" icon={Zap} />
        <StatCard label="异常信号" value={failed} hint="失败任务与源通知" icon={AlertTriangle} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold">调度器任务</h2>
            <Badge>{scheduler.beat_jobs.length}</Badge>
          </div>
          <div className="space-y-3">
            {scheduler.beat_jobs.map((item) => (
              <div key={item.name} className="rounded-md border border-border bg-slate-50 p-3">
                <div className="truncate font-medium text-slate-950">{item.name}</div>
                <div className="mt-1 truncate text-xs text-slate-500">{item.task}</div>
                <div className="mt-2 inline-flex rounded bg-white px-2 py-1 text-xs text-slate-600">
                  周期 {formatSeconds(item.schedule_seconds)}
                </div>
              </div>
            ))}
            {scheduler.beat_jobs.length === 0 ? <div className="text-sm text-slate-500">暂无 Celery Beat 任务。</div> : null}
          </div>
        </Card>

        <Card>
          <h2 className="mb-4 font-semibold">数据源概况</h2>
          <div className="grid grid-cols-2 gap-3 text-sm">
            <div className="rounded-md bg-slate-50 p-3">
              <div className="text-slate-500">总数</div>
              <div className="mt-2 text-2xl font-semibold">{metrics.source_health.total_sources}</div>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <div className="text-slate-500">启用</div>
              <div className="mt-2 text-2xl font-semibold">{metrics.source_health.enabled_sources}</div>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <div className="text-slate-500">停用</div>
              <div className="mt-2 text-2xl font-semibold">{metrics.source_health.disabled_sources}</div>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <div className="text-slate-500">失败通知</div>
              <div className="mt-2 text-2xl font-semibold">{metrics.source_health.recently_failed_notifications}</div>
            </div>
          </div>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <StatCard label="分析任务总数" value={metrics.provider_metrics.analysis_jobs_total} icon={ServerCog} />
        <StatCard label="平均风险评分" value={metrics.provider_metrics.avg_score} icon={Activity} />
        <StatCard label="模型调用次数" value={metrics.llm_usage.total_calls} icon={RadioTower} />
        <StatCard label="平均延迟" value={`${metrics.llm_usage.avg_latency_ms} ms`} icon={Clock3} />
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-semibold">Token 用量</h2>
          <div className="grid gap-3 md:grid-cols-3">
            <div className="rounded-md bg-slate-50 p-3">
              <div className="text-sm text-slate-500">Prompt Tokens</div>
              <div className="mt-2 text-2xl font-semibold">{metrics.llm_usage.total_prompt_tokens}</div>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <div className="text-sm text-slate-500">Completion Tokens</div>
              <div className="mt-2 text-2xl font-semibold">{metrics.llm_usage.total_completion_tokens}</div>
            </div>
            <div className="rounded-md bg-slate-50 p-3">
              <div className="text-sm text-slate-500">Total Tokens</div>
              <div className="mt-2 text-2xl font-semibold">{metrics.llm_usage.total_tokens}</div>
            </div>
          </div>
        </Card>
        <Card>
          <h2 className="mb-4 font-semibold">风险等级分布</h2>
          <Bars data={metrics.provider_metrics.severity_distribution} />
        </Card>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="flex items-center justify-between border-b border-border px-4 py-3">
          <div>
            <h2 className="font-semibold">数据源调度状态</h2>
            <p className="mt-1 text-xs text-slate-500">按源查看采集间隔、最近采集和下次执行时间。</p>
          </div>
          <Database size={18} className="text-slate-400" />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[900px] table-fixed text-sm">
            <colgroup>
              <col className="w-[34%]" />
              <col className="w-[110px]" />
              <col className="w-[120px]" />
              <col className="w-[190px]" />
              <col className="w-[190px]" />
            </colgroup>
            <thead>
              <tr className="border-b border-border bg-slate-50 text-left text-slate-500">
                <th className="p-3 font-medium">数据源</th>
                <th className="p-3 font-medium whitespace-nowrap">状态</th>
                <th className="p-3 font-medium whitespace-nowrap">间隔</th>
                <th className="p-3 font-medium whitespace-nowrap">上次采集</th>
                <th className="p-3 font-medium whitespace-nowrap">下次执行</th>
              </tr>
            </thead>
            <tbody>
              {scheduler.sources.map((item) => (
                <tr key={item.source_id} className="border-b border-border last:border-0 hover:bg-slate-50">
                  <td className="p-3">
                    <div className="truncate font-medium text-slate-950">{item.name}</div>
                    <div className="mt-1 truncate text-xs text-slate-500">
                      source #{item.source_id} | {item.enabled ? "已启用" : "已停用"}
                    </div>
                  </td>
                  <td className="p-3 whitespace-nowrap">
                    <span className="rounded bg-slate-100 px-2 py-1 text-xs text-slate-600">{item.status}</span>
                  </td>
                  <td className="p-3 whitespace-nowrap">{item.interval_minutes} 分钟</td>
                  <td className="p-3 whitespace-nowrap text-slate-600">{formatDate(item.last_collected_at)}</td>
                  <td className="p-3 whitespace-nowrap text-slate-600">{formatDate(item.next_run_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
        {scheduler.sources.length === 0 ? <div className="p-4 text-sm text-slate-500">暂无数据源。</div> : null}
      </Card>
    </div>
  );
}
