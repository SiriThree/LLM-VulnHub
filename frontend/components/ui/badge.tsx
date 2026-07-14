import { HTMLAttributes } from "react";

import { formatReviewStatus, formatSeverity, severityTone } from "@/lib/presentation";
import { cn } from "@/lib/utils";

export function Badge({ className, children, ...props }: HTMLAttributes<HTMLSpanElement>) {
  const raw = String(children ?? "");
  const looksLikeSeverity =
    raw.includes("危") || ["critical", "high", "medium", "low", "严重", "高危", "中危", "低危"].includes(raw.toLowerCase());
  const text = looksLikeSeverity ? formatSeverity(raw) : formatReviewStatus(raw);
  const color =
    text === "已发布"
      ? "bg-emerald-600 text-white"
      : text === "待人工复核"
        ? "bg-amber-500 text-white"
        : text === "已驳回"
          ? "bg-rose-600 text-white"
          : text === "已入库"
            ? "bg-sky-600 text-white"
            : looksLikeSeverity
              ? severityTone(raw)
              : "bg-slate-100 text-slate-700";

  return (
    <span className={cn("inline-flex items-center rounded px-2 py-1 text-xs font-medium", color, className)} {...props}>
      {text}
    </span>
  );
}
