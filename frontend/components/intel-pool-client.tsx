"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";
import { Check, GitMerge, RefreshCcw, RotateCcw, ShieldCheck, X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHero } from "@/components/page-hero";
import {
  api,
  IntelligenceItem,
  IntelligenceLineage,
  IntelligenceListResponse,
  IntelligenceStats,
  ReviewAction,
  ReviewActionListResponse,
  ReviewStats,
} from "@/lib/api";
import { useSessionDraft } from "@/lib/use-session-draft";

const STATUS_OPTIONS = [
  { value: "reviewable", label: "待审核队列" },
  { value: "", label: "全部" },
  { value: "pending_review", label: "待人工复核" },
  { value: "triaged", label: "仅完成分流" },
  { value: "approved", label: "已发布" },
  { value: "ignored", label: "已过滤噪声" },
  { value: "rejected", label: "人工驳回" },
];

const STATUS_LABELS: Record<string, string> = {
  pending_review: "待人工复核",
  approved: "已发布",
  rejected: "人工驳回",
  triaged: "仅完成分流",
  stored: "已入库",
  ignored: "已过滤噪声",
};

const ACTION_LABELS: Record<string, string> = {
  approve: "通过发布",
  reject: "驳回",
  approve_merge: "合并发布",
  undo_review: "撤销审核",
};

const PUBLISHABLE_STATUSES = new Set(["pending_review", "triaged"]);
const PAGE_SIZE_OPTIONS = [5, 10, 20, 50];

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
  const [status, setStatus] = useState(initialStatus || "reviewable");
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [notes, setNotes] = useState("");
  const [noteDrafts, setNoteDrafts] = useSessionDraft<Record<string, string>>(
    "llm-vulnhub:intelligence-review-note-drafts:v1",
    {},
  );
  const [actions, setActions] = useState<ReviewAction[]>([]);
  const [globalActions, setGlobalActions] = useState<ReviewAction[]>([]);
  const [stats, setStats] = useState<IntelligenceStats | null>(null);
  const [reviewStats, setReviewStats] = useState<ReviewStats | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [lineage, setLineage] = useState<IntelligenceLineage | null>(null);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(10);
  const [total, setTotal] = useState(0);

  async function load(nextSelectedId?: number | null) {
    const query = new URLSearchParams({ page: String(page), page_size: String(pageSize) });
    if (status) query.set("status", status);
    const res = await api<IntelligenceListResponse>(`/intel/items?${query}`).catch(() => ({
      items: [],
      total: 0,
      page,
      page_size: pageSize,
    }));
    setItems(res.items);
    setTotal(res.total);

    const resolvedSelectedId =
      nextSelectedId !== undefined && nextSelectedId !== null && res.items.some((item) => item.id === nextSelectedId)
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

  async function loadLineage(intelItemId: number) {
    const res = await api<IntelligenceLineage>(`/intel/items/${intelItemId}/lineage`).catch(() => null);
    setLineage(res);
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
  }, [status, page, pageSize]);

  useEffect(() => {
    if (selectedId) {
      loadActions(selectedId);
      loadLineage(selectedId);
    } else {
      setActions([]);
      setLineage(null);
    }
  }, [selectedId]);

  const selected = useMemo(() => items.find((item) => item.id === selectedId) ?? null, [items, selectedId]);
  const canApproveSelected = selected ? PUBLISHABLE_STATUSES.has(selected.status) : false;
  const canUndoSelected = selected ? !PUBLISHABLE_STATUSES.has(selected.status) : false;
  const selectedItems = useMemo(() => items.filter((item) => selectedIds.includes(item.id)), [items, selectedIds]);
  const canBatchReview = selectedItems.length > 0 && selectedItems.every((item) => PUBLISHABLE_STATUSES.has(item.status));
  const canBatchUndo = selectedItems.length > 0 && selectedItems.every((item) => !PUBLISHABLE_STATUSES.has(item.status));
  const pageCount = Math.max(1, Math.ceil(total / pageSize));

  useEffect(() => {
    if (!selected) {
      setNotes("");
      return;
    }
    const key = String(selected.id);
    setNotes(Object.prototype.hasOwnProperty.call(noteDrafts, key) ? noteDrafts[key] : selected.review_notes ?? "");
  }, [noteDrafts, selected]);

  function updateNotes(value: string) {
    setNotes(value);
    if (!selected) return;
    setNoteDrafts((current) => ({ ...current, [String(selected.id)]: value }));
  }

  function clearNoteDrafts(itemIds: number[]) {
    setNoteDrafts((current) => {
      const next = { ...current };
      itemIds.forEach((itemId) => delete next[String(itemId)]);
      return next;
    });
  }

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
    if (!selected || !canApproveSelected) return;
    setSubmitting(true);
    setMessage("");
    try {
      const updated = await api<IntelligenceItem>(`/intel/items/${selected.id}/approve`, {
        method: "POST",
        body: JSON.stringify({ actor: "analyst", notes }),
      });
      clearNoteDrafts([selected.id]);
      setMessage(
        updated.vulnerability_id
          ? `情报 #${selected.id} 已发布到漏洞库，并关联漏洞 #${updated.vulnerability_id}。`
          : `情报 #${selected.id} 已完成审核。`,
      );
      setSelectedId(updated.id);
      setPage(1);
      setStatus("approved");
      await refreshSideData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "确认入库失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function reject() {
    if (!selected || !canApproveSelected) return;
    setSubmitting(true);
    setMessage("");
    try {
      const updated = await api<IntelligenceItem>(`/intel/items/${selected.id}/reject`, {
        method: "POST",
        body: JSON.stringify({ actor: "analyst", notes }),
      });
      clearNoteDrafts([selected.id]);
      setMessage(`情报 #${updated.id} 已驳回。`);
      setSelectedId(updated.id);
      setPage(1);
      setStatus("rejected");
      await refreshSideData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "驳回失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function undoReview() {
    if (!selected || !canUndoSelected) return;
    setSubmitting(true);
    setMessage("");
    try {
      const updated = await api<IntelligenceItem>(`/intel/items/${selected.id}/undo`, {
        method: "POST",
        body: JSON.stringify({ notes }),
      });
      clearNoteDrafts([selected.id]);
      setMessage(`情报 #${updated.id} 已撤销原审核结果并恢复为待审核。`);
      setSelectedId(updated.id);
      setPage(1);
      setStatus("reviewable");
      await refreshSideData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "撤销审核失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function runBatch(action: "approve" | "reject" | "undo") {
    if (selectedIds.length === 0) return;
    setSubmitting(true);
    setMessage("");
    try {
      const endpoint =
        action === "approve"
          ? "/intel/items/batch-approve"
          : action === "reject"
            ? "/intel/items/batch-reject"
            : "/intel/items/batch-undo";
      const res = await api<{ items: IntelligenceItem[] }>(endpoint, {
        method: "POST",
        body: JSON.stringify({ actor: "analyst", notes, item_ids: selectedIds }),
      });
      clearNoteDrafts(selectedIds);
      setMessage(
        action === "approve"
          ? `已批量通过 ${res.items.length} 条情报。`
          : action === "reject"
            ? `已批量驳回 ${res.items.length} 条情报。`
            : `已批量撤销 ${res.items.length} 条情报，现可重新审核。`,
      );
      setSelectedIds([]);
      if (action === "undo") {
        setPage(1);
        setStatus("reviewable");
      } else {
        await load();
      }
      await refreshSideData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "批量处理失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function approveMerge(candidateId: number) {
    if (!selected) return;
    setSubmitting(true);
    setMessage("");
    try {
      const updated = await api<{ candidate_vulnerability_id: number }>(`/intel/merge-candidates/${candidateId}/approve`, {
        method: "POST",
        body: JSON.stringify({ actor: "analyst", notes }),
      });
      clearNoteDrafts([selected.id]);
      setMessage(`情报 #${selected.id} 已合并到漏洞 #${updated.candidate_vulnerability_id}。`);
      setSelectedId(selected.id);
      setPage(1);
      setStatus("approved");
      await refreshSideData();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "合并失败。");
    } finally {
      setSubmitting(false);
    }
  }

  return (
    <div className="space-y-5">
      <PageHero
        title="情报池"
        description="采集结果先进入情报池，经过相关性判断、字段抽取、相似记录比对和人工复核后，再发布到正式漏洞库。"
        eyebrow="审核与发布工作流"
        actions={<Button type="button" className="border border-white/20 bg-white/10 text-white hover:bg-white/20" onClick={() => load(selectedId)}>
          <RefreshCcw size={16} />
          刷新
        </Button>}
      />

      {message ? <div className="rounded-md border border-border bg-white p-3 text-sm">{message}</div> : null}

      {stats ? (
        <div className="grid gap-4 md:grid-cols-3 xl:grid-cols-7">
          <Card><div className="text-sm text-slate-500">情报总量</div><div className="mt-3 text-3xl font-semibold">{stats.total}</div></Card>
          <Card><div className="text-sm text-slate-500">待审核队列</div><div className="mt-3 text-3xl font-semibold">{stats.reviewable}</div></Card>
          <Card><div className="text-sm text-slate-500">待人工复核</div><div className="mt-3 text-3xl font-semibold">{stats.pending_review}</div></Card>
          <Card><div className="text-sm text-slate-500">高风险待复核</div><div className="mt-3 text-3xl font-semibold">{stats.high_risk_pending_review}</div></Card>
          <Card><div className="text-sm text-slate-500">待合并候选</div><div className="mt-3 text-3xl font-semibold">{stats.merge_candidates_pending}</div></Card>
          <Card><div className="text-sm text-slate-500">已发布</div><div className="mt-3 text-3xl font-semibold">{stats.approved}</div></Card>
          <Card><div className="text-sm text-slate-500">已过滤噪声</div><div className="mt-3 text-3xl font-semibold">{stats.ignored}</div></Card>
        </div>
      ) : null}

      {reviewStats ? (
        <div className="grid gap-4 md:grid-cols-4 xl:grid-cols-7">
          <Card><div className="text-sm text-slate-500">审核动作总数</div><div className="mt-3 text-3xl font-semibold">{reviewStats.total_actions}</div></Card>
          <Card><div className="text-sm text-slate-500">通过发布</div><div className="mt-3 text-3xl font-semibold">{reviewStats.approvals}</div></Card>
          <Card><div className="text-sm text-slate-500">驳回次数</div><div className="mt-3 text-3xl font-semibold">{reviewStats.rejections}</div></Card>
          <Card><div className="text-sm text-slate-500">合并次数</div><div className="mt-3 text-3xl font-semibold">{reviewStats.merges}</div></Card>
          <Card><div className="text-sm text-slate-500">撤销次数</div><div className="mt-3 text-3xl font-semibold">{reviewStats.undos}</div></Card>
          <Card><div className="text-sm text-slate-500">24h 审核动作</div><div className="mt-3 text-3xl font-semibold">{reviewStats.last_24h_actions}</div></Card>
          <Card><div className="text-sm text-slate-500">参与审核人数</div><div className="mt-3 text-3xl font-semibold">{reviewStats.unique_actors}</div></Card>
        </div>
      ) : null}

      <div className="grid gap-4 xl:grid-cols-[1.2fr_0.8fr]">
        <Card>
          <div className="flex flex-wrap items-center gap-3">
            <span className="text-sm text-slate-500">状态筛选</span>
            <select
              className="h-10 rounded-md border border-border bg-white px-3 text-sm"
              value={status}
              onChange={(event) => {
                setPage(1);
                setStatus(event.target.value);
              }}
            >
              {STATUS_OPTIONS.map((option) => (
                <option key={option.value} value={option.value}>{option.label}</option>
              ))}
            </select>
            <label className="flex items-center gap-2 text-sm text-slate-500">
              每页
              <select
                className="h-10 rounded-md border border-border bg-white px-2 text-sm text-slate-700"
                value={pageSize}
                onChange={(event) => {
                  setPage(1);
                  setPageSize(Number(event.target.value));
                }}
              >
                {PAGE_SIZE_OPTIONS.map((value) => <option key={value} value={value}>{value} 条</option>)}
              </select>
            </label>
            <div className="text-sm text-slate-500">共 {total} 条</div>
            <div className="ml-auto flex shrink-0 items-center gap-2">
              <span className="text-sm text-slate-500">已选择 {selectedIds.length} 条</span>
              <Button
                type="button"
                onClick={() => runBatch("approve")}
                disabled={submitting || !canBatchReview}
              >
                批量确认入库
              </Button>
              <Button type="button" className="bg-accent" onClick={() => runBatch("reject")} disabled={submitting || !canBatchReview}>
                批量驳回
              </Button>
              <Button
                type="button"
                className="border border-border bg-white text-slate-700"
                onClick={() => runBatch("undo")}
                disabled={submitting || !canBatchUndo}
              >
                <RotateCcw size={16} />
                批量撤销
              </Button>
            </div>
          </div>
        </Card>

        <Card>
          <div className="text-sm font-semibold">审核人分布</div>
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
            <div className="mt-3 text-sm text-slate-500">暂时还没有审核动作。</div>
          )}
        </Card>
      </div>

      <div className="grid gap-4 xl:grid-cols-[0.95fr_1.05fr]">
        <Card className="p-0">
          <div className="flex items-center justify-between border-b border-border px-4 py-3">
            <div className="font-semibold">情报列表</div>
            <label className="flex items-center gap-2 text-xs text-slate-500">
              <input type="checkbox" checked={items.length > 0 && selectedIds.length === items.length} onChange={toggleSelectAll} />
              全选
            </label>
          </div>
          <div>
            {items.length > 0 ? items.map((item) => (
              <div
                key={item.id}
                className={`flex items-start gap-3 border-b border-border px-4 py-3 transition last:border-0 ${selectedId === item.id ? "bg-muted" : "bg-white hover:bg-slate-50"}`}
              >
                <input className="mt-1" type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => toggleSelection(item.id)} />
                <button type="button" className="min-w-0 flex-1 text-left" onClick={() => setSelectedId(item.id)}>
                  <div className="flex items-start justify-between gap-3">
                    <div className="min-w-0">
                      <div className="line-clamp-2 font-medium">{item.title}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        分类 {item.triage_category} | 置信度 {Math.round(item.triage_confidence * 100)}%
                      </div>
                    </div>
                    <span className="shrink-0 whitespace-nowrap rounded bg-white px-2 py-1 text-xs">{STATUS_LABELS[item.status] ?? item.status}</span>
                  </div>
                </button>
              </div>
            )) : (
              <div className="p-4 text-sm text-slate-500">
                {status === "reviewable"
                  ? "当前没有待审核情报。若想查看被系统过滤的普通安全公告或噪声条目，请切换到“已过滤噪声”。"
                  : "当前筛选条件下没有情报记录。"}
              </div>
            )}
          </div>
          <div className="flex items-center justify-between border-t border-border px-4 py-3 text-sm">
            <span className="text-slate-500">第 {page} / {pageCount} 页</span>
            <div className="flex gap-2">
              <Button
                type="button"
                className="border border-border bg-white text-slate-700"
                disabled={page <= 1}
                onClick={() => setPage((current) => Math.max(1, current - 1))}
              >
                上一页
              </Button>
              <Button
                type="button"
                className="border border-border bg-white text-slate-700"
                disabled={page >= pageCount}
                onClick={() => setPage((current) => Math.min(pageCount, current + 1))}
              >
                下一页
              </Button>
            </div>
          </div>
        </Card>

        <Card>
          {selected ? (
            <div className="space-y-5">
              <div className="flex items-start justify-between gap-4">
                <div className="min-w-0">
                  <h2 className="text-lg font-semibold">{selected.title}</h2>
                  <div className="mt-1 text-sm text-slate-500">
                    状态 {STATUS_LABELS[selected.status] ?? selected.status} | 分类 {selected.triage_category} | 置信度 {Math.round(selected.triage_confidence * 100)}%
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    intelligence #{selected.id}
                    {selected.vulnerability_id ? (
                      <>
                        {" "} | 已关联
                        <Link className="ml-1 text-primary hover:underline" href={`/vulnerabilities/${selected.vulnerability_id}`}>
                          漏洞 #{selected.vulnerability_id}
                        </Link>
                      </>
                    ) : null}
                  </div>
                </div>
                <div className="flex shrink-0 gap-2">
                  <Button type="button" onClick={approve} disabled={submitting || !canApproveSelected}>
                    <Check size={16} />
                    确认入库
                  </Button>
                  <Button type="button" onClick={reject} disabled={submitting || !canApproveSelected} className="bg-accent">
                    <X size={16} />
                    驳回
                  </Button>
                  <Button
                    type="button"
                    onClick={undoReview}
                    disabled={submitting || !canUndoSelected}
                    className="border border-border bg-white text-slate-700"
                  >
                    <RotateCcw size={16} />
                    撤销
                  </Button>
                </div>
              </div>

              {!canApproveSelected ? (
                <div className="rounded-md border border-border bg-muted/40 p-3 text-sm text-slate-600">
                  该条目当前状态为“{STATUS_LABELS[selected.status] ?? selected.status}”，默认不属于待审核候选，因此不会直接进入漏洞库。
                </div>
              ) : null}

              <div className="grid gap-4 xl:grid-cols-2">
                <div className="space-y-2">
                  <div className="text-sm font-semibold">原始情报</div>
                  <div className="max-h-72 overflow-auto rounded-md border border-border bg-white p-3 text-sm leading-6">{selected.raw_text}</div>
                </div>
                <div className="space-y-2">
                  <div className="text-sm font-semibold">相关性判断</div>
                  <div className="rounded-md border border-border bg-white p-3 text-sm leading-6">
                    <div>判定原因：{selected.triage_reason || "暂无说明"}</div>
                    <div className="mt-2 break-all">来源 URL：{selected.url ?? "-"}</div>
                    <div className="mt-2">归一化文本长度：{selected.normalized_text.length}</div>
                    <div className="mt-2">合并候选数：{lineage?.merge_candidates.length ?? selected.merge_candidates.length}</div>
                  </div>
                </div>
              </div>

              {lineage ? (
                <div className="space-y-3">
                  <div className="flex items-center gap-2 text-sm font-semibold">
                    <ShieldCheck size={16} />
                    来源可信度与血缘链路
                  </div>
                  <div className="grid gap-3 md:grid-cols-3">
                    <div className="rounded-md border border-border bg-white p-3 text-sm">
                      <div className="text-xs text-slate-500">来源</div>
                      <div className="mt-1 font-medium">{lineage.source?.name ?? "未关联来源"}</div>
                      <div className="mt-1 text-slate-600">{lineage.source?.source_type ?? "-"}</div>
                      <div className="mt-2 text-xs text-slate-500">
                        可信度 {lineage.source?.trust_score ?? "-"} | {lineage.source?.trust_level ?? "-"}
                      </div>
                    </div>
                    <div className="rounded-md border border-border bg-white p-3 text-sm">
                      <div className="text-xs text-slate-500">原始文档</div>
                      <div className="mt-1 font-medium">{lineage.collected_document?.title ?? "未关联文档"}</div>
                      <div className="mt-2 text-xs text-slate-500">
                        文档状态 {lineage.collected_document?.status ?? "-"} | AI 相关 {lineage.collected_document?.is_ai_related ? "是" : "否"}
                      </div>
                    </div>
                    <div className="rounded-md border border-border bg-white p-3 text-sm">
                      <div className="text-xs text-slate-500">入库结果</div>
                      {lineage.linked_vulnerability ? (
                        <>
                          <div className="mt-1 font-medium">{lineage.linked_vulnerability.title}</div>
                          <div className="mt-2 text-xs text-slate-500">
                            {lineage.linked_vulnerability.severity} | score {lineage.linked_vulnerability.score}
                          </div>
                        </>
                      ) : (
                        <div className="mt-1 text-slate-600">尚未入库</div>
                      )}
                    </div>
                  </div>
                  <div className="flex flex-wrap gap-2">
                    {(lineage.source?.signals ?? []).map((signal) => (
                      <span key={signal} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                        {signal}
                      </span>
                    ))}
                  </div>
                  <div className="space-y-3">
                    {lineage.trace.map((event) => (
                      <div key={`${event.stage}-${event.timestamp ?? "na"}`} className="rounded-md border border-border bg-white p-3 text-sm">
                        <div className="flex items-center justify-between gap-3">
                          <div className="font-medium">{event.title}</div>
                          <div className="text-xs text-slate-400">{event.timestamp ? new Date(event.timestamp).toLocaleString() : "-"}</div>
                        </div>
                        <div className="mt-1 text-xs text-slate-500">阶段 {event.stage} | 状态 {event.status}</div>
                        <div className="mt-2 text-slate-700">{event.detail}</div>
                      </div>
                    ))}
                  </div>
                </div>
              ) : null}

              <div className="space-y-2">
                <div className="text-sm font-semibold">审核备注</div>
                <textarea
                  className="min-h-24 w-full rounded-md border border-border bg-white p-3 text-sm outline-none"
                  value={notes}
                  onChange={(event) => updateNotes(event.target.value)}
                  placeholder="记录审核判断、合并理由、需要补充的信息。"
                />
              </div>

              <div className="space-y-2">
                <div className="text-sm font-semibold">结构化抽取结果</div>
                <div className="grid gap-3 md:grid-cols-2">
                  {([
                    ["title", selected.extracted_data.title],
                    ["vuln_type", selected.extracted_data.vuln_type],
                    ["severity", selected.extracted_data.severity],
                    ["score", selected.extracted_data.score],
                    ["affected_component", selected.extracted_data.affected_component],
                    ["status", selected.extracted_data.status],
                  ] as Array<[string, unknown]>).map(([label, value]) => (
                    <FieldCard key={label} label={label} value={value} />
                  ))}
                </div>
                {["description", "attack_method", "impact", "mitigation", "risk_reason", "review_summary"].map((key) => (
                  <FieldCard key={key} label={key} value={selected.extracted_data[key]} />
                ))}
              </div>

              <div className="space-y-2">
                <div className="text-sm font-semibold">去重 / 合并建议</div>
                {(lineage?.merge_candidates ?? []).length > 0 ? (
                  <div className="space-y-3">
                    {lineage?.merge_candidates.map((candidate) => (
                      <div key={candidate.id} className="rounded-md border border-border bg-white p-3">
                        <div className="flex items-start justify-between gap-3">
                          <div>
                            <div className="font-medium">
                              候选漏洞 #{candidate.candidate_vulnerability_id} {candidate.candidate_title ? `| ${candidate.candidate_title}` : ""}
                            </div>
                            <div className="mt-1 text-sm text-slate-600">{candidate.merge_reason}</div>
                            <div className="mt-2 flex flex-wrap gap-2">
                              {candidate.match_signals.map((signal) => (
                                <span key={signal} className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-600">
                                  {signal}
                                </span>
                              ))}
                            </div>
                            <div className="mt-2 text-xs text-slate-400">
                              相似度 {candidate.merge_score.toFixed(2)} | 质量 {candidate.quality} | {candidate.review_hint}
                            </div>
                          </div>
                          <Button
                            type="button"
                            onClick={() => approveMerge(candidate.id)}
                            disabled={submitting || !canApproveSelected || candidate.status !== "pending"}
                          >
                            <GitMerge size={16} />
                            {candidate.status === "approved" ? "已合并" : "合并"}
                          </Button>
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
