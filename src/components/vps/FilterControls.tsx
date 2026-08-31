"use client";

import { useState } from "react";

import { merchantTitle, sortMerchants } from "@/lib/merchant-notes";
import { type ListQueryState } from "@/lib/query-state";
import { cn } from "@/lib/utils";
import { useListData } from "@/components/vps/list-data-context";

/**
 * 桌面端侧栏筛选（1:1 复刻旧站 components/FilterBar.vue）：
 * 实时监控胶囊 → 服务商平铺多选 → 硬件配置折叠筛选。
 *
 * 表单控件采用 `text-base sm:text-xs`：移动端 16px 规避 iOS 聚焦缩放（AGENTS.md），
 * sm 及以上恢复旧站的 12px 观感。
 */

export interface MerchantOption {
  slug: string;
  name: string;
  count?: number;
  in_stock_count?: number;
}

const NUM_SELECT_CLASS =
  "border-border bg-card text-foreground w-full rounded-lg border px-2 py-1 text-base focus:border-blue-500 focus:outline-none sm:text-xs";

function NumSelect({
  label,
  value,
  options,
  onChange,
}: {
  label: string;
  value: number | undefined;
  options: { value: string; label: string }[];
  onChange: (v: number | undefined) => void;
}) {
  return (
    <div>
      <label className="mb-1.5 block font-bold text-slate-500 dark:text-slate-400">{label}</label>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
        className={NUM_SELECT_CLASS}
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </div>
  );
}

export function FilterControls({
  merchants,
}: {
  merchants: MerchantOption[];
}) {
  const { state, apply } = useListData();
  // 硬件配置筛选默认展开：筛选条件直接可见，省去一次点击
  const [showAdvanced, setShowAdvanced] = useState(true);
  const [priceMin, setPriceMin] = useState(state.min_price?.toString() ?? "");
  const [priceMax, setPriceMax] = useState(state.max_price?.toString() ?? "");

  const selected = state.merchant;
  const toggleMerchant = (slug: string) => {
    apply({
      merchant: selected.includes(slug)
        ? selected.filter((s) => s !== slug)
        : [...selected, slug],
    });
  };

  const totalInStock = merchants.reduce((a, m) => a + (m.in_stock_count ?? 0), 0);
  const totalCount = merchants.reduce((a, m) => a + (m.count ?? 0), 0);

  const applyAdvanced = () => {
    apply({
      min_price: priceMin === "" ? undefined : Number(priceMin),
      max_price: priceMax === "" ? undefined : Number(priceMax),
    });
  };

  return (
    <div className="flex flex-col gap-3.5">
      {/* 1. 顶部状态微胶囊（实时监控中 · 到货即时提醒） */}
      <div className="border-border/80 bg-card flex items-center justify-between rounded-xl border px-3 py-2 text-xs">
        <div className="flex items-center gap-1.5 font-bold text-slate-800 dark:text-slate-200">
          <span aria-hidden className="relative flex h-2 w-2">
            <span className="absolute inline-flex h-full w-full animate-ping rounded-full bg-emerald-400 opacity-75" />
            <span className="relative inline-flex h-2 w-2 rounded-full bg-emerald-500 shadow-[0_0_6px_#10b981]" />
          </span>
          <span className="tracking-tight">GoVPS 实时监控</span>
        </div>
        <span className="text-[11px] font-medium text-slate-400 dark:text-slate-500">
          到货/降价推送
        </span>
      </div>

      {/* 2. 服务商平铺多选模块 */}
      <div className="border-border/80 bg-card flex flex-col gap-2.5 rounded-2xl border p-3.5 shadow-sm">
        <div className="flex items-center justify-between px-0.5">
          <div className="flex items-center gap-1.5">
            <span className="text-xs font-black tracking-tight text-slate-800 dark:text-slate-200">
              服务商
            </span>
            <span className="text-[10px] font-medium text-slate-400 dark:text-slate-500">
              （支持多选）
            </span>
          </div>
          {selected.length > 0 && (
            <button
              type="button"
              onClick={() => apply({ merchant: [] })}
              className="text-[11px] font-bold text-blue-600 transition-colors hover:text-blue-700 dark:text-blue-400"
            >
              清空已选 ({selected.length})
            </button>
          )}
        </div>

        {/* 全部服务商快捷总选按钮 */}
        <button
          type="button"
          onClick={() => apply({ merchant: [] })}
          className={cn(
            "group flex w-full items-center justify-between rounded-xl border px-3 py-2 text-xs font-bold transition-all",
            selected.length === 0
              ? "border-blue-500 bg-blue-600 text-white shadow-sm"
              : "border-slate-200/70 bg-slate-50/80 text-slate-700 hover:border-slate-300 hover:bg-slate-100 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-300 dark:hover:bg-slate-800",
          )}
        >
          <span className="flex items-center gap-2">
            <span
              aria-hidden
              className={cn(
                "flex h-4 w-4 items-center justify-center rounded border transition-colors",
                selected.length === 0
                  ? "border-white bg-white text-blue-600"
                  : "border-slate-300 bg-white group-hover:border-slate-400 dark:border-slate-600 dark:bg-slate-900",
              )}
            >
              {selected.length === 0 && (
                <svg
                  className="h-3 w-3"
                  viewBox="0 0 24 24"
                  fill="none"
                  stroke="currentColor"
                  strokeWidth="3"
                >
                  <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                </svg>
              )}
            </span>
            <span className="truncate">全部服务商</span>
          </span>
          <span className="flex items-center gap-1.5 text-[11px]">
            <span
              className={cn(
                selected.length === 0
                  ? "text-blue-100"
                  : "font-semibold text-emerald-600 dark:text-emerald-400",
              )}
            >
              {totalInStock} 在售
            </span>
            <span className={selected.length === 0 ? "text-blue-200" : "text-slate-400"}>
              / {totalCount}
            </span>
          </span>
        </button>

        {/* 服务商平铺列表项 */}
        <div className="space-y-1 pt-0.5">
          {sortMerchants(merchants).map((m) => {
            const on = selected.includes(m.slug);
            const stock = m.in_stock_count ?? m.count ?? 0;
            return (
              <button
                key={m.slug}
                type="button"
                aria-pressed={on}
                title={merchantTitle(m.slug, m.name)}
                onClick={() => toggleMerchant(m.slug)}
                className={cn(
                  "group relative flex w-full cursor-pointer items-center justify-between rounded-xl border px-2.5 py-2 text-left text-xs transition-colors select-none",
                  on
                    ? "border-blue-200/80 bg-blue-50/80 font-semibold text-blue-900 dark:border-blue-800 dark:bg-blue-950/50 dark:text-blue-200"
                    : "border-transparent bg-white text-slate-700 hover:border-slate-200/70 hover:bg-slate-50/80 dark:bg-transparent dark:text-slate-300 dark:hover:bg-slate-800",
                )}
              >
                <span className="flex min-w-0 flex-1 items-center gap-2.5">
                  <span
                    aria-hidden
                    className={cn(
                      "flex h-4 w-4 shrink-0 items-center justify-center rounded border transition-colors",
                      on
                        ? "border-blue-600 bg-blue-600 text-white"
                        : "border-slate-300 bg-white group-hover:border-slate-400 dark:border-slate-600 dark:bg-slate-900",
                    )}
                  >
                    {on && (
                      <svg
                        className="h-3 w-3"
                        viewBox="0 0 24 24"
                        fill="none"
                        stroke="currentColor"
                        strokeWidth="3"
                      >
                        <path strokeLinecap="round" strokeLinejoin="round" d="M4.5 12.75l6 6 9-13.5" />
                      </svg>
                    )}
                  </span>
                  <span className="truncate text-[13px] font-bold tracking-tight text-slate-800 dark:text-slate-200">
                    {m.name}
                  </span>
                </span>
                <span className="flex shrink-0 items-center gap-1 font-mono text-[11px]">
                  <span
                    className={cn(
                      "font-bold",
                      stock > 0
                        ? "text-emerald-600 dark:text-emerald-400"
                        : "text-rose-500 dark:text-rose-400",
                    )}
                  >
                    {stock}
                  </span>
                  <span className="text-slate-300 dark:text-slate-600">/</span>
                  <span className="text-slate-400 dark:text-slate-500">{m.count || 0}</span>
                </span>
              </button>
            );
          })}
        </div>
      </div>

      {/* 3. 高级硬件规格筛选折叠卡片 */}
      <div className="border-border/80 bg-card rounded-2xl border p-3.5 shadow-sm">
        <button
          type="button"
          onClick={() => setShowAdvanced((v) => !v)}
          aria-expanded={showAdvanced}
          className="flex w-full items-center justify-between py-0.5 text-xs font-black text-slate-800 transition-colors hover:text-blue-600 dark:text-slate-200 dark:hover:text-blue-400"
        >
          <span className="flex items-center gap-1.5">
            <svg
              aria-hidden
              className="h-3.5 w-3.5 text-blue-600 dark:text-blue-400"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M10.5 6h9.75M10.5 6a1.5 1.5 0 1 1-3 0m3 0a1.5 1.5 0 1 0-3 0M3.75 6H7.5m3 12h9.75m-9.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-3.75 0H7.5m9-6h3.75m-3.75 0a1.5 1.5 0 0 1-3 0m3 0a1.5 1.5 0 0 0-3 0m-9.75 0h9.75"
              />
            </svg>
            硬件配置筛选
          </span>
          <svg
            aria-hidden
            className={cn(
              "h-3.5 w-3.5 text-slate-400 transition-transform duration-200",
              showAdvanced && "rotate-180",
            )}
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
          </svg>
        </button>

        {showAdvanced && (
          <div className="border-border mt-3 space-y-3 border-t pt-3 text-xs">
            <div>
              <label className="mb-1.5 block font-bold text-slate-500 dark:text-slate-400">
                折算年付价格 ($)
              </label>
              <div className="flex items-center gap-1.5">
                <input
                  type="number"
                  min="0"
                  inputMode="numeric"
                  value={priceMin}
                  onChange={(e) => setPriceMin(e.target.value)}
                  placeholder="最低"
                  aria-label="最低年付价格（美元）"
                  className="border-border bg-card w-full rounded-lg border px-2 py-1 text-base focus:border-blue-500 focus:outline-none sm:text-xs"
                />
                <span className="text-slate-300">-</span>
                <input
                  type="number"
                  min="0"
                  inputMode="numeric"
                  value={priceMax}
                  onChange={(e) => setPriceMax(e.target.value)}
                  placeholder="最高"
                  aria-label="最高年付价格（美元）"
                  className="border-border bg-card w-full rounded-lg border px-2 py-1 text-base focus:border-blue-500 focus:outline-none sm:text-xs"
                />
              </div>
            </div>

            <NumSelect
              label="最低内存"
              value={state.min_ram}
              onChange={(v) => apply({ min_ram: v })}
              options={[
                { value: "", label: "不限" },
                { value: "0.5", label: "512MB +" },
                { value: "1", label: "1GB +" },
                { value: "2", label: "2GB +" },
                { value: "4", label: "4GB +" },
                { value: "8", label: "8GB +" },
              ]}
            />
            <NumSelect
              label="最低 CPU"
              value={state.min_cpu}
              onChange={(v) => apply({ min_cpu: v })}
              options={[
                { value: "", label: "不限" },
                { value: "1", label: "1 核 +" },
                { value: "2", label: "2 核 +" },
                { value: "4", label: "4 核 +" },
                { value: "8", label: "8 核 +" },
              ]}
            />
            <NumSelect
              label="最低带宽"
              value={state.min_port}
              onChange={(v) => apply({ min_port: v })}
              options={[
                { value: "", label: "不限" },
                { value: "100", label: "100Mbps +" },
                { value: "500", label: "500Mbps +" },
                { value: "1000", label: "1Gbps +" },
              ]}
            />
            <NumSelect
              label="最低月流量"
              value={state.min_bw}
              onChange={(v) => apply({ min_bw: v })}
              options={[
                { value: "", label: "不限" },
                { value: "500", label: "500GB +" },
                { value: "1000", label: "1TB +" },
                { value: "2000", label: "2TB +" },
              ]}
            />

            <div className="flex gap-2 pt-1">
              <button
                type="button"
                onClick={applyAdvanced}
                className="flex-1 rounded-xl bg-blue-600 py-1.5 text-xs font-bold text-white shadow-sm transition-colors hover:bg-blue-700"
              >
                应用配置筛选
              </button>
              <button
                type="button"
                onClick={() => {
                  setPriceMin("");
                  setPriceMax("");
                  apply({
                    min_price: undefined,
                    max_price: undefined,
                    min_ram: undefined,
                    min_cpu: undefined,
                    min_bw: undefined,
                    min_port: undefined,
                  });
                }}
                className="rounded-xl border border-slate-200 px-3 py-1.5 text-xs font-medium text-slate-500 transition-colors hover:bg-slate-50 dark:border-slate-700 dark:hover:bg-slate-800"
              >
                重置
              </button>
            </div>
          </div>
        )}
      </div>
    </div>
  );
}
