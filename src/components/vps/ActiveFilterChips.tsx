"use client";

import { useRouter } from "next/navigation";
import { X } from "lucide-react";

import { Button } from "@/components/ui/button";
import { LINE_OPTIONS } from "@/lib/query-state";
import type { ListQueryState } from "@/lib/query-state";
import { withParams } from "@/lib/query-state";

/** 已启用筛选的 chips 展示，点 × 移除对应条件（URL 状态同步）。 */

const BOOL_LABELS: Partial<Record<keyof ListQueryState, string>> = {
  in_stock: "仅看有货",
  price_drop: "降价中",
  lowest_price: "史低价",
  recent_restock: "近期补货",
  recommended: "精选推荐",
};

const NUM_LABELS: Partial<Record<keyof ListQueryState, string>> = {
  min_price: "年付 ≥",
  max_price: "年付 ≤",
  min_ram: "内存 ≥",
  min_cpu: "CPU ≥",
  min_bw: "流量 ≥",
  min_port: "带宽 ≥",
};

export function ActiveFilterChips({ state }: { state: ListQueryState }) {
  const router = useRouter();

  const chips: { key: keyof ListQueryState | "keyword"; label: string; value?: string }[] = [];
  for (const m of state.merchant) chips.push({ key: "merchant", label: "商家", value: m });
  for (const l of state.location) chips.push({ key: "location", label: "机房", value: l });
  for (const ln of state.line) {
    const opt = LINE_OPTIONS.find((o) => o.value === ln);
    chips.push({ key: "line", label: "线路", value: opt?.label ?? ln });
  }
  if (state.keyword.trim()) chips.push({ key: "keyword", label: "搜索", value: state.keyword.trim() });
  for (const [k, label] of Object.entries(NUM_LABELS)) {
    const v = state[k as keyof ListQueryState];
    if (typeof v === "number") chips.push({ key: k as keyof ListQueryState, label, value: String(v) });
  }
  for (const [k, label] of Object.entries(BOOL_LABELS)) {
    if (state[k as keyof ListQueryState] === true) chips.push({ key: k as keyof ListQueryState, label });
  }

  if (chips.length === 0) return null;

  const remove = (key: keyof ListQueryState | "keyword", value?: string) => {
    if (key === "keyword") return router.push(`/vps?${withParams(state, { keyword: "" })}`);
    if (key === "merchant" || key === "location" || key === "line") {
      const rest = state[key].filter((v) => v !== value);
      return router.push(`/vps?${withParams(state, { [key]: rest } as Partial<ListQueryState>)}`);
    }
    if (typeof state[key] === "boolean") {
      return router.push(`/vps?${withParams(state, { [key]: false } as Partial<ListQueryState>)}`);
    }
    return router.push(`/vps?${withParams(state, { [key]: undefined } as Partial<ListQueryState>)}`);
  };

  return (
    <ul className="flex flex-wrap items-center gap-1.5" aria-label="已启用筛选">
      {chips.map((c, i) => (
        <li key={`${c.key}-${c.value ?? i}`}>
          <Button
            variant="outline"
            size="sm"
            className="h-7 gap-1 rounded-full px-2.5 text-xs"
            onClick={() => remove(c.key, c.value)}
          >
            <span className="text-muted-foreground">{c.label}</span>
            {c.value && <span className="max-w-40 truncate">{c.value}</span>}
            <X aria-hidden className="h-3 w-3" />
            <span className="sr-only">移除筛选 {c.label} {c.value ?? ""}</span>
          </Button>
        </li>
      ))}
      <li>
        <Button
          variant="ghost"
          size="sm"
          className="h-7 px-2 text-xs text-muted-foreground"
          onClick={() => router.push("/vps")}
        >
          清空全部
        </Button>
      </li>
    </ul>
  );
}
