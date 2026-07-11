import { AiExtractClient } from "@/components/ai-extract-client";

export default function AiExtractPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">AI 结构化抽取</h1>
        <p className="text-sm text-slate-500">粘贴非结构化漏洞文本，确认字段后标准化入库。</p>
      </div>
      <AiExtractClient />
    </div>
  );
}
