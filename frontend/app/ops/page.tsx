import { Card } from "@/components/ui/card";
import { api, OpsMetrics, SchedulerOverview } from "@/lib/api";

function Bars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  const max = Math.max(1, ...entries.map(([, value]) => value), 1);

  if (entries.length === 0) {
    return <div className="text-sm text-slate-500">暂无数据</div>;
  }

  return (
    <div className="space-y-3">
      {entries.map(([key, value]) => (
        <div key={key}>
          <div className="mb-1 flex justify-between text-sm">
            <span>{key}</span>
            <span>{value}</span>
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

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">Operations</h1>
        <p className="text-sm text-slate-500">观察采集、分析、审核与模型调用的运行指标，用于日常巡检和演示生产化能力。</p>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card><div className="text-sm text-slate-500">排队任务</div><div className="mt-3 text-4xl font-semibold">{metrics.queue_metrics.queued}</div></Card>
        <Card><div className="text-sm text-slate-500">运行中任务</div><div className="mt-3 text-4xl font-semibold">{metrics.queue_metrics.running}</div></Card>
        <Card><div className="text-sm text-slate-500">成功任务</div><div className="mt-3 text-4xl font-semibold">{metrics.queue_metrics.success}</div></Card>
        <Card><div className="text-sm text-slate-500">失败任务</div><div className="mt-3 text-4xl font-semibold">{metrics.queue_metrics.failed}</div></Card>
      </div>

      <div className="grid gap-4 md:grid-cols-4">
        <Card><div className="text-sm text-slate-500">数据源总数</div><div className="mt-3 text-4xl font-semibold">{metrics.source_health.total_sources}</div></Card>
        <Card><div className="text-sm text-slate-500">启用数据源</div><div className="mt-3 text-4xl font-semibold">{metrics.source_health.enabled_sources}</div></Card>
        <Card><div className="text-sm text-slate-500">停用数据源</div><div className="mt-3 text-4xl font-semibold">{metrics.source_health.disabled_sources}</div></Card>
        <Card><div className="text-sm text-slate-500">源失败通知</div><div className="mt-3 text-4xl font-semibold">{metrics.source_health.recently_failed_notifications}</div></Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-semibold">分析供应商分布</h2>
          <Bars data={metrics.provider_metrics.provider_distribution} />
        </Card>
        <Card>
          <h2 className="mb-4 font-semibold">分析严重等级分布</h2>
          <Bars data={metrics.provider_metrics.severity_distribution} />
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Card>
          <div className="text-sm text-slate-500">分析任务总数</div>
          <div className="mt-3 text-4xl font-semibold">{metrics.provider_metrics.analysis_jobs_total}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">平均风险评分</div>
          <div className="mt-3 text-4xl font-semibold">{metrics.provider_metrics.avg_score}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">模型调用次数</div>
          <div className="mt-3 text-4xl font-semibold">{metrics.llm_usage.total_calls}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">平均延迟</div>
          <div className="mt-3 text-4xl font-semibold">{metrics.llm_usage.avg_latency_ms} ms</div>
        </Card>
      </div>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <div className="text-sm text-slate-500">Prompt Tokens</div>
          <div className="mt-3 text-3xl font-semibold">{metrics.llm_usage.total_prompt_tokens}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">Completion Tokens</div>
          <div className="mt-3 text-3xl font-semibold">{metrics.llm_usage.total_completion_tokens}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">Total Tokens</div>
          <div className="mt-3 text-3xl font-semibold">{metrics.llm_usage.total_tokens}</div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-semibold">LLM 供应商</h2>
          <Bars data={metrics.llm_usage.provider_distribution} />
        </Card>
        <Card>
          <h2 className="mb-4 font-semibold">模型</h2>
          <Bars data={metrics.llm_usage.model_distribution} />
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-semibold">调度器任务</h2>
          <div className="space-y-3">
            {scheduler.beat_jobs.map((item) => (
              <div key={item.name} className="rounded-md border border-border bg-slate-50 p-3">
                <div className="font-medium">{item.name}</div>
                <div className="mt-1 text-sm text-slate-600">{item.task}</div>
                <div className="mt-2 text-xs text-slate-500">调度周期 {item.schedule_seconds} 秒</div>
              </div>
            ))}
            {scheduler.beat_jobs.length === 0 ? <div className="text-sm text-slate-500">暂无 Celery Beat 任务。</div> : null}
          </div>
        </Card>

        <Card>
          <h2 className="mb-4 font-semibold">数据源调度状态</h2>
          <div className="space-y-3">
            {scheduler.sources.map((item) => (
              <div key={item.source_id} className="rounded-md border border-border bg-slate-50 p-3">
                <div className="flex items-center justify-between gap-3">
                  <div className="font-medium">{item.name}</div>
                  <span className="rounded bg-white px-2 py-1 text-xs text-slate-600">{item.status}</span>
                </div>
                <div className="mt-2 grid gap-1 text-xs text-slate-500">
                  <div>间隔 {item.interval_minutes} 分钟</div>
                  <div>上次采集 {item.last_collected_at ? new Date(item.last_collected_at).toLocaleString() : "-"}</div>
                  <div>下次执行 {item.next_run_at ? new Date(item.next_run_at).toLocaleString() : "-"}</div>
                </div>
              </div>
            ))}
            {scheduler.sources.length === 0 ? <div className="text-sm text-slate-500">暂无数据源。</div> : null}
          </div>
        </Card>
      </div>
    </div>
  );
}
