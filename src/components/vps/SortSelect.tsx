"use client";

import { ArrowUpDown, ChevronDown } from "lucide-react";

import { SORT_OPTIONS, type ListQueryState, type SortValue } from "@/lib/query-state";

export function SortSelect({
  state,
  onChange,
}: {
  state: ListQueryState;
  onChange: (sort: SortValue) => void;
}) {
  return (
    <div className="relative flex items-center">
      <label htmlFor="sort-select" className="sr-only">
        套餐排序方式
      </label>
      <div className="pointer-events-none absolute left-2.5 flex items-center text-slate-500 dark:text-slate-400">
        <ArrowUpDown className="h-3.5 w-3.5" aria-hidden />
      </div>
      <select
        id="sort-select"
        value={state.sort}
        onChange={(e) => onChange(e.target.value as SortValue)}
        aria-label="套餐排序方式"
        className="border-border bg-card text-foreground cursor-pointer appearance-none rounded-xl border py-1.5 pl-8 pr-7 text-xs font-bold shadow-xs transition-colors hover:border-slate-300 focus:border-blue-500 focus:outline-none dark:hover:border-slate-700"
      >
        {SORT_OPTIONS.map((opt) => (
          <option key={opt.value} value={opt.value}>
            {opt.label}
          </option>
        ))}
      </select>
      <div className="pointer-events-none absolute right-2 flex items-center text-slate-400">
        <ChevronDown className="h-3 w-3" aria-hidden />
      </div>
    </div>
  );
}
