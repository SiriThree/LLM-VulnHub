"use client";

import { useEffect, useState } from "react";
import { LogIn, LogOut, ShieldCheck } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { api, AuthSession } from "@/lib/api";


export function RoleSimulator() {
  const [session, setSession] = useState<AuthSession | null>(null);
  const [username, setUsername] = useState("analyst");
  const [password, setPassword] = useState("");
  const [message, setMessage] = useState("");
  const [busy, setBusy] = useState(false);

  useEffect(() => {
    void api<AuthSession>("/auth/status").then(setSession).catch(() => setSession({ authenticated: false }));
  }, []);

  async function login() {
    setBusy(true);
    setMessage("");
    try {
      const current = await api<AuthSession>("/auth/login", {
        method: "POST",
        body: JSON.stringify({ username: username.trim(), password }),
      });
      setSession(current);
      setPassword("");
      setMessage("登录成功，会话由服务端保存，角色不能在浏览器中修改。");
      window.location.reload();
    } catch (error) {
      setMessage(String(error));
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    setBusy(true);
    try {
      await api("/auth/logout", { method: "POST" });
      window.location.assign("/login");
    } catch (error) {
      setMessage(String(error));
      setBusy(false);
    }
  }

  return (
    <Card className="space-y-4">
      <div className="flex items-start gap-3">
        <div className="rounded-md bg-emerald-100 p-2 text-emerald-700">
          <ShieldCheck size={18} />
        </div>
        <div>
          <h2 className="font-semibold">登录会话</h2>
          <p className="text-sm text-slate-500">身份和角色由后端校验，浏览器只保存 HttpOnly 随机会话 Cookie。</p>
        </div>
      </div>

      {session?.authenticated ? (
        <div className="flex flex-col gap-3 rounded-lg border border-emerald-200 bg-emerald-50 p-4 sm:flex-row sm:items-center sm:justify-between">
          <div>
            <div className="font-medium text-emerald-950">{session.actor}</div>
            <div className="mt-1 text-sm text-emerald-800">当前角色：{session.role}</div>
          </div>
          <Button type="button" className="bg-slate-800" disabled={busy} onClick={logout}>
            <LogOut size={16} /> 退出登录
          </Button>
        </div>
      ) : (
        <div className="grid gap-3 md:grid-cols-[1fr_1fr_auto]">
          <Input maxLength={120} value={username} onChange={(event) => setUsername(event.target.value)} placeholder="用户名" />
          <Input maxLength={256} type="password" value={password} onChange={(event) => setPassword(event.target.value)} placeholder="密码" />
          <Button type="button" disabled={busy || !username.trim() || !password} onClick={login}>
            <LogIn size={16} /> 登录
          </Button>
        </div>
      )}

      {message ? <div className="rounded-md bg-muted px-3 py-2 text-sm text-slate-600">{message}</div> : null}
      <p className="text-xs leading-5 text-slate-500">
        账户密码通过环境变量配置；连续失败会触发限速，写操作还需要与会话绑定的 CSRF Token。
      </p>
    </Card>
  );
}
