import Link from "next/link";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { VulnerabilityForm } from "@/components/vulnerability-form";
import { api, VulnerabilityDetail, VulnerabilityLineage } from "@/lib/api";

function isSafeExternalUrl(value: string | null | undefined): value is string {
  if (!value) return false;
  try {
    const parsed = new URL(value);
    return parsed.protocol === "http:" || parsed.protocol === "https:";
  } catch {
    return false;
  }
}

export default async function DetailPage({ params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  const [vulnerability, lineage] = await Promise.all([
    api<VulnerabilityDetail>(`/vulnerabilities/${id}`),
    api<VulnerabilityLineage>(`/vulnerabilities/${id}/lineage`).catch(() => null),
  ]);

  const timeline = [
    ...vulnerability.occurrences.map((occurrence) => ({
      id: `occ-${occurrence.id}`,
      time: occurrence.published_at || occurrence.created_at,
      title: occurrence.intelligence_title || `情报 #${occurrence.intelligence_item_id ?? "-"}`,
      type: "来源情报",
      detail: occurrence.evidence_excerpt || "暂无证据摘录",
    })),
    ...vulnerability.analyses.map((analysis) => ({
      id: `analysis-${analysis.id}`,
      time: analysis.created_at,
      title: analysis.model_name,
      type: "AI 分析",
      detail: analysis.risk_reason || analysis.summary || "暂无分析说明",
    })),
  ].sort((a, b) => new Date(b.time).getTime() - new Date(a.time).getTime());

  return (
    <div className="space-y-5">
      <div className="flex items-start justify-between">
        <div>
          <Link className="text-sm text-primary" href="/vulnerabilities">
            返回漏洞库
          </Link>
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

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <h2 className="mb-3 font-semibold">漏洞详情</h2>
          <div className="grid grid-cols-2 gap-4 text-sm">
            <div><span className="text-slate-500">来源：</span>{vulnerability.source || "未填写"}</div>
            <div><span className="text-slate-500">标签：</span>{vulnerability.tags.join("、") || "暂无"}</div>
            <div><span className="text-slate-500">可见范围：</span>{vulnerability.visibility}</div>
            <div className="col-span-2">
              <span className="text-slate-500">参考链接：</span>
              {isSafeExternalUrl(vulnerability.reference_url) ? (
                <a className="break-all text-primary hover:underline" href={vulnerability.reference_url} rel="noopener noreferrer" target="_blank">
                  {vulnerability.reference_url}
                </a>
              ) : "暂无"}
            </div>
            <div className="col-span-2">
              <span className="text-slate-500">来源链接：</span>
              {isSafeExternalUrl(vulnerability.source_url) ? (
                <a className="break-all text-primary hover:underline" href={vulnerability.source_url} rel="noopener noreferrer" target="_blank">
                  {vulnerability.source_url}
                </a>
              ) : "暂无"}
            </div>
          </div>

          <div className="mt-5 space-y-4 text-sm">
            <div><div className="font-medium">漏洞描述</div><div className="mt-1 whitespace-pre-wrap text-slate-700">{vulnerability.description || "暂无"}</div></div>
            <div><div className="font-medium">攻击方式</div><div className="mt-1 whitespace-pre-wrap text-slate-700">{vulnerability.attack_method || "暂无"}</div></div>
            <div><div className="font-medium">影响范围</div><div className="mt-1 whitespace-pre-wrap text-slate-700">{vulnerability.impact || "暂无"}</div></div>
            <div><div className="font-medium">修复建议</div><div className="mt-1 whitespace-pre-wrap text-slate-700">{vulnerability.mitigation || "暂无"}</div></div>
          </div>
        </Card>

        <div className="space-y-4">
          <Card>
            <h2 className="mb-3 font-semibold">漏洞时间线</h2>
            {timeline.length > 0 ? (
              <div className="space-y-3">
                {timeline.map((item) => (
                  <div key={item.id} className="rounded-md border border-border bg-white p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium">{item.type} | {item.title}</div>
                      <div className="text-xs text-slate-400">{new Date(item.time).toLocaleString()}</div>
                    </div>
                    <div className="mt-2 whitespace-pre-wrap text-slate-600">{item.detail}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-slate-500">当前没有可展示的时间线事件。</div>
            )}
          </Card>

          <Card>
            <h2 className="mb-3 font-semibold">来源情报</h2>
            {vulnerability.occurrences.length > 0 ? (
              <div className="space-y-3">
                {vulnerability.occurrences.map((occurrence) => (
                  <div key={occurrence.id} className="rounded-md border border-border bg-white p-3 text-sm">
                    <div className="flex items-start justify-between gap-3">
                      <div>
                        <div className="font-medium">{occurrence.intelligence_title || `情报 #${occurrence.intelligence_item_id ?? "-"}`}</div>
                        <div className="mt-1 text-xs text-slate-500">状态 {occurrence.intelligence_status ?? "-"} | 置信度 {Math.round(occurrence.confidence * 100)}%</div>
                      </div>
                      {occurrence.intelligence_item_id ? <Link className="text-primary hover:underline" href={`/intel-pool?selected=${occurrence.intelligence_item_id}`}>查看情报</Link> : null}
                    </div>
                    <div className="mt-2 whitespace-pre-wrap text-slate-700">{occurrence.evidence_excerpt || "暂无证据摘录"}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-slate-500">当前没有来源情报记录。</div>
            )}
          </Card>

          <Card>
            <h2 className="mb-3 font-semibold">AI 分析记录</h2>
            {vulnerability.analyses.length > 0 ? (
              <div className="space-y-3">
                {vulnerability.analyses.map((analysis) => (
                  <div key={analysis.id} className="rounded-md border border-border bg-white p-3 text-sm">
                    <div className="flex items-center justify-between gap-3">
                      <div className="font-medium">{analysis.model_name}</div>
                      <div className="text-xs text-slate-400">{new Date(analysis.created_at).toLocaleString()}</div>
                    </div>
                    <div className="mt-2 text-slate-700">{analysis.summary}</div>
                    <div className="mt-2 text-xs text-slate-500">风险说明：{analysis.risk_reason || "暂无"}</div>
                    <div className="mt-1 text-xs text-slate-500">修复建议：{analysis.suggested_fix || "暂无"}</div>
                  </div>
                ))}
              </div>
            ) : (
              <div className="text-sm text-slate-500">当前没有 AI 分析记录。</div>
            )}
          </Card>
        </div>
      </div>

      {lineage ? (
        <Card>
          <h2 className="mb-3 font-semibold">采集血缘与可信度</h2>
          <div className="grid gap-3 md:grid-cols-2 xl:grid-cols-3">
            {lineage.occurrences.map((item) => (
              <div key={item.occurrence_id} className="rounded-md border border-border bg-white p-3 text-sm">
                <div className="font-medium">{item.intelligence_title || `情报 #${item.intelligence_item_id ?? "-"}`}</div>
                <div className="mt-1 text-xs text-slate-500">
                  来源 {item.source_name ?? "未记录"} {item.source_type ? `| ${item.source_type}` : ""}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  来源可信度 {item.source_trust_score ?? "-"} | {item.source_trust_level ?? "-"}
                </div>
                <div className="mt-1 text-xs text-slate-500">
                  文档 {item.collected_document_title ?? "未记录"} | 情报状态 {item.intelligence_status ?? "-"}
                </div>
                <div className="mt-2 line-clamp-4 text-slate-700">{item.evidence_excerpt}</div>
                {item.intelligence_item_id ? (
                  <div className="mt-3">
                    <Link className="text-xs text-primary hover:underline" href={`/intel-pool?selected=${item.intelligence_item_id}`}>
                      查看上游情报
                    </Link>
                  </div>
                ) : null}
              </div>
            ))}
          </div>

          {lineage.review_actions.length > 0 ? (
            <div className="mt-4 space-y-3">
              <div className="text-sm font-semibold">相关审核动作</div>
              {lineage.review_actions.map((action) => (
                <div key={action.id} className="rounded-md border border-border bg-white p-3 text-sm">
                  <div className="flex items-center justify-between gap-3">
                    <div className="font-medium">{action.action}</div>
                    <div className="text-xs text-slate-400">{new Date(action.created_at).toLocaleString()}</div>
                  </div>
                  <div className="mt-1 text-slate-600">执行人：{action.actor}</div>
                  <div className="mt-1 text-slate-600">备注：{action.reason || "-"}</div>
                </div>
              ))}
            </div>
          ) : null}
        </Card>
      ) : null}

      <Card>
        <h2 className="mb-3 font-semibold">编辑漏洞</h2>
        <VulnerabilityForm mode="edit" vulnerabilityId={vulnerability.id} initial={vulnerability} />
      </Card>
    </div>
  );
}
