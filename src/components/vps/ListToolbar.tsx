"use client";

import { useRouter } from "next/navigation";
import { SlidersHorizontal } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Sheet,
  SheetContent,
  SheetHeader,
  SheetTitle,
  SheetTrigger,
} from "@/components/ui/sheet";
import {
  SORT_OPTIONS,
  withParams,
  type ListQueryState,
} from "@/lib/query-state";
import { FilterControls } from "./FilterControls";

interface MerchantOption {
  slug: string;
  name: string;
  in_stock_count: number;
}

/** 列表工具行：排序切换（原生 select，移动端原生滚轮体验）+ 移动端筛选抽屉入口。 */

export function ListToolbar({
  state,
  merchants,
}: {
  state: ListQueryState;
  merchants: MerchantOption[];
}) {
  const router = useRouter();

  return (
    <div className="flex items-center gap-2">
      {/* 移动端：筛选抽屉（shadcn Sheet）；lg+ 由侧栏承担 */}
      <Sheet>
        <SheetTrigger asChild>
          <Button variant="outline" size="sm" className="gap-1.5 lg:hidden">
            <SlidersHorizontal aria-hidden className="h-4 w-4" />
            筛选
          </Button>
        </SheetTrigger>
        <SheetContent side="bottom" className="overflow-y-auto px-4 pb-8">
          <SheetHeader>
            <SheetTitle>筛选条件</SheetTitle>
          </SheetHeader>
          <div className="px-1">
            <FilterControls state={state} merchants={merchants} />
          </div>
        </SheetContent>
      </Sheet>

      <label className="ml-auto flex items-center gap-2 text-sm">
        <span className="text-muted-foreground whitespace-nowrap">排序</span>
        <select
          value={state.sort}
          onChange={(e) => router.push(`/vps?${withParams(state, { sort: e.target.value as ListQueryState["sort"] })}`)}
          className="border-input bg-background focus-visible:ring-ring/50 h-9 rounded-md border px-2 py-1 text-base outline-none focus-visible:ring-[3px] md:text-sm"
        >
          {SORT_OPTIONS.map((o) => (
            <option key={o.value} value={o.value}>
              {o.label}
            </option>
          ))}
        </select>
      </label>
    </div>
  );
}
