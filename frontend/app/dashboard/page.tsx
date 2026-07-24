import Link from "next/link";
import { ArrowRight, Database, Radar, ShieldAlert } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { GuestNotice } from "@/components/guest-notice";
import { PageHero } from "@/components/page-hero";
import { Pagination } from "@/components/pagination";
import { api, AuthSession, Vulnerability } from "@/lib/api";
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

export default async function DashboardPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const recentPage = Math.max(1, Number(sp.recent_page ?? 1) || 1);
  const recentPageSize = Math.max(1, Number(sp.recent_page_size ?? 5) || 5);
  const highPage = Math.max(1, Number(sp.high_page ?? 1) || 1);
  const highPageSize = Math.max(1, Number(sp.high_page_size ?? 5) || 5);
  const paginationQuery = { ...sp };
  const emptyStats: Stats = {
    total: 0,
    severity_distribution: {},
    type_distribution: {},
    top_components: [],
    recent: [],
    high_risk: [],
  };

  const [stats, session] = await Promise.all([
    api<Stats>("/vulnerabilities/dashboard").catch(() => emptyStats),
    api<AuthSession>("/auth/status").catch((): AuthSession => ({ authenticated: false })),
  ]);
  const role = session.role ?? "guest";
  const isGuest = role === "guest";
  const canOperate = role === "analyst" || role === "admin";
  const criticalHigh = (stats.severity_distribution["严重"] ?? 0) + (stats.severity_distribution["高危"] ?? 0);
  const mediumLow = (stats.severity_distribution["中危"] ?? 0) + (stats.severity_distribution["低危"] ?? 0);
  const recentItems = stats.recent.slice((recentPage - 1) * recentPageSize, recentPage * recentPageSize);
  const highRiskItems = stats.high_risk.slice((highPage - 1) * highPageSize, highPage * highPageSize);

  return (
    <div className="space-y-6">
      {isGuest ? <GuestNotice /> : null}

      <PageHero
        title="漏洞概览"
        description="查看已入库漏洞、风险分布和近期热点。"
        actions={<div className="flex flex-wrap gap-3">
            {canOperate ? (
              <>
                <Link className="inline-flex h-10 items-center gap-2 rounded-md bg-white px-4 text-sm font-medium text-slate-950 hover:bg-slate-100" href="/collectors">
                  <Radar size={16} />
                  查看采集链路
                </Link>
                <Link className="inline-flex h-10 items-center gap-2 rounded-md border border-white/20 bg-white/10 px-4 text-sm font-medium text-white hover:bg-white/20" href="/ai-extract">
                  <Database size={16} />
                  新增漏洞
                </Link>
              </>
            ) : (
              <Link className="inline-flex h-10 items-center gap-2 rounded-md bg-white px-4 text-sm font-medium text-slate-950 hover:bg-slate-100" href="/vulnerabilities">
                <Database size={16} />
                浏览公开漏洞
              </Link>
            )}
          </div>}
      />

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 xl:grid-cols-4">
        <Card>
          <div className="text-sm text-slate-500">漏洞总数</div>
          <div className="mt-3 text-3xl font-semibold">{stats.total}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">严重 / 高危</div>
          <div className="mt-3 text-3xl font-semibold">{criticalHigh}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">中低风险</div>
          <div className="mt-3 text-3xl font-semibold">{mediumLow}</div>
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
              <p className="mt-1 text-sm text-slate-500">最近入库的漏洞记录。</p>
            </div>
            <Link className="inline-flex items-center gap-1 text-sm text-primary hover:underline" href="/vulnerabilities">
              查看全部
              <ArrowRight size={14} />
            </Link>
          </div>
          <div className="space-y-3">
            {recentItems.length ? recentItems.map((vulnerability) => (
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
            )) : <EmptyState>尚无已入库记录</EmptyState>}
          </div>
          <Pagination
            total={stats.recent.length}
            page={recentPage}
            pageSize={recentPageSize}
            basePath="/dashboard"
            query={paginationQuery}
            pageParam="recent_page"
            pageSizeParam="recent_page_size"
          />
        </Card>

        <Card>
          <div className="mb-4 flex items-center justify-between">
            <div>
              <h2 className="font-semibold">高风险漏洞</h2>
              <p className="mt-1 text-sm text-slate-500">按风险评分从高到低排列。</p>
            </div>
            {canOperate ? (
              <Link className="inline-flex items-center gap-1 text-sm text-primary hover:underline" href="/intel-pool">
                查看情报池
                <ArrowRight size={14} />
              </Link>
            ) : null}
          </div>
          <div className="space-y-3">
            {highRiskItems.length ? highRiskItems.map((vulnerability) => (
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
            )) : <EmptyState>尚无高优先级记录</EmptyState>}
          </div>
          <Pagination
            total={stats.high_risk.length}
            page={highPage}
            pageSize={highPageSize}
            basePath="/dashboard"
            query={paginationQuery}
            pageParam="high_page"
            pageSizeParam="high_page_size"
          />
        </Card>
      </div>
    </div>
  );
}

function EmptyState({ children }: { children: React.ReactNode }) {
  return <div className="rounded-md border border-dashed border-slate-200 px-4 py-8 text-center text-sm text-slate-400">{children}</div>;
}
