"use client";

import { FormEvent, useState } from "react";
import { LockKeyhole, LogIn } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, AuthSession } from "@/lib/api";


export default function LoginPage() {
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  async function submit(event: FormEvent) {
    event.preventDefault();
    setBusy(true);
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
      setMessage(String(error));
      setBusy(false);
    }
  }

  return (
    <div className="fixed inset-0 z-50 grid place-items-center bg-slate-950 px-4">
      <Card className="w-full max-w-md space-y-5 border-slate-700 bg-white p-6 shadow-2xl">
        <div>
          <div className="mb-4 inline-flex rounded-lg bg-slate-900 p-3 text-white">
            <LockKeyhole size={22} />
          </div>
          <h1 className="text-2xl font-semibold text-slate-950">登录 LLM-VulnHub</h1>
          <p className="mt-2 text-sm leading-6 text-slate-500">使用由部署环境配置的 viewer、analyst 或 admin 账户。</p>
        </div>

        <form className="space-y-4" onSubmit={submit}>
          <label className="block space-y-2">
            <span className="text-sm font-medium text-slate-700">用户名</span>
            <Input autoComplete="username" maxLength={120} value={username} onChange={(event) => setUsername(event.target.value)} />
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
          <Button className="w-full" disabled={busy || !username.trim() || !password} type="submit">
            <LogIn size={16} /> {busy ? "验证中..." : "登录"}
          </Button>
        </form>

        {message ? <div className="rounded-md bg-rose-50 px-3 py-2 text-sm text-rose-700">{message}</div> : null}
        <p className="text-xs leading-5 text-slate-500">会话 Cookie 不可由 JavaScript 读取；写操作同时校验 CSRF Token。</p>
      </Card>
    </div>
  );
}
