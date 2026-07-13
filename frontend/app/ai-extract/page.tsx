import { AiExtractClient } from "@/components/ai-extract-client";

export default function AiExtractPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">AI 结构化抽取</h1>
        <p className="text-sm text-slate-500">
          输入原始漏洞文本，查看 Triage / Extraction / Merge / Risk / Reviewer 多阶段 AI 分析结果。
        </p>
      </div>
      <AiExtractClient />
    </div>
  );
}
