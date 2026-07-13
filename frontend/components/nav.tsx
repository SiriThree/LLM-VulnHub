"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import {
  BarChart3,
  Bell,
  Bot,
  Database,
  FilePlus2,
  FileSearch,
  Inbox,
  LineChart,
  ListChecks,
  MessageSquare,
  Radar,
  Settings,
} from "lucide-react";

import { cn } from "@/lib/utils";

const items = [
  { href: "/dashboard", label: "Dashboard", icon: BarChart3 },
  { href: "/intel-pool", label: "情报池", icon: Inbox },
  { href: "/notifications", label: "通知中心", icon: Bell },
  { href: "/vulnerabilities", label: "漏洞库", icon: Database },
  { href: "/vulnerabilities/new", label: "手动新增", icon: FilePlus2 },
  { href: "/ai-extract", label: "AI 抽取", icon: Bot },
  { href: "/collectors", label: "动态采集", icon: Radar },
  { href: "/tasks", label: "任务中心", icon: ListChecks },
  { href: "/ops", label: "Operations", icon: LineChart },
  { href: "/rag-chat", label: "RAG 问答", icon: MessageSquare },
  { href: "/settings", label: "设置", icon: Settings },
  { href: "http://localhost:8000/docs", label: "OpenAPI", icon: FileSearch },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 w-60 overflow-y-auto border-r border-border bg-white px-3 py-4 shadow-sm">
      <div className="mb-6 px-2">
        <div className="text-lg font-semibold text-slate-900">LLM-VulnHub</div>
        <div className="text-xs text-slate-500">AI 大模型漏洞与情报平台</div>
      </div>
      <nav className="space-y-1">
        {items.map((item) => {
          const Icon = item.icon;
          const active =
            item.href === "/dashboard"
              ? pathname === "/dashboard" || pathname === "/"
              : pathname.startsWith(item.href);

          return (
            <Link
              key={item.href}
              href={item.href}
              className={cn(
                "flex h-10 items-center gap-3 rounded-md px-3 text-sm text-slate-700 transition hover:bg-muted",
                active && "bg-muted font-medium text-primary",
              )}
            >
              <Icon size={17} />
              <span>{item.label}</span>
            </Link>
          );
        })}
      </nav>
    </aside>
  );
}
