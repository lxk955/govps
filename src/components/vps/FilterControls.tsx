"use client";

import { useRouter } from "next/navigation";
import { useState } from "react";
import { Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import {
  LINE_OPTIONS,
  withParams,
  type ListQueryState,
} from "@/lib/query-state";

/**
 * 筛选表单（Client）：桌面侧栏与移动 Sheet 共用同一份字段。
 * 提交时把表单值写回 URL（resetPage），由 RSC 按新 searchParams 重取数据。
 */

interface MerchantOption {
  slug: string;
  name: string;
  in_stock_count: number;
}

export function FilterControls({
  state,
  merchants,
  onApplied,
}: {
  state: ListQueryState;
  merchants: MerchantOption[];
  /** Sheet 场景：应用后关闭抽屉 */
  onApplied?: () => void;
}) {
  const router = useRouter();
  const [keyword, setKeyword] = useState(state.keyword);

  const apply = (patch: Partial<ListQueryState>) => {
    router.push(`/vps?${withParams(state, patch)}`);
    onApplied?.();
  };

  const toggleIn = (key: "merchant" | "location" | "line", value: string, checked: boolean) => {
    const current = state[key];
    const next = checked ? [...current, value] : current.filter((v) => v !== value);
    apply({ [key]: next } as Partial<ListQueryState>);
  };

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    apply({ keyword });
  };

  return (
    <form onSubmit={onSubmit} className="flex flex-col gap-5">
      {/* 关键词搜索 */}
      <div className="flex flex-col gap-1.5">
        <Label htmlFor="vps-keyword">关键词搜索</Label>
        <div className="flex gap-2">
          <Input
            id="vps-keyword"
            type="search"
            placeholder="如：洛杉矶 CN2 2核 1T"
            className="text-base"
            value={keyword}
            onChange={(e) => setKeyword(e.target.value)}
          />
          <Button type="submit" aria-label="搜索">
            <Search aria-hidden className="h-4 w-4" />
            <span className="sr-only sm:not-sr-only">搜索</span>
          </Button>
        </div>
      </div>

      {/* 商家多选 */}
      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-sm font-medium">商家</legend>
        <div className="grid max-h-44 grid-cols-1 gap-1 overflow-y-auto sm:grid-cols-2 lg:grid-cols-1">
          {merchants.map((m) => (
            <label key={m.slug} className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-muted/60">
              <input
                type="checkbox"
                className="accent-primary h-4 w-4"
                checked={state.merchant.includes(m.slug)}
                onChange={(e) => toggleIn("merchant", m.slug, e.target.checked)}
              />
              <span className="min-w-0 truncate">{m.name}</span>
              <span className="text-muted-foreground ml-auto text-xs whitespace-nowrap">
                {m.in_stock_count} 有货
              </span>
            </label>
          ))}
        </div>
      </fieldset>

      {/* 线路多选 */}
      <fieldset className="flex flex-col gap-1.5">
        <legend className="text-sm font-medium">线路</legend>
        <div className="grid grid-cols-2 gap-1 lg:grid-cols-1">
          {LINE_OPTIONS.map((o) => (
            <label key={o.value} className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-muted/60">
              <input
                type="checkbox"
                className="accent-primary h-4 w-4"
                checked={state.line.includes(o.value)}
                onChange={(e) => toggleIn("line", o.value, e.target.checked)}
              />
              {o.label}
            </label>
          ))}
        </div>
      </fieldset>

      {/* 价格区间（折算年付，原币数值口径与后端一致） */}
      <div className="flex flex-col gap-1.5">
        <span className="text-sm font-medium">折年价格区间</span>
        <div className="flex items-center gap-2">
          <Input
            aria-label="最低年付价"
            inputMode="decimal"
            type="number"
            min={0}
            step="1"
            placeholder="最低"
            defaultValue={state.min_price ?? ""}
            className="text-base"
            onBlur={(e) =>
              apply({ min_price: e.target.value === "" ? undefined : Number(e.target.value) })
            }
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          />
          <span className="text-muted-foreground">–</span>
          <Input
            aria-label="最高年付价"
            inputMode="decimal"
            type="number"
            min={0}
            step="1"
            placeholder="最高"
            defaultValue={state.max_price ?? ""}
            className="text-base"
            onBlur={(e) =>
              apply({ max_price: e.target.value === "" ? undefined : Number(e.target.value) })
            }
            onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
          />
        </div>
      </div>

      {/* 配置下限 */}
      <div className="grid grid-cols-2 gap-3">
        {(
          [
            ["min_cpu", "CPU ≥ 核", "min_cpu"],
            ["min_ram", "内存 ≥ GB", "min_ram"],
            ["min_bw", "流量 ≥ GB", "min_bw"],
            ["min_port", "带宽 ≥ Mbps", "min_port"],
          ] as const
        ).map(([key, label]) => (
          <div key={key} className="flex flex-col gap-1">
            <Label htmlFor={`f-${key}`} className="text-xs text-muted-foreground">
              {label}
            </Label>
            <Input
              id={`f-${key}`}
              inputMode="numeric"
              type="number"
              min={0}
              defaultValue={state[key] ?? ""}
              className="h-9 text-base"
              onBlur={(e) =>
                apply({ [key]: e.target.value === "" ? undefined : Number(e.target.value) } as Partial<ListQueryState>)
              }
              onKeyDown={(e) => e.key === "Enter" && (e.target as HTMLInputElement).blur()}
            />
          </div>
        ))}
      </div>

      {/* 快捷开关 */}
      <div className="flex flex-col gap-1.5">
        {(
          [
            ["in_stock", "仅看有货"],
            ["price_drop", "只看降价中"],
            ["lowest_price", "只看史低价"],
            ["recent_restock", "只看近期补货"],
            ["recommended", "只看精选推荐"],
          ] as const
        ).map(([key, label]) => (
          <label key={key} className="flex cursor-pointer items-center gap-2 rounded px-1 py-0.5 text-sm hover:bg-muted/60">
            <input
              type="checkbox"
              className="accent-primary h-4 w-4"
              checked={state[key] === true}
              onChange={(e) => apply({ [key]: e.target.checked } as Partial<ListQueryState>)}
            />
            {label}
          </label>
        ))}
      </div>

      <Button
        type="button"
        variant="ghost"
        className="text-muted-foreground"
        onClick={() => router.push("/vps")}
      >
        清空全部筛选
      </Button>
    </form>
  );
}
