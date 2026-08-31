"use client";

import Link from "next/link";

import { useListData } from "@/components/vps/list-data-context";
import { withParams } from "@/lib/query-state";
import { cn } from "@/lib/utils";

/**
 * 底部统计与翻页（1:1 复刻旧站 ProductList.vue 底部条）。
 * 翻页保留 <Link> href：爬虫可跟随、可新标签打开；左键点击拦截走 store
 * （缓存命中瞬时，未命中加载态），不再触发 RSC 导航。
 */
export function Pagination({ freshness }: { freshness?: string | null }) {
  const { state, data, apply } = useListData();
  const total = data?.total ?? 0;

  const totalPages = Math.max(1, Math.ceil(total / state.size));
  const page = Math.min(state.page, totalPages);

  const navClass = (disabled: boolean) =>
    cn(
      "border-border bg-card text-foreground rounded-xl border px-3 py-1 text-xs font-semibold transition-colors",
      disabled
        ? "pointer-events-none opacity-40"
        : "hover:border-slate-300 hover:bg-slate-50 dark:hover:bg-slate-800",
    );

  const goPage = (page: number) => (e: React.MouseEvent) => {
    e.preventDefault();
    apply({ page }, { resetPage: false });
  };

  return (
    <div className="border-border mt-8 flex flex-wrap items-center justify-center gap-3 border-t pt-5 text-sm">
      <span className="text-xs text-slate-500 sm:text-sm dark:text-slate-400">
        共{" "}
        <b className="text-slate-900 font-bold dark:text-slate-100">{total}</b> 个套餐
      </span>

      {freshness && (
        <>
          <span className="text-slate-300 dark:text-slate-600">·</span>
          <span
            className="text-xs text-slate-400 dark:text-slate-500"
            title="后端爬虫最近一次成功确认库存的时间"
          >
            库存确认于 {freshness}
          </span>
        </>
      )}

      {total > state.size && (
        <>
          <span className="text-slate-300 dark:text-slate-600">·</span>
          <div className="flex items-center gap-2">
            <Link
              href={`/vps?${withParams(state, { page: page - 1 }, { resetPage: false })}`}
              onClick={page > 1 ? goPage(page - 1) : undefined}
              aria-disabled={page <= 1}
              className={navClass(page <= 1)}
            >
              上一页
            </Link>
            <span className="text-slate-700 px-1 text-xs font-bold dark:text-slate-200">
              {page} / {totalPages}
            </span>
            <Link
              href={`/vps?${withParams(state, { page: page + 1 }, { resetPage: false })}`}
              onClick={page < totalPages ? goPage(page + 1) : undefined}
              aria-disabled={page >= totalPages}
              className={navClass(page >= totalPages)}
            >
              下一页
            </Link>
          </div>
        </>
      )}
    </div>
  );
}
