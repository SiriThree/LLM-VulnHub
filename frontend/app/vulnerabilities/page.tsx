import Link from "next/link";
import { Plus, Search } from "lucide-react";
import { api, Vulnerability } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";

type ListResponse = { items: Vulnerability[]; total: number; page: number; page_size: number };

export default async function VulnerabilitiesPage({ searchParams }: { searchParams: Promise<Record<string, string | undefined>> }) {
  const sp = await searchParams;
  const query = new URLSearchParams();
  for (const key of ["q", "severity", "vuln_type", "component", "status"]) {
    if (sp[key]) query.set(key, sp[key]!);
  }
  const empty: ListResponse = { items: [], total: 0, page: 1, page_size: 20 };
  const data = await api<ListResponse>(`/vulnerabilities?${query}`).catch(() => empty);

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between">
        <div>
          <h1 className="text-2xl font-semibold">漏洞库</h1>
          <p className="text-sm text-slate-500">支持搜索、筛选、详情查看、手动新增和 AI 导入。</p>
        </div>
        <div className="flex gap-2">
          <Link className="inline-flex h-9 items-center gap-2 rounded-md border border-border bg-white px-3 text-sm font-medium" href="/vulnerabilities/new">
            <Plus size={16} />
            手动新增
          </Link>
          <Link className="rounded-md bg-primary px-3 py-2 text-sm font-medium text-white" href="/ai-extract">
            AI 导入
          </Link>
        </div>
      </div>

      <form className="grid grid-cols-6 gap-3 rounded-lg border border-border bg-white p-4">
        <div className="col-span-2 flex items-center gap-2 rounded-md border border-border px-3">
          <Search size={16} />
          <input name="q" defaultValue={sp.q ?? ""} className="h-9 flex-1 outline-none" placeholder="标题、描述、组件" />
        </div>
        <select name="severity" defaultValue={sp.severity ?? ""} className="rounded-md border border-border px-3 text-sm">
          <option value="">全部等级</option>
          <option value="严重">严重</option>
          <option value="高危">高危</option>
          <option value="中危">中危</option>
          <option value="低危">低危</option>
        </select>
        <input name="vuln_type" defaultValue={sp.vuln_type ?? ""} className="rounded-md border border-border px-3 text-sm outline-none" placeholder="漏洞类型" />
        <input name="component" defaultValue={sp.component ?? ""} className="rounded-md border border-border px-3 text-sm outline-none" placeholder="影响组件" />
        <select name="status" defaultValue={sp.status ?? ""} className="rounded-md border border-border px-3 text-sm">
          <option value="">全部状态</option>
          <option value="未修复">未修复</option>
          <option value="待确认">待确认</option>
          <option value="已修复">已修复</option>
          <option value="已忽略">已忽略</option>
        </select>
        <button className="col-span-6 rounded-md bg-primary px-3 py-2 text-sm font-medium text-white md:col-span-1">筛选</button>
      </form>

      <Card className="p-0">
        <table className="w-full border-collapse text-sm">
          <thead>
            <tr className="border-b border-border bg-muted text-left">
              <th className="p-3">标题</th>
              <th>类型</th>
              <th>等级</th>
              <th>评分</th>
              <th>影响组件</th>
              <th>状态</th>
              <th>创建时间</th>
              <th className="pr-3">操作</th>
            </tr>
          </thead>
          <tbody>
            {data.items.map((v) => (
              <tr key={v.id} className="border-b border-border last:border-0 hover:bg-muted">
                <td className="p-3 font-medium">
                  <Link href={`/vulnerabilities/${v.id}`}>{v.title}</Link>
                </td>
                <td>{v.vuln_type}</td>
                <td><Badge>{v.severity}</Badge></td>
                <td>{v.score}</td>
                <td>{v.affected_component}</td>
                <td>{v.status}</td>
                <td>{new Date(v.created_at).toLocaleString()}</td>
                <td className="pr-3">
                  <Link className="text-primary hover:underline" href={`/vulnerabilities/${v.id}`}>查看 / 编辑</Link>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
      <div className="text-sm text-slate-500">共 {data.total} 条漏洞记录</div>
    </div>
  );
}
