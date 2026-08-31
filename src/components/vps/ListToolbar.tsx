"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";
import { LayoutGrid, List, Search, X } from "lucide-react";

import { MobileFilterSheet } from "@/components/vps/mobile-filter-sheet";
import type { MerchantOption } from "@/components/vps/FilterControls";
import { LINE_OPTIONS, type ListQueryState, withParams } from "@/lib/query-state";
import { cn } from "@/lib/utils";

/**
 * 列表顶部工具栏（1:1 复刻旧站 ProductList.vue 顶部两行）：
 * 第 1 行 搜索框 + 视图切换；第 2 行 快捷筛选胶囊排（移动端横向滚动）。
 *
 * 未复刻「❤️ 我的关注」胶囊：该筛选依赖登录凭证，而列表页为 RSC 服务端取数，
 * 请求不携带用户 token，直接下发会被后端判 401（详见交付说明）。
 */

const POPULAR_LOCATIONS = [
  { name: "洛杉矶", flag: "🇺🇸" },
  { name: "东京", flag: "🇯🇵" },
  { name: "香港", flag: "🇭🇰" },
  { name: "新加坡", flag: "🇸🇬" },
] as const;

/**
 * 顶部快捷胶囊只放最常用的三条优质线路：胶囊排同时承载快捷筛选与热门机房，
 * 全量 7 档会让顶部过宽、移动端横向滚动过长。
 * 其余线路（CN2 GT / 普通 BGP / 国际线路）由搜索框模糊匹配或 URL 参数筛选；
 * 已选条件栏仍从完整 LINE_OPTIONS 取中文名，故此处只过滤渲染、不裁剪常量。
 */
const QUICK_LINE_KEYS: readonly string[] = ["cn2_gia", "9929", "cmin2"];

const QUICK_FILTERS = [
  { key: "recent_restock", label: "最新补货", icon: "⚡", tone: "emerald" },
  { key: "lowest_price", label: "史低价", icon: "🏷️", tone: "rose" },
  { key: "price_drop", label: "降价中", icon: "📉", tone: "orange" },
  { key: "in_stock", label: "仅看有货", icon: "🟢", tone: "emerald" },
] as const;

const TONE_ON: Record<string, string> = {
  emerald:
    "border-emerald-500 bg-emerald-50 text-emerald-700 ring-2 ring-emerald-100 dark:bg-emerald-950/50 dark:text-emerald-300 dark:ring-emerald-900/50",
  rose: "border-rose-500 bg-rose-50 text-rose-600 ring-2 ring-rose-100 dark:bg-rose-950/50 dark:text-rose-300 dark:ring-rose-900/50",
  orange:
    "border-orange-500 bg-orange-50 text-orange-600 ring-2 ring-orange-100 dark:bg-orange-950/50 dark:text-orange-300 dark:ring-orange-900/50",
  blue: "border-blue-500 bg-blue-50 text-blue-700 ring-2 ring-blue-100 dark:bg-blue-950/50 dark:text-blue-300 dark:ring-blue-900/50",
  indigo:
    "border-indigo-500 bg-indigo-50 text-indigo-600 ring-2 ring-indigo-100 dark:bg-indigo-950/50 dark:text-indigo-300 dark:ring-indigo-900/50",
};

/*
 * px-2.5（仅移动端）：390px 视口下 4 个胶囊约需 342px，可用 358px，但实测
 * 第 4 个仍差约 5px 被 flex-wrap 挤到下一行，一组变两行（共 5 排）。收窄
 * 内边距后四个能排进一行，才符合「按类别三排」的预期；桌面端恢复 px-3。
 */
const CHIP_BASE =
  "shrink-0 flex cursor-pointer items-center gap-1 rounded-xl border px-2 py-1 text-xs font-bold transition-all sm:px-3";
const CHIP_OFF =
  "border-border bg-slate-50/70 text-slate-600 hover:border-slate-300 hover:bg-slate-100 dark:bg-slate-800/60 dark:text-slate-300 dark:hover:bg-slate-800";

function Chip({
  active,
  tone,
  onClick,
  children,
}: {
  active: boolean;
  tone: keyof typeof TONE_ON;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(CHIP_BASE, active ? TONE_ON[tone] : CHIP_OFF)}
    >
      {children}
    </button>
  );
}

export function ListToolbar({
  state,
  merchants,
  total,
}: {
  state: ListQueryState;
  merchants: MerchantOption[];
  /** 当前筛选结果数，移动端抽屉底部需要展示 */
  total: number;
}) {
  const router = useRouter();
  const [kw, setKw] = useState(state.keyword);

  useEffect(() => setKw(state.keyword), [state.keyword]);

  const go = (patch: Partial<ListQueryState>) => {
    router.push(`/vps?${withParams(state, patch)}`);
  };

  const toggleIn = (key: "location" | "line", value: string) => {
    const cur = state[key];
    go({ [key]: cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value] });
  };

  const setView = (view: "card" | "list") => go({ view });

  const submitKeyword = () => go({ keyword: kw });

  return (
    <div className="mb-5 flex flex-col gap-3">
      {/* 第 1 行：左侧快捷搜索框，右侧视图切换 */}
      <div className="flex flex-wrap items-center justify-between gap-3">
        <form
          role="search"
          onSubmit={(e) => {
            e.preventDefault();
            submitKeyword();
          }}
          className="relative min-w-[220px] flex-1 sm:max-w-md"
        >
          <span className="pointer-events-none absolute inset-y-0 left-0 flex items-center pl-3 text-slate-400">
            <Search aria-hidden className="h-4 w-4" />
          </span>
          <input
            type="text"
            value={kw}
            onChange={(e) => setKw(e.target.value)}
            aria-label="搜索套餐、机房、线路或配置"
            placeholder="搜索套餐、机房、线路或配置..."
            className="border-border bg-slate-50/70 focus:border-blue-500 focus:ring-blue-100 text-foreground placeholder:text-slate-400 w-full rounded-xl border py-1.5 pr-8 pl-9 text-base transition-all focus:bg-white focus:ring-2 focus:outline-none sm:text-sm dark:bg-slate-800/60 dark:focus:bg-slate-900"
          />
          {kw && (
            <button
              type="button"
              onClick={() => {
                setKw("");
                go({ keyword: "" });
              }}
              title="清空搜索"
              aria-label="清空搜索"
              className="absolute inset-y-0 right-0 flex cursor-pointer items-center pr-2.5 text-slate-400 hover:text-slate-600"
            >
              <X aria-hidden className="h-4 w-4" />
            </button>
          )}
        </form>

        <div className="flex items-center gap-2">
          <MobileFilterSheet state={state} merchants={merchants} total={total} />
          {/*
           * 视图切换仅 md 及以上显示：小屏只给卡片视图。列表（表格）形态在
           * 窄屏下需要横向滚动，体验不如卡片；少一个出错的交互面也更稳。
           */}
          <div
            role="group"
            aria-label="视图模式"
            className="border-border hidden items-center gap-0.5 rounded-xl border bg-slate-50/70 p-0.5 md:flex dark:bg-slate-800/60"
          >
            <button
              type="button"
              onClick={() => setView("card")}
              aria-pressed={state.view === "card"}
              aria-label="卡片视图"
              title="卡片视图"
              className={cn(
                "cursor-pointer rounded-lg px-2 py-1 transition-colors",
                state.view === "card"
                  ? "bg-card text-blue-600 shadow-sm dark:text-blue-400"
                  : "text-slate-500 hover:text-slate-700 dark:text-slate-400",
              )}
            >
              <LayoutGrid aria-hidden className="h-4 w-4" />
            </button>
            <button
              type="button"
              onClick={() => setView("list")}
              aria-pressed={state.view === "list"}
              aria-label="列表视图"
              title="列表视图"
              className={cn(
                "cursor-pointer rounded-lg px-2 py-1 transition-colors",
                state.view === "list"
                  ? "bg-card text-blue-600 shadow-sm dark:text-blue-400"
                  : "text-slate-500 hover:text-slate-700 dark:text-slate-400",
              )}
            >
              <List aria-hidden className="h-4 w-4" />
            </button>
          </div>
        </div>
      </div>

      {/*
       * 第 2 行：快捷筛选胶囊。
       * 移动端按类别分三排（快捷筛选 / 热门机房 / 线路）：原先是单行横向滚动，
       * 右侧胶囊在屏外看不见。桌面端仍合并为一行，组间用竖线分隔。
       * 各组用 flex-wrap 兜底，避免窄屏横向溢出（AGENTS.md 要求）。
       */}
      <div className="flex flex-col gap-1.5 py-0.5 md:flex-row md:items-center md:gap-2">
        <div className="flex flex-wrap items-center gap-1 sm:gap-2">
          {QUICK_FILTERS.map((f) => (
            <Chip
              key={f.key}
              tone={f.tone}
              active={Boolean(state[f.key])}
              onClick={() => go({ [f.key]: !state[f.key] } as Partial<ListQueryState>)}
            >
              <span aria-hidden>{f.icon}</span> {f.label}
            </Chip>
          ))}
        </div>

        <div aria-hidden className="bg-border hidden h-4 w-px shrink-0 md:block" />

        <div className="flex flex-wrap items-center gap-1 sm:gap-2">
          {POPULAR_LOCATIONS.map((loc) => (
            <Chip
              key={loc.name}
              tone="blue"
              active={state.location.includes(loc.name)}
              onClick={() => toggleIn("location", loc.name)}
            >
              <span aria-hidden>{loc.flag}</span> {loc.name}
            </Chip>
          ))}
        </div>

        <div aria-hidden className="bg-border hidden h-4 w-px shrink-0 md:block" />

        <div className="flex flex-wrap items-center gap-1 sm:gap-2">
          {LINE_OPTIONS.filter((opt) => QUICK_LINE_KEYS.includes(opt.value)).map((opt) => (
            <Chip
              key={opt.value}
              tone="indigo"
              active={state.line.includes(opt.value)}
              onClick={() => toggleIn("line", opt.value)}
            >
              {opt.label}
            </Chip>
          ))}
        </div>
      </div>
    </div>
  );
}
