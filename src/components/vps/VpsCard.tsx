import Link from "next/link";
import { ArrowUpRight, CheckCircle2, Clock3, Flame, Tag, XCircle } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CompareButton } from "@/components/compare/compare-button";
import { WatchButton } from "@/components/vps/watch-button";
import type { ProductListItem } from "@/lib/api/endpoints";
import { formatCycle, formatPrice, timeAgo } from "@/lib/format";
import { productHref } from "@/lib/slug";
import { cn } from "@/lib/utils";

/** 移动端卡片形态（VpsCard/VpsRow 双形态之一，refactor-plan P1 交付物）。 */

function StockBadge({ inStock }: { inStock: boolean }) {
  return inStock ? (
    <Badge className="gap-1 bg-emerald-600 text-white hover:bg-emerald-600">
      <CheckCircle2 aria-hidden className="h-3 w-3" />
      有货
    </Badge>
  ) : (
    <Badge variant="secondary" className="gap-1 text-muted-foreground">
      <XCircle aria-hidden className="h-3 w-3" />
      缺货
    </Badge>
  );
}

export function VpsCard({ product }: { product: ProductListItem }) {
  const p = product;
  const specs = [
    p.cpu_cores != null ? `${p.cpu_cores} 核` : null,
    p.ram_gb != null ? `${p.ram_gb}G 内存` : null,
    p.disk_gb != null ? `${p.disk_gb}G 盘` : null,
    p.bandwidth_gb != null
      ? p.bandwidth_gb < 0
        ? "不限流量"
        : `${p.bandwidth_gb >= 1000 ? `${(p.bandwidth_gb / 1000).toFixed(p.bandwidth_gb % 1000 === 0 ? 0 : 1)}T` : `${p.bandwidth_gb}G`} 流量`
      : null,
    p.port_mbps != null ? `${p.port_mbps}M 带宽` : null,
  ].filter(Boolean) as string[];

  return (
    <article
      className={cn(
        "bg-card text-card-foreground flex min-w-0 flex-col gap-3 rounded-xl border p-4",
        !p.in_stock && "opacity-80",
      )}
    >
      <header className="flex min-w-0 items-start justify-between gap-2">
        <div className="min-w-0">
          <p className="text-muted-foreground text-xs">{p.merchant.name}</p>
          <h3 className="mt-0.5 break-words text-sm leading-snug font-semibold">
            {p.recommended && (
              <Badge className="mr-1.5 align-middle bg-amber-500 text-white hover:bg-amber-500">
                精选
              </Badge>
            )}
            <Link href={productHref(p.id, p.name)} className="hover:text-sky-700 hover:underline dark:hover:text-sky-400">
              {p.name}
            </Link>
          </h3>
        </div>
        <StockBadge inStock={p.in_stock} />
      </header>

      <ul className="text-muted-foreground flex flex-wrap gap-x-2 gap-y-1 text-xs" aria-label="配置规格">
        {specs.map((s) => (
          <li key={s} className="bg-muted rounded px-1.5 py-0.5">
            {s}
          </li>
        ))}
        {p.location && <li className="bg-muted rounded px-1.5 py-0.5">{p.location}</li>}
        {p.line_tags.slice(0, 3).map((t) => (
          <li key={t} className="rounded bg-sky-100 px-1.5 py-0.5 text-sky-800 dark:bg-sky-950 dark:text-sky-300">
            {t}
          </li>
        ))}
      </ul>

      {(p.price_dropped || p.is_recent_restock || p.is_lowest_price) && (
        <ul className="flex flex-wrap gap-1.5 text-xs" aria-label="动态标记">
          {p.price_dropped && (
            <li className="flex items-center gap-1 rounded bg-red-50 px-1.5 py-0.5 text-red-700 dark:bg-red-950 dark:text-red-300">
              <Tag aria-hidden className="h-3 w-3" /> 降价中
            </li>
          )}
          {p.is_lowest_price && (
            <li className="flex items-center gap-1 rounded bg-purple-50 px-1.5 py-0.5 text-purple-700 dark:bg-purple-950 dark:text-purple-300">
              史低价
            </li>
          )}
          {p.is_recent_restock && (
            <li className="flex items-center gap-1 rounded bg-emerald-50 px-1.5 py-0.5 text-emerald-700 dark:bg-emerald-950 dark:text-emerald-300">
              <Clock3 aria-hidden className="h-3 w-3" /> 近期补货
            </li>
          )}
        </ul>
      )}

      {p.hot_score != null && p.hot_score > 0 && (
        <p className="text-muted-foreground flex items-center gap-1 text-xs">
          <Flame aria-hidden className="h-3.5 w-3.5 text-orange-500" />
          推荐指数 {p.hot_score}
          {p.recommend_reasons.length > 0 && (
            <span className="truncate">· {p.recommend_reasons[0]}</span>
          )}
        </p>
      )}

      <footer className="mt-auto flex items-end justify-between gap-2">
        <div className="min-w-0">
          <p className="text-base font-bold">
            {formatPrice(p.price, p.currency)}
            <span className="text-muted-foreground text-xs font-normal">
              {formatCycle(p.billing_cycle)}
            </span>
          </p>
          <p className="text-muted-foreground text-xs">
            折年 ≈ {formatPrice(p.price_yearly, p.currency)}
            {p.currency !== "USD" && p.price_yearly_converted != null && (
              <span className="ml-1">≈ ${p.price_yearly_converted.toFixed(2)}</span>
            )}
            <span className="mx-1">·</span>
            <time dateTime={p.updated_at ?? undefined}>{timeAgo(p.updated_at)}</time>更新
          </p>
        </div>
        <div className="flex shrink-0 items-center gap-1.5">
          <CompareButton productId={p.id} size="icon" />
          <WatchButton productId={p.id} size="icon" />
          <Button asChild size="sm" disabled={!p.in_stock}>
            <a
              href={`/go/${p.id}?src=list`}
              aria-disabled={!p.in_stock}
              className={cn(!p.in_stock && "pointer-events-none")}
            >
              购买
              <ArrowUpRight aria-hidden className="h-4 w-4" />
            </a>
          </Button>
        </div>
      </footer>
    </article>
  );
}
