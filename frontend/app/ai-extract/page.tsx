import { AiExtractClient } from "@/components/ai-extract-client";
import { PageHero } from "@/components/page-hero";

export default function AiExtractPage() {
  return (
    <div className="space-y-5">
      <PageHero
        title="漏洞信息辅助抽取"
        description="从原始材料提取标准字段，经人工修订确认后入库，并可查看离线评测结果。"
        eyebrow="结构化分析"
      />
      <AiExtractClient />
    </div>
  );
}
