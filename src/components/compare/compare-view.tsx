"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowUpRight, Loader2, Scale, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { useCurrency } from "@/components/currency-provider";
import {
  getProductDetail,
  type ProductDetail,
} from "@/lib/api/endpoints";
import {
  COMPARE_MAX,
  getCompareIds,
  useCompareIds,
} from "@/lib/compare-store";
import { fmtPort, fmtSize, fmtTraffic, lineBadgeClass, lineInfo } from "@/lib/display";
import { cycleLabel, formatPrice } from "@/lib/format";
import { productHref } from "@/lib/slug";
import { cn } from "@/lib/utils";

/**
 * 对比视图（P6）：≤4 款并排。
 * 价格行跟随全站币种开关；跨套餐可比口径是「折年价」
 * （人民币/美元按汇率，原币模式下用美元横比）。
 */

const CARRIERS = ["电信", "联通", "移动"] as const;

type CompareSlot = {
  id: number;
  product: ProductDetail | null;
  error: boolean;
};

function carrierRoute(
  rows: string[],
  carrier: (typeof CARRIERS)[number],
): string {
  const prefix = `${carrier}:`;
  const hit = rows.find((r) => r.startsWith(prefix));
  return hit ? hit.slice(prefix.length) : "普通直连";
}

export function CompareView({ initialIds }: { initialIds: number[] }) {
  const router = useRouter();
  const { ids, ready, remove, clear, replace } = useCompareIds();
  const { mode, convert } = useCurrency();
  const [slots, setSlots] = useState<CompareSlot[]>([]);
  const [loading, setLoading] = useState(false);

  // 首次挂载：URL ids 优先（可分享），否则取 localStorage 工作集并镜像到 URL
  useEffect(() => {
    if (!ready) return;
    if (initialIds.length > 0) {
      replace(initialIds);
    } else {
      const stored = getCompareIds();
      if (stored.length > 0) router.replace(`/compare?ids=${stored.join(",")}`);
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [ready]);

  const effective = ready ? (initialIds.length > 0 ? [...new Set(initialIds)].slice(0, COMPARE_MAX) : ids) : [];

  const load = useCallback(async (list: number[]) => {
    setLoading(true);
    const results = await Promise.all(
      list.map(async (id): Promise<CompareSlot> => {
        try {
          return { id, product: await getProductDetail(id), error: false };
        } catch {
          return { id, product: null, error: true };
        }
      }),
    );
    setSlots(results);
    setLoading(false);
  }, []);

  const retryOne = async (id: number) => {
    try {
      const product = await getProductDetail(id);
      setSlots((prev) => prev.map((s) => (s.id === id ? { id, product, error: false } : s)));
    } catch {
      setSlots((prev) => prev.map((s) => (s.id === id ? { id, product: null, error: true } : s)));
    }
  };

  useEffect(() => {
    if (!ready) return;
    if (effective.length > 0) void load(effective);
    else setSlots([]);
  }, [ready, effective.join(",")]); // eslint-disable-line react-hooks/exhaustive-deps

  const removeOne = (id: number) => {
    remove(id);
    const rest = effective.filter((x) => x !== id);
    router.replace(rest.length > 0 ? `/compare?ids=${rest.join(",")}` : "/compare");
  };

  const clearAll = () => {
    clear();
    router.replace("/compare");
  };

  const loaded = slots.filter((s): s is CompareSlot & { product: ProductDetail } => s.product != null);
  const failedCount = slots.filter((s) => s.error).length;
  const lineById = new Map(loaded.map((s) => [s.product.id, lineInfo(s.product)]));
  const yearlyLabel = "折年价";
  const comparableHint =
    mode === "original"
      ? "原币标价币种不同时不可直接横比，跨套餐请看折年价（按美元换算）。"
      : "原币或付款周期不同时不可直接横比，跨套餐请看折年价（按当前币种换算）。";

  return (
    <>
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight lg:text-2xl">套餐对比</h1>
          <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
            最多对比 {COMPARE_MAX} 款。{comparableHint}
          </p>
          {failedCount > 0 && (
            <p className="mt-1.5 text-xs text-rose-600 dark:text-rose-400">
              有 {failedCount} 款套餐加载失败，可点列头重试或移除。
            </p>
          )}
          {/* 3 款及以上在窄屏放不下，提示可横向滑动（2 款时刚好放得下，无需提示） */}
          {slots.length >= 3 && (
            <p className="text-muted-foreground mt-1.5 text-xs sm:hidden">
              ← 左右滑动查看全部 {slots.length} 款
            </p>
          )}
        </div>
        {slots.length > 0 && (
          <Button variant="ghost" size="sm" className="text-muted-foreground" onClick={clearAll}>
            清空对比
          </Button>
        )}
      </header>

      {loading ? (
        <div className="bg-card text-muted-foreground flex items-center justify-center gap-2 rounded-xl border p-12 text-sm" role="status">
          <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
          加载对比数据…
        </div>
      ) : effective.length === 0 ? (
        <div className="flex flex-col items-center gap-3 rounded-xl border border-dashed p-12 text-center">
          <Scale aria-hidden className="text-muted-foreground h-8 w-8" />
          <p className="text-muted-foreground text-sm">还没有选择要对比的套餐。</p>
          <p className="text-muted-foreground max-w-md text-xs leading-relaxed">
            在 VPS 列表或详情页点击「对比」按钮，最多加入 {COMPARE_MAX} 款，
            即可在此并排比较价格、配置、机房、三网线路与库存。
          </p>
          <Button asChild size="sm">
            <Link href="/">去列表选择</Link>
          </Button>
        </div>
      ) : (
        <div className="overflow-x-auto pb-2">
          {/*
            不在 table 上设 min-w：那会连「只有 2 款」也撑到固定宽度，
            白白多出横向滚动。宽度交给各列自己的 min-width 控制——
            首列 80px（min-w-20）+ 每款 144px（min-w-36）：
              2 款 = 368px < 390px 视口 → 无需滚动（移动端最常见的用法）
              3–4 款 = 512 / 656px → 横向滑动，首列 sticky 保证始终知道在看哪一项。
          */}
          {/*
            table-fixed：列宽由下方 w-* 决定，不被长套餐名撑开。
            只写 min-w 不够——那只是下限，长产品名仍会把列顶宽，导致 2 款也要滚动。
          */}
          <table className="w-full table-fixed border-separate border-spacing-0 text-left">
            <caption className="sr-only">VPS 套餐对比表</caption>
            <thead>
              <tr>
                <th scope="col" className="bg-background sticky left-0 z-10 w-20 min-w-20 p-1.5 align-bottom sm:w-24 sm:p-2">
                  <span className="text-muted-foreground text-xs font-normal">对比项</span>
                </th>
                {slots.map((s) => (
                  <th key={s.id} scope="col" className="w-36 p-1.5 align-bottom sm:w-44 sm:p-2">
                    {s.product ? (
                      <div className="bg-card rounded-t-xl border border-b-0 p-2 sm:p-3">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-muted-foreground truncate text-xs">{s.product.merchant.name}</p>
                          <button
                            type="button"
                            aria-label={`移除 ${s.product.name}`}
                            className="text-muted-foreground hover:text-foreground shrink-0"
                            onClick={() => removeOne(s.product!.id)}
                          >
                            <X aria-hidden className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <Link
                          href={productHref(s.product.id, s.product.name)}
                          className="mt-0.5 block break-words text-xs font-semibold hover:text-sky-700 hover:underline sm:text-sm dark:hover:text-sky-400"
                        >
                          {s.product.name}
                        </Link>
                      </div>
                    ) : (
                      <div className="bg-card rounded-t-xl border border-b-0 border-dashed p-2 sm:p-3">
                        <div className="flex items-start justify-between gap-2">
                          <p className="text-muted-foreground truncate text-xs">套餐 #{s.id}</p>
                          <button
                            type="button"
                            aria-label={`移除套餐 ${s.id}`}
                            className="text-muted-foreground hover:text-foreground shrink-0"
                            onClick={() => removeOne(s.id)}
                          >
                            <X aria-hidden className="h-3.5 w-3.5" />
                          </button>
                        </div>
                        <p className="mt-1 text-xs font-medium text-rose-600 dark:text-rose-400">加载失败</p>
                        <button
                          type="button"
                          onClick={() => void retryOne(s.id)}
                          className="mt-1 text-[11px] font-semibold text-blue-600 hover:underline dark:text-blue-400"
                        >
                          重试
                        </button>
                      </div>
                    )}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="text-sm">
              <Row label="价格">
                <SlotCells slots={slots}>
                  {(p) => {
                    const info = convert(p.price, p.currency);
                    return (
                      <>
                        <span className="font-bold tabular-nums">{info.displayPrice}</span>
                        <span className="text-muted-foreground text-xs">
                          /{cycleLabel(p.billing_cycle)}
                        </span>
                        {info.isConverted && (
                          <div className="text-muted-foreground mt-0.5 text-[11px]" title={info.rateNotice}>
                            原 {info.originalPrice}
                          </div>
                        )}
                      </>
                    );
                  }}
                </SlotCells>
              </Row>
              <Row label={yearlyLabel}>
                <SlotCells slots={slots}>
                  {(p) => {
                    const yearly = yearlyComparable(p, mode, convert);
                    return (
                      <>
                        <span className="font-bold text-sky-800 tabular-nums dark:text-sky-300">
                          {yearly.display}
                          <span className="text-muted-foreground text-xs font-normal">/年</span>
                        </span>
                        {yearly.original && (
                          <div className="text-muted-foreground mt-0.5 text-[11px]">
                            原 {yearly.original}/年
                          </div>
                        )}
                      </>
                    );
                  }}
                </SlotCells>
              </Row>
              <Row label="库存">
                <SlotCells slots={slots}>
                  {(p) =>
                    p.in_stock ? (
                      <Badge className="gap-1 bg-emerald-600 text-white hover:bg-emerald-600">有货</Badge>
                    ) : (
                      <Badge variant="secondary" className="gap-1 text-muted-foreground">缺货</Badge>
                    )
                  }
                </SlotCells>
              </Row>
              <Row label="CPU">
                <SlotCells slots={slots} className="tabular-nums">
                  {(p) => (p.cpu_cores != null ? `${p.cpu_cores} 核` : "—")}
                </SlotCells>
              </Row>
              <Row label="内存">
                <SlotCells slots={slots} className="tabular-nums">
                  {(p) => (p.ram_gb != null ? fmtSize(p.ram_gb) : "—")}
                </SlotCells>
              </Row>
              <Row label="硬盘">
                <SlotCells slots={slots} className="tabular-nums">
                  {(p) => (p.disk_gb != null ? fmtSize(p.disk_gb) : "—")}
                </SlotCells>
              </Row>
              <Row label="月流量">
                <SlotCells slots={slots} className="tabular-nums">
                  {(p) => (p.bandwidth_gb == null ? "—" : fmtTraffic(p.bandwidth_gb))}
                </SlotCells>
              </Row>
              <Row label="带宽">
                <SlotCells slots={slots} className="tabular-nums">
                  {(p) => (p.port_mbps != null ? fmtPort(p.port_mbps) : "—")}
                </SlotCells>
              </Row>
              <Row label="机房">
                <SlotCells slots={slots}>{(p) => p.location || "—"}</SlotCells>
              </Row>
              {CARRIERS.map((carrier) => (
                <Row key={carrier} label={carrier}>
                  <SlotCells slots={slots}>
                    {(p) => (
                      <CarrierRoute route={carrierRoute(lineById.get(p.id)?.carrierRows ?? [], carrier)} />
                    )}
                  </SlotCells>
                </Row>
              ))}
              <Row label="购买">
                <SlotCells slots={slots} className="pb-3 sm:pb-4">
                  {(p) =>
                    p.in_stock ? (
                      <a
                        href={`/go/${p.id}?src=compare`}
                        rel="nofollow sponsored noopener"
                        className="inline-flex items-center gap-0.5 rounded-md border px-2.5 py-1.5 text-sm transition-colors hover:bg-muted"
                      >
                        前往购买
                        <ArrowUpRight aria-hidden className="h-3.5 w-3.5" />
                      </a>
                    ) : (
                      <span className="text-muted-foreground text-xs">缺货不可购买</span>
                    )
                  }
                </SlotCells>
              </Row>
            </tbody>
          </table>
        </div>
      )}

      {slots.length > 0 && (
        <footer className="text-muted-foreground mt-4 border-t pt-3 text-xs leading-relaxed">
          {slots.length < 2 && (
            <>已选 {slots.length} 款，再加 {2 - slots.length} 款即可对比。{" "}</>
          )}
          {comparableHint} 汇率来源见
          {" "}<Link href="/api/rates" className="underline underline-offset-2">/api/rates</Link>。
        </footer>
      )}
    </>
  );
}

function SlotCells({
  slots,
  className,
  children,
}: {
  slots: CompareSlot[];
  className?: string;
  children: (p: ProductDetail) => React.ReactNode;
}) {
  return (
    <>
      {slots.map((s) => (
        <td
          key={s.id}
          className={cn("bg-card border-r border-t p-2 last:border-r-0 sm:p-3", className)}
        >
          {s.product ? children(s.product) : <span className="text-muted-foreground text-xs">—</span>}
        </td>
      ))}
    </>
  );
}

function yearlyComparable(
  p: ProductDetail,
  mode: "original" | "CNY" | "USD",
  convert: ReturnType<typeof useCurrency>["convert"],
): { display: string; original: string | null } {
  const originalYearly = formatPrice(p.price_yearly, p.currency);
  if (mode === "original") {
    if (p.currency === "USD") {
      return { display: originalYearly, original: null };
    }
    if (p.price_yearly_converted != null) {
      return { display: formatPrice(p.price_yearly_converted, "USD"), original: originalYearly };
    }
    return { display: "暂无汇率", original: originalYearly };
  }
  const info = convert(p.price_yearly, p.currency);
  return {
    display: info.displayPrice,
    original: info.isConverted ? info.originalPrice : null,
  };
}

function Row({
  label,
  children,
}: {
  label: string;
  children: React.ReactNode;
}) {
  return (
    <tr>
      <th scope="row" className="bg-background sticky left-0 z-10 p-1.5 align-top text-xs font-normal sm:p-2">
        <span className="text-muted-foreground">{label}</span>
      </th>
      {children}
    </tr>
  );
}

const MUTED_ROUTES = new Set(["普通直连", "国际BGP"]);

function CarrierRoute({ route }: { route: string }) {
  if (MUTED_ROUTES.has(route)) {
    return <span className="text-muted-foreground text-xs">{route}</span>;
  }
  return (
    <span
      className={`inline-block max-w-full truncate rounded border px-1.5 py-0.5 text-xs font-medium ${lineBadgeClass(route)}`}
      title={route}
    >
      {route}
    </span>
  );
}
