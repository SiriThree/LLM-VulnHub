import Link from "next/link";

import { VulnerabilityForm } from "@/components/vulnerability-form";
import { PageHero } from "@/components/page-hero";

export default function NewVulnerabilityPage() {
  return (
    <div className="space-y-5">
      <PageHero
        title="手动新增漏洞"
        description="手动补录或修正标准化漏洞记录。"
        actions={<Link className="text-sm text-slate-200 hover:text-white" href="/vulnerabilities">
          返回漏洞库
        </Link>}
      />
      <VulnerabilityForm mode="create" />
    </div>
  );
}
