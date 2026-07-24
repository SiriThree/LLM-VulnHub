import {
  AlertTriangle,
  ArrowRight,
  CheckCircle2,
  CircleDot,
  Database,
  ExternalLink,
  GitBranch,
  Layers3,
  LockKeyhole,
  Network,
  ServerCog,
  ShieldCheck,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Card } from "@/components/ui/card";
import { api } from "@/lib/api";
import { cn } from "@/lib/utils";

type ArchitectureNode = {
  id: string;
  label: string;
  layer: string;
  description: string;
};

type ArchitectureEdge = {
  source: string;
  target: string;
  label: string;
};

type TrustBoundary = {
  id: string;
  title: string;
  trust_level: "untrusted" | "controlled" | "third_party";
  description: string;
  assets: string[];
};

type Threat = {
  id: string;
  category: string;
  title: string;
  scenario: string;
  impact: string;
  current_controls: string[];
  recommended_controls: string[];
  priority: "严重" | "高" | "中" | "低";
  status: "已实施" | "部分实施" | "规划中";
};

type SecurityModel = {
  version: string;
  scope: string;
  business_flow: string[];
  architecture_nodes: ArchitectureNode[];
  architecture_edges: ArchitectureEdge[];
  trust_boundaries: TrustBoundary[];
  threats: Threat[];
  rag_controls: string[];
  release_baseline: string[];
};

const LAYER_ORDER = ["交互层", "服务层", "任务层", "数据层", "模型层", "外部依赖"];

const LAYER_ICONS = {
  交互层: Network,
  服务层: ServerCog,
  任务层: GitBranch,
  数据层: Database,
  模型层: CircleDot,
  外部依赖: ExternalLink,
} as const;

const PRIORITY_STYLE: Record<Threat["priority"], string> = {
  严重: "bg-rose-100 text-rose-800",
  高: "bg-amber-100 text-amber-800",
  中: "bg-sky-100 text-sky-800",
  低: "bg-emerald-100 text-emerald-800",
};

const STATUS_STYLE: Record<Threat["status"], string> = {
  已实施: "bg-emerald-100 text-emerald-800",
  部分实施: "bg-amber-100 text-amber-800",
  规划中: "bg-slate-100 text-slate-700",
};

export default async function SecurityModelPage() {
  const model = await api<SecurityModel>("/security-model").catch(() => null);

  if (!model) {
    return (
      <Card className="border-amber-200 bg-amber-50 p-6">
        <div className="flex items-start gap-3 text-amber-900">
          <AlertTriangle className="mt-0.5 shrink-0" size={19} />
          <div>
            <h1 className="font-semibold">安全模型暂时不可用</h1>
            <p className="mt-1 text-sm text-amber-800">请确认后端服务已更新并能够访问 `/api/v1/security-model`。</p>
          </div>
        </div>
      </Card>
    );
  }

  const criticalCount = model.threats.filter((item) => item.priority === "严重").length;
  const controlledCount = model.threats.filter((item) => item.status === "已实施").length;
  const layerGroups = LAYER_ORDER.map((layer) => ({
    layer,
    nodes: model.architecture_nodes.filter((node) => node.layer === layer),
  })).filter((group) => group.nodes.length > 0);

  return (
    <div className="space-y-6">
      <section className="overflow-hidden rounded-xl border border-slate-800 bg-slate-950 px-5 py-6 text-white shadow-soft sm:px-6 sm:py-7">
        <div className="flex flex-col gap-5 xl:flex-row xl:items-end xl:justify-between">
          <div className="max-w-3xl">
            <div className="mb-3 inline-flex items-center gap-2 rounded-full border border-white/10 bg-white/10 px-3 py-1 text-xs text-slate-200">
              <ShieldCheck size={14} /> Security Model v{model.version}
            </div>
            <h1 className="text-2xl font-semibold tracking-tight sm:text-3xl">系统架构与威胁模型</h1>
            <p className="mt-2 text-sm leading-6 text-slate-300">{model.scope}</p>
          </div>
          <div className="grid grid-cols-3 gap-5 text-sm sm:gap-8">
            <Metric value={model.threats.length} label="识别风险" />
            <Metric value={criticalCount} label="严重风险" />
            <Metric value={controlledCount} label="已实施控制" />
          </div>
        </div>
      </section>

      <Card className="p-0">
        <SectionHeader icon={GitBranch} title="情报处理流程" description="从采集到入库的完整步骤。" />
        <div className="grid gap-3 p-4 sm:grid-cols-2 xl:grid-cols-4 2xl:grid-cols-8">
          {model.business_flow.map((step, index) => (
            <div className="relative flex items-center gap-2 xl:block" key={step}>
              <div className="flex min-h-20 flex-1 items-center rounded-lg border border-slate-200 bg-slate-50 p-3 xl:min-h-24 xl:flex-col xl:items-start xl:justify-between">
                <span className="mr-3 flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-slate-900 text-xs font-semibold text-white xl:mr-0">
                  {index + 1}
                </span>
                <span className="text-sm font-medium leading-5 text-slate-800">{step}</span>
              </div>
              {index < model.business_flow.length - 1 ? <ArrowRight className="shrink-0 text-slate-300 xl:absolute xl:-right-3 xl:top-10 xl:z-10" size={17} /> : null}
            </div>
          ))}
        </div>
      </Card>

      <Card className="p-0">
        <SectionHeader icon={Layers3} title="系统架构" description="当前系统组件及其关系。" />
        <div className="grid gap-4 p-4 md:grid-cols-2 xl:grid-cols-3">
          {layerGroups.map(({ layer, nodes }) => {
            const Icon = LAYER_ICONS[layer as keyof typeof LAYER_ICONS] ?? Layers3;
            return (
              <section className="rounded-lg border border-slate-200 bg-slate-50 p-4" key={layer}>
                <div className="mb-3 flex items-center gap-2 text-sm font-semibold text-slate-900">
                  <Icon size={17} className="text-primary" /> {layer}
                </div>
                <div className="space-y-2">
                  {nodes.map((node) => (
                    <div className="rounded-md border border-slate-200 bg-white p-3" key={node.id}>
                      <div className="text-sm font-medium text-slate-900">{node.label}</div>
                      <div className="mt-1 text-xs leading-5 text-slate-500">{node.description}</div>
                    </div>
                  ))}
                </div>
              </section>
            );
          })}
        </div>
        <div className="border-t border-slate-100 px-4 py-3 text-xs text-slate-500">
        </div>
      </Card>

      <Card className="p-0">
        <SectionHeader icon={LockKeyhole} title="信任边界" description="不同信任域之间的数据会经过校验、裁剪和审计。" />
        <div className="grid gap-4 p-4 lg:grid-cols-3">
          {model.trust_boundaries.map((boundary) => (
            <section
              className={cn(
                "rounded-lg border p-4",
                boundary.trust_level === "untrusted" && "border-rose-200 bg-rose-50",
                boundary.trust_level === "controlled" && "border-emerald-200 bg-emerald-50",
                boundary.trust_level === "third_party" && "border-amber-200 bg-amber-50",
              )}
              key={boundary.id}
            >
              <div className="flex items-center justify-between gap-3">
                <h3 className="font-semibold text-slate-900">{boundary.title}</h3>
                <BoundaryBadge level={boundary.trust_level} />
              </div>
              <p className="mt-2 text-sm leading-6 text-slate-600">{boundary.description}</p>
              <ul className="mt-3 space-y-2 text-sm text-slate-700">
                {boundary.assets.map((asset) => (
                  <li className="flex items-center gap-2" key={asset}>
                    <CircleDot size={13} className="shrink-0 text-slate-400" /> {asset}
                  </li>
                ))}
              </ul>
            </section>
          ))}
        </div>
      </Card>

      <Card className="overflow-hidden p-0">
        <SectionHeader icon={AlertTriangle} title="STRIDE 风险清单" description="列出已实施和待补充的控制措施。" />
        <div className="overflow-x-auto">
          <table className="w-full min-w-[1180px] table-fixed text-sm">
            <colgroup>
              <col className="w-16" />
              <col className="w-24" />
              <col className="w-44" />
              <col className="w-72" />
              <col className="w-64" />
              <col className="w-64" />
              <col className="w-20" />
              <col className="w-24" />
            </colgroup>
            <thead>
              <tr className="border-b border-border bg-slate-50 text-left text-slate-500">
                <th className="p-3 font-medium">编号</th>
                <th className="p-3 font-medium">类别</th>
                <th className="p-3 font-medium">威胁</th>
                <th className="p-3 font-medium">场景与影响</th>
                <th className="p-3 font-medium">当前控制</th>
                <th className="p-3 font-medium">建议补强</th>
                <th className="p-3 font-medium">优先级</th>
                <th className="p-3 font-medium">状态</th>
              </tr>
            </thead>
            <tbody>
              {model.threats.map((threat) => (
                <tr className="border-b border-border align-top last:border-0 hover:bg-slate-50" key={threat.id}>
                  <td className="p-3 font-semibold text-slate-900">{threat.id}</td>
                  <td className="p-3 text-slate-600">{threat.category}</td>
                  <td className="p-3 font-medium text-slate-900">{threat.title}</td>
                  <td className="p-3 text-xs leading-5 text-slate-600">
                    <div>{threat.scenario}</div>
                    <div className="mt-2 text-slate-500">影响：{threat.impact}</div>
                  </td>
                  <td className="p-3"><CompactList items={threat.current_controls} /></td>
                  <td className="p-3"><CompactList items={threat.recommended_controls} /></td>
                  <td className="p-3"><span className={cn("rounded px-2 py-1 text-xs font-medium", PRIORITY_STYLE[threat.priority])}>{threat.priority}</span></td>
                  <td className="p-3"><span className={cn("rounded px-2 py-1 text-xs font-medium", STATUS_STYLE[threat.status])}>{threat.status}</span></td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </Card>

      <div className="grid gap-4 xl:grid-cols-2">
        <Card className="p-0">
          <SectionHeader icon={ShieldCheck} title="RAG 专项控制" description="针对投毒、提示注入、引用错误和越权检索。" />
          <Checklist items={model.rag_controls} />
        </Card>
        <Card className="p-0">
          <SectionHeader icon={CheckCircle2} title="上线安全基线" description="上线前需要完成的安全检查。" />
          <Checklist items={model.release_baseline} />
        </Card>
      </div>
    </div>
  );
}

function Metric({ value, label }: { value: number; label: string }) {
  return (
    <div>
      <div className="text-2xl font-semibold">{value}</div>
      <div className="mt-1 text-xs text-slate-400">{label}</div>
    </div>
  );
}

function SectionHeader({ icon: Icon, title, description }: { icon: typeof ShieldCheck; title: string; description: string }) {
  return (
    <div className="flex items-start gap-3 border-b border-slate-100 px-4 py-4 sm:px-5">
      <div className="rounded-md bg-slate-100 p-2 text-slate-600"><Icon size={17} /></div>
      <div>
        <h2 className="font-semibold text-slate-900">{title}</h2>
        <p className="mt-1 text-xs leading-5 text-slate-500">{description}</p>
      </div>
    </div>
  );
}

function BoundaryBadge({ level }: { level: TrustBoundary["trust_level"] }) {
  const labels = { untrusted: "不可信", controlled: "受控", third_party: "第三方" };
  return <Badge>{labels[level]}</Badge>;
}

function CompactList({ items }: { items: string[] }) {
  return (
    <ul className="space-y-1 text-xs leading-5 text-slate-600">
      {items.map((item) => <li key={item}>• {item}</li>)}
    </ul>
  );
}

function Checklist({ items }: { items: string[] }) {
  return (
    <ul className="space-y-3 p-4 sm:p-5">
      {items.map((item) => (
        <li className="flex items-start gap-3 text-sm leading-6 text-slate-700" key={item}>
          <CheckCircle2 className="mt-1 shrink-0 text-emerald-600" size={16} /> {item}
        </li>
      ))}
    </ul>
  );
}
