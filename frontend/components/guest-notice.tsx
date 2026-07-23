import Link from "next/link";
import { Eye, LogIn } from "lucide-react";


export function GuestNotice({ detail = false }: { detail?: boolean }) {
  return (
    <div className="flex flex-col gap-3 rounded-xl border border-amber-200 bg-amber-50 px-4 py-3 text-sm text-amber-950 sm:flex-row sm:items-center sm:justify-between">
      <div className="flex items-start gap-3">
        <Eye className="mt-0.5 shrink-0 text-amber-700" size={18} />
        <div>
          <div className="font-medium">当前为访客模式</div>
          <div className="mt-1 leading-5 text-amber-800">
            {detail
              ? "这里只展示公开摘要；攻击复现、来源证据、完整处置建议和分析记录已隐藏。"
              : "只能浏览公开漏洞摘要，不能执行新增、编辑、检索或审核操作。"}
          </div>
        </div>
      </div>
      <Link className="inline-flex shrink-0 items-center gap-2 font-medium text-amber-900 hover:underline" href="/login">
        <LogIn size={15} />
        账号登录
      </Link>
    </div>
  );
}
