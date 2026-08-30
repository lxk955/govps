import Link from "next/link";

import { CompareButton } from "@/components/compare/compare-button";
import { CardBuyZone } from "@/components/vps/card-buy-zone";
import { CardTagRow } from "@/components/vps/card-tag-row";
import { WatchButton } from "@/components/vps/watch-button";
import type { ProductListItem, WatchPrefs } from "@/lib/api/endpoints";
import { lineInfo, lineTierClass, shortName } from "@/lib/display";
import { productHref } from "@/lib/slug";
import { cn } from "@/lib/utils";

/**
 * 卡片形态（1:1 复刻旧站 components/ProductCard.vue 的四段式版式）：
 * 头部三行槽 → 2×2 规格矩阵 → 机房与三网线路 → 吸底价格与购买。
 * 各段高度固定（24/20/22/44/68px），保证网格中多卡片严格对齐。
 */

function fmtSize(gb: number | null): string {
  return `${gb || 1}G`;
}

function fmtBw(gb: number | null | undefined): string {
  if (gb == null) return "按量";
  if (gb < 0) return "无限";
  return gb >= 1000 ? `${(gb / 1000).toFixed(gb % 1000 === 0 ? 0 : 1)}T` : `${gb}G`;
}

function fmtPort(mbps: number | null | undefined): string {
  if (!mbps) return "";
  return mbps >= 1000 ? `${(mbps / 1000).toFixed(mbps % 1000 === 0 ? 0 : 1)}Gbps` : `${mbps}Mbps`;
}

export function VpsCard({
  product,
  watchHydrate = false,
  unwatchPrefs,
  onUnwatched,
}: {
  product: ProductListItem;
  /** 挂载后查询真实关注状态（关注页用；列表网格不逐个查询） */
  watchHydrate?: boolean;
  /** 转发给 WatchButton：取关时随撤销事件带上原偏好（关注页用） */
  unwatchPrefs?: WatchPrefs;
  /** 转发给 WatchButton：取关后回调（关注页用于刷新列表） */
  onUnwatched?: () => void;
}) {
  const p = product;
  const line = lineInfo(p);

  // 规格条目：固定 4 项（CPU / 内存 / 硬盘 / 流量@带宽），形成严格 2×2 矩阵
  const specItems = [
    p.cpu_cores != null ? `${p.cpu_cores} 核 CPU` : "CPU —",
    p.ram_gb != null ? `${fmtSize(p.ram_gb)} 内存` : "内存 —",
    p.disk_gb != null ? `${fmtSize(p.disk_gb)} 硬盘` : "硬盘 —",
    p.port_mbps
      ? `${fmtBw(p.bandwidth_gb)}@${fmtPort(p.port_mbps)}`
      : `${fmtBw(p.bandwidth_gb)} 流量`,
  ];

  const tooltip = p.recommend_reasons.length
    ? `${p.name}\n💡 推荐特点：${p.recommend_reasons.join(" · ")}`
    : p.name;

  return (
    <article className="border-border bg-card group flex h-full flex-col gap-3 rounded-2xl border p-4 shadow-sm transition-all duration-200 hover:-translate-y-0.5 hover:shadow-md">
      {/* 1. 头部区域：3 行全宽专属槽（商家/操作、套餐标题、标签徽章流） */}
      <div className="flex flex-col gap-1.5">
        <div className="flex h-6 items-center justify-between gap-2">
          <span className="text-muted-foreground truncate text-xs font-semibold tracking-wide uppercase">
            {p.merchant.name}
          </span>
          <div className="flex shrink-0 items-center gap-0.5">
            <CompareButton productId={p.id} size="xs" />
            <WatchButton
              productId={p.id}
              size="xs"
              hydrate={watchHydrate}
              unwatchPrefs={unwatchPrefs}
              onUnwatched={onUnwatched}
            />
          </div>
        </div>

        {/* 第 2 行：套餐标题（整行通栏，单行截断） */}
        <Link
          href={productHref(p.id, p.name)}
          title={tooltip}
          className="text-foreground hover:text-blue-600 dark:hover:text-blue-400 block h-5 truncate text-[14.5px] leading-snug font-bold transition-colors"
        >
          {shortName(p)}
        </Link>

        {/* 第 3 行：标签槽 */}
        <CardTagRow product={p} />
      </div>

      {/* 2. 硬件与网络规格区：严格 2×2 四格矩阵，高度 44px 绝对统一 */}
      <div className="grid h-11 grid-cols-2 gap-x-2 gap-y-1.5 text-[12px] font-medium text-slate-600 dark:text-slate-400">
        {specItems.map((s) => (
          <div key={s} className="flex items-center gap-1.5 truncate" title={s}>
            <span aria-hidden className="h-1.5 w-1.5 shrink-0 rounded-full bg-blue-500/70" />
            <span className="truncate">{s}</span>
          </div>
        ))}
      </div>

      {/* 3. 机房与线路区域：顶层机房+线路等级，底层三网明细微胶囊 */}
      <div className="bg-muted/50 border-border/60 flex h-[68px] flex-col justify-between rounded-xl border p-2 text-xs">
        <div className="flex h-[18px] min-w-0 items-center">
          <div
            className="flex shrink-0 items-center gap-1 truncate text-[11.5px] font-bold text-slate-800 dark:text-slate-200"
            title={p.location || "多机房 (可迁)"}
          >
            <svg
              aria-hidden
              className="h-3.5 w-3.5 shrink-0 text-blue-500"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
            >
              <path
                strokeLinecap="round"
                strokeLinejoin="round"
                d="M17.657 16.657L13.414 20.9a1.998 1.998 0 01-2.827 0l-4.244-4.243a8 8 0 1111.314 0z"
              />
              <path strokeLinecap="round" strokeLinejoin="round" d="M15 11a3 3 0 11-6 0 3 3 0 016 0z" />
            </svg>
            <span className="truncate">{p.location || "多机房 (可迁)"}</span>
          </div>
          <div className="flex min-w-0 flex-1 items-center justify-center">
            <span className={cn("shrink-0 text-[10.5px]", lineTierClass(line.level))}>
              {line.tier}
            </span>
          </div>
        </div>

        <div className="border-border/60 grid grid-cols-3 gap-1 border-t pt-1 text-[10px]">
          {line.carrierRows.map((r) => (
            <div
              key={r}
              title={r}
              className="border-border bg-card text-muted-foreground truncate rounded border px-1 py-0.5 text-center font-medium"
            >
              {r}
            </div>
          ))}
        </div>
      </div>

      {/* 4. 底部价格与购买区：严格吸底对齐 */}
      <CardBuyZone product={p} />
    </article>
  );
}
