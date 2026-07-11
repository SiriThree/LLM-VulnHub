import { Card } from "@/components/ui/card";

export default function SettingsPage() {
  return (
    <div className="space-y-5">
      <div><h1 className="text-2xl font-semibold">设置</h1><p className="text-sm text-slate-500">模型 API 与运行参数通过后端环境变量配置。</p></div>
      <Card>
        <h2 className="mb-3 font-semibold">环境变量</h2>
        <div className="grid grid-cols-2 gap-3 text-sm">
          {["LLM_PROVIDER=mock|openai|deepseek", "OPENAI_API_KEY=...", "DEEPSEEK_API_KEY=...", "DATABASE_URL=postgresql+psycopg://...", "REDIS_URL=redis://redis:6379/0", "NEXT_PUBLIC_API_BASE=http://localhost:8000/api/v1"].map((item) => <code className="rounded bg-muted p-3" key={item}>{item}</code>)}
        </div>
      </Card>
    </div>
  );
}
