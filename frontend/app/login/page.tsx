"use client";

import { FormEvent, useState } from "react";
import { ArrowRight, Eye, KeyRound, LogIn, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, AuthSession } from "@/lib/api";


function readableError(error: unknown): string {
  const message = error instanceof Error ? error.message : String(error);
  try {
    const parsed = JSON.parse(message) as { detail?: string };
    return parsed.detail || "登录失败，请稍后重试。";
  } catch {
    return message || "登录失败，请稍后重试。";
  }
}

export default function LoginPage() {
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState<"account" | "guest" | null>(null);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy("account");
    setMessage("");
    try {
      await api<AuthSession>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
      });
      const requested = new URLSearchParams(window.location.search).get("next") || "/dashboard";
      const destination = requested.startsWith("/") && !requested.startsWith("//") ? requested : "/dashboard";
      window.location.assign(destination);
    } catch (error) {
      setMessage(readableError(error));
      setBusy(null);
    }
  }

  async function enterAsGuest() {
    setBusy("guest");
    setMessage("");
    try {
      await api<AuthSession>("/auth/guest", { method: "POST" });
      window.location.assign("/dashboard");
    } catch (error) {
      setMessage(readableError(error));
      setBusy(null);
    }
  }

  return (
    <div className="fixed inset-0 z-50 overflow-y-auto bg-slate-950 px-4 py-8 sm:px-6">
      <div className="mx-auto grid min-h-full w-full max-w-5xl place-items-center">
        <Card className="grid w-full overflow-hidden border-slate-700 bg-white p-0 shadow-2xl lg:grid-cols-[0.92fr_1.08fr]">
          <section className="flex flex-col justify-between bg-slate-900 p-6 text-white sm:p-8">
            <div>
              <div className="inline-flex rounded-xl bg-white/10 p-3 text-emerald-300">
                <ShieldCheck size={26} />
              </div>
              <div className="mt-6 text-sm font-medium tracking-wide text-emerald-300">LLM-VulnHub</div>
              <h1 className="mt-2 text-3xl font-semibold tracking-tight">漏洞情报管理平台</h1>
              <p className="mt-4 max-w-md text-sm leading-7 text-slate-300">
                登录后可进行采集、审核和漏洞检索；访客可以直接浏览公开内容。
              </p>
            </div>

            <div className="mt-10 rounded-xl border border-white/10 bg-white/5 p-5">
              <div className="flex items-center gap-2 font-medium">
                <Eye size={18} className="text-emerald-300" />
                访客浏览
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-300">
                无需账号，只能查看公开漏洞摘要。攻击复现、来源证据、处置建议和平台操作不会开放。
              </p>
              <Button
                className="mt-4 w-full bg-white text-slate-950 hover:bg-slate-100"
                disabled={busy !== null}
                onClick={enterAsGuest}
                type="button"
              >
                {busy === "guest" ? "正在进入..." : "以访客身份浏览"}
                <ArrowRight size={16} />
              </Button>
            </div>
          </section>

          <section className="p-6 sm:p-8 lg:p-10">
            <div className="mb-7">
              <div className="inline-flex rounded-lg bg-slate-100 p-3 text-slate-700">
                <KeyRound size={22} />
              </div>
              <h2 className="mt-5 text-2xl font-semibold text-slate-950">账号登录</h2>
              <p className="mt-2 text-sm leading-6 text-slate-500">
                适用于 viewer、analyst 和 admin 账号，权限由后端会话确定。
              </p>
            </div>

            <form className="space-y-4" onSubmit={submit}>
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">用户名</span>
                <Input
                  autoComplete="username"
                  maxLength={120}
                  value={username}
                  onChange={(event) => setUsername(event.target.value)}
                />
              </label>
              <label className="block space-y-2">
                <span className="text-sm font-medium text-slate-700">密码</span>
                <Input
                  autoComplete="current-password"
                  maxLength={256}
                  type="password"
                  value={password}
                  onChange={(event) => setPassword(event.target.value)}
                />
              </label>
              <Button className="w-full" disabled={busy !== null || !username.trim() || !password} type="submit">
                <LogIn size={16} /> {busy === "account" ? "正在验证..." : "登录"}
              </Button>
            </form>

            {message ? <div className="mt-4 rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{message}</div> : null}

          </section>
        </Card>
      </div>
    </div>
  );
}
