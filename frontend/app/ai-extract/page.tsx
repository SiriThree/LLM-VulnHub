import { AiExtractClient } from "@/components/ai-extract-client";

export default function AiExtractPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">漏洞信息辅助抽取</h1>
        <p className="text-sm text-slate-500">
          从原始材料提取标准字段，经人工修订确认后入库，并可查看离线评测结果。
        </p>
      </div>
      <AiExtractClient />
    </div>
  );
}
