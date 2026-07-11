"use client";

import { useState } from "react";
import Link from "next/link";
import { Send } from "lucide-react";
import { api, Vulnerability } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Textarea } from "@/components/ui/input";
import { Badge } from "@/components/ui/badge";

type Hit = { vulnerability: Vulnerability; similarity: number; chunk_text: string };

export default function RagChatPage() {
  const [question, setQuestion] = useState("Prompt Injection 漏洞如何防护？");
  const [answer, setAnswer] = useState("");
  const [refs, setRefs] = useState<Hit[]>([]);
  const [loading, setLoading] = useState(false);

  async function ask() {
    setLoading(true);
    try {
      const res = await api<{ answer: string; references: Hit[] }>("/rag/ask", { method: "POST", body: JSON.stringify({ question, top_k: 5 }) });
      setAnswer(res.answer);
      setRefs(res.references);
    } finally { setLoading(false); }
  }

  return (
    <div className="space-y-5">
      <div><h1 className="text-2xl font-semibold">RAG 智能问答</h1><p className="text-sm text-slate-500">基于漏洞库召回记录，再生成带引用的回答。</p></div>
      <div className="grid grid-cols-[1fr_360px] gap-4">
        <div className="space-y-4">
          <Card><Textarea value={question} onChange={(e) => setQuestion(e.target.value)} /><Button className="mt-3" onClick={ask} disabled={loading}><Send size={16} />{loading ? "生成中" : "提问"}</Button></Card>
          <Card><h2 className="mb-3 font-semibold">AI 回答</h2><div className="min-h-48 whitespace-pre-wrap text-sm leading-7 text-slate-700">{answer || "等待问题..."}</div></Card>
        </div>
        <Card><h2 className="mb-3 font-semibold">召回漏洞</h2><div className="space-y-3">{refs.map((h) => <Link href={`/vulnerabilities/${h.vulnerability.id}`} key={h.vulnerability.id} className="block rounded-md border border-border p-3 hover:bg-muted"><div className="mb-2 flex items-center justify-between"><span className="text-sm font-medium">{h.vulnerability.title}</span><Badge>{h.vulnerability.severity}</Badge></div><div className="text-xs text-slate-500">相似度 {Math.round(h.similarity * 100)}%</div></Link>)}</div></Card>
      </div>
    </div>
  );
}
