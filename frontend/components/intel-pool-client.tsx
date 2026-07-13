"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Check, GitMerge, RefreshCcw, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import {
  api,
  IntelligenceItem,
  IntelligenceListResponse,
  IntelligenceStats,
  MergeCandidate,
  ReviewAction,
  ReviewActionListResponse,
  ReviewStats,
} from "@/lib/api";

const STATUS_OPTIONS = [
  { value: "", label: "全部" },
  { value: "pending_review", label: "待复核" },
  { value: "approved", label: "已发布" },
  { value: "rejected", label: "已驳回" },
  { value: "triaged", label: "已分流" },
];

const STATUS_LABELS: Record<string, string> = {
  pending_review: "待复核",
  approved: "已发布",
  rejected: "已驳回",
  triaged: "已分流",
  stored: "已入库",
  ignored: "已忽略",
};

const ACTION_LABELS: Record<string, string> = {
  approve: "通过发布",
  reject: "驳回",
  approve_merge: "归并发布",
};

function FieldCard({ label, value }: { label: string; value: unknown }) {
  return (
    <div className="rounded-md border border-border bg-white p-3 text-sm">
      <div className="text-xs text-slate-500">{label}</div>
      <div className="mt-1 whitespace-pre-wrap break-words">{String(value ?? "-")}</div>
    </div>
  );
}

type Props = {
  initialSelected?: string;
  initialStatus?: string;
};

export function IntelligencePoolClient({ initialSelected, initialStatus }: Props) {
  const [items, setItems] = useState<IntelligenceItem[]>([]);
  const [selectedId, setSelectedId] = useState<number | null>(
    initialSelected && Number.isFinite(Number(initialSelected)) ? Number(initialSelected) : null,
  );
  const [status, setStatus] = useState(initialStatus || "pending_review");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [notes, setNotes] = useState("");
  const [actions, setActions] = useState<ReviewAction[]>([]);
  const [globalActions, setGlobalActions] = useState<ReviewAction[]>([]);
  const [stats, setStats] = useState<IntelligenceStats | null>(null);
  const [reviewStats, setReviewStats] = useState<ReviewStats | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);

  async function load(nextSelectedId?: number | null) {
    const query = status ? `?status=${encodeURIComponent(status)}` : "";
    const res = await api<IntelligenceListResponse>(`/intel/items${query}`).catch(() => ({ items: [] }));
    setItems(res.items);

    const resolvedSelectedId =
      nextSelectedId !== undefined
        ? nextSelectedId
        : selectedId && res.items.some((item) => item.id === selectedId)
          ? selectedId
          : res.items[0]?.id ?? null;
    setSelectedId(resolvedSelectedId);
    setSelectedIds((current) => current.filter((id) => res.items.some((item) => item.id === id)));
  }

  async function loadActions(intelItemId: number) {
    const res = await api<ReviewActionListResponse>(`/intel/items/${intelItemId}/actions`).catch(() => ({ items: [] }));
    setActions(res.items);
  }

  async function loadGlobalActions() {
    const res = await api<ReviewActionListResponse>("/intel/review-actions?limit=12").catch(() => ({ items: [] }));
    setGlobalActions(res.items);
  }

  async function loadStats() {
    const res = await api<IntelligenceStats>("/intel/stats").catch(() => null);
    setStats(res);
  }

  async function loadReviewStats() {
    const res = await api<ReviewStats>("/intel/review-stats").catch(() => null);
    setReviewStats(res);
  }

  useEffect(() => {
    load();
    loadStats();
    loadReviewStats();
    loadGlobalActions();
  }, [status]);

  useEffect(() => {
    if (selectedId) {
      loadActions(selectedId);
    } else {
      setActions([]);
    }
  }, [selectedId]);

  const selected = useMemo(() => items.find((item) => item.id === selectedId) ?? null, [items, selectedId]);

  useEffect(() => {
    setNotes(selected?.review_notes ?? "");
  }, [selected?.id]);

  function toggleSelection(itemId: number) {
    setSelectedIds((current) => (current.includes(itemId) ? current.filter((id) => id !== itemId) : [...current, itemId]));
  }

  function toggleSelectAll() {
    if (selectedIds.length === items.length) {
      setSelectedIds([]);
      return;
    }
    setSelectedIds(items.map((item) => item.id));
  }

  async function refreshSideData() {
    await loadStats();
    await loadReviewStats();
    await loadGlobalActions();
  }

  async function approve() {
    if (!selected) return;
    setSubmitting(true);
    setMessage("");
    try {
      const updated = await api<IntelligenceItem>(`/intel/items/${selected.id}/approve`, {
        method: "POST",
        body: JSON.stringify({ actor: "analyst", notes }),
      });
      setMessage(
        updated.vulnerability_id
          ? `情报 #${selected.id} 已发布到漏洞库，关联漏洞 #${updated.vulnerability_id}。`
          : `情报 #${selected.id} 已通过复核。`,
      );
      await load(updated.id);
      await loadActions(updated.id);
      await refreshSideData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "审核通过失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function reject() {
    if (!selected) return;
    setSubmitting(true);
    setMessage("");
    try {
      const updated = await api<IntelligenceItem>(`/intel/items/${selected.id}/reject`, {
        method: "POST",
        body: JSON.stringify({ actor: "analyst", notes }),
      });
      setMessage(`情报 #${updated.id} 已驳回。`);
      await load(updated.id);
      await loadActions(updated.id);
      await refreshSideData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "驳回失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function runBatch(action: "approve" | "reject") {
    if (selectedIds.length === 0) return;
    setSubmitting(true);
    setMessage("");
    try {
      const endpoint = action === "approve" ? "/intel/items/batch-approve" : "/intel/items/batch-reject";
      const res = await api<{ items: IntelligenceItem[] }>(endpoint, {
        method: "POST",
        body: JSON.stringify({ actor: "analyst", notes, item_ids: selectedIds }),
      });
      setMessage(action === "approve" ? `已批量通过 ${res.items.length} 条情报。` : `已批量驳回 ${res.items.length} 条情报。`);
      setSelectedIds([]);
      await load(selectedId);
      await refreshSideData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "批量处理失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function approveMerge(candidate: MergeCandidate) {
    setSubmitting(true);
    setMessage("");
    try {
      await api(`/intel/merge-candidates/${candidate.id}/approve`, {
        method: "POST",
        body: JSON.stringify({ actor: "analyst", notes }),
      });
      setMessage(`合并候选 #${candidate.id} 已通过，情报将归并到漏洞 #${candidate.candidate_vulnerability_id}。`);
      await load(candidate.intelligence_item_id);
      await loadActions(candidate.intelligence_item_id);
      await refreshSideData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "合并失败。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <div className="flex items-end justify-between gap-4">
        <div>
          <h1 className="text-2xl font-semibold">情报池</h1>
          <p className="text-sm text-slate-500">
            采集候选先进入情报池，经过 AI 判定、结构化抽取、合并建议和人工复核后，再发布到正式漏洞库。
          </p>
        </div>
        <Button type="button" className="border border-border bg-white text-slate-700" onClick={() => load(selectedId)}>
          <RefreshCcw size={16} />
          刷新
        </Button>
      </div>

      {message ? <div className="rounded-md border border-border bg-white p-3 text-sm">{message}</div> : null}

      {stats ? (
        <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
          <Card><div className="text-sm text-slate-500">情报总量</div><div className="mt-3 text-3xl font-semibold">{stats.total}</div></Card>
          <Card><div className="text-sm text-slate-500">待复核</div><div className="mt-3 text-3xl font-semibold">{stats.pending_review}</div></Card>
          <Card><div className="text-sm text-slate-500">高风险待复核</div><div className="mt-3 text-3xl font-semibold">{stats.high_risk_pending_review}</div></Card>
          <Card><div className="text-sm text-slate-500">待合并候选</div><div className="mt-3 text-3xl font-semibold">{stats.merge_candidates_pending}</div></Card>
          <Card><div className="text-sm text-slate-500">已发布</div><div className="mt-3 text-3xl font-semibold">{stats.approved}</div></Card>
          <Card><div className="text-sm text-slate-500">已驳回</div><div className="mt-3 text-3xl font-semibold">{stats.rejected}</div></Card>
        </div>
      ) : null}

      {reviewStats ? (
        <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-6">
          <Card><div className="text-sm text-slate-500">审核动作总数</div><div className="mt-3 text-3xl font-semibold">{reviewStats.total_actions}</div></Card>
          <Card><div className="text-sm text-slate-500">通过发布</div><div className="mt-3 text-3xl font-semibold">{reviewStats.approvals}</div></Card>
          <Card><div className="text-sm text-slate-500">驳回次数</div><div className="mt-3 text-3xl font-semibold">{reviewStats.rejections}</div></Card>
          <Card><div className="text-sm text-slate-500">归并次数</div><div className="mt-3 text-3xl font-semibold">{reviewStats.merges}</div></Card>
          <Card><div className="text-sm text-slate-500">24h 动作</div><div className="mt-3 text-3xl font-semibold">{reviewStats.last_24h_actions}</div></Card>
          <Card><div className="text-sm text-slate-500">参与审核员</div><div className="mt-3 text-3xl font-semibold">{reviewStats.unique_actors}</div></Card>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-slate-500">状态筛选</span>
            <select className="h-10 rounded-md border border-border bg-white px-3 text-sm" value={status} onChange={(event) => setStatus(event.target.value)}>
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <div className="text-sm text-slate-500">当前 {items.length} 条</div>
            <div className="ml-auto flex items-center gap-2">
              <span className="text-sm text-slate-500">已选择 {selectedIds.length} 条</span>
              <Button type="button" onClick={() => runBatch("approve")} disabled={submitting || selectedIds.length === 0}>批量通过</Button>
              <Button type="button" className="bg-accent" onClick={() => runBatch("reject")} disabled={submitting || selectedIds.length === 0}>批量驳回</Button>
            </div>
          </div>
        </Card>

        <Card>
          <div className="text-sm font-semibold">审核员分布</div>
          {reviewStats && reviewStats.top_actors.length > 0 ? (
            <div className="mt-3 space-y-3">
              {reviewStats.top_actors.map((actor) => (
                <div key={String(actor.actor)} className="flex items-center justify-between text-sm">
                  <span>{String(actor.actor)}</span>
                  <span className="font-medium">{Number(actor.count)}</span>
                </div>
              ))}
            </div>
          ) : (
            <div className="mt-3 text-sm text-slate-500">暂无审核员动作。</div>
          )}
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="p-0">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="font-semibold">待处理情报</div>
            <label className="flex items-center gap-2 text-xs text-slate-500">
              <input type="checkbox" checked={items.length > 0 && selectedIds.length === items.length} onChange={toggleSelectAll} />
              全选
            </label>
          </div>
          <div className="max-h-[74vh] overflow-auto">
            {items.length > 0 ? items.map((item) => (
              <div key={item.id} className={`flex items-start gap-3 border-b border-border px-4 py-3 transition last:border-0 ${selectedId === item.id ? "bg-muted" : "bg-white hover:bg-slate-50"}`}>
                <input className="mt-1" type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => toggleSelection(item.id)} />
                <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setSelectedId(item.id)}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="line-clamp-2 font-medium">{item.title}</div>
                      <div className="mt-1 text-xs text-slate-500">分类 {item.triage_category} · 置信度 {Math.round(item.triage_confidence * 100)}%</div>
                    </div>
                    <span className="rounded bg-white px-2 py-1 text-xs">{STATUS_LABELS[item.status] ?? item.status}</span>
                  </div>
                </button>
              </div>
            )) : <div className="p-4 text-sm text-slate-500">当前筛选条件下没有情报记录。</div>}
          </div>
        </Card>

        <Card>
          {selected ? (
            <div className="space-y-5">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h2 className="text-lg font-semibold">{selected.title}</h2>
                  <div className="mt-1 text-sm text-slate-500">
                    状态 {STATUS_LABELS[selected.status] ?? selected.status} · 分类 {selected.triage_category} · 置信度 {Math.round(selected.triage_confidence * 100)}%
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    intelligence #{selected.id}
                    {selected.vulnerability_id ? <> · 已关联 <Link className="ml-1 text-primary hover:underline" href={`/vulnerabilities/${selected.vulnerability_id}`}>漏洞 #{selected.vulnerability_id}</Link></> : null}
                  </div>
                </div>
                <div className="flex gap-2">
                  <Button type="button" onClick={approve} disabled={submitting}><Check size={16} />发布</Button>
                  <Button type="button" onClick={reject} disabled={submitting} className="bg-accent"><X size={16} />驳回</Button>
                </div>
              </div>

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="space-y-2">
                  <div className="text-sm font-semibold">原始情报</div>
                  <div className="max-h-72 overflow-auto rounded-md border border-border bg-white p-3 text-sm leading-6">{selected.raw_text}</div>
                </div>
                <div className="space-y-2">
                  <div className="text-sm font-semibold">AI 判定</div>
                  <div className="rounded-md border border-border bg-white p-3 text-sm leading-6">
                    <div>判定原因：{selected.triage_reason || "暂无说明"}</div>
                    <div className="mt-2 break-all">来源 URL：{selected.url ?? "-"}</div>
                    <div className="mt-2">归一化文本长度：{selected.normalized_text.length}</div>
                    <div className="mt-2">候选合并数：{selected.merge_candidates.length}</div>
                  </div>
                </div>
              </div>

              <div className="space-y-2">
                <div className="text-sm font-semibold">复核备注</div>
                <textarea className="min-h-24 w-full rounded-md border border-border bg-white p-3 text-sm outline-none" value={notes} onChange={(event) => setNotes(event.target.value)} placeholder="记录审核判断、合并理由、需要补充的信息。" />
              </div>

              <div className="space-y-2">
                <div className="text-sm font-semibold">结构化抽取结果</div>
                <div className="grid gap-3 md:grid-cols-2">
                  {([["title", selected.extracted_data.title], ["vuln_type", selected.extracted_data.vuln_type], ["severity", selected.extracted_data.severity], ["score", selected.extracted_data.score], ["affected_component", selected.extracted_data.affected_component], ["status", selected.extracted_data.status]] as Array<[string, unknown]>).map(([label, value]) => (
                    <FieldCard key={label} label={label} value={value} />
                  ))}
                </div>
                {["description", "attack_method", "impact", "mitigation", "risk_reason", "review_summary"].map((key) => (
                  <FieldCard key={key} label={key} value={selected.extracted_data[key]} />
                ))}
              </div>

              <div className="space-y-2">
                <div className="text-sm font-semibold">合并候选</div>
                {selected.merge_candidates.length > 0 ? (
                  <div className="space-y-3">
                    {selected.merge_candidates.map((candidate) => (
                      <div key={candidate.id} className="rounded-md border border-border bg-white p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-medium">候选漏洞 #{candidate.candidate_vulnerability_id}</div>
                            <div className="mt-1 text-sm text-slate-600">{candidate.merge_reason}</div>
                            <div className="mt-1 text-xs text-slate-400">合并分数 {candidate.merge_score.toFixed(2)} · 状态 {candidate.status}</div>
                          </div>
                          <Button type="button" onClick={() => approveMerge(candidate)} disabled={submitting}><GitMerge size={16} />合并</Button>
                        </div>
                      </div>
                    ))}
                  </div>
                ) : <div className="rounded-md border border-border bg-white p-3 text-sm text-slate-500">当前没有合并候选。</div>}
              </div>

              <div className="space-y-2">
                <div className="text-sm font-semibold">审核历史</div>
                {actions.length > 0 ? (
                  <div className="space-y-3">
                    {actions.map((action) => (
                      <div key={action.id} className="rounded-md border border-border bg-white p-3 text-sm">
                        <div className="flex items-center justify-between gap-3">
                          <div className="font-medium">{ACTION_LABELS[action.action] ?? action.action}</div>
                          <div className="text-xs text-slate-400">{new Date(action.created_at).toLocaleString()}</div>
                        </div>
                        <div className="mt-1 text-slate-600">执行人：{action.actor}</div>
                        <div className="mt-1 text-slate-600">备注：{action.reason || "-"}</div>
                      </div>
                    ))}
                  </div>
                ) : <div className="rounded-md border border-border bg-white p-3 text-sm text-slate-500">当前还没有审核动作。</div>}
              </div>
            </div>
          ) : <div className="text-sm text-slate-500">请选择一条情报查看详细内容。</div>}
        </Card>
      </div>

      <Card>
        <div className="mb-3 font-semibold">全局审核动态</div>
        {globalActions.length > 0 ? (
          <div className="space-y-3">
            {globalActions.map((action) => (
              <div key={action.id} className="flex items-start justify-between gap-4 rounded-md border border-border bg-white p-3 text-sm">
                <div>
                  <div className="font-medium">{ACTION_LABELS[action.action] ?? action.action}</div>
                  <div className="mt-1 text-slate-600">执行人：{action.actor}</div>
                  <div className="mt-1 text-slate-600">备注：{action.reason || "-"}</div>
                </div>
                <div className="text-xs text-slate-400">{new Date(action.created_at).toLocaleString()}</div>
              </div>
            ))}
          </div>
        ) : (
          <div className="text-sm text-slate-500">当前还没有审核动态。</div>
        )}
      </Card>
    </div>
  );
}
