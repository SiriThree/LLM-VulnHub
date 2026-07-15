import { PromptEvalPanel } from "@/components/prompt-eval-panel";
import { RoleSimulator } from "@/components/role-simulator";
import { Card } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div className="space-y-5">
      <div>
        <h1 className="text-2xl font-semibold">设置</h1>
        <p className="text-sm text-slate-500">统一查看模型接入、运行环境和演示权限配置。</p>
      </div>

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
            "NEXT_PUBLIC_API_BASE=http://localhost:8001/api/v1",
            "DEFAULT_ACTOR=local-admin",
            "DEFAULT_ROLE=admin",
          ].map((item) => (
            <code className="rounded-md bg-muted p-3" key={item}>
              {item}
            </code>
          ))}
        </div>
      </Card>

      <Card className="space-y-3">
        <h2 className="font-semibold">推荐验证动作</h2>
        <div className="grid gap-3 text-sm text-slate-600 md:grid-cols-3">
          <div className="rounded-md bg-slate-50 p-3">
            <div className="font-medium text-slate-900">模型抽取</div>
            <div className="mt-1 leading-6">切到 AI 抽取页，输入真实漏洞描述，观察标题、类型、组件、攻击方式、修复建议是否随文本变化。</div>
          </div>
          <div className="rounded-md bg-slate-50 p-3">
            <div className="font-medium text-slate-900">权限控制</div>
            <div className="mt-1 leading-6">用 viewer 角色尝试确认通知、编辑漏洞或新增数据源，验证后端是否返回 403。</div>
          </div>
          <div className="rounded-md bg-slate-50 p-3">
            <div className="font-medium text-slate-900">运行观测</div>
            <div className="mt-1 leading-6">进入 Operations 页，查看任务状态、模型调用次数和 token 消耗。</div>
          </div>
        </div>
      </Card>
    </div>
  );
}
