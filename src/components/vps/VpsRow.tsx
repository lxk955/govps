import Link from "next/link";
import { ArrowUpRight } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CompareButton } from "@/components/compare/compare-button";
import { WatchButton } from "@/components/vps/watch-button";
import type { ProductListItem } from "@/lib/api/endpoints";
import { formatCycle, formatPrice, timeAgo } from "@/lib/format";
import { productHref } from "@/lib/slug";

/** 桌面表格式行形态（VpsCard/VpsRow 双形态之一）。仅 lg+ 视口渲染显示。 */

export function VpsRow({ product }: { product: ProductListItem }) {
  const p = product;
  return (
    <tr className={p.in_stock ? "" : "opacity-70"}>
      <td className="px-3 py-3 align-top">
        <p className="text-muted-foreground text-xs">{p.merchant.name}</p>
        <p className="mt-0.5 max-w-[16rem] xl:max-w-[24rem] break-words text-sm font-medium">
          {p.recommended && (
            <Badge className="mr-1.5 align-middle bg-amber-500 text-white hover:bg-amber-500">
              精选
            </Badge>
          )}
          <Link href={productHref(p.id, p.name)} className="hover:text-sky-700 hover:underline dark:hover:text-sky-400">
            {p.name}
          </Link>
        </p>
        {(p.price_dropped || p.is_lowest_price || p.is_recent_restock) && (
          <p className="mt-1 flex flex-wrap gap-1 text-xs">
            {p.price_dropped && (
              <span className="rounded bg-red-50 px-1 text-red-700 dark:bg-red-950 dark:text-red-300">
                降价中
              </span>
            )}
            {p.is_lowest_price && (
              <span className="rounded bg-purple-50 px-1 text-purple-700 dark:bg-purple-950 dark:text-purple-300">
                史低价
              </span>
            )}
            {p.is_recent_restock && (
              <span className="rounded bg-emerald-50 px-1 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
                近期补货
              </span>
            )}
          </p>
        )}
      </td>
      <td className="text-muted-foreground px-3 py-3 text-sm break-words align-top">
        {[p.cpu_cores != null ? `${p.cpu_cores}C` : null, p.ram_gb != null ? `${p.ram_gb}G` : null, p.disk_gb != null ? `${p.disk_gb}G 盘` : null]
          .filter(Boolean)
          .join(" / ")}
      </td>
      <td className="text-muted-foreground px-3 py-3 text-sm align-top">
        {p.bandwidth_gb != null ? (p.bandwidth_gb < 0 ? "不限" : `${(p.bandwidth_gb / 1024).toFixed(1)}T`) : "—"}
        {p.port_mbps != null && <span className="block">{p.port_mbps}M</span>}
      </td>
      <td className="px-3 py-3 text-sm break-words align-top">
        {p.location || "—"}
        {p.line_tags.length > 0 && (
          <span className="text-muted-foreground block text-xs">{p.line_tags.join(" / ")}</span>
        )}
      </td>
      <td className="px-3 py-3 align-top">
        <span
          className={
            p.in_stock
              ? "inline-flex items-center gap-1 text-sm font-medium text-emerald-700 dark:text-emerald-400"
              : "text-muted-foreground inline-flex items-center gap-1 text-sm"
          }
        >
          <span aria-hidden className={p.in_stock ? "h-2 w-2 rounded-full bg-emerald-500" : "bg-muted-foreground h-2 w-2 rounded-full"} />
          {p.in_stock ? "有货" : "缺货"}
        </span>
        <span className="text-muted-foreground mt-0.5 block text-xs">
          {p.hot_score != null && `推荐 ${p.hot_score}`}
        </span>
      </td>
      <td className="px-3 py-3 text-right align-top">
        <p className="text-sm font-bold whitespace-nowrap">
          {formatPrice(p.price, p.currency)}
          <span className="text-muted-foreground text-xs font-normal">{formatCycle(p.billing_cycle)}</span>
        </p>
        <p className="text-muted-foreground text-xs whitespace-nowrap">
          折年 ≈ {formatPrice(p.price_yearly, p.currency)}
          {p.currency !== "USD" && p.price_yearly_converted != null && (
            <span className="ml-1">≈ ${p.price_yearly_converted.toFixed(2)}</span>
          )}
        </p>
        <p className="text-muted-foreground mt-0.5 text-xs whitespace-nowrap">{timeAgo(p.updated_at)}更新</p>
      </td>
      <td className="px-3 py-3 text-right align-top">
        <div className="flex items-center justify-end gap-1.5">
          <CompareButton productId={p.id} size="icon" />
          <WatchButton productId={p.id} size="icon" />
          <Button asChild size="sm" disabled={!p.in_stock}>
            <a href={`/go/${p.id}?src=list`} aria-disabled={!p.in_stock} className={p.in_stock ? "" : "pointer-events-none"}>
              购买
              <ArrowUpRight aria-hidden className="h-4 w-4" />
            </a>
          </Button>
        </div>
      </td>
    </tr>
  );
}
