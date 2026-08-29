import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { CompareButton } from "@/components/compare/compare-button";
import {
  DetailBuyButton,
  DetailCycleProvider,
  DetailPriceCard,
  DetailPromoBar,
} from "@/components/vps/detail-cycle";
import { PriceHistoryChart } from "@/components/vps/price-history-chart";
import {
  getProductDetail,
  getRateSnapshots,
  listProducts,
  type ProductDetail,
} from "@/lib/api/endpoints";
import { lineInfo, lineTierClass, shortName } from "@/lib/display";
import { currencySymbol, formatPrice, timeAgo } from "@/lib/format";
import { testIpFor } from "@/lib/merchant-test-ips";
import { parseSlugId, productHref } from "@/lib/slug";
import { ApiError } from "@/lib/api/client";

interface PageProps {
  params: Promise<{ slug: string }>;
}

type FetchResult =
  | { ok: true; product: ProductDetail }
  | { ok: false; status: number };

async function fetchProduct(slug: string): Promise<FetchResult> {
  const id = parseSlugId(slug);
  if (id == null) return { ok: false, status: 404 };
  try {
    return { ok: true, product: await getProductDetail(id) };
  } catch (e) {
    // 区分「后端确认不存在」与「取数失败」：后者多为免费实例休眠返回的 429，
    // 若一律落到 notFound() 会让用户误以为套餐已下架。
    return { ok: false, status: e instanceof ApiError ? e.status : 0 };
  }
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const res = await fetchProduct(slug);
  if (!res.ok) return { title: res.status === 404 ? "套餐不存在" : "数据加载失败" };
  const p = res.product;

  const specBits = [
    p.cpu_cores != null ? `${p.cpu_cores}核` : null,
    p.ram_gb != null ? `${p.ram_gb}G内存` : null,
    p.disk_gb != null ? `${p.disk_gb}G盘` : null,
    p.location,
    ...p.line_tags.slice(0, 2),
  ]
    .filter(Boolean)
    .join(" · ");

  const description = `${p.merchant.name} ${p.name}：${specBits}，${formatPrice(p.price, p.currency)}（折年 ≈ ${formatPrice(p.price_yearly, p.currency)}），${p.in_stock ? "当前有货" : "暂时缺货"}。GoVPS 监控价格与库存变动。`;

  return {
    title: `${p.name} - ${p.merchant.name}`,
    description,
    alternates: { canonical: productHref(p.id, p.name) },
    openGraph: {
      title: `${p.name} - ${p.merchant.name} | GoVPS`,
      description,
      type: "website",
      url: productHref(p.id, p.name),
      siteName: "GoVPS",
    },
  };
}

export default async function VpsDetailPage({ params }: PageProps) {
  const { slug } = await params;
  const res = await fetchProduct(slug);
  if (!res.ok) {
    // 后端确认不存在才走 404；其余（休眠 429、网络失败）提示重试，不误报下架
    if (res.status === 404) notFound();
    return (
      <div className="flex flex-col items-center gap-3 rounded-xl border border-red-100 bg-red-50 p-12 text-center dark:border-red-900 dark:bg-red-950/30">
        <div className="text-3xl" aria-hidden>
          📡
        </div>
        <p className="text-sm font-medium text-red-600 dark:text-red-400">
          套餐数据加载失败，通常是数据服务正在启动，请稍后重试。
        </p>
        <Link
          href={`/vps/${slug}`}
          className="rounded-xl bg-red-600 px-4 py-1.5 text-xs font-bold text-white transition-colors hover:bg-red-700"
        >
          重新加载
        </Link>
      </div>
    );
  }
  const p = res.product;

  const rateSnapshots = await getRateSnapshots(90)
    .then((r) => r.snapshots)
    .catch(() => ({}));

  // 相似推荐：同机房优先，回退同商家；排除自身，取前 4
  let similar = (
    await listProducts({
      ...(p.location ? { location: [p.location] } : {}),
      merchant: [p.merchant.slug],
      size: 6,
    }).catch(() => ({ total: 0, items: [] }))
  ).items.filter((x) => x.id !== p.id);
  if (similar.length < 3 && p.location) {
    const byMerchant = await listProducts({
      merchant: [p.merchant.slug],
      size: 8,
    }).catch(() => ({ total: 0, items: [] }));
    similar = byMerchant.items.filter((x) => x.id !== p.id);
  }
  similar = similar.slice(0, 4);

  // 旧站逻辑：优先用商家机房测试 IP——购买页域名通常是商家官网，
  // 并不代表机房出口线路；都没有时回退到域名。
  let host = testIpFor(p.merchant.slug, p.location) ?? "";
  if (!host) {
    try {
      host = new URL(p.purchase_url).hostname;
    } catch {
      /* 购买链接异常时不展示 IP 检测入口 */
    }
  }

  const line = lineInfo(p);
  const short = shortName(p);
  const sym = currencySymbol(p.currency);

  const jsonLd = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: p.name,
    brand: { "@type": "Brand", name: p.merchant.name },
    offers: {
      "@type": "Offer",
      price: String(p.price),
      priceCurrency: p.currency,
      availability: `https://schema.org/${p.in_stock ? "InStock" : "OutOfStock"}`,
      url: p.purchase_url,
    },
  };

  return (
    <div className="space-y-6">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <DetailCycleProvider product={p}>
        {p.price_dropped && p.prev_price != null && null}

        {/* 头部信息 */}
        <div className="border-border bg-card flex flex-wrap items-start justify-between gap-4 rounded-2xl border p-6 shadow-sm">
          <div className="max-w-2xl space-y-2">
            <div className="flex items-center gap-2 text-xs font-medium text-slate-400 dark:text-slate-500">
              <span className="bg-muted text-foreground rounded px-2 py-0.5 font-bold">
                {p.merchant.name}
              </span>
              {p.location && (
                <span className="bg-muted text-muted-foreground rounded px-2 py-0.5 font-bold">
                  {p.location}
                </span>
              )}
            </div>

            <h1 className="text-slate-900 text-2xl leading-snug font-black dark:text-slate-100">
              {short}
            </h1>
            {short !== p.name && (
              <div className="text-xs text-slate-400 dark:text-slate-500" title={p.name}>
                {p.name}
              </div>
            )}

            {/* 标签区 */}
            <div className="flex flex-wrap items-center gap-2 pt-1">
              <span className={lineTierClass(line.level)}>{line.tier}</span>
              <span className="bg-muted text-muted-foreground rounded px-2 py-0.5 text-xs font-medium">
                {line.carrierRows.join(" ")}
              </span>

              {p.hot_score != null && p.hot_score >= 80 && (
                <span className="rounded border border-rose-200 bg-rose-50 px-2 py-0.5 text-xs font-bold text-rose-600 dark:border-rose-800 dark:bg-rose-950/60 dark:text-rose-300">
                  🔥 综合热度 {Math.round(p.hot_score)}
                </span>
              )}

              {p.is_recent_restock && p.in_stock && (
                <span className="inline-flex animate-pulse items-center gap-1 rounded border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-xs font-bold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300">
                  ⚡ 最新补货
                </span>
              )}

              <span
                className={`rounded-full px-2.5 py-0.5 text-xs font-bold ${
                  p.in_stock
                    ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
                    : "bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-300"
                }`}
              >
                {p.in_stock ? "● 有货" : "● 缺货"}
              </span>
              {p.last_checked_at && (
                <span
                  className="text-[11px] text-slate-400 dark:text-slate-500"
                  title="后端爬虫最近一次成功确认该套餐库存的时间"
                >
                  确认于 {timeAgo(p.last_checked_at)}
                </span>
              )}
              {p.price_dropped && (
                <span className="rounded bg-orange-100 px-2 py-0.5 text-xs font-bold text-orange-600 dark:bg-orange-950/60 dark:text-orange-300">
                  降价促销中
                </span>
              )}
            </div>
          </div>

          <DetailBuyButton product={p} />
        </div>

        {/* 优惠码一键复制通告栏 */}
        <DetailPromoBar slug={p.merchant.slug} />

        {/* 规格与价格概览卡片 */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <DetailPriceCard />

          <div className="border-border bg-card rounded-2xl border p-5 shadow-sm">
            <div className="text-xs font-medium text-slate-400 dark:text-slate-500">
              历史原价 / 降幅
            </div>
            <div className="text-slate-500 mt-1 text-2xl font-black dark:text-slate-400">
              {p.prev_price != null ? `${sym}${formatPrice(p.prev_price, p.currency)}` : "—"}
            </div>
            {p.price_dropped && (
              <div className="mt-2 text-xs font-bold text-rose-600 dark:text-rose-400">
                相比原价已直降 {sym}
                {formatPrice((p.prev_price || 0) - p.price, p.currency)}
              </div>
            )}
          </div>

          <div className="border-border bg-card rounded-2xl border p-5 shadow-sm">
            <div className="text-xs font-medium text-slate-400 dark:text-slate-500">硬件规格</div>
            <div className="text-slate-800 mt-1 text-sm leading-6 font-bold dark:text-slate-200">
              {[
                p.cpu_cores && `${p.cpu_cores} 核 CPU`,
                p.ram_gb && `${p.ram_gb}G 内存`,
                p.disk_gb && `${p.disk_gb}G 存储`,
              ]
                .filter(Boolean)
                .join(" · ") || "规格见官网详情"}
            </div>
          </div>

          <div className="border-border bg-card rounded-2xl border p-5 shadow-sm">
            <div className="text-xs font-medium text-slate-400 dark:text-slate-500">
              网络与带宽
            </div>
            <div className="text-slate-800 mt-1 text-sm leading-6 font-bold dark:text-slate-200">
              {[
                p.bandwidth_gb
                  ? p.bandwidth_gb < 0
                    ? "无限月流量"
                    : `${p.bandwidth_gb >= 1000 ? `${p.bandwidth_gb / 1000}T` : `${p.bandwidth_gb}G`} 流量/月`
                  : "",
                p.port_mbps
                  ? p.port_mbps >= 1000
                    ? `${p.port_mbps / 1000}Gbps 端口`
                    : `${p.port_mbps}Mbps 端口`
                  : "",
              ]
                .filter(Boolean)
                .join(" · ") || "见商家网络说明"}
            </div>
            {host && (
              <Link
                href={`/ip?q=${encodeURIComponent(host)}`}
                title={`检测 ${p.merchant.name} 机房测试 IP ${host}`}
                className="mt-3 inline-flex cursor-pointer items-center gap-1 rounded-lg border border-blue-100 bg-blue-50/60 px-2 py-1 text-xs font-bold text-blue-600 transition-colors hover:border-blue-300 hover:bg-blue-50 dark:border-blue-900 dark:bg-blue-950/40 dark:text-blue-300"
              >
                🔍 检测该机房 IP 纯净度
              </Link>
            )}
          </div>
        </div>
      </DetailCycleProvider>

      {/* 历史价格走势 */}
      <div className="border-border bg-card rounded-2xl border p-6 shadow-sm">
        <h2 className="text-slate-900 mb-3 text-base font-bold dark:text-slate-100">价格走势监测</h2>
        {p.price_snapshots.length > 0 ? (
          <PriceHistoryChart
            points={p.price_snapshots}
            currency={p.currency}
            snapshots={rateSnapshots}
          />
        ) : (
          <p className="text-muted-foreground py-6 text-center text-sm">暂无价格快照记录</p>
        )}
      </div>

      {/* 库存变化历史 */}
      <div className="border-border bg-card rounded-2xl border p-6 shadow-sm">
        <h2 className="text-slate-900 mb-3 text-base font-bold dark:text-slate-100">库存异动追踪</h2>
        {p.stock_snapshots.length > 0 ? (
          <ul className="border-border divide-border divide-y text-sm">
            {[...p.stock_snapshots].reverse().map((s, i) => (
              <li key={`${s.checked_at}-${i}`} className="flex items-center justify-between py-2">
                <div className="flex items-center gap-2">
                  <span
                    aria-hidden
                    className={`inline-block h-2.5 w-2.5 rounded-full ${
                      s.in_stock
                        ? "bg-emerald-500 ring-2 ring-emerald-100 dark:ring-emerald-900"
                        : "bg-rose-500 ring-2 ring-rose-100 dark:ring-rose-900"
                    }`}
                  />
                  <span
                    className={`font-bold ${
                      s.in_stock
                        ? "text-emerald-700 dark:text-emerald-400"
                        : "text-rose-600 dark:text-rose-400"
                    }`}
                  >
                    {s.in_stock ? "补货（有货）" : "售罄（缺货）"}
                  </span>
                </div>
                <span className="text-xs text-slate-400 dark:text-slate-500">
                  {new Date(s.checked_at).toLocaleString("zh-CN")}
                </span>
              </li>
            ))}
          </ul>
        ) : (
          <p className="text-sm text-slate-400 dark:text-slate-500">
            持续监控中，暂无库存异动记录。
          </p>
        )}
      </div>

      {/* 相似推荐（新站增补，旧站无此模块） */}
      {similar.length > 0 && (
        <div>
          <h2 className="text-slate-900 mb-2 text-base font-bold dark:text-slate-100">相似套餐</h2>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {similar.map((s) => (
              <li key={s.id} className="min-w-0">
                <Link
                  href={productHref(s.id, s.name)}
                  className="border-border bg-card hover:border-ring block h-full rounded-xl border p-3 transition-colors"
                >
                  <p className="text-muted-foreground text-xs">{s.merchant.name}</p>
                  <p className="mt-0.5 break-words text-sm font-medium">{s.name}</p>
                  <p className="mt-1.5 text-sm font-bold tabular-nums">
                    {formatPrice(s.price, s.currency)}
                  </p>
                  <p className="text-muted-foreground mt-0.5 text-xs">
                    {s.location || ""} {s.in_stock ? "· 有货" : "· 缺货"}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        </div>
      )}

      <div className="flex flex-wrap items-center gap-3">
        <Link
          href="/vps"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm transition-colors"
        >
          <ArrowLeft aria-hidden className="h-4 w-4" />
          返回列表
        </Link>
        <CompareButton productId={p.id} />
      </div>

      <footer className="text-muted-foreground text-xs leading-relaxed">
        数据定期同步自各商家官网；价格为商家原币标价，「折年」为同币种按付款周期折算。
        库存与价格以商家页面为准——最近核对于{" "}
        <time dateTime={p.last_checked_at ?? undefined}>{timeAgo(p.last_checked_at)}</time>。
      </footer>
    </div>
  );
}
