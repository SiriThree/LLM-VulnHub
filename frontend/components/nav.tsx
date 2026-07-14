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

const groups = [
  {
    title: "总览",
    items: [
      { href: "/dashboard", label: "平台看板", icon: BarChart3 },
      { href: "/ops", label: "运行运营", icon: LineChart },
      { href: "/notifications", label: "通知中心", icon: Bell },
    ],
  },
  {
    title: "情报流程",
    items: [
      { href: "/collectors", label: "动态采集", icon: Radar },
      { href: "/intel-pool", label: "情报池", icon: Inbox },
      { href: "/tasks", label: "任务中心", icon: ListChecks },
    ],
  },
  {
    title: "漏洞资产",
    items: [
      { href: "/vulnerabilities", label: "漏洞库", icon: Database },
      { href: "/vulnerabilities/new", label: "手动新增", icon: FilePlus2 },
      { href: "/ai-extract", label: "AI 抽取", icon: Bot },
      { href: "/rag-chat", label: "RAG 问答", icon: MessageSquare },
    ],
  },
  {
    title: "系统",
    items: [
      { href: "/settings", label: "设置", icon: Settings },
      { href: "http://localhost:8000/docs", label: "OpenAPI", icon: FileSearch },
    ],
  },
];

export function Nav() {
  const pathname = usePathname();

  return (
    <aside className="fixed inset-y-0 left-0 w-64 overflow-y-auto border-r border-border bg-white px-4 py-5 shadow-sm">
      <div className="mb-8 px-2">
        <div className="text-lg font-semibold text-slate-900">LLM-VulnHub</div>
        <div className="mt-1 text-xs leading-5 text-slate-500">AI 大模型漏洞动态采集、分析研判与标准化入库平台</div>
      </div>

      <nav className="space-y-6">
        {groups.map((group) => (
          <div key={group.title}>
            <div className="mb-2 px-2 text-[11px] font-semibold uppercase tracking-[0.08em] text-slate-400">{group.title}</div>
            <div className="space-y-1">
              {group.items.map((item) => {
                const Icon = item.icon;
                const active =
                  item.href === "/dashboard"
                    ? pathname === "/dashboard" || pathname === "/"
                    : item.href.startsWith("http")
                      ? false
                      : pathname.startsWith(item.href);

                return (
                  <Link
                    key={item.href}
                    href={item.href}
                    className={cn(
                      "flex h-10 items-center gap-3 rounded-md px-3 text-sm text-slate-700 transition hover:bg-slate-50",
                      active && "bg-slate-100 font-medium text-slate-900",
                    )}
                  >
                    <Icon size={17} />
                    <span>{item.label}</span>
                  </Link>
                );
              })}
            </div>
          </div>
        ))}
      </nav>
    </aside>
  );
}
