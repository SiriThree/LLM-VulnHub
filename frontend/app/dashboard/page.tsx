import Link from "next/link";
import { ArrowRight, Database, Radar, ShieldAlert, Sparkles } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api, Vulnerability } from "@/lib/api";
import { formatSeverity } from "@/lib/presentation";

type Stats = {
  total: number;
  severity_distribution: Record<string, number>;
  type_distribution: Record<string, number>;
  top_components: { name: string; count: number }[];
  recent: Vulnerability[];
  high_risk: Vulnerability[];
};

function Bars({ data }: { data: Record<string, number> }) {
  const entries = Object.entries(data);
  const max = Math.max(1, ...entries.map(([, value]) => value));

  return (
    <div className="space-y-3">
      {entries.map(([key, value]) => (
        <div key={key}>
          <div className="mb-1 flex justify-between text-sm">
            <span>{formatSeverity(key) || key}</span>
            <span className="font-medium">{value}</span>
          </div>
          <div className="h-2 rounded bg-slate-100">
            <div className="h-2 rounded bg-slate-800" style={{ width: `${(value / max) * 100}%` }} />
          </div>
        </div>
      ))}
    </div>
  );
}

export default async function DashboardPage() {
  const emptyStats: Stats = {
    total: 0,
    severity_distribution: {},
    type_distribution: {},
    top_components: [],
    recent: [],
    high_risk: [],
  };

  const stats = await api<Stats>("/vulnerabilities/dashboard").catch(() => emptyStats);
  const criticalHigh = (stats.severity_distribution["严重"] ?? 0) + (stats.severity_distribution["高危"] ?? 0);
  const mediumLow = (stats.severity_distribution["中危"] ?? 0) + (stats.severity_distribution["低危"] ?? 0);

  return (
    <div className="space-y-6">
      <section className="rounded-lg border border-border bg-white p-6 shadow-soft">
        <div className="flex flex-col gap-6 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full bg-slate-100 px-3 py-1 text-xs font-medium text-slate-600">
            </div>
            <h1 className="text-3xl font-semibold tracking-tight text-slate-950">AI 漏洞情报运营总览</h1>
          </div>
          <div className="flex flex-wrap gap-3">
            <Link className="inline-flex h-10 items-center gap-2 rounded-md bg-slate-900 px-4 text-sm font-medium text-white" href="/collectors">
              <Radar size={16} />
              去看采集链路
            </Link>
            <Link className="inline-flex h-10 items-center gap-2 rounded-md border border-border bg-white px-4 text-sm font-medium text-slate-700" href="/ai-extract">
              <Database size={16} />
              录入 / 抽取漏洞
            </Link>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
        <Card>
          <div className="text-sm text-slate-500">漏洞总数</div>
          <div className="mt-3 text-3xl font-semibold">{stats.total}</div>
          <div className="mt-2 text-xs text-slate-400">平台内已形成标准记录的漏洞资产</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">严重 / 高危</div>
          <div className="mt-3 text-3xl font-semibold">{criticalHigh}</div>
          <div className="mt-2 text-xs text-slate-400">优先进入人工复核与修复跟踪的记录</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">中低风险</div>
          <div className="mt-3 text-3xl font-semibold">{mediumLow}</div>
          <div className="mt-2 text-xs text-slate-400">更适合归档分析与持续观察</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">热点组件</div>
          <div className="mt-3 text-lg font-semibold">{stats.top_components[0]?.name ?? "暂无"}</div>
          <div className="mt-2 text-xs text-slate-400">{stats.top_components[0]?.count ?? 0} 条相关漏洞命中</div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold">风险等级分布</h2>
            <ShieldAlert size={16} className="text-slate-400" />
          </div>
          <Bars data={stats.severity_distribution} />
        </Card>
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <h2 className="font-semibold">漏洞类型分布</h2>
            <span className="text-xs text-slate-400">{Object.keys(stats.type_distribution).length} 个类型</span>
          </div>
          <div className="space-y-3">
            {Object.entries(stats.type_distribution)
              .sort((a, b) => b[1] - a[1])
              .slice(0, 8)
              .map(([key, value]) => (
                <div key={key} className="flex items-center justify-between rounded-md border border-border bg-slate-50 px-3 py-2 text-sm">
                  <span className="truncate">{key}</span>
                  <span className="font-medium text-slate-700">{value}</span>
                </div>
              ))}
          </div>
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-semibold">最近新增漏洞</h2>
              <p className="mt-1 text-sm text-slate-500">适合在演示时展示平台最新入库结果。</p>
            </div>
            <Link className="inline-flex items-center gap-1 text-sm text-primary hover:underline" href="/vulnerabilities">
              查看全部
              <ArrowRight size={14} />
            </Link>
          </div>
          <div className="space-y-3">
            {stats.recent.map((vulnerability) => (
              <Link
                className="flex items-center justify-between rounded-md border border-border p-3 text-sm transition hover:bg-slate-50"
                href={`/vulnerabilities/${vulnerability.id}`}
                key={vulnerability.id}
              >
                <div className="min-w-0">
                  <div className="truncate font-medium">{vulnerability.title}</div>
                  <div className="mt-1 text-xs text-slate-500">{vulnerability.affected_component}</div>
                </div>
                <Badge>{vulnerability.severity}</Badge>
              </Link>
            ))}
          </div>
        </Card>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-semibold">高优先级漏洞</h2>
              <p className="mt-1 text-sm text-slate-500">按风险分值排序，突出最值得处理的条目。</p>
            </div>
            <Link className="inline-flex items-center gap-1 text-sm text-primary hover:underline" href="/intel-pool">
              去看情报池
              <ArrowRight size={14} />
            </Link>
          </div>
          <div className="space-y-3">
            {stats.high_risk.map((vulnerability) => (
              <Link
                className="flex items-center justify-between rounded-md border border-border p-3 text-sm transition hover:bg-slate-50"
                href={`/vulnerabilities/${vulnerability.id}`}
                key={vulnerability.id}
              >
                <div className="min-w-0">
                  <div className="truncate font-medium">{vulnerability.title}</div>
                  <div className="mt-1 text-xs text-slate-500">{vulnerability.vuln_type}</div>
                </div>
                <div className="text-right">
                  <div className="font-semibold text-slate-900">{vulnerability.score}</div>
                  <div className="mt-1">
                    <Badge>{vulnerability.severity}</Badge>
                  </div>
                </div>
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
