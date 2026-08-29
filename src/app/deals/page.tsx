import type { Metadata } from "next";
import Link from "next/link";

import { DealsRangeSelect } from "@/components/deals/deals-range-select";
import { WatchButton } from "@/components/vps/watch-button";
import { getEvents, type EventItem } from "@/lib/api/endpoints";
import { lineInfo, lineTierClass, shortName } from "@/lib/display";
import { currencySymbol, cycleLabel, formatPrice, timeAgo } from "@/lib/format";
import { productHref } from "@/lib/slug";
import { cn } from "@/lib/utils";

export const metadata: Metadata = {
  title: "降价与补货动态",
  description:
    "VPS 降价榜与补货动态：近 24/72/168 小时内降幅最大的套餐排行与最新补货事件流。",
  alternates: { canonical: "/deals" },
};

const WINDOWS = [24, 72, 168];

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

function first(v: string | string[] | undefined): string | undefined {
  return Array.isArray(v) ? v[0] : v;
}

export default async function DealsPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const type = first(sp.type) === "RESTOCK" ? "RESTOCK" : "PRICE_DROP";
  const hoursRaw = Number(first(sp.hours));
  const hours = WINDOWS.includes(hoursRaw) ? hoursRaw : 24;
  const isDrop = type === "PRICE_DROP";

  let items: EventItem[] = [];
  let error = false;
  try {
    items = (await getEvents(type, hours)).items;
  } catch {
    error = true;
  }

  return (
    <div className="border-border bg-card rounded-xl border p-5 shadow-sm">
      <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold">{isDrop ? "降价榜" : "补货动态"}</h1>
          <p className="text-muted-foreground text-sm">
            {isDrop ? "按降幅排序，越大越靠前" : "最新补货在前，手快有手慢无"}
          </p>
        </div>

        <div className="flex items-center gap-2">
          {/* 双榜切换（URL 状态，可分享） */}
          <div className="border-border bg-card flex rounded-lg border p-0.5 text-sm">
            <Link
              href={`/deals?type=PRICE_DROP&hours=${hours}`}
              aria-current={isDrop ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 transition-colors",
                isDrop ? "bg-orange-500 text-white" : "text-slate-500 hover:text-slate-700 dark:text-slate-400",
              )}
            >
              降价榜
            </Link>
            <Link
              href={`/deals?type=RESTOCK&hours=${hours}`}
              aria-current={!isDrop ? "page" : undefined}
              className={cn(
                "rounded-md px-3 py-1.5 transition-colors",
                !isDrop ? "bg-emerald-600 text-white" : "text-slate-500 hover:text-slate-700 dark:text-slate-400",
              )}
            >
              补货动态
            </Link>
          </div>
          <DealsRangeSelect type={type} hours={hours} />
        </div>
      </div>

      {error ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-red-100 bg-red-50 p-12 text-center dark:border-red-900 dark:bg-red-950/30">
          <div className="text-3xl">📡</div>
          <p className="text-sm font-medium text-red-600 dark:text-red-400">
            动态数据加载失败，请稍后重试。
          </p>
          <Link
            href={`/deals?type=${type}&hours=${hours}`}
            className="rounded-xl bg-red-600 px-4 py-1.5 text-xs font-bold text-white transition-colors hover:bg-red-700"
          >
            重新加载
          </Link>
        </div>
      ) : items.length === 0 ? (
        <div className="border-border rounded-xl border border-dashed p-12 text-center text-sm text-slate-400 dark:text-slate-500">
          近 {hours} 小时内暂无{isDrop ? "降价" : "补货"}事件。
        </div>
      ) : (
        <div className="space-y-3">
          {items.map((ev, i) => {
            const prod = ev.product;
            const sym = currencySymbol(prod.currency);
            const line = lineInfo(prod);
            return (
              <div
                key={ev.id}
                className="border-border bg-card flex flex-wrap items-center gap-3 rounded-xl border p-4"
              >
                {/* 排名 / 图标 */}
                <div className="w-8 shrink-0 text-center">
                  {isDrop ? (
                    <span
                      className={cn(
                        "text-lg font-bold",
                        i < 3 ? "text-orange-500" : "text-slate-300 dark:text-slate-600",
                      )}
                    >
                      {i + 1}
                    </span>
                  ) : (
                    <span
                      aria-hidden
                      className="inline-block h-2.5 w-2.5 rounded-full bg-emerald-500"
                    />
                  )}
                </div>

                {/* 产品信息 */}
                <div className="min-w-0 flex-1">
                  <Link
                    href={productHref(prod.id, prod.name)}
                    title={prod.name}
                    className="text-foreground hover:text-blue-600 dark:hover:text-blue-400 block truncate font-medium"
                  >
                    {shortName(prod)}
                  </Link>
                  <div className="mt-0.5 flex flex-wrap items-center gap-1.5 text-xs text-slate-400 dark:text-slate-500">
                    <span>{prod.merchant.name}</span>
                    {prod.location && (
                      <span className="bg-muted rounded px-1.5 py-0.5">{prod.location}</span>
                    )}
                    <span className={lineTierClass(line.level)}>{line.tier}</span>
                    <span className="text-slate-300 dark:text-slate-600">·</span>
                    <span>{line.carrierRows.join(" ")}</span>
                  </div>
                </div>

                {/* 变化信息 */}
                <div className="shrink-0 text-right">
                  {isDrop ? (
                    <>
                      {ev.drop_percent != null && (
                        <span className="rounded bg-orange-100 px-2 py-0.5 text-sm font-bold text-orange-600 dark:bg-orange-950/60 dark:text-orange-300">
                          ↓ {ev.drop_percent}%
                        </span>
                      )}
                      <div className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                        <s>
                          {sym}
                          {formatPrice(Number(ev.old_value ?? 0), prod.currency)}
                        </s>{" "}
                        →{" "}
                        <b className="text-slate-700 dark:text-slate-300">
                          {sym}
                          {formatPrice(Number(ev.new_value ?? prod.price), prod.currency)}
                        </b>
                      </div>
                    </>
                  ) : (
                    <>
                      <span className="rounded bg-emerald-100 px-2 py-0.5 text-sm font-medium text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
                        补货
                      </span>
                      <div className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                        {sym}
                        {formatPrice(prod.price, prod.currency)}/{cycleLabel(prod.billing_cycle)}
                      </div>
                    </>
                  )}
                  <div className="mt-1 text-xs text-slate-400 dark:text-slate-500">
                    {timeAgo(ev.created_at)}
                  </div>
                </div>

                {/* 当前库存状态 + 关注入口（缺货时正是「到货提醒」的最佳转化时机） */}
                <div className="flex shrink-0 items-center gap-2">
                  <span
                    className={cn(
                      "rounded px-1.5 py-0.5 text-xs font-medium",
                      prod.in_stock
                        ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                        : "bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-300",
                    )}
                  >
                    {prod.in_stock ? "有货" : "缺货"}
                  </span>
                  <WatchButton productId={prod.id} size="icon" />
                </div>
              </div>
            );
          })}
        </div>
      )}
    </div>
  );
}
