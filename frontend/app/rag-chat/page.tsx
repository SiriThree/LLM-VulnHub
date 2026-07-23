"use client";

import Link from "next/link";
import { FormEvent, KeyboardEvent, useMemo, useState } from "react";
import {
  AlertCircle,
  ArrowUpRight,
  BookOpen,
  Check,
  Copy,
  Database,
  Search,
  Send,
  ShieldCheck,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { api, Vulnerability } from "@/lib/api";
import { useSessionDraft } from "@/lib/use-session-draft";

type Hit = { vulnerability: Vulnerability; similarity: number; chunk_text: string };
type RagResponse = { answer: string; references: Hit[] };

const EXAMPLE_QUESTIONS = [
  "RAG 数据泄露通常有哪些缓解措施？",
  "Prompt Injection 漏洞应该如何防护？",
  "哪些漏洞会影响 Agent 或工具调用链路？",
];

export default function RagChatPage() {
  const [question, setQuestion] = useSessionDraft("llm-vulnhub:rag-question-draft:v1", EXAMPLE_QUESTIONS[0]);
  const [answer, setAnswer] = useSessionDraft("llm-vulnhub:rag-answer-draft:v1", "");
  const [refs, setRefs] = useSessionDraft<Hit[]>("llm-vulnhub:rag-references-draft:v1", []);
  const [topK, setTopK] = useSessionDraft("llm-vulnhub:rag-top-k-draft:v1", 5);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState("");
  const [copied, setCopied] = useState(false);

  const uniqueRefs = useMemo(
    () => refs.filter((hit, index, list) => list.findIndex((item) => item.vulnerability.id === hit.vulnerability.id) === index),
    [refs],
  );
  const topSimilarity = refs.length ? Math.round(Math.max(...refs.map((hit) => hit.similarity)) * 100) : 0;

  async function ask(event?: FormEvent) {
    event?.preventDefault();
    const normalizedQuestion = question.trim();
    if (normalizedQuestion.length < 2 || loading) {
      if (normalizedQuestion.length < 2) setError("请输入至少 2 个字符的问题。");
      return;
    }

    setLoading(true);
    setError("");
    setCopied(false);
    try {
      const result = await api<RagResponse>("/rag/ask", {
        method: "POST",
        body: JSON.stringify({ question: normalizedQuestion, top_k: topK }),
      });
      setAnswer(result.answer);
      setRefs(result.references);
    } catch (requestError) {
      setError(requestError instanceof Error ? requestError.message : "问答服务暂时不可用，请稍后重试。");
    } finally {
      setLoading(false);
    }
  }

  function handleKeyDown(event: KeyboardEvent<HTMLTextAreaElement>) {
    if ((event.ctrlKey || event.metaKey) && event.key === "Enter") {
      event.preventDefault();
      void ask();
    }
  }

  async function copyAnswer() {
    if (!answer) return;
    await navigator.clipboard.writeText(answer);
    setCopied(true);
    window.setTimeout(() => setCopied(false), 1600);
  }

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950 px-5 py-6 text-white shadow-soft sm:px-6 sm:py-7">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs text-slate-200">
              <ShieldCheck size={14} /> 回答范围限定于已入库漏洞
            </div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">漏洞知识检索</h1>
            <p className="mt-2 text-sm leading-6 text-slate-300">从漏洞库检索相关证据，整理回答并保留可核验的记录来源。</p>
          </div>
          <div className="flex gap-6 text-sm">
            <div>
              <div className="text-2xl font-semibold">{refs.length || "-"}</div>
              <div className="mt-1 text-xs text-slate-400">召回片段</div>
            </div>
            <div>
              <div className="text-2xl font-semibold">{topSimilarity ? `${topSimilarity}%` : "-"}</div>
              <div className="mt-1 text-xs text-slate-400">最高相关度</div>
            </div>
          </div>
        </div>
      </section>

      <div className="grid grid-cols-1 gap-5 xl:grid-cols-[minmax(0,1fr)_380px]">
        <div className="min-w-0 space-y-5">
          <Card className="p-5">
            <form onSubmit={ask}>
              <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                <label className="flex items-center gap-2 text-sm font-semibold text-slate-900" htmlFor="rag-question">
                  <Search size={16} className="text-slate-500" /> 输入安全问题
                </label>
                <span className="text-xs text-slate-400">Ctrl / Command + Enter 快速提交</span>
              </div>
              <Textarea
                className="min-h-28 resize-y border-slate-200 bg-slate-50 text-[15px] leading-6 focus:bg-white"
                id="rag-question"
                maxLength={1000}
                onChange={(event) => {
                  setQuestion(event.target.value);
                  if (error) setError("");
                }}
                onKeyDown={handleKeyDown}
                placeholder="例如：RAG 系统应如何防止跨租户数据泄露？"
                value={question}
              />
              <div className="mt-3 flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                <div className="flex items-center gap-2 text-sm text-slate-500">
                  <label htmlFor="top-k">召回数量</label>
                  <select
                    className="h-9 rounded-md border border-border bg-white px-2 text-sm text-slate-700 outline-none focus:border-primary"
                    id="top-k"
                    onChange={(event) => setTopK(Number(event.target.value))}
                    value={topK}
                  >
                    {[3, 5, 8, 10].map((value) => (
                      <option key={value} value={value}>
                        {value} 条
                      </option>
                    ))}
                  </select>
                </div>
                <Button className="h-10 px-5" disabled={loading || question.trim().length < 2} type="submit">
                  {loading ? <span className="h-4 w-4 animate-spin rounded-full border-2 border-white/40 border-t-white" /> : <Send size={16} />}
                  {loading ? "正在检索与整理" : "检索并回答"}
                </Button>
              </div>
            </form>

            <div className="mt-5 border-t border-slate-100 pt-4">
              <div className="mb-2 text-xs font-medium text-slate-400">试试这些问题</div>
              <div className="flex flex-wrap gap-2">
                {EXAMPLE_QUESTIONS.map((example) => (
                  <button
                    className="rounded-full border border-slate-200 bg-white px-3 py-1.5 text-left text-xs text-slate-600 transition hover:border-slate-300 hover:bg-slate-50 hover:text-slate-900"
                    key={example}
                    onClick={() => {
                      setQuestion(example);
                      setError("");
                    }}
                    type="button"
                  >
                    {example}
                  </button>
                ))}
              </div>
            </div>
          </Card>

          {error ? (
            <div className="flex items-start gap-3 rounded-lg border border-rose-200 bg-rose-50 px-4 py-3 text-sm text-rose-800" role="alert">
              <AlertCircle className="mt-0.5 shrink-0" size={17} />
              <div>
                <div className="font-medium">问答请求失败</div>
                <div className="mt-1 break-words text-rose-700">{error}</div>
              </div>
            </div>
          ) : null}

          <Card className="min-h-72 p-0">
            <div className="flex items-center justify-between border-b border-slate-100 px-5 py-4">
              <div className="flex items-center gap-2">
                <ShieldCheck size={17} className="text-primary" />
                <h2 className="font-semibold">分析结果</h2>
              </div>
              {answer ? (
                <button
                  className="inline-flex items-center gap-1.5 rounded-md px-2 py-1 text-xs text-slate-500 hover:bg-slate-100 hover:text-slate-900"
                  onClick={() => void copyAnswer()}
                  type="button"
                >
                  {copied ? <Check size={14} /> : <Copy size={14} />}
                  {copied ? "已复制" : "复制"}
                </button>
              ) : null}
            </div>
            <div className="p-5">
              {loading ? (
                <div className="space-y-3 py-3" aria-label="正在整理回答">
                  <div className="h-4 w-full animate-pulse rounded bg-slate-100" />
                  <div className="h-4 w-11/12 animate-pulse rounded bg-slate-100" />
                  <div className="h-4 w-4/5 animate-pulse rounded bg-slate-100" />
                  <div className="mt-6 h-4 w-10/12 animate-pulse rounded bg-slate-100" />
                </div>
              ) : answer ? (
                <div className="whitespace-pre-wrap text-[15px] leading-7 text-slate-700">{answer}</div>
              ) : (
                <div className="flex min-h-48 flex-col items-center justify-center text-center">
                  <div className="mb-3 rounded-full bg-slate-100 p-3 text-slate-400">
                    <BookOpen size={22} />
                  </div>
                  <div className="text-sm font-medium text-slate-700">等待检索</div>
                  <p className="mt-1 max-w-sm text-xs leading-5 text-slate-400">提交问题后，这里会显示整理后的结论；参考记录会列在右侧。</p>
                </div>
              )}
            </div>
          </Card>
        </div>

        <aside className="min-w-0">
          <Card className="p-0 xl:sticky xl:top-6">
            <div className="border-b border-slate-100 px-4 py-4">
              <div className="flex items-center justify-between">
                <div className="flex items-center gap-2">
                  <Database size={17} className="text-slate-500" />
                  <h2 className="font-semibold">参考漏洞</h2>
                </div>
                {uniqueRefs.length > 0 ? <span className="rounded-full bg-slate-100 px-2 py-1 text-xs text-slate-500">{uniqueRefs.length} 条记录</span> : null}
              </div>
              <p className="mt-1 text-xs text-slate-400">按综合相关性从高到低排列</p>
            </div>
            <div className="max-h-[calc(100vh-12rem)] space-y-3 overflow-y-auto p-3">
              {loading ? (
                [0, 1, 2].map((item) => (
                  <div className="rounded-lg border border-slate-100 p-3" key={item}>
                    <div className="h-4 w-4/5 animate-pulse rounded bg-slate-100" />
                    <div className="mt-3 h-3 w-full animate-pulse rounded bg-slate-100" />
                    <div className="mt-2 h-2 w-full animate-pulse rounded bg-slate-100" />
                  </div>
                ))
              ) : uniqueRefs.length ? (
                uniqueRefs.map((hit, index) => {
                  const similarity = Math.round(hit.similarity * 100);
                  return (
                    <Link
                      className="group block rounded-lg border border-slate-200 bg-white p-3 transition hover:border-slate-300 hover:bg-slate-50"
                      href={`/vulnerabilities/${hit.vulnerability.id}`}
                      key={hit.vulnerability.id}
                    >
                      <div className="mb-2 flex items-start gap-2">
                        <span className="flex h-5 w-5 shrink-0 items-center justify-center rounded bg-slate-900 text-[10px] font-semibold text-white">{index + 1}</span>
                        <div className="min-w-0 flex-1 text-sm font-medium leading-5 text-slate-800">{hit.vulnerability.title}</div>
                        <ArrowUpRight className="shrink-0 text-slate-300 transition group-hover:text-slate-600" size={15} />
                      </div>
                      <div className="mb-3 line-clamp-3 text-xs leading-5 text-slate-500">{hit.chunk_text}</div>
                      <div className="flex items-center justify-between gap-3">
                        <Badge>{hit.vulnerability.severity}</Badge>
                        <div className="flex flex-1 items-center justify-end gap-2">
                          <div className="h-1.5 w-16 overflow-hidden rounded-full bg-slate-100">
                            <div className="h-full rounded-full bg-slate-700" style={{ width: `${Math.max(4, similarity)}%` }} />
                          </div>
                          <span className="w-8 text-right text-[11px] font-medium text-slate-500">{similarity}%</span>
                        </div>
                      </div>
                    </Link>
                  );
                })
              ) : (
                <div className="flex min-h-52 flex-col items-center justify-center px-5 text-center">
                  <Search size={22} className="text-slate-300" />
                  <div className="mt-3 text-sm font-medium text-slate-600">暂无召回记录</div>
                  <p className="mt-1 text-xs leading-5 text-slate-400">提交问题后，相关漏洞与证据片段会显示在这里。</p>
                </div>
              )}
            </div>
          </Card>
        </aside>
      </div>
    </div>
  );
}
