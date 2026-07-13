import Link from "next/link";

import { VulnerabilityForm } from "@/components/vulnerability-form";

export default function NewVulnerabilityPage() {
  return (
    <div className="space-y-5">
      <div>
        <Link className="text-sm text-primary" href="/vulnerabilities">
          返回漏洞库
        </Link>
        <h1 className="mt-2 text-2xl font-semibold">手动新增漏洞</h1>
        <p className="text-sm text-slate-500">手动录入一条标准化漏洞记录，用于补录、纠错或演示。</p>
      </div>
      <VulnerabilityForm mode="create" />
    </div>
  );
}
