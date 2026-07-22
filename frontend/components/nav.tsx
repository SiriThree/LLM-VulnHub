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
  ShieldCheck,
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
      { href: "/ai-extract", label: "辅助抽取", icon: Bot },
      { href: "/rag-chat", label: "知识检索", icon: MessageSquare },
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
    <>
      <header className="fixed inset-x-0 top-0 z-40 flex h-16 items-center justify-between border-b border-border bg-white/95 px-4 backdrop-blur lg:hidden">
        <Link className="flex items-center gap-2 font-semibold text-slate-900" href="/dashboard">
          <ShieldCheck className="text-primary" size={20} />
          LLM-VulnHub
        </Link>
        <details className="group relative">
          <summary className="cursor-pointer list-none rounded-md border border-border px-3 py-2 text-sm text-slate-700 marker:content-none">
            导航
          </summary>
          <div className="absolute right-0 mt-2 max-h-[calc(100vh-5rem)] w-64 overflow-y-auto rounded-lg border border-border bg-white p-3 shadow-soft">
            <Navigation pathname={pathname} compact />
          </div>
        </details>
      </header>

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 overflow-y-auto border-r border-border bg-white px-4 py-5 shadow-sm lg:block">
      <div className="mb-8 px-2">
        <Link className="flex items-center gap-2 text-lg font-semibold text-slate-900" href="/dashboard">
          <ShieldCheck className="text-primary" size={21} />
          LLM-VulnHub
        </Link>
        <div className="mt-2 text-xs leading-5 text-slate-500">LLM、RAG 与 Agent 漏洞情报采集和研判平台</div>
      </div>
      <Navigation pathname={pathname} />
      </aside>
    </>
  );
}

function Navigation({ pathname, compact = false }: { pathname: string; compact?: boolean }) {
  return (
      <nav className={compact ? "space-y-4" : "space-y-6"}>
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
  );
}
