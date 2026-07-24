import { PromptEvalPanel } from "@/components/prompt-eval-panel";
import { RoleSimulator } from "@/components/role-simulator";
import { Card } from "@/components/ui/card";
import { PageHero } from "@/components/page-hero";

export default function SettingsPage() {
  return (
    <div className="space-y-5">
      <PageHero
        title="设置"
        description="查看模型接入、运行环境和当前登录会话。"
        eyebrow="系统配置"
      />

      <RoleSimulator />

      <PromptEvalPanel />

      <Card>
        <h2 className="mb-3 font-semibold">环境变量</h2>
        <div className="grid gap-3 text-sm md:grid-cols-2">
          {[
            "LLM_PROVIDER=mock|openai|deepseek",
            "OPENAI_API_KEY=...",
            "DEEPSEEK_API_KEY=...",
            "DATABASE_URL=postgresql+psycopg://...",
            "REDIS_URL=redis://redis:6379/0",
            "NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1",
            "AUTH_ADMIN_PASSWORD=不少于 12 位",
            "AUTH_ANALYST_PASSWORD=不少于 12 位",
            "AUTH_VIEWER_PASSWORD=不少于 12 位",
            "AUTH_COOKIE_SECURE=true（HTTPS）",
          ].map((item) => (
            <code className="rounded-md bg-muted p-3" key={item}>
              {item}
            </code>
          ))}
        </div>
      </Card>

      <Card className="space-y-3">
        <h2 className="font-semibold">功能自检</h2>
        <div className="grid gap-3 text-sm text-slate-600 md:grid-cols-3">
          <div className="rounded-md bg-slate-50 p-3">
            <div className="font-medium text-slate-900">模型抽取</div>
            <div className="mt-1 leading-6">进入信息提取页，输入一段漏洞描述，核对标题、类型、组件、攻击方式和修复建议。</div>
          </div>
          <div className="rounded-md bg-slate-50 p-3">
            <div className="font-medium text-slate-900">权限控制</div>
            <div className="mt-1 leading-6">分别使用 viewer、analyst 和 admin 账户登录，确认服务端角色权限和记录可见范围。</div>
          </div>
          <div className="rounded-md bg-slate-50 p-3">
            <div className="font-medium text-slate-900">运行状态检查</div>
            <div className="mt-1 leading-6">进入运营中心，查看任务状态、模型调用次数和 Token 用量。</div>
          </div>
        </div>
      </Card>
    </div>
  );
}
