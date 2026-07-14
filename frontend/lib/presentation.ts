export function formatSeverity(value: string | null | undefined): string {
  const key = String(value ?? "").trim().toLowerCase();
  if (!key) return "未分级";
  if (["critical", "严重", "严重漏洞"].includes(key)) return "严重";
  if (["high", "高危"].includes(key)) return "高危";
  if (["medium", "中危"].includes(key)) return "中危";
  if (["low", "低危"].includes(key)) return "低危";
  return String(value);
}

export function severityTone(value: string | null | undefined): string {
  const label = formatSeverity(value);
  if (label === "严重") return "bg-rose-600 text-white";
  if (label === "高危") return "bg-amber-500 text-white";
  if (label === "中危") return "bg-sky-600 text-white";
  if (label === "低危") return "bg-emerald-600 text-white";
  return "bg-slate-100 text-slate-700";
}

export function formatReviewStatus(value: string | null | undefined): string {
  const key = String(value ?? "").trim().toLowerCase();
  const map: Record<string, string> = {
    pending_review: "待人工复核",
    approved: "已发布",
    rejected: "已驳回",
    triaged: "仅完成分流",
    stored: "已入库",
    ignored: "已忽略",
    queued_analysis: "等待 AI 分析",
    processed: "已处理",
    new: "新建",
  };
  return map[key] ?? (value ? String(value) : "未标记");
}

export function formatVulnerabilityStatus(value: string | null | undefined): string {
  const key = String(value ?? "").trim().toLowerCase();
  const map: Record<string, string> = {
    open: "待修复",
    fixed: "已修复",
    ignored: "已忽略",
    pending: "待确认",
  };
  if (map[key]) return map[key];
  return value ? String(value) : "待确认";
}

export function formatSourceType(value: string | null | undefined): string {
  const key = String(value ?? "").trim().toLowerCase();
  const map: Record<string, string> = {
    local_file: "本地样本",
    rss: "RSS / Blog",
    web: "Web 页面",
    github: "GitHub Advisory",
  };
  return map[key] ?? (value ? String(value) : "未知来源");
}

export function formatSourceRuntimeStatus(value: string | null | undefined): string {
  const key = String(value ?? "").trim().toLowerCase();
  const map: Record<string, string> = {
    healthy: "健康",
    due: "待调度",
    never_run: "未采集",
    disabled: "已停用",
  };
  return map[key] ?? (value ? String(value) : "未知");
}
