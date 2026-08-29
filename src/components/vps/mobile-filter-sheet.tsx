"use client";

import { useState } from "react";
import { useRouter } from "next/navigation";
import { SlidersHorizontal } from "lucide-react";

import { MobileFilterContent } from "@/components/vps/mobile-filter-content";
import type { MerchantOption } from "@/components/vps/FilterControls";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import { type ListQueryState, withParams } from "@/lib/query-state";

/**
 * 移动端筛选抽屉（对应旧站 Teleport 的底部 Drawer）。
 *
 * 结构：固定头部（清空） + 中间滚动区（分组折叠） + 固定底部（结果数）。
 * 中间区必须自己滚动：SheetContent 是 flex flex-col，子项默认 flex-shrink:1
 * 会被压缩而非撑开溢出，需 flex-1 + min-h-0 才真正可滚。
 *
 * 筛选条件点选即生效（见 MobileFilterContent），底部按钮只负责收起抽屉，
 * 因此文案是「查看 N 个套餐」而不是「应用」。
 */

const SPEC_KEYS = ["min_ram", "min_cpu", "min_port", "min_bw", "min_price", "max_price"] as const;

export function MobileFilterSheet({
  state,
  merchants,
  total,
}: {
  state: ListQueryState;
  merchants: MerchantOption[];
  /** 当前筛选条件下的套餐总数，用于底部按钮 */
  total: number;
}) {
  const [open, setOpen] = useState(false);
  const router = useRouter();

  const activeCount =
    state.merchant.length +
    state.line.length +
    SPEC_KEYS.filter((k) => state[k] !== undefined).length;

  const clearAll = () => {
    router.push(
      `/vps?${withParams(state, {
        merchant: [],
        line: [],
        min_ram: undefined,
        min_cpu: undefined,
        min_port: undefined,
        min_bw: undefined,
        min_price: undefined,
        max_price: undefined,
      })}`,
    );
  };

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          type="button"
          className="border-border bg-card text-foreground cursor-pointer rounded-xl border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-slate-50 lg:hidden dark:hover:bg-slate-800"
        >
          <SlidersHorizontal aria-hidden className="mr-1 inline h-4 w-4" />
          筛选
          {activeCount > 0 && (
            <span className="ml-1 rounded-full bg-blue-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
              {activeCount}
            </span>
          )}
        </button>
      </SheetTrigger>

      {/*
       * 必须用确定高度 h-[85dvh]，不能用 shadcn bottom 变体默认的 h-auto：
       * height:auto 的 flex 容器里，中间区 flex-1（flex-basis:0）对容器高度的
       * 贡献为 0，容器高度只剩头部+底部，中间内容被挤成几乎不可见——表现为
       * 「只能看到服务商的一小截」。给定高度后 flex 才能正确分配剩余空间。
       * gap-0 / p-0：头部与底部要贴边，间距由各自内部控制。
       */}
      <SheetContent side="bottom" className="flex h-[85dvh] flex-col gap-0 rounded-t-3xl p-0">
        <div className="border-border flex items-center justify-between border-b px-4 py-3.5">
          <SheetTitle className="text-sm font-bold">筛选</SheetTitle>
          {activeCount > 0 && (
            <button
              type="button"
              onClick={clearAll}
              className="text-xs font-bold text-blue-600 dark:text-blue-400"
            >
              清空全部
            </button>
          )}
        </div>

        <div className="min-h-0 flex-1 touch-pan-y overflow-y-auto overscroll-contain px-4">
          <MobileFilterContent state={state} merchants={merchants} />
        </div>

        <div className="border-border border-t p-3">
          <button
            type="button"
            onClick={() => setOpen(false)}
            className="w-full cursor-pointer rounded-xl bg-blue-600 py-2.5 text-sm font-bold text-white transition-colors hover:bg-blue-700"
          >
            查看 {total} 个套餐
          </button>
        </div>
      </SheetContent>
    </Sheet>
  );
}
