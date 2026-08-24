import type { Metadata } from "next";
import Link from "next/link";
import { BellRing, Tag } from "lucide-react";

import { getEvents, type EventItem } from "@/lib/api/endpoints";
import { currencySymbol, formatCycle, timeAgo } from "@/lib/format";
import { productHref } from "@/lib/slug";

export const metadata: Metadata = {
  title: "降价与补货动态",
  description:
    "VPS 降价榜与补货动态：近 24/72/168 小时内降幅最大的套餐排行与最新补货事件流。",
  alternates: { canonical: "/deals" },
};

const WINDOWS = [24, 72, 168] as const;
const TABS = [
  { type: "PRICE_DROP" as const, label: "降价榜" },
  { type: "RESTOCK" as const, label: "补货动态" },
];

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

function hrefFor(type: string, hours: number): string {
  return `/deals?type=${type}&hours=${hours}`;
}

function DropRow({ ev }: { ev: EventItem }) {
  const p = ev.product;
  const oldPrice = ev.old_value != null ? Number(ev.old_value) : null;
  return (
    <li className="flex min-w-0 items-center gap-3 py-3">
      <span className="bg-destructive/10 text-destructive w-14 shrink-0 rounded-md px-1.5 py-1 text-center text-xs font-bold tabular-nums">
        -{ev.drop_percent?.toFixed(1) ?? "?"}%
      </span>
      <div className="min-w-0 flex-1">
        <Link
          href={productHref(p.id, p.name)}
          className="block truncate font-medium hover:text-sky-700 hover:underline dark:hover:text-sky-400"
        >
          {p.name}
        </Link>
        <p className="text-muted-foreground mt-0.5 truncate text-xs">
          {p.merchant.name} · {p.location || "—"}
        </p>
      </div>
      <div className="shrink-0 text-right">
        <p className="text-sm font-bold whitespace-nowrap tabular-nums">
          {currencySymbol(p.currency)}
          {(ev.new_value ? Number(ev.new_value) : p.price).toFixed(2)}
          <span className="text-muted-foreground text-xs font-normal">{formatCycle(p.billing_cycle)}</span>
        </p>
        {oldPrice != null && (
          <p className="text-muted-foreground text-xs whitespace-nowrap line-through tabular-nums">
            {currencySymbol(p.currency)}
            {oldPrice.toFixed(2)}
          </p>
        )}
      </div>
    </li>
  );
}

function RestockRow({ ev }: { ev: EventItem }) {
  const p = ev.product;
  return (
    <li className="flex min-w-0 items-center gap-3 py-3">
      <span
        aria-hidden
        className={`h-2 w-2 shrink-0 rounded-full ${p.in_stock ? "bg-emerald-500" : "bg-muted-foreground/40"}`}
      />
      <div className="min-w-0 flex-1">
        <Link
          href={productHref(p.id, p.name)}
          className="block truncate font-medium hover:text-sky-700 hover:underline dark:hover:text-sky-400"
        >
          {p.name}
        </Link>
        <p className="text-muted-foreground mt-0.5 truncate text-xs">
          {p.merchant.name} · {p.location || "—"}
          {!p.in_stock && " · 现已缺货"}
        </p>
      </div>
      <time className="text-muted-foreground shrink-0 text-xs tabular-nums" dateTime={ev.created_at}>
        {timeAgo(ev.created_at)}
      </time>
    </li>
  );
}

export default async function DealsPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const typeParam = first(sp.type);
  const type: "PRICE_DROP" | "RESTOCK" =
    typeParam === "RESTOCK" ? "RESTOCK" : "PRICE_DROP";
  const hoursParam = Number(first(sp.hours));
  const hours = (WINDOWS as readonly number[]).includes(hoursParam) ? hoursParam : 24;

  let items: EventItem[] = [];
  let error = false;
  try {
    items = (await getEvents(type, hours)).items;
  } catch {
    error = true;
  }

  return (
    <div className="mx-auto w-full max-w-4xl px-4 py-6">
      <header className="mb-5">
        <h1 className="text-xl font-bold tracking-tight lg:text-2xl">降价与补货动态</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          基于扫描期捕获的库存与价格变动事件；同一套餐在去重窗口内的重复事件只记一次。
        </p>
      </header>

      {/* 双榜 Tab + 时间窗口（URL 状态，可分享） */}
      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
        <nav aria-label="动态类型" className="flex gap-1 rounded-lg border p-1">
          {TABS.map((t) => (
            <Link
              key={t.type}
              href={hrefFor(t.type, hours)}
              aria-current={type === t.type ? "page" : undefined}
              className={`inline-flex items-center gap-1.5 rounded-md px-3 py-1.5 text-sm transition-colors ${
                type === t.type ? "bg-primary text-primary-foreground" : "hover:bg-muted"
              }`}
            >
              {t.type === "PRICE_DROP" ? (
                <Tag aria-hidden className="h-3.5 w-3.5" />
              ) : (
                <BellRing aria-hidden className="h-3.5 w-3.5" />
              )}
              {t.label}
            </Link>
          ))}
        </nav>

        <nav aria-label="时间范围" className="flex gap-1">
          {WINDOWS.map((w) => (
            <Link
              key={w}
              href={hrefFor(type, w)}
              aria-current={hours === w ? "true" : undefined}
              className={`rounded-md px-2.5 py-1.5 text-sm transition-colors ${
                hours === w ? "bg-muted font-medium" : "text-muted-foreground hover:bg-muted"
              }`}
            >
              {w}h
            </Link>
          ))}
        </nav>
      </div>

      <section aria-label={`${type === "PRICE_DROP" ? "降价榜" : "补货动态"}（近 ${hours} 小时）`} className="bg-card rounded-xl border px-4">
        {error ? (
          <div role="alert" className="border-destructive/30 bg-destructive/5 text-destructive my-6 rounded-lg p-6 text-center text-sm">
            动态数据加载失败，请稍后重试。
          </div>
        ) : items.length === 0 ? (
          <p className="text-muted-foreground py-12 text-center text-sm">
            近 {hours} 小时内暂无{type === "PRICE_DROP" ? "降价" : "补货"}事件。
          </p>
        ) : (
          <ul className="divide-y divide-border">
            {items.map((ev) =>
              type === "PRICE_DROP" ? <DropRow key={ev.id} ev={ev} /> : <RestockRow key={ev.id} ev={ev} />,
            )}
          </ul>
        )}
      </section>

      <footer className="text-muted-foreground mt-4 text-xs leading-relaxed">
        价格为商家原币标价；「降价」以相邻两次成功抓取的价格差计算，
        解析失败或价格为 0 的快照不参与判定。
      </footer>
    </div>
  );
}
