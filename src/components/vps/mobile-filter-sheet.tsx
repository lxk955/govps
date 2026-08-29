"use client";

import { useState } from "react";
import { SlidersHorizontal } from "lucide-react";

import {
  FilterControls,
  type MerchantOption,
} from "@/components/vps/FilterControls";
import { Sheet, SheetContent, SheetTitle, SheetTrigger } from "@/components/ui/sheet";
import type { ListQueryState } from "@/lib/query-state";

/**
 * 移动端筛选抽屉（对应旧站 Teleport 的底部 Drawer）。
 * 抽屉保持打开以支持商家多选，由用户手动关闭——与旧站行为一致。
 */
export function MobileFilterSheet({
  state,
  merchants,
}: {
  state: ListQueryState;
  merchants: MerchantOption[];
}) {
  const [open, setOpen] = useState(false);

  return (
    <Sheet open={open} onOpenChange={setOpen}>
      <SheetTrigger asChild>
        <button
          type="button"
          className="border-border bg-card text-foreground cursor-pointer rounded-xl border px-3 py-1.5 text-sm font-medium transition-colors hover:bg-slate-50 lg:hidden dark:hover:bg-slate-800"
        >
          <SlidersHorizontal aria-hidden className="mr-1 inline h-4 w-4" />
          筛选
        </button>
      </SheetTrigger>
      <SheetContent side="bottom" className="flex max-h-[85dvh] flex-col rounded-t-3xl p-4">
        <SheetTitle className="shrink-0 text-sm font-bold">筛选条件</SheetTitle>
        {/*
         * 滚动交给独立的内容区，不能直接放在 SheetContent 上：
         * SheetContent 是 flex flex-col，子项默认 flex-shrink:1 会被压缩而不是
         * 撑开溢出，于是内容被裁掉且不出现滚动。这里用 flex-1 + min-h-0
         * （覆盖 flex 子项默认的 min-height:auto，允许收缩）才真正可滚；
         * overscroll-contain 防止滚到底后带着背景页面一起动。
         */}
        <div className="min-h-0 flex-1 touch-pan-y overflow-y-auto overscroll-contain">
          <FilterControls state={state} merchants={merchants} />
        </div>
      </SheetContent>
    </Sheet>
  );
}
