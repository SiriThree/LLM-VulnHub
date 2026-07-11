"use client";

import { useEffect, useMemo, useState } from "react";
import { Play, Plus } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, CollectedDocument, DataSource, TaskListResponse, TaskRecord } from "@/lib/api";

type RunResponse = {
  task_id: number;
  status: string;
  current_stage: string;
  queued_at: string;
  message: string;
};

const DOC_STATUS_LABELS: Record<string, string> = {
  ignored: "已忽略",
  pending_review: "待复核",
  stored: "已入库",
};

export default function CollectorsPage() {
  const [sources, setSources] = useState<DataSource[]>([]);
  const [docs, setDocs] = useState<CollectedDocument[]>([]);
  const [tasks, setTasks] = useState<TaskRecord[]>([]);
  const [message, setMessage] = useState("");
  const [submitting, setSubmitting] = useState(false);
  const [form, setForm] = useState({
    name: "本地演示数据源",
    source_type: "local_file",
    url: "../data/sample_sources.json",
    interval_minutes: 5,
  });

  async function load() {
    const [sourceList, documentList, taskList] = await Promise.all([
      api<DataSource[]>("/sources").catch(() => []),
      api<CollectedDocument[]>("/collectors/documents").catch(() => []),
      api<TaskListResponse>("/tasks").catch(() => ({ items: [] })),
    ]);
    setSources(sourceList);
    setDocs(documentList);
    setTasks(taskList.items.filter((task) => task.task_type === "crawl").slice(0, 5));
  }

  useEffect(() => {
    load();
    const timer = window.setInterval(load, 4000);
    return () => window.clearInterval(timer);
  }, []);

  async function createSource() {
    setSubmitting(true);
    setMessage("");
    try {
      await api("/sources", {
        method: "POST",
        body: JSON.stringify({ ...form, enabled: true }),
      });
      setMessage("数据源已添加。");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "添加数据源失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function run(sourceId?: number) {
    setSubmitting(true);
    setMessage("");
    try {
      const res = await api<RunResponse>("/collectors/run", {
        method: "POST",
        body: JSON.stringify({ source_id: sourceId }),
      });
      setMessage(`任务 #${res.task_id} 已进入队列，当前阶段：${res.current_stage}`);
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "采集任务触发失败。");
    } finally {
      setSubmitting(false);
    }
  }

  async function approve(id: number) {
    setSubmitting(true);
    setMessage("");
    try {
      await api(`/collectors/documents/${id}/approve`, { method: "POST" });
      setMessage("文档已确认入库。");
      await load();
    } catch (error) {
      setMessage(error instanceof Error ? error.message : "确认入库失败。");
    } finally {
      setSubmitting(false);
    }
  }

  const activeTasks = useMemo(
    () => tasks.filter((task) => task.status === "queued" || task.status === "running"),
    [tasks],
  );

  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">动态采集中心</h1>
        <p className="text-sm text-slate-500">
          采集任务会进入异步流水线，按源抓取、解析、AI 判断、结构化抽取、去重与入库。
        </p>
      </div>

      {message ? <div className="rounded-md border border-border bg-white p-3 text-sm">{message}</div> : null}

      <div className="grid gap-4 xl:grid-cols-[1.1fr_0.9fr]">
        <Card>
          <h2 className="mb-3 font-semibold">新增数据源</h2>
          <div className="grid gap-3 md:grid-cols-5">
            <Input
              value={form.name}
              onChange={(e) => setForm({ ...form, name: e.target.value })}
              placeholder="数据源名称"
            />
            <select
              className="h-10 rounded-md border border-border bg-background px-3 text-sm"
              value={form.source_type}
              onChange={(e) => setForm({ ...form, source_type: e.target.value })}
            >
              <option value="local_file">local_file</option>
              <option value="rss">rss</option>
              <option value="web">web</option>
              <option value="github">github</option>
            </select>
            <Input
              className="md:col-span-2"
              value={form.url}
              onChange={(e) => setForm({ ...form, url: e.target.value })}
              placeholder="源地址 / 文件路径 / API URL"
            />
            <Button onClick={createSource} disabled={submitting}>
              <Plus size={16} />
              添加
            </Button>
          </div>
        </Card>

        <Card>
          <div className="mb-3 flex items-center justify-between">
            <h2 className="font-semibold">活跃流水线</h2>
            <span className="text-sm text-slate-500">{activeTasks.length} 个任务运行中</span>
          </div>
          <div className="space-y-3">
            {activeTasks.length > 0 ? (
              activeTasks.map((task) => (
                <div key={task.id} className="rounded-md border border-border bg-slate-50 p-3">
                  <div className="flex items-center justify-between">
                    <div className="font-medium">任务 #{task.id}</div>
                    <span className="rounded bg-white px-2 py-1 text-xs">{task.status}</span>
                  </div>
                  <div className="mt-2 text-sm text-slate-600">{task.output_data.last_message}</div>
                  <div className="mt-2 text-xs text-slate-400">
                    当前阶段 {task.output_data.current_stage ?? "queued"} · {task.output_data.source_total ?? 0} 个源
                    {" · "}
                    {task.output_data.execution_mode ?? "pending"}
                    {" · "}
                    第 {task.output_data.attempt_count ?? 0} 次执行
                  </div>
                </div>
              ))
            ) : (
              <div className="rounded-md bg-slate-50 p-3 text-sm text-slate-500">当前没有正在运行的采集任务。</div>
            )}
          </div>
        </Card>
      </div>

      <Card className="p-0">
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted text-left">
              <th className="p-3">名称</th>
              <th>类型</th>
              <th>URL</th>
              <th>周期</th>
              <th>最近采集</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {sources.map((source) => (
              <tr className="border-b border-border last:border-0" key={source.id}>
                <td className="p-3 font-medium">{source.name}</td>
                <td>{source.source_type}</td>
                <td className="max-w-md truncate">{source.url}</td>
                <td>{source.interval_minutes} min</td>
                <td>
                  {source.last_collected_at ? new Date(source.last_collected_at).toLocaleString() : "未采集"}
                </td>
                <td>
                  <Button className="h-8" onClick={() => run(source.id)} disabled={submitting}>
                    <Play size={14} />
                    立即采集
                  </Button>
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>

      <div className="flex items-center gap-3">
        <Button onClick={() => run()} disabled={submitting}>
          <Play size={16} />
          采集全部启用源
        </Button>
        <span className="text-sm text-slate-600">任务会进入异步处理队列，可在任务中心持续观察。</span>
      </div>

      <Card className="p-0">
        <div className="border-b border-border p-4 font-semibold">采集文档与待确认队列</div>
        <table className="w-full text-sm">
          <thead>
            <tr className="border-b border-border bg-muted text-left">
              <th className="p-3">标题</th>
              <th>AI 相关</th>
              <th>置信度</th>
              <th>状态</th>
              <th>漏洞 ID</th>
              <th>操作</th>
            </tr>
          </thead>
          <tbody>
            {docs.map((doc) => (
              <tr className="border-b border-border last:border-0" key={doc.id}>
                <td className="p-3">{doc.title}</td>
                <td>{doc.is_ai_related ? "是" : "否"}</td>
                <td>{Math.round(doc.confidence * 100)}%</td>
                <td>{DOC_STATUS_LABELS[doc.status] ?? doc.status}</td>
                <td>{doc.vulnerability_id ?? "-"}</td>
                <td>
                  {doc.status === "pending_review" ? (
                    <Button className="h-8" onClick={() => approve(doc.id)} disabled={submitting}>
                      确认入库
                    </Button>
                  ) : null}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </Card>
    </div>
  );
}
