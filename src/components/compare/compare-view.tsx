"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { useRouter } from "next/navigation";
import { ArrowUpRight, Loader2, Scale, X } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import {
  getProductDetail,
  type ProductDetail,
} from "@/lib/api/endpoints";
import {
  COMPARE_MAX,
  getCompareIds,
  useCompareIds,
} from "@/lib/compare-store";
import { lineBadgeClass, lineInfo } from "@/lib/display";
import { currencySymbol, cycleLabel } from "@/lib/format";
import { productHref } from "@/lib/slug";

/**
 * 对比视图（P6）：≤4 款并排。
 * - 数据口径：原价（供应商原币/周期）为主位；USD 换算价与 P5 接口一致；
 *   跨套餐比较以「折年 ≈ USD」为唯一可比口径，原价行明确标注不可直接横比。
 * - 移动端：整表横向滚动（AGENTS.md 大表格条款）。
 */

const CARRIERS = ["电信", "联通", "移动"] as const;

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
  const [items, setItems] = useState<(ProductDetail | null)[]>([]);
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
      list.map((id) => getProductDetail(id).catch(() => null)),
    );
    setItems(results);
    setLoading(false);
  }, []);

  useEffect(() => {
    if (!ready) return;
    if (effective.length > 0) void load(effective);
    else setItems([]);
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

  const loaded = items.filter((x): x is ProductDetail => x != null);
  const lineById = new Map(loaded.map((p) => [p.id, lineInfo(p)]));

  return (
    <>
      <header className="mb-4 flex flex-wrap items-end justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight lg:text-2xl">套餐对比</h1>
          <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
            最多对比 {COMPARE_MAX} 款；不同币种/付款周期的「原价」不可直接横比，
            跨套餐比较请以「折年 ≈ USD」为准（换算口径见页尾）。
          </p>
          {/* 3 款及以上在窄屏放不下，提示可横向滑动（2 款时刚好放得下，无需提示） */}
          {loaded.length >= 3 && (
            <p className="text-muted-foreground mt-1.5 text-xs sm:hidden">
              ← 左右滑动查看全部 {loaded.length} 款
            </p>
          )}
        </div>
        {loaded.length > 0 && (
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
            <Link href="/vps">去列表选择</Link>
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
                {loaded.map((p) => (
                  <th key={p.id} scope="col" className="w-36 p-1.5 align-bottom sm:w-44 sm:p-2">
                    <div className="bg-card rounded-t-xl border border-b-0 p-2 sm:p-3">
                      <div className="flex items-start justify-between gap-2">
                        <p className="text-muted-foreground truncate text-xs">{p.merchant.name}</p>
                        <button
                          type="button"
                          aria-label={`移除 ${p.name}`}
                          className="text-muted-foreground hover:text-foreground shrink-0"
                          onClick={() => removeOne(p.id)}
                        >
                          <X aria-hidden className="h-3.5 w-3.5" />
                        </button>
                      </div>
                      <Link
                        href={productHref(p.id, p.name)}
                        className="mt-0.5 block break-words text-xs font-semibold hover:text-sky-700 hover:underline sm:text-sm dark:hover:text-sky-400"
                      >
                        {p.name}
                      </Link>
                    </div>
                  </th>
                ))}
              </tr>
            </thead>
            <tbody className="text-sm">
              <Row label="价格（原币标价）" hint="各套餐自身标价，币种/周期不同不可直接横比">
                {loaded.map((p) => (
                  <td key={p.id} className="bg-card border-r border-t p-2 last:border-r-0 sm:p-3">
                    <span className="font-bold tabular-nums">
                      {currencySymbol(p.currency)}{p.price.toFixed(2)}
                    </span>
                    <span className="text-muted-foreground text-xs">
                      /{cycleLabel(p.billing_cycle)}
                    </span>
                  </td>
                ))}
              </Row>
              <Row label="折年价（原币）">
                {loaded.map((p) => (
                  <td key={p.id} className="bg-card border-r border-t p-2 last:border-r-0 sm:p-3 tabular-nums">
                    {currencySymbol(p.currency)}{p.price_yearly.toFixed(2)}<span className="text-muted-foreground text-xs">/年</span>
                  </td>
                ))}
              </Row>
              <Row label="折年 ≈ USD" hint="跨套餐可比口径；换算汇率见页尾说明">
                {loaded.map((p) => (
                  <td key={p.id} className="bg-card border-r border-t p-2 last:border-r-0 sm:p-3">
                    {p.currency !== "USD" && p.price_yearly_converted != null ? (
                      <span className="font-bold text-sky-800 tabular-nums dark:text-sky-300">
                        ${p.price_yearly_converted.toFixed(2)}<span className="text-muted-foreground text-xs font-normal">/年</span>
                      </span>
                    ) : p.currency === "USD" ? (
                      <span className="text-muted-foreground text-xs">即原价（USD）</span>
                    ) : (
                      <span className="text-muted-foreground text-xs">暂无汇率</span>
                    )}
                  </td>
                ))}
              </Row>
              <Row label="库存">
                {loaded.map((p) => (
                  <td key={p.id} className="bg-card border-r border-t p-2 last:border-r-0 sm:p-3">
                    {p.in_stock ? (
                      <Badge className="gap-1 bg-emerald-600 text-white hover:bg-emerald-600">有货</Badge>
                    ) : (
                      <Badge variant="secondary" className="gap-1 text-muted-foreground">缺货</Badge>
                    )}
                  </td>
                ))}
              </Row>
              <Row label="CPU / 内存 / 硬盘">
                {loaded.map((p) => (
                  <td key={p.id} className="bg-card border-r border-t p-2 last:border-r-0 sm:p-3 tabular-nums">
                    {[p.cpu_cores != null ? `${p.cpu_cores}C` : null, p.ram_gb != null ? `${p.ram_gb}G` : null, p.disk_gb != null ? `${p.disk_gb}G` : null]
                      .filter(Boolean)
                      .join(" / ") || "—"}
                  </td>
                ))}
              </Row>
              <Row label="月流量 / 带宽">
                {loaded.map((p) => (
                  <td key={p.id} className="bg-card border-r border-t p-2 last:border-r-0 sm:p-3 tabular-nums">
                    {p.bandwidth_gb == null ? "—" : p.bandwidth_gb < 0 ? "不限" : `${p.bandwidth_gb.toLocaleString("zh-CN")}G`}
                    <span className="text-muted-foreground"> / </span>
                    {p.port_mbps != null ? `${p.port_mbps}M` : "—"}
                  </td>
                ))}
              </Row>
              <Row label="机房">
                {loaded.map((p) => (
                  <td key={p.id} className="bg-card border-r border-t p-2 last:border-r-0 sm:p-3">
                    {p.location || "—"}
                  </td>
                ))}
              </Row>
              {CARRIERS.map((carrier) => (
                <Row key={carrier} label={carrier}>
                  {loaded.map((p) => (
                    <td key={p.id} className="bg-card border-r border-t p-2 last:border-r-0 sm:p-3">
                      <CarrierRoute route={carrierRoute(lineById.get(p.id)?.carrierRows ?? [], carrier)} />
                    </td>
                  ))}
                </Row>
              ))}
              <Row label="购买">
                {loaded.map((p) => (
                  <td key={p.id} className="bg-card border-r border-t p-2 pb-3 last:border-r-0 sm:p-3 sm:pb-4">
                    {p.in_stock ? (
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
                    )}
                  </td>
                ))}
              </Row>
            </tbody>
          </table>
        </div>
      )}

      {loaded.length > 0 && loaded.length < 2 && (
        <p className="text-muted-foreground mt-3 rounded-lg bg-muted/50 px-3 py-2 text-xs">
          已选 {loaded.length} 款——至少加入 2 款才能形成有效对比，可在列表页继续添加。
        </p>
      )}

      {loaded.length > 0 && (
        <footer className="text-muted-foreground mt-4 border-t pt-3 text-xs leading-relaxed">
          换算口径：USD 参考价 = 原价 ÷ 每美元汇率（units_per_usd，来源与更新时间见
          {" "}<Link href="/api/rates" className="underline underline-offset-2">/api/rates</Link>）；
          历史价格换算使用对应日期的汇率快照。「价格（原币标价）」行为各套餐自身口径，
          币种与付款周期不同的时间不可直接比较。
        </footer>
      )}
    </>
  );
}

function Row({
  label,
  hint,
  children,
}: {
  label: string;
  hint?: string;
  children: React.ReactNode;
}) {
  return (
    <tr>
      <th scope="row" className="bg-background sticky left-0 z-10 p-1.5 align-top text-xs font-normal sm:p-2">
        <span className="text-muted-foreground">{label}</span>
        {/*
          行内说明窄屏隐藏：80px 的首列放不下，会挤成好几行把行高撑大。
          该信息（不同币种/周期不可直接横比）在页面顶部的说明里已完整给出。
        */}
        {hint && (
          <span className="text-muted-foreground/70 mt-0.5 hidden text-[10px] leading-snug sm:block">
            {hint}
          </span>
        )}
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
