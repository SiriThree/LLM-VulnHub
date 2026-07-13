"use client";

import { useMemo, useState } from "react";
import { Shield, UserCog } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";

const ROLES = [
  {
    value: "viewer",
    label: "viewer",
    description: "只能查看看板、漏洞详情、运维指标，不能修改数据。",
  },
  {
    value: "analyst",
    label: "analyst",
    description: "可以采集、审核、分析、编辑漏洞，但不能删除关键配置。",
  },
  {
    value: "admin",
    label: "admin",
    description: "拥有全量权限，可管理数据源、删除记录、导出审计信息。",
  },
] as const;

type RoleValue = (typeof ROLES)[number]["value"];

function setCookie(name: string, value: string) {
  document.cookie = `${name}=${encodeURIComponent(value)}; path=/; max-age=2592000; samesite=lax`;
}

function clearCookie(name: string) {
  document.cookie = `${name}=; path=/; expires=Thu, 01 Jan 1970 00:00:00 GMT; samesite=lax`;
}

export function RoleSimulator() {
  const [actor, setActor] = useState("demo-analyst");
  const [role, setRole] = useState<RoleValue>("analyst");
  const [saved, setSaved] = useState("");

  const currentRole = useMemo(() => ROLES.find((item) => item.value === role) ?? ROLES[1], [role]);

  const applyContext = () => {
    const actorValue = actor.trim() || "demo-analyst";
    setCookie("llm_vulnhub_actor", actorValue);
    setCookie("llm_vulnhub_role", role);
    setSaved(`已切换为 ${role} / ${actorValue}，刷新后所有页面都会按该角色访问后端。`);
    window.location.reload();
  };

  const resetContext = () => {
    clearCookie("llm_vulnhub_actor");
    clearCookie("llm_vulnhub_role");
    setSaved("已恢复为后端默认身份。");
    window.location.reload();
  };

  return (
    <Card className="space-y-4">
      <div className="flex items-start gap-3">
        <div className="rounded-md bg-muted p-2 text-primary">
          <Shield size={18} />
        </div>
        <div>
          <h2 className="font-semibold">角色模拟器</h2>
          <p className="text-sm text-slate-500">用于演示 RBAC。前端会把当前角色写入 cookie，并在服务端和客户端请求中自动附带 `X-Actor` / `X-Role`。</p>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-[1.2fr_1fr]">
        <div className="space-y-3">
          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">操作者</span>
            <Input value={actor} onChange={(event) => setActor(event.target.value)} placeholder="例如 sec-analyst-li" />
          </label>

          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">角色</span>
            <select
              value={role}
              onChange={(event) => setRole(event.target.value as RoleValue)}
              className="h-10 w-full rounded-md border border-border bg-white px-3 text-sm outline-none focus:border-primary"
            >
              {ROLES.map((item) => (
                <option key={item.value} value={item.value}>
                  {item.label}
                </option>
              ))}
            </select>
          </label>

          <div className="flex flex-wrap gap-3">
            <Button type="button" onClick={applyContext}>
              <UserCog size={16} />
              应用角色
            </Button>
            <Button type="button" className="border border-border bg-white text-slate-700" onClick={resetContext}>
              恢复默认
            </Button>
          </div>

          {saved ? <div className="rounded-md bg-muted px-3 py-2 text-sm text-slate-600">{saved}</div> : null}
        </div>

        <div className="rounded-lg border border-border bg-slate-50 p-4 text-sm text-slate-600">
          <div className="font-medium text-slate-900">当前选中</div>
          <div className="mt-2">角色：{currentRole.label}</div>
          <div className="mt-1">说明：{currentRole.description}</div>
          <div className="mt-3 leading-6">
            建议演示顺序：
            <br />
            1. 用 `viewer` 进入通知中心或采集页面尝试写操作。
            <br />
            2. 观察接口返回 403。
            <br />
            3. 切到 `analyst` 或 `admin` 后重新执行，确认权限放开。
          </div>
        </div>
      </div>
    </Card>
  );
}
