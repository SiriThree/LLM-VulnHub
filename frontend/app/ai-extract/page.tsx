import { AiExtractClient } from "@/components/ai-extract-client";

export default function AiExtractPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">AI 结构化抽取</h1>
        <p className="text-sm text-slate-500">
          输入原始漏洞文本，查看 AI 多阶段抽取、人工修订确认入库，以及离线评测质量。
        </p>
      </div>
      <AiExtractClient />
    </div>
  );
}
