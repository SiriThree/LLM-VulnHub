"use client";

import Link from "next/link";
import { useEffect, useMemo, useState } from "react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { PageHero } from "@/components/page-hero";
import { Pagination } from "@/components/pagination";
import { api, NotificationEvent, NotificationListResponse } from "@/lib/api";

const EVENT_LABELS: Record<string, string> = {
  high_risk_pending_review: "高风险待复核",
  source_failure: "源采集失败",
};

const SEVERITY_STYLES: Record<string, string> = {
  info: "bg-slate-100 text-slate-700",
  warning: "bg-amber-100 text-amber-800",
  高危: "bg-orange-100 text-orange-800",
  严重: "bg-red-100 text-red-800",
};

export default function NotificationsPage() {
  const [items, setItems] = useState<NotificationEvent[]>([]);
  const [eventType, setEventType] = useState("");
  const [status, setStatus] = useState("");
  const [acknowledged, setAcknowledged] = useState("");
  const [busyId, setBusyId] = useState<number | null>(null);
  const [selectedIds, setSelectedIds] = useState<number[]>([]);
  const [page, setPage] = useState(1);
  const [pageSize, setPageSize] = useState(5);
  const [total, setTotal] = useState(0);

  async function load() {
    const query = new URLSearchParams();
    if (eventType) query.set("event_type", eventType);
    if (status) query.set("status", status);
    if (acknowledged) query.set("acknowledged", acknowledged);
    query.set("page", String(page));
    query.set("page_size", String(pageSize));
    const res = await api<NotificationListResponse>(`/notifications?${query}`).catch(() => ({
      items: [],
      total: 0,
      page,
      page_size: pageSize,
    }));
    setItems(res.items);
    setTotal(res.total);
    setSelectedIds((current) => current.filter((id) => res.items.some((item) => item.id === id)));
  }

  useEffect(() => {
    load();
  }, [eventType, status, acknowledged, page, pageSize]);

  const counts = useMemo(
    () => ({
      unread: items.filter((item) => !item.acknowledged).length,
      highRisk: items.filter((item) => item.event_type === "high_risk_pending_review").length,
      sourceFailure: items.filter((item) => item.event_type === "source_failure").length,
    }),
    [items],
  );

  function toggleSelection(id: number) {
    setSelectedIds((current) => (current.includes(id) ? current.filter((item) => item !== id) : [...current, id]));
  }

  async function toggleAcknowledged(item: NotificationEvent) {
    setBusyId(item.id);
    try {
      if (item.acknowledged) {
        await api(`/notifications/${item.id}/unacknowledge`, { method: "POST" });
      } else {
        await api(`/notifications/${item.id}/acknowledge`, {
          method: "POST",
          body: JSON.stringify({ actor: "analyst", note: "Reviewed from notification center." }),
        });
      }
      await load();
    } finally {
      setBusyId(null);
    }
  }

  async function batchAcknowledge() {
    if (selectedIds.length === 0) return;
    setBusyId(-1);
    try {
      await api("/notifications/batch-acknowledge", {
        method: "POST",
        body: JSON.stringify({ task_ids: selectedIds, actor: "analyst", note: "Batch acknowledged from notification center." }),
      });
      setSelectedIds([]);
      await load();
    } finally {
      setBusyId(null);
    }
  }

  return (
    <div className="space-y-5">
      <PageHero
        title="通知中心"
        description="集中查看高风险待复核事件、采集源异常和异步流水线产出的关键通知。"
        eyebrow="事件提醒与确认"
      />

      <div className="grid gap-4 md:grid-cols-4">
        <Card><div className="text-sm text-slate-500">当页记录</div><div className="mt-3 text-4xl font-semibold">{items.length}</div></Card>
        <Card><div className="text-sm text-slate-500">未读通知</div><div className="mt-3 text-4xl font-semibold">{counts.unread}</div></Card>
        <Card><div className="text-sm text-slate-500">高风险待复核</div><div className="mt-3 text-4xl font-semibold">{counts.highRisk}</div></Card>
        <Card><div className="text-sm text-slate-500">源采集失败</div><div className="mt-3 text-4xl font-semibold">{counts.sourceFailure}</div></Card>
      </div>

      <div className="grid gap-3 rounded-lg border border-border bg-white p-4 md:grid-cols-5">
        <select value={eventType} onChange={(event) => { setPage(1); setEventType(event.target.value); }} className="rounded-md border border-border px-3 text-sm">
          <option value="">全部事件</option>
          <option value="high_risk_pending_review">高风险待复核</option>
          <option value="source_failure">源采集失败</option>
        </select>
        <select value={status} onChange={(event) => { setPage(1); setStatus(event.target.value); }} className="rounded-md border border-border px-3 text-sm">
          <option value="">全部任务状态</option>
          <option value="queued">queued</option>
          <option value="running">running</option>
          <option value="success">success</option>
          <option value="failed">failed</option>
        </select>
        <select value={acknowledged} onChange={(event) => { setPage(1); setAcknowledged(event.target.value); }} className="rounded-md border border-border px-3 text-sm">
          <option value="">全部阅读状态</option>
          <option value="false">未读</option>
          <option value="true">已读</option>
        </select>
        <Button type="button" className="border border-border bg-white text-slate-700" onClick={() => load()}>
          刷新
        </Button>
        <Button type="button" onClick={batchAcknowledge} disabled={selectedIds.length === 0 || busyId === -1}>
          批量已读
        </Button>
      </div>

      <div className="text-sm text-slate-500">当前已选择 {selectedIds.length} 条通知</div>

      <div className="space-y-3" style={{ minHeight: `${pageSize * 220}px` }}>
        {items.length > 0 ? (
          items.map((item) => {
            const severityStyle = SEVERITY_STYLES[item.severity] ?? "bg-slate-100 text-slate-700";
            return (
              <Card key={item.id}>
                <div className="flex items-start gap-4">
                  <input className="mt-1" type="checkbox" checked={selectedIds.includes(item.id)} onChange={() => toggleSelection(item.id)} />
                  <div className="flex flex-1 items-start justify-between gap-4">
                    <div className="min-w-0">
                      <div className="flex items-center gap-2">
                        <span className={`rounded px-2 py-1 text-xs font-medium ${severityStyle}`}>{item.severity}</span>
                        <span className="text-xs text-slate-500">{EVENT_LABELS[item.event_type] ?? item.event_type}</span>
                        <span className={`rounded px-2 py-1 text-xs ${item.acknowledged ? "bg-slate-100 text-slate-600" : "bg-blue-100 text-blue-700"}`}>
                          {item.acknowledged ? "已读" : "未读"}
                        </span>
                      </div>
                      <h2 className="mt-3 text-lg font-semibold">{item.title}</h2>
                      <p className="mt-2 text-sm text-slate-600">{item.message}</p>
                      <div className="mt-3 flex flex-wrap gap-x-4 gap-y-2 text-xs text-slate-400">
                        <span>notification #{item.id}</span>
                        <span>task status {item.task_status}</span>
                        <span>queue {item.queue_name ?? "-"}</span>
                        <span>{new Date(item.created_at).toLocaleString()}</span>
                      </div>
                      {item.acknowledged ? (
                        <div className="mt-2 text-xs text-slate-500">
                          已由 {item.acknowledged_by ?? "unknown"} 于 {item.acknowledged_at ? new Date(item.acknowledged_at).toLocaleString() : "-"} 确认
                          {item.acknowledgment_note ? ` · ${item.acknowledgment_note}` : ""}
                        </div>
                      ) : null}
                    </div>
                    <div className="flex flex-col items-end gap-2 text-sm">
                      {item.intel_item_id ? (
                        <Link className="text-primary hover:underline" href={`/intel-pool?selected=${item.intel_item_id}&status=pending_review`}>
                          情报 #{item.intel_item_id}
                        </Link>
                      ) : null}
                      {item.document_id ? <span className="text-slate-500">文档 #{item.document_id}</span> : null}
                      {item.analysis_job_id ? <span className="text-slate-500">分析 #{item.analysis_job_id}</span> : null}
                      {item.source_id ? <Link className="text-primary hover:underline" href="/collectors">源 #{item.source_id}</Link> : null}
                      <Button type="button" disabled={busyId === item.id || busyId === -1} onClick={() => toggleAcknowledged(item)}>
                        {item.acknowledged ? "标记未读" : "确认已读"}
                      </Button>
                    </div>
                  </div>
                </div>
                <div className="mt-4 rounded-md border border-border bg-slate-50 p-3 text-sm">
                  <div className="text-xs text-slate-500">payload</div>
                  <pre className="mt-2 overflow-auto whitespace-pre-wrap break-all text-xs text-slate-700">{JSON.stringify(item.payload, null, 2)}</pre>
                </div>
              </Card>
            );
          })
        ) : (
          <Card><div className="text-sm text-slate-500">当前筛选条件下没有通知事件。</div></Card>
        )}
      </div>
      <Pagination
        className="rounded-lg border border-border bg-white px-4 pb-3 shadow-soft"
        total={total}
        page={page}
        pageSize={pageSize}
        onPageChange={setPage}
        onPageSizeChange={(value) => {
          setPage(1);
          setPageSize(value);
        }}
      />
    </div>
  );
}
