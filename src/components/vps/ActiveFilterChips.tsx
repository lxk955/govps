"use client";

import type { MerchantOption } from "@/components/vps/FilterControls";
import { useListData } from "@/components/vps/list-data-context";
import { LINE_OPTIONS } from "@/lib/query-state";

/**
 * 已激活筛选条件标签栏（1:1 复刻旧站 ProductList.vue 第 3 行）：
 * 「已选条件：」前缀 + 可单独叉掉的标签 + 一键清空。
 */
export function ActiveFilterChips({ merchants }: { merchants: MerchantOption[] }) {
  const { state, apply, reset } = useListData();
  const go = apply;

  type Tag = { key: string; label: string; remove: () => void };
  const tags: Tag[] = [];

  for (const slug of state.merchant) {
    tags.push({
      key: `m:${slug}`,
      label: merchants.find((m) => m.slug === slug)?.name ?? slug,
      remove: () => go({ merchant: state.merchant.filter((s) => s !== slug) }),
    });
  }
  for (const loc of state.location) {
    tags.push({
      key: `l:${loc}`,
      label: loc,
      remove: () => go({ location: state.location.filter((v) => v !== loc) }),
    });
  }
  for (const ln of state.line) {
    tags.push({
      key: `ln:${ln}`,
      label: LINE_OPTIONS.find((o) => o.value === ln)?.label ?? ln,
      remove: () => go({ line: state.line.filter((v) => v !== ln) }),
    });
  }
  if (state.keyword.trim()) {
    tags.push({
      key: "kw",
      label: `关键词「${state.keyword.trim()}」`,
      remove: () => go({ keyword: "" }),
    });
  }
  if (state.in_stock) tags.push({ key: "in_stock", label: "仅看有货", remove: () => go({ in_stock: undefined }) });
  if (state.price_drop) tags.push({ key: "price_drop", label: "降价中", remove: () => go({ price_drop: undefined }) });
  if (state.lowest_price) tags.push({ key: "lowest_price", label: "史低价", remove: () => go({ lowest_price: undefined }) });
  if (state.recent_restock)
    tags.push({ key: "recent_restock", label: "最新补货", remove: () => go({ recent_restock: undefined }) });
  if (state.recommended) tags.push({ key: "recommended", label: "精选推荐", remove: () => go({ recommended: undefined }) });
  if (state.min_price !== undefined || state.max_price !== undefined) {
    tags.push({
      key: "price",
      label: `年付 $${state.min_price ?? 0} - ${state.max_price ?? "∞"}`,
      remove: () => go({ min_price: undefined, max_price: undefined }),
    });
  }
  if (state.min_ram !== undefined)
    tags.push({ key: "ram", label: `内存 ${state.min_ram}G+`, remove: () => go({ min_ram: undefined }) });
  if (state.min_cpu !== undefined)
    tags.push({ key: "cpu", label: `CPU ${state.min_cpu} 核+`, remove: () => go({ min_cpu: undefined }) });
  if (state.min_bw !== undefined)
    tags.push({
      key: "bw",
      label: `流量 ${state.min_bw >= 1000 ? `${state.min_bw / 1000}TB` : `${state.min_bw}GB`}+`,
      remove: () => go({ min_bw: undefined }),
    });
  if (state.min_port !== undefined)
    tags.push({
      key: "port",
      label: `带宽 ${state.min_port >= 1000 ? `${state.min_port / 1000}Gbps` : `${state.min_port}Mbps`}+`,
      remove: () => go({ min_port: undefined }),
    });

  if (tags.length === 0) return null;

  return (
    <div className="flex flex-wrap items-center gap-1.5 pt-1">
      <span className="text-[11px] font-medium text-slate-400 dark:text-slate-500">已选条件：</span>
      {tags.map((t) => (
        <span
          key={t.key}
          className="border-border bg-slate-50 text-foreground inline-flex items-center gap-1 rounded-lg border px-2 py-0.5 text-xs font-medium transition-colors hover:bg-slate-100 dark:bg-slate-800/60 dark:hover:bg-slate-800"
        >
          <span>{t.label}</span>
          <button
            type="button"
            onClick={t.remove}
            title={`移除筛选条件：${t.label}`}
            aria-label={`移除筛选条件：${t.label}`}
            className="ml-0.5 cursor-pointer text-slate-400 hover:text-slate-700 dark:hover:text-slate-200"
          >
            ✕
          </button>
        </span>
      ))}
      <button
        type="button"
        onClick={reset}
        className="ml-1 cursor-pointer text-xs font-bold text-rose-600 transition-colors hover:text-rose-700 dark:text-rose-400"
      >
        清空全部
      </button>
    </div>
  );
}
