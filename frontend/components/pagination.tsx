"use client";

import Link from "next/link";
import { useRouter } from "next/navigation";
import { FormEvent, useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import { cn } from "@/lib/utils";

type PaginationCommonProps = {
  total: number;
  page: number;
  pageSize: number;
  pageSizeOptions?: number[];
  itemLabel?: string;
  className?: string;
};

type ControlledPaginationProps = PaginationCommonProps & {
  onPageChange: (page: number) => void;
  onPageSizeChange: (pageSize: number) => void;
  basePath?: never;
  query?: never;
  pageParam?: never;
  pageSizeParam?: never;
};

type LinkPaginationProps = PaginationCommonProps & {
  basePath: string;
  query?: Record<string, string | undefined>;
  pageParam?: string;
  pageSizeParam?: string;
  onPageChange?: never;
  onPageSizeChange?: never;
};

export type PaginationProps = ControlledPaginationProps | LinkPaginationProps;

export function Pagination(props: PaginationProps) {
  const router = useRouter();
  const {
    total,
    page,
    pageSize,
    pageSizeOptions = [5, 10, 20, 50],
    itemLabel = "条记录",
    className,
  } = props;
  const pageCount = Math.max(1, Math.ceil(total / pageSize));
  const safePage = Math.min(Math.max(1, page), pageCount);
  const isLinkMode = "basePath" in props && Boolean(props.basePath);
  const [jumpPage, setJumpPage] = useState(safePage);

  useEffect(() => {
    setJumpPage(safePage);
  }, [safePage]);

  function buildHref(nextPage: number, nextPageSize = pageSize) {
    if (!isLinkMode) return "#";
    const query = new URLSearchParams();
    Object.entries(props.query ?? {}).forEach(([key, value]) => {
      if (value) query.set(key, value);
    });
    query.set(props.pageParam ?? "page", String(nextPage));
    query.set(props.pageSizeParam ?? "page_size", String(nextPageSize));
    return `${props.basePath}?${query.toString()}`;
  }

  function changePageSize(nextPageSize: number) {
    if (isLinkMode) {
      router.push(buildHref(1, nextPageSize));
    } else if (props.onPageSizeChange) {
      props.onPageSizeChange(nextPageSize);
    }
  }

  function submitJump(event: FormEvent) {
    event.preventDefault();
    const target = Math.min(Math.max(1, Number(jumpPage) || 1), pageCount);
    setJumpPage(target);
    if (isLinkMode) {
      router.push(buildHref(target));
    } else if (props.onPageChange) {
      props.onPageChange(target);
    }
  }

  const previousDisabled = safePage <= 1;
  const nextDisabled = safePage >= pageCount;
  const controlClass = "h-9 min-w-[76px] border border-border bg-white px-3 text-slate-700";

  return (
    <nav
      aria-label="分页"
      className={cn(
        "mt-auto grid min-h-16 shrink-0 items-center gap-3 border-t border-border pt-3 text-sm sm:grid-cols-[minmax(0,1fr)_auto_144px_176px]",
        className,
      )}
    >
      <div className="min-w-0 text-slate-500">
        共 {total} {itemLabel} · 第 {safePage} / {pageCount} 页
      </div>
      <label className="flex items-center gap-2 whitespace-nowrap text-slate-500">
        每页
        <select
          aria-label="每页数量"
          className="h-9 w-20 rounded-md border border-border bg-white px-2 text-slate-700"
          value={pageSize}
          onChange={(event) => changePageSize(Number(event.target.value))}
        >
          {pageSizeOptions.map((value) => (
            <option key={value} value={value}>{value} 条</option>
          ))}
        </select>
      </label>
      <form className="grid w-36 grid-cols-[64px_72px] gap-2" onSubmit={submitJump}>
        <input
          aria-label="跳转页码"
          className="h-9 min-w-0 rounded-md border border-border bg-white px-2 text-center text-slate-700 outline-none focus:border-primary"
          inputMode="numeric"
          min={1}
          max={pageCount}
          type="number"
          value={jumpPage}
          onChange={(event) => setJumpPage(Number(event.target.value))}
        />
        <Button className="h-9 border border-border bg-white px-2 text-slate-700" type="submit">
          跳转
        </Button>
      </form>
      <div className="grid w-44 grid-cols-2 gap-2 justify-self-start sm:justify-self-end">
        {isLinkMode ? (
          previousDisabled ? (
            <span className={cn(controlClass, "inline-flex items-center justify-center rounded-md opacity-50")}>上一页</span>
          ) : (
            <Link className={cn(controlClass, "inline-flex items-center justify-center rounded-md hover:bg-slate-50")} href={buildHref(safePage - 1)}>
              上一页
            </Link>
          )
        ) : (
          <Button className={controlClass} type="button" disabled={previousDisabled} onClick={() => props.onPageChange?.(safePage - 1)}>
            上一页
          </Button>
        )}
        {isLinkMode ? (
          nextDisabled ? (
            <span className={cn(controlClass, "inline-flex items-center justify-center rounded-md opacity-50")}>下一页</span>
          ) : (
            <Link className={cn(controlClass, "inline-flex items-center justify-center rounded-md hover:bg-slate-50")} href={buildHref(safePage + 1)}>
              下一页
            </Link>
          )
        ) : (
          <Button className={controlClass} type="button" disabled={nextDisabled} onClick={() => props.onPageChange?.(safePage + 1)}>
            下一页
          </Button>
        )}
      </div>
    </nav>
  );
}
