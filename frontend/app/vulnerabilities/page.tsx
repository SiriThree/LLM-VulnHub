import Link from "next/link";
import { Plus, Search } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api, Vulnerability } from "@/lib/api";
import { formatVulnerabilityStatus } from "@/lib/presentation";

type ListResponse = { items: Vulnerability[]; total: number; page: number; page_size: number };

export default async function VulnerabilitiesPage({
  searchParams,
}: {
  searchParams: Promise<Record<string, string | undefined>>;
}) {
  const sp = await searchParams;
  const currentPage = Math.max(1, Number(sp.page ?? 1) || 1);
  const pageSize = Math.min(100, Math.max(1, Number(sp.page_size ?? 20) || 20));
  const query = new URLSearchParams();
  for (const key of ["q", "severity", "vuln_type", "component", "status", "page", "page_size"]) {
    if (sp[key]) query.set(key, sp[key]!);
  }
  query.set("page", String(currentPage));
  query.set("page_size", String(pageSize));
  const empty: ListResponse = { items: [], total: 0, page: 1, page_size: 20 };
  const data = await api<ListResponse>(`/vulnerabilities?${query}`).catch(() => empty);
  const totalPages = Math.max(1, Math.ceil(data.total / data.page_size));
  const pageNumbers = Array.from(
    new Set([1, data.page - 1, data.page, data.page + 1, totalPages].filter((page) => page >= 1 && page <= totalPages)),
  ).sort((a, b) => a - b);

  function pageHref(page: number) {
    const next = new URLSearchParams(query);
    next.set("page", String(page));
    return `/vulnerabilities?${next.toString()}`;
  }

  const activeFilters = [
    sp.q ? `关键词: ${sp.q}` : null,
    sp.severity ? `等级: ${sp.severity}` : null,
    sp.vuln_type ? `类型: ${sp.vuln_type}` : null,
    sp.component ? `组件: ${sp.component}` : null,
    sp.status ? `状态: ${sp.status}` : null,
  ].filter(Boolean) as string[];

  return (
    <div className="space-y-5">
      <div className="flex flex-col gap-4 xl:flex-row xl:items-end xl:justify-between">
        <div>
          <h1 className="text-2xl font-semibold">漏洞库</h1>
          <p className="mt-1 text-sm text-slate-500">查询和维护经复核的标准化漏洞记录，支持筛选、详情查看与辅助抽取入库。</p>
        </div>
        <div className="flex gap-2">
          <Link className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm font-medium" href="/vulnerabilities/new">
            <Plus size={16} />
            手动新增
          </Link>
          <Link className="inline-flex h-9 items-center rounded-md bg-slate-900 px-3 text-sm font-medium text-white" href="/ai-extract">
            辅助抽取
          </Link>
        </div>
      </div>

      <form className="rounded-lg border border-border bg-white p-4 shadow-soft">
        <div className="grid gap-3 xl:grid-cols-[2fr_1fr_1fr_1fr_1fr_auto]">
          <div className="flex items-center gap-2 rounded-md border border-border px-3">
            <Search size={16} />
            <input name="q" defaultValue={sp.q ?? ""} className="h-10 flex-1 bg-transparent text-sm outline-none" placeholder="搜索标题、描述、影响组件" />
          </div>
          <select name="severity" defaultValue={sp.severity ?? ""} className="h-10 rounded-md border border-border bg-white px-3 text-sm">
            <option value="">全部等级</option>
            <option value="严重">严重</option>
            <option value="高危">高危</option>
            <option value="中危">中危</option>
            <option value="低危">低危</option>
          </select>
          <input name="vuln_type" defaultValue={sp.vuln_type ?? ""} className="h-10 rounded-md border border-border px-3 text-sm outline-none" placeholder="漏洞类型" />
          <input name="component" defaultValue={sp.component ?? ""} className="h-10 rounded-md border border-border px-3 text-sm outline-none" placeholder="影响组件" />
          <input name="status" defaultValue={sp.status ?? ""} className="h-10 rounded-md border border-border px-3 text-sm outline-none" placeholder="状态" />
          <button className="inline-flex h-10 items-center justify-center rounded-md bg-slate-900 px-4 text-sm font-medium text-white">筛选</button>
        </div>
        <div className="mt-3 flex flex-wrap gap-2">
          {activeFilters.length > 0 ? (
            activeFilters.map((filter) => (
              <span key={filter} className="rounded-full bg-slate-100 px-3 py-1 text-xs text-slate-600">
                {filter}
              </span>
            ))
          ) : (
            <span className="text-xs text-slate-400">当前未设置筛选条件</span>
          )}
        </div>
      </form>

      <div className="grid gap-4 md:grid-cols-3">
        <Card>
          <div className="text-sm text-slate-500">结果总数</div>
          <div className="mt-3 text-3xl font-semibold">{data.total}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">当前页</div>
          <div className="mt-3 text-3xl font-semibold">{data.page}</div>
        </Card>
        <Card>
          <div className="text-sm text-slate-500">每页条数</div>
          <div className="mt-3 text-3xl font-semibold">{data.page_size}</div>
        </Card>
      </div>

      <Card className="overflow-hidden p-0">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1260px] table-fixed border-collapse text-sm">
            <colgroup>
              <col className="w-[32%]" />
              <col className="w-[15%]" />
              <col className="w-[72px]" />
              <col className="w-[64px]" />
              <col className="w-[34%]" />
              <col className="w-[96px]" />
              <col className="w-[128px]" />
              <col className="w-[76px]" />
            </colgroup>
            <thead>
              <tr className="border-b border-border bg-slate-50 text-left text-slate-500">
                <th className="p-3 font-medium">标题</th>
                <th className="p-3 font-medium">类型</th>
                <th className="p-3 font-medium whitespace-nowrap">等级</th>
                <th className="p-3 font-medium whitespace-nowrap">评分</th>
                <th className="p-3 font-medium">影响组件</th>
                <th className="p-3 font-medium whitespace-nowrap">状态</th>
                <th className="p-3 font-medium whitespace-nowrap">创建时间</th>
                <th className="p-3 font-medium whitespace-nowrap">操作</th>
              </tr>
            </thead>
            <tbody>
              {data.items.map((vulnerability) => (
                <tr key={vulnerability.id} className="border-b border-border last:border-0 hover:bg-slate-50">
                  <td className="p-3">
                    <Link href={`/vulnerabilities/${vulnerability.id}`} className="block">
                      <div className="max-w-[320px] truncate font-medium text-slate-900">{vulnerability.title}</div>
                      <div className="mt-1 text-xs text-slate-500">{vulnerability.tags.slice(0, 3).join("、") || "暂无标签"}</div>
                    </Link>
                  </td>
                  <td className="p-3">
                    <div className="line-clamp-2">{vulnerability.vuln_type}</div>
                  </td>
                  <td className="p-3 whitespace-nowrap"><Badge>{vulnerability.severity}</Badge></td>
                  <td className="p-3 whitespace-nowrap font-semibold text-slate-900">{vulnerability.score}</td>
                  <td className="p-3">
                    <div className="line-clamp-2">{vulnerability.affected_component}</div>
                  </td>
                  <td className="p-3 whitespace-nowrap">{formatVulnerabilityStatus(vulnerability.status)}</td>
                  <td className="p-3 whitespace-nowrap">{new Date(vulnerability.created_at).toLocaleString()}</td>
                  <td className="p-3 whitespace-nowrap">
                    <Link className="text-primary hover:underline" href={`/vulnerabilities/${vulnerability.id}`}>
                      查看详情
                    </Link>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>
      <div className="flex flex-col gap-3 text-sm text-slate-500 md:flex-row md:items-center md:justify-between">
        <div>
          共 {data.total} 条漏洞记录，第 {data.page} / {totalPages} 页
        </div>
        <div className="flex flex-wrap items-center gap-2">
          <Link
            className={`inline-flex h-9 items-center whitespace-nowrap rounded-md border border-border px-3 ${
              data.page <= 1 ? "pointer-events-none opacity-50" : "bg-white hover:bg-slate-50"
            }`}
            href={pageHref(Math.max(1, data.page - 1))}
          >
            上一页
          </Link>
          {pageNumbers.map((page, index) => (
            <span key={page} className="flex items-center gap-2">
              {index > 0 && page - pageNumbers[index - 1] > 1 ? <span className="text-slate-400">...</span> : null}
              <Link
                className={`inline-flex h-9 min-w-9 items-center justify-center rounded-md border border-border px-3 ${
                  page === data.page ? "bg-slate-900 text-white" : "bg-white hover:bg-slate-50"
                }`}
                href={pageHref(page)}
              >
                {page}
              </Link>
            </span>
          ))}
          <Link
            className={`inline-flex h-9 items-center whitespace-nowrap rounded-md border border-border px-3 ${
              data.page >= totalPages ? "pointer-events-none opacity-50" : "bg-white hover:bg-slate-50"
            }`}
            href={pageHref(Math.min(totalPages, data.page + 1))}
          >
            下一页
          </Link>
        </div>
      </div>
    </div>
  );
}
