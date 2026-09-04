import Link from "next/link";

import { CardTagRow } from "@/components/vps/card-tag-row";
import { RowBuyZone } from "@/components/vps/row-buy-zone";
import type { ProductListItem, WatchPrefs } from "@/lib/api/endpoints";
import { fmtPort, fmtTraffic, lineInfo, lineTierClass, shortName } from "@/lib/display";
import { productHref } from "@/lib/slug";

/**
 * 行形态（1:1 复刻旧站 components/ProductRow.vue）。
 *
 * 注意与旧结构的差异：旧站并非 <table>，而是**每行一张独立圆角卡片**纵向堆叠，
 * 除产品列外各列固定宽度严格对齐；移动端纵向堆叠为两段（信息 / 价格+操作）。
 */

export function VpsRow({
  product,
  unwatchPrefs,
  onUnwatched,
  watchHydrate = false,
}: {
  product: ProductListItem;
  /** 转发给行内 WatchButton：取关时随撤销事件带上原偏好（关注页列表视图用） */
  unwatchPrefs?: WatchPrefs;
  /** 转发给行内 WatchButton：取关后回调（关注页用于刷新列表） */
  onUnwatched?: () => void;
  /** 挂载后查询真实关注状态（关注页必须开启，否则已关注条目显示成空心形） */
  watchHydrate?: boolean;
}) {
  const p = product;
  const line = lineInfo(p);

  // 规格列：固定两行，行高一致
  const specTop =
    [
      p.cpu_cores ? `${p.cpu_cores} 核` : "",
      p.ram_gb ? `${p.ram_gb}G 内存` : "",
      p.disk_gb ? `${p.disk_gb}G 硬盘` : "",
    ]
      .filter(Boolean)
      .join(" · ") || "—";
  const specBottom = (() => {
    if (p.bandwidth_gb == null && !p.port_mbps) return "—";
    const bw =
      p.bandwidth_gb == null ? "" : p.bandwidth_gb < 0 ? "不限流量/月" : `${fmtTraffic(p.bandwidth_gb)} 流量`;
    const port = p.port_mbps ? fmtPort(p.port_mbps) : "";
    if (bw && port) return `${bw}@${port}`;
    return bw || `${port} 带宽`;
  })();

  const tooltip = p.recommend_reasons.length
    ? `${p.name}\n💡 推荐特点：${p.recommend_reasons.join(" · ")}`
    : p.name;

  return (
    <div className="border-border bg-card group flex flex-col gap-2.5 overflow-hidden rounded-xl border px-4 py-3 shadow-sm transition-all hover:shadow-md sm:flex-row sm:items-center sm:gap-3">
      {/* 产品：商家 + 标签 + 套餐名 */}
      <div className="min-w-0 flex-1">
        <div className="flex flex-wrap items-center gap-1.5 text-xs">
          <span className="text-muted-foreground truncate font-medium">{p.merchant.name}</span>
          <CardTagRow product={p} variant="row" />
        </div>
        <Link
          href={productHref(p.id, p.name)}
          title={tooltip}
          className="text-foreground hover:text-blue-600 dark:hover:text-blue-400 mt-1 block truncate text-[15px] leading-snug font-bold"
        >
          {shortName(p)}
        </Link>
        {/* 移动端摘要行：桌面端隐藏的规格与库存状态在这里补齐 */}
        <div className="mt-1 flex items-center gap-1.5 text-[11px] text-slate-400 lg:hidden dark:text-slate-500">
          <span className="truncate">{specTop}</span>
          <span
            className={`ml-auto inline-flex shrink-0 items-center gap-1 rounded px-1.5 py-px text-[10px] font-medium ${
              p.in_stock
                ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                : "bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-300"
            }`}
          >
            {p.in_stock ? "有货" : "缺货"}
          </span>
        </div>
      </div>

      {/* 规格：固定 220px，两行 */}
      <div
        className="hidden w-[220px] shrink-0 leading-5 lg:block"
        title={`${specTop}；${specBottom}`}
      >
        <div className="text-muted-foreground truncate text-[13px]">{specTop}</div>
        <div className="truncate text-xs text-slate-400 dark:text-slate-500">{specBottom}</div>
      </div>

      {/* 机房：固定 100px */}
      <div className="hidden w-[100px] shrink-0 md:block">
        {p.location ? (
          <span
            title={p.location}
            className="bg-muted text-muted-foreground inline-block max-w-full truncate rounded px-1.5 py-0.5 text-xs"
          >
            {p.location}
          </span>
        ) : (
          <span className="text-xs text-slate-300 dark:text-slate-600">—</span>
        )}
      </div>

      {/* 线路：固定 168px，两层（总结等级 + 电/联/移三行明细） */}
      <div className="hidden w-[168px] shrink-0 leading-[1.35] lg:block">
        <div className="text-[13px]">
          <span className={lineTierClass(line.level)}>{line.tier}</span>
        </div>
        <div className="mt-0.5 space-y-px text-[11px] text-slate-400 dark:text-slate-500">
          {line.carrierRows.map((r) => (
            <div key={r} className="truncate">
              {r}
            </div>
          ))}
        </div>
      </div>

      {/* 价格 + 状态 + 操作 */}
      <RowBuyZone
        product={p}
        unwatchPrefs={unwatchPrefs}
        onUnwatched={onUnwatched}
        watchHydrate={watchHydrate}
      />
    </div>
  );
}
