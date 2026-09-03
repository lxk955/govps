"use client";

import { useEffect, useState } from "react";
import { useRouter } from "next/navigation";

import type { MerchantOption } from "@/components/vps/FilterControls";
import { merchantTitle, sortMerchants } from "@/lib/merchant-notes";
import { LINE_OPTIONS, type ListQueryState, withParams } from "@/lib/query-state";
import { cn } from "@/lib/utils";

/**
 * 移动端筛选内容：分组折叠（Accordion）+ 点选即生效。
 *
 * 刻意与桌面端侧栏（FilterControls）分开实现：桌面侧栏展开后内容近 850px，
 * 原样塞进底部抽屉要滚动很久。这里改为分组折叠、默认只展开「服务商」，
 * 几乎无需滚动（AGENTS.md：移动端应调整信息密度与交互形态，而不是把
 * 桌面布局缩小）。
 *
 * 折叠用原生 <details>/<summary>：零依赖、语义化、键盘可访问。
 *
 * 点选即生效：选择后直接 push 应用筛选，不再需要「应用」按钮。价格区间是
 * 自由输入，无法逐字符应用，因此改为失焦或回车时提交。
 */

function Section({
  title,
  hint,
  defaultOpen = false,
  children,
}: {
  title: string;
  hint?: React.ReactNode;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  return (
    <details open={defaultOpen} className="border-border group border-b last:border-b-0">
      <summary className="flex cursor-pointer items-center justify-between gap-2 py-3.5 text-sm font-bold select-none">
        <span>{title}</span>
        <span className="flex items-center gap-2">
          {hint}
          <svg
            aria-hidden
            className="text-muted-foreground h-4 w-4 shrink-0 transition-transform group-open:rotate-180"
            viewBox="0 0 24 24"
            fill="none"
            stroke="currentColor"
            strokeWidth="2"
          >
            <path strokeLinecap="round" strokeLinejoin="round" d="m19.5 8.25-7.5 7.5-7.5-7.5" />
          </svg>
        </span>
      </summary>
      <div className="pb-4">{children}</div>
    </details>
  );
}

function Chip({
  active,
  onClick,
  children,
}: {
  active: boolean;
  onClick: () => void;
  children: React.ReactNode;
}) {
  return (
    <button
      type="button"
      aria-pressed={active}
      onClick={onClick}
      className={cn(
        "cursor-pointer rounded-full border px-3 py-1.5 text-xs font-semibold transition-colors",
        active
          ? "border-blue-600 bg-blue-600 text-white"
          : "border-border bg-card text-foreground hover:border-blue-300 dark:hover:border-blue-500",
      )}
    >
      {children}
    </button>
  );
}

/** 规格下拉：变更即时应用。移动端 select 用 text-base（16px）避免 iOS 聚焦缩放 */
function SpecSelect({
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
    <label className="flex items-center justify-between gap-3 py-2">
      <span className="text-muted-foreground text-xs font-medium">{label}</span>
      <select
        value={value ?? ""}
        onChange={(e) => onChange(e.target.value === "" ? undefined : Number(e.target.value))}
        className="border-border bg-card text-foreground rounded-lg border px-2 py-1.5 text-base focus:border-blue-500 focus:outline-none"
      >
        {options.map((o) => (
          <option key={o.value} value={o.value}>
            {o.label}
          </option>
        ))}
      </select>
    </label>
  );
}

const NUM_OPTIONS = {
  ram: [
    { value: "", label: "不限" },
    { value: "0.5", label: "512MB+" },
    { value: "1", label: "1GB+" },
    { value: "2", label: "2GB+" },
    { value: "4", label: "4GB+" },
    { value: "8", label: "8GB+" },
  ],
  cpu: [
    { value: "", label: "不限" },
    { value: "1", label: "1 核+" },
    { value: "2", label: "2 核+" },
    { value: "4", label: "4 核+" },
    { value: "8", label: "8 核+" },
  ],
  port: [
    { value: "", label: "不限" },
    { value: "100", label: "100Mbps+" },
    { value: "500", label: "500Mbps+" },
    { value: "1000", label: "1Gbps+" },
  ],
  bw: [
    { value: "", label: "不限" },
    { value: "500", label: "500GB+" },
    { value: "1000", label: "1TB+" },
    { value: "2000", label: "2TB+" },
  ],
};

export function MobileFilterContent({
  state,
  merchants,
}: {
  state: ListQueryState;
  merchants: MerchantOption[];
}) {
  const router = useRouter();
  const [priceMin, setPriceMin] = useState(state.min_price?.toString() ?? "");
  const [priceMax, setPriceMax] = useState(state.max_price?.toString() ?? "");

  // 点选即生效后 state 会变化，同步回本地输入值
  useEffect(() => setPriceMin(state.min_price?.toString() ?? ""), [state.min_price]);
  useEffect(() => setPriceMax(state.max_price?.toString() ?? ""), [state.max_price]);

  const apply = (patch: Partial<ListQueryState>) => {
    router.push(`/?${withParams(state, patch)}`);
  };

  const toggleIn = (key: "merchant" | "line", value: string) => {
    const cur = state[key];
    apply({ [key]: cur.includes(value) ? cur.filter((v) => v !== value) : [...cur, value] });
  };

  /** 价格是自由输入，失焦/回车才提交，避免逐字符触发跳转 */
  const commitPrice = () => {
    const min = priceMin === "" ? undefined : Number(priceMin);
    const max = priceMax === "" ? undefined : Number(priceMax);
    if (min === state.min_price && max === state.max_price) return;
    apply({ min_price: min, max_price: max });
  };

  const specCount = [
    state.min_ram,
    state.min_cpu,
    state.min_port,
    state.min_bw,
    state.min_price,
    state.max_price,
  ].filter((v) => v !== undefined).length;

  return (
    <div>
      {/* 1. 服务商（默认展开） */}
      <Section
        title="服务商"
        defaultOpen
        hint={
          state.merchant.length > 0 ? (
            <span className="rounded-full bg-blue-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
              {state.merchant.length}
            </span>
          ) : null
        }
      >
        <div className="flex flex-wrap gap-2">
          <Chip active={state.merchant.length === 0} onClick={() => apply({ merchant: [] })}>
            全部
          </Chip>
          {sortMerchants(merchants).map((m) => (
            <Chip
              key={m.slug}
              active={state.merchant.includes(m.slug)}
              onClick={() => toggleIn("merchant", m.slug)}
            >
              {m.name}
              <span className="ml-1 opacity-60">{m.in_stock_count ?? m.count ?? 0}</span>
            </Chip>
          ))}
        </div>
        {/* 悬停/长按提示沿用商家简介（桌面端同样的信息） */}
        <p className="sr-only">
          {sortMerchants(merchants)
            .map((m) => merchantTitle(m.slug, m.name))
            .join("；")}
        </p>
      </Section>

      {/* 2. 价格区间 */}
      <Section
        title="价格区间（年付 $）"
        hint={
          state.min_price !== undefined || state.max_price !== undefined ? (
            <span className="rounded-full bg-blue-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
              已设
            </span>
          ) : null
        }
      >
        <div className="flex items-center gap-2">
          <input
            type="number"
            min="0"
            inputMode="numeric"
            value={priceMin}
            onChange={(e) => setPriceMin(e.target.value)}
            onBlur={commitPrice}
            onKeyDown={(e) => e.key === "Enter" && commitPrice()}
            placeholder="最低"
            aria-label="最低年付价格（美元）"
            className="border-border bg-card w-full rounded-lg border px-3 py-2 text-base focus:border-blue-500 focus:outline-none"
          />
          <span className="text-muted-foreground">-</span>
          <input
            type="number"
            min="0"
            inputMode="numeric"
            value={priceMax}
            onChange={(e) => setPriceMax(e.target.value)}
            onBlur={commitPrice}
            onKeyDown={(e) => e.key === "Enter" && commitPrice()}
            placeholder="最高"
            aria-label="最高年付价格（美元）"
            className="border-border bg-card w-full rounded-lg border px-3 py-2 text-base focus:border-blue-500 focus:outline-none"
          />
        </div>
      </Section>

      {/* 3. 硬件配置 */}
      <Section
        title="硬件配置"
        hint={
          specCount > 0 ? (
            <span className="rounded-full bg-blue-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
              {specCount}
            </span>
          ) : null
        }
      >
        <SpecSelect
          label="最低内存"
          value={state.min_ram}
          options={NUM_OPTIONS.ram}
          onChange={(v) => apply({ min_ram: v })}
        />
        <SpecSelect
          label="最低 CPU"
          value={state.min_cpu}
          options={NUM_OPTIONS.cpu}
          onChange={(v) => apply({ min_cpu: v })}
        />
        <SpecSelect
          label="最低带宽"
          value={state.min_port}
          options={NUM_OPTIONS.port}
          onChange={(v) => apply({ min_port: v })}
        />
        <SpecSelect
          label="最低月流量"
          value={state.min_bw}
          options={NUM_OPTIONS.bw}
          onChange={(v) => apply({ min_bw: v })}
        />
        {specCount > 0 && (
          <button
            type="button"
            onClick={() =>
              apply({
                min_ram: undefined,
                min_cpu: undefined,
                min_port: undefined,
                min_bw: undefined,
                min_price: undefined,
                max_price: undefined,
              })
            }
            className="text-muted-foreground hover:text-foreground mt-1 text-xs underline"
          >
            清除配置条件
          </button>
        )}
      </Section>

      {/* 4. 线路 */}
      <Section
        title="线路"
        hint={
          state.line.length > 0 ? (
            <span className="rounded-full bg-blue-600 px-1.5 py-0.5 text-[10px] font-bold text-white">
              {state.line.length}
            </span>
          ) : null
        }
      >
        <div className="flex flex-wrap gap-2">
          {LINE_OPTIONS.map((opt) => (
            <Chip
              key={opt.value}
              active={state.line.includes(opt.value)}
              onClick={() => toggleIn("line", opt.value)}
            >
              {opt.label}
            </Chip>
          ))}
        </div>
      </Section>
    </div>
  );
}
