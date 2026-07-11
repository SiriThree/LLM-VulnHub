"use client";

import { useState } from "react";
import { Bot, Save } from "lucide-react";
import { api, Vulnerability } from "@/lib/api";
import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input, Textarea } from "@/components/ui/input";

const sample =
  "某 LLM Agent 应用将外部网页内容直接拼接进系统 Prompt 中，攻击者可以在网页中隐藏恶意指令，诱导模型泄露系统提示词或执行未授权工具调用。";

type ExtractResult = Partial<Vulnerability> & {
  tags?: string[];
  risk_reason?: string;
  similar?: Vulnerability[];
};

export function AiExtractClient() {
  const [raw, setRaw] = useState(sample);
  const [result, setResult] = useState<ExtractResult | null>(null);
  const [loading, setLoading] = useState(false);
  const [message, setMessage] = useState("");

  async function handleExtract() {
    setLoading(true);
    setMessage("");
    try {
      const extracted = await api<ExtractResult>("/ai/extract", {
        method: "POST",
        body: JSON.stringify({ raw_text: raw })
      });
      setResult(extracted);
    } catch (error) {
      setMessage(String(error));
    } finally {
      setLoading(false);
    }
  }

  async function handleSave() {
    if (!result) return;
    const saved = await api<Vulnerability>("/vulnerabilities", {
      method: "POST",
      body: JSON.stringify(result)
    });
    setMessage(`已入库：#${saved.id} ${saved.title}`);
  }

  function updateField(key: string, value: string) {
    setResult((current) => ({
      ...(current ?? {}),
      [key]: key === "score" ? Number(value) : value
    }));
  }

  return (
    <>
      <div className="grid grid-cols-2 gap-4">
        <Card>
          <h2 className="mb-3 font-semibold">原始漏洞文本</h2>
          <Textarea className="min-h-96" value={raw} onChange={(event) => setRaw(event.target.value)} />
          <Button className="mt-3" type="button" onClick={handleExtract} disabled={loading}>
            <Bot size={16} />
            {loading ? "解析中" : "AI 解析"}
          </Button>
        </Card>
        <Card>
          <h2 className="mb-3 font-semibold">抽取结果预览</h2>
          {result ? (
            <div className="space-y-3">
              {["title", "vuln_type", "severity", "score", "affected_component", "description", "attack_method", "impact", "mitigation"].map((key) => (
                <label className="block" key={key}>
                  <span className="mb-1 block text-xs text-slate-500">{key}</span>
                  {["description", "attack_method", "impact", "mitigation"].includes(key) ? (
                    <Textarea value={String((result as Record<string, unknown>)[key] ?? "")} onChange={(event) => updateField(key, event.target.value)} />
                  ) : (
                    <Input value={String((result as Record<string, unknown>)[key] ?? "")} onChange={(event) => updateField(key, event.target.value)} />
                  )}
                </label>
              ))}
              <div className="rounded-md bg-muted p-3 text-sm text-slate-600">{result.risk_reason}</div>
              {result.similar && result.similar.length > 0 ? (
                <div className="text-sm text-slate-600">相似漏洞：{result.similar.map((item) => item.title).join("、")}</div>
              ) : null}
              <Button type="button" onClick={handleSave}>
                <Save size={16} />
                确认入库
              </Button>
            </div>
          ) : (
            <div className="rounded-md bg-muted p-4 text-sm text-slate-500">等待解析结果</div>
          )}
        </Card>
      </div>
      {message ? <div className="rounded-md border border-border bg-white p-3 text-sm">{message}</div> : null}
    </>
  );
}
