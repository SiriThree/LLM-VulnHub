import { Suspense } from "react";

import { IntelligencePoolClient } from "@/components/intel-pool-client";

type SearchParams = Promise<Record<string, string | undefined>>;

export default async function IntelligencePoolPage({ searchParams }: { searchParams: SearchParams }) {
  const sp = await searchParams;
  return (
    <Suspense fallback={<div className="text-sm text-slate-500">加载情报池...</div>}>
      <IntelligencePoolClient initialSelected={sp.selected} initialStatus={sp.status} />
    </Suspense>
  );
}
