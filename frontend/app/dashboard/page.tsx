import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api, Vulnerability } from "@/lib/api";

type Stats = {
  total: number;
  severity_distribution: Record<string, number>;
  type_distribution: Record<string, number>;
  top_components: { name: string; count: number }[];
  recent: Vulnerability[];
  high_risk: Vulnerability[];
};

function Bars({ data }: { data: Record<string, number> }) {
  const max = Math.max(1, ...Object.values(data));

  return (
    <div className="space-y-3">
      {Object.entries(data).map(([key, value]) => (
        <div key={key}>
          <div className="mb-1 flex justify-between text-sm">
            <span>{key}</span>
            <span>{value}</span>
          </div>
          <div className="h-2 rounded bg-muted">
            <div
              className="h-2 rounded bg-primary"
              style={{ width: `${(value / max) * 100}%` }}
            />
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
  const criticalHigh =
    (stats.severity_distribution["严重"] ?? 0) + (stats.severity_distribution["高危"] ?? 0);

  return (
    <div className="space-y-6">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">漏洞态势看板</h1>
          <p className="text-sm text-slate-500">
            动态采集、AI 标准化抽取和 RAG 检索的统一入口。
          </p>
        </div>
        <Link
          className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white"
          href="/ai-extract"
        >
          录入漏洞
        </Link>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-4">
        <Card>
          <div className="text-sm text-slate-500">漏洞总数</div>
          <div className="mt-2 text-3xl font-semibold">{stats.total}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">严重/高危</div>
          <div className="mt-2 text-3xl font-semibold">{criticalHigh}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">类型数量</div>
          <div className="mt-2 text-3xl font-semibold">
            {Object.keys(stats.type_distribution).length}
          </div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">Top 组件</div>
          <div className="mt-2 text-lg font-semibold">
            {stats.top_components[0]?.name ?? "暂无"}
          </div>
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="mb-4 font-semibold">风险等级分布</h2>
          <Bars data={stats.severity_distribution} />
        </Card>
        <Card>
          <h2 className="mb-4 font-semibold">漏洞类型分布</h2>
          <Bars data={stats.type_distribution} />
        </Card>
      </div>

      <div className="grid grid-cols-1 gap-4 xl:grid-cols-2">
        <Card>
          <h2 className="mb-3 font-semibold">最近新增漏洞</h2>
          <div className="space-y-2">
            {stats.recent.map((vulnerability) => (
              <Link
                className="flex items-center justify-between rounded-md border border-border p-3 text-sm hover:bg-muted"
                href={`/vulnerabilities/${vulnerability.id}`}
                key={vulnerability.id}
              >
                <span>{vulnerability.title}</span>
                <Badge>{vulnerability.severity}</Badge>
              </Link>
            ))}
          </div>
        </Card>
        <Card>
          <h2 className="mb-3 font-semibold">高风险漏洞</h2>
          <div className="space-y-2">
            {stats.high_risk.map((vulnerability) => (
              <Link
                className="flex items-center justify-between rounded-md border border-border p-3 text-sm hover:bg-muted"
                href={`/vulnerabilities/${vulnerability.id}`}
                key={vulnerability.id}
              >
                <span>{vulnerability.title}</span>
                <span className="font-semibold">{vulnerability.score}</span>
              </Link>
            ))}
          </div>
        </Card>
      </div>
    </div>
  );
}
