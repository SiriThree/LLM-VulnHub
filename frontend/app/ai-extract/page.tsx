import { AiExtractClient } from "@/components/ai-extract-client";
import { PageHero } from "@/components/page-hero";

export default function AiExtractPage() {
  return (
    <div className="space-y-5">
      <PageHero
        title="漏洞信息提取"
        description="从原文提取漏洞字段，核对后保存到漏洞库。"
      />
      <AiExtractClient />
    </div>
  );
}
