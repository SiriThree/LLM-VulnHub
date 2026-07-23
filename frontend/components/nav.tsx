"use client";

import { useEffect, useState } from "react";
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
  LogIn,
  MessageSquare,
  Radar,
  Settings,
  ShieldCheck,
  ShieldEllipsis,
} from "lucide-react";

import { api, AuthSession } from "@/lib/api";
import { cn } from "@/lib/utils";

type Role = NonNullable<AuthSession["role"]>;

const roleRank: Record<Role, number> = {
  guest: 0,
  viewer: 1,
  analyst: 2,
  admin: 3,
};

const groups = [
  {
    title: "总览",
    items: [
      { href: "/dashboard", label: "平台看板", icon: BarChart3, minRole: "guest" as Role },
      { href: "/ops", label: "运行运营", icon: LineChart, minRole: "viewer" as Role },
      { href: "/notifications", label: "通知中心", icon: Bell, minRole: "analyst" as Role },
    ],
  },
  {
    title: "情报流程",
    items: [
      { href: "/collectors", label: "动态采集", icon: Radar, minRole: "analyst" as Role },
      { href: "/intel-pool", label: "情报池", icon: Inbox, minRole: "analyst" as Role },
      { href: "/tasks", label: "任务中心", icon: ListChecks, minRole: "analyst" as Role },
    ],
  },
  {
    title: "漏洞资产",
    items: [
      { href: "/vulnerabilities", label: "公开漏洞", icon: Database, minRole: "guest" as Role },
      { href: "/vulnerabilities/new", label: "手动新增", icon: FilePlus2, minRole: "analyst" as Role },
      { href: "/ai-extract", label: "辅助抽取", icon: Bot, minRole: "analyst" as Role },
      { href: "/rag-chat", label: "知识检索", icon: MessageSquare, minRole: "viewer" as Role },
    ],
  },
  {
    title: "系统",
    items: [
      { href: "/security-model", label: "安全设计", icon: ShieldEllipsis, minRole: "viewer" as Role },
      { href: "/settings", label: "设置", icon: Settings, minRole: "viewer" as Role },
      { href: "http://localhost:8000/docs", label: "OpenAPI", icon: FileSearch, minRole: "admin" as Role },
    ],
  },
];

export function Nav() {
  const pathname = usePathname();
  const [session, setSession] = useState<AuthSession | null>(null);

  useEffect(() => {
    void api<AuthSession>("/auth/status")
      .then(setSession)
      .catch(() => setSession({ authenticated: false }));
  }, [pathname]);

  const role = session?.authenticated ? (session.role ?? "guest") : "guest";

  return (
    <>
      <header className="fixed inset-x-0 top-0 z-40 flex h-16 items-center justify-between border-b border-border bg-white/95 px-4 backdrop-blur lg:hidden">
        <Link className="flex items-center gap-2 font-semibold text-slate-900" href="/dashboard">
          <ShieldCheck className="text-primary" size={20} />
          LLM-VulnHub
          {role === "guest" ? <span className="rounded-full bg-slate-100 px-2 py-0.5 text-[10px] text-slate-500">访客</span> : null}
        </Link>
        <details className="group relative">
          <summary className="cursor-pointer list-none rounded-md border border-border px-3 py-2 text-sm text-slate-700 marker:content-none">
            导航
          </summary>
          <div className="absolute right-0 mt-2 max-h-[calc(100vh-5rem)] w-64 overflow-y-auto rounded-lg border border-border bg-white p-3 shadow-soft">
            <Navigation pathname={pathname} role={role} compact />
          </div>
        </details>
      </header>

      <aside className="fixed inset-y-0 left-0 z-30 hidden w-64 overflow-y-auto border-r border-border bg-white px-4 py-5 shadow-sm lg:block">
        <div className="mb-8 px-2">
          <Link className="flex items-center gap-2 text-lg font-semibold text-slate-900" href="/dashboard">
            <ShieldCheck className="text-primary" size={21} />
            LLM-VulnHub
          </Link>
          <div className="mt-2 text-xs leading-5 text-slate-500">
            {role === "guest" ? "访客模式：仅浏览公开漏洞摘要" : "LLM、RAG 与 Agent 漏洞情报管理平台"}
          </div>
        </div>
        <Navigation pathname={pathname} role={role} />
      </aside>
    </>
  );
}

function Navigation({ pathname, role, compact = false }: { pathname: string; role: Role; compact?: boolean }) {
  const visibleGroups = groups
    .map((group) => ({
      ...group,
      items: group.items.filter((item) => roleRank[role] >= roleRank[item.minRole]),
    }))
    .filter((group) => group.items.length > 0);

  return (
    <nav className={compact ? "space-y-4" : "space-y-6"}>
      {visibleGroups.map((group) => (
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

      {role === "guest" ? (
        <div className="rounded-lg border border-emerald-200 bg-emerald-50 p-3">
          <div className="text-xs leading-5 text-emerald-900">登录账号后可使用知识检索和工作流功能。</div>
          <Link className="mt-2 flex items-center gap-2 text-sm font-medium text-emerald-800 hover:underline" href="/login">
            <LogIn size={15} />
            账号登录
          </Link>
        </div>
      ) : null}
    </nav>
  );
}
