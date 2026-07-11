import Link from "next/link";
import { api, Vulnerability } from "@/lib/api";
import { Card } from "@/components/ui/card";
import { Badge } from "@/components/ui/badge";
import { VulnerabilityForm } from "@/components/vulnerability-form";

export default async function DetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const vulnerability = await api<Vulnerability>(`/vulnerabilities/${id}`);

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <Link className="text-sm text-primary" href="/vulnerabilities">返回漏洞库</Link>
          <h1 className="mt-2 text-2xl font-semibold">{vulnerability.title}</h1>
        </div>
        <div className="flex gap-2">
          <Badge>{vulnerability.severity}</Badge>
          <span className="rounded bg-muted px-2 py-1 text-xs font-medium">{vulnerability.score} 分</span>
        </div>
      </div>

      <div className="grid grid-cols-4 gap-4">
        <Card><div className="text-xs text-slate-500">漏洞类型</div><div className="mt-1 font-medium">{vulnerability.vuln_type}</div></Card>
        <Card><div className="text-xs text-slate-500">影响组件</div><div className="mt-1 font-medium">{vulnerability.affected_component}</div></Card>
        <Card><div className="text-xs text-slate-500">状态</div><div className="mt-1 font-medium">{vulnerability.status}</div></Card>
        <Card><div className="text-xs text-slate-500">AI 置信度</div><div className="mt-1 font-medium">{Math.round(vulnerability.confidence * 100)}%</div></Card>
      </div>

      <Card>
        <h2 className="mb-3 font-semibold">漏洞详情</h2>
        <div className="grid grid-cols-2 gap-4 text-sm">
          <div><span className="text-slate-500">来源：</span>{vulnerability.source || "unknown"}</div>
          <div><span className="text-slate-500">标签：</span>{vulnerability.tags.join("、") || "无"}</div>
          <div className="col-span-2"><span className="text-slate-500">参考链接：</span>{vulnerability.reference_url ? <a className="text-primary hover:underline" href={vulnerability.reference_url}>{vulnerability.reference_url}</a> : "暂无"}</div>
          <div className="col-span-2"><span className="text-slate-500">源链接：</span>{vulnerability.source_url ? <a className="text-primary hover:underline" href={vulnerability.source_url}>{vulnerability.source_url}</a> : "暂无"}</div>
        </div>
      </Card>

      <Card>
        <h2 className="mb-3 font-semibold">编辑漏洞</h2>
        <VulnerabilityForm mode="edit" vulnerabilityId={vulnerability.id} initial={vulnerability} />
      </Card>
    </div>
  );
}
