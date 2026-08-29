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
      <SheetContent
        side="bottom"
        className="max-h-[85dvh] overflow-y-auto rounded-t-3xl p-4"
      >
        <SheetTitle className="mb-3 text-sm font-bold">筛选条件</SheetTitle>
        <FilterControls state={state} merchants={merchants} />
      </SheetContent>
    </Sheet>
  );
}
