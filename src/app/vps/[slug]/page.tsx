import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowLeft } from "lucide-react";

import { CompareButton } from "@/components/compare/compare-button";
import {
  DetailBuyButton,
  DetailCycleProvider,
  DetailPriceCard,
} from "@/components/vps/detail-cycle";
import { DetailShareButton } from "@/components/vps/detail-share-button";
import { PriceHistoryChart } from "@/components/vps/price-history-chart";
import {
  getProductDetail,
  getRateSnapshots,
  listProducts,
  type ProductDetail,
} from "@/lib/api/endpoints";
import { fmtPort, fmtSize, fmtTraffic, lineInfo, lineTierClass, shortName } from "@/lib/display";
import { formatPrice, timeAgo } from "@/lib/format";
import { testIpFor } from "@/lib/merchant-test-ips";
import { parseSlugId, productHref } from "@/lib/slug";
import { ApiError } from "@/lib/api/client";
import { SITE_URL } from "@/lib/site";

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
    // 区分「后端确认不存在」与「取数失败」：后者提示加载失败，
    // 一律 notFound() 会让用户误以为套餐已下架。
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
    ...p.line_tags,
  ]
    .filter(Boolean)
    .join(" · ");

  const description = `${p.merchant.name} ${p.name}：${specBits}，${formatPrice(p.price, p.currency)}（折年 ≈ ${formatPrice(p.price_yearly, p.currency)}），${p.in_stock ? "当前有货" : "暂时缺货"}。GoVPS 监控价格与库存变动。`;
  const canonicalUrl = `${SITE_URL}${productHref(p.id, p.name)}`;

  return {
    title: `${p.name} - ${p.merchant.name}`,
    description,
    alternates: { canonical: canonicalUrl },
    openGraph: {
      title: `${p.name} - ${p.merchant.name} | GoVPS · VPS雷达`,
      description,
      type: "website",
      url: canonicalUrl,
      siteName: "GoVPS · VPS雷达",
    },
    twitter: {
      card: "summary_large_image",
      title: `${p.name} - ${p.merchant.name} | GoVPS · VPS雷达`,
      description,
    },
  };
}

export default async function VpsDetailPage({ params }: PageProps) {
  const { slug } = await params;
  const productPromise = fetchProduct(slug);
  const ratesPromise = getRateSnapshots(90)
    .then((r) => r.snapshots)
    .catch((): Record<string, Record<string, number>> => ({}));

  const res = await productPromise;
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

  // 汇率不依赖产品，与相似套餐并行；产品返回后立刻开始相似查询
  const [rateSnapshots, similarFirst] = await Promise.all([
    ratesPromise,
    listProducts({
      ...(p.location ? { location: [p.location] } : {}),
      merchant: [p.merchant.slug],
      size: 6,
    }).catch(() => ({ total: 0, items: [] })),
  ]);
  let similar = similarFirst.items.filter((x) => x.id !== p.id);
  if (similar.length < 3 && p.location) {
    const byMerchant = await listProducts({
      merchant: [p.merchant.slug],
      size: 8,
    }).catch(() => ({ total: 0, items: [] }));
    similar = byMerchant.items.filter((x) => x.id !== p.id);
  }
  similar = similar.slice(0, 4);

  /*
   * 只认精确匹配的机房测试 IP（testIpFor 已不做跨机房回退）。
   * 不再回退到购买页域名：官网域名通常不是机房出口，拿它测出的纯净度与该套餐
   * 所在机房无关，等同于错误数据。按「宁缺毋错」，取不到就不展示检测入口。
   */
  const host = testIpFor(p.merchant.slug, p.location);

  const line = lineInfo(p);
  const short = shortName(p);

  const pageCanonicalUrl = `${SITE_URL}${productHref(p.id, p.name)}`;

  const jsonLdProduct = {
    "@context": "https://schema.org",
    "@type": "Product",
    name: `${p.merchant.name} ${p.name}`,
    description: `${p.merchant.name} ${p.name} - ${p.cpu_cores != null ? `${p.cpu_cores}核 CPU, ` : ""}${p.ram_gb != null ? `${p.ram_gb}GB 内存, ` : ""}${p.disk_gb != null ? `${p.disk_gb}GB 硬盘, ` : ""}${p.location ? `机房: ${p.location}, ` : ""}当前状态: ${p.in_stock ? "有货在售" : "缺货"}`,
    brand: { "@type": "Brand", name: p.merchant.name },
    offers: {
      "@type": "Offer",
      price: String(p.price),
      priceCurrency: p.currency,
      availability: `https://schema.org/${p.in_stock ? "InStock" : "OutOfStock"}`,
      url: pageCanonicalUrl,
    },
  };

  const jsonLdBreadcrumb = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "首页",
        item: SITE_URL,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: p.merchant.name,
        item: `${SITE_URL}/?merchant=${encodeURIComponent(p.merchant.slug)}`,
      },
      {
        "@type": "ListItem",
        position: 3,
        name: p.name,
        item: pageCanonicalUrl,
      },
    ],
  };

  return (
    <div className="space-y-6">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdProduct) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLdBreadcrumb) }}
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

          <div className="flex flex-wrap items-center gap-2.5">
            <DetailShareButton product={p} />
            <DetailBuyButton product={p} />
          </div>
        </div>

        {/* 规格与价格概览卡片 */}
        <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-4">
          <DetailPriceCard />

          <div className="border-border bg-card rounded-2xl border p-5 shadow-sm">
            <div className="text-xs font-medium text-slate-400 dark:text-slate-500">
              历史原价 / 降幅
            </div>
            <div className="text-slate-500 mt-1 text-2xl font-black dark:text-slate-400">
              {p.prev_price != null ? formatPrice(p.prev_price, p.currency) : "—"}
            </div>
            {p.price_dropped && (
              <div className="mt-2 text-xs font-bold text-rose-600 dark:text-rose-400">
                相比原价已直降 {formatPrice((p.prev_price || 0) - p.price, p.currency)}
              </div>
            )}
          </div>

          <div className="border-border bg-card rounded-2xl border p-5 shadow-sm">
            <div className="text-xs font-medium text-slate-400 dark:text-slate-500">硬件规格</div>
            <div className="text-slate-800 mt-1 text-sm leading-6 font-bold dark:text-slate-200">
              {[
                p.cpu_cores && `${p.cpu_cores} 核 CPU`,
                p.ram_gb && `${fmtSize(p.ram_gb)} 内存`,
                p.disk_gb && `${fmtSize(p.disk_gb)} 存储`,
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
                p.bandwidth_gb != null
                  ? p.bandwidth_gb < 0
                    ? "不限月流量"
                    : `${fmtTraffic(p.bandwidth_gb)} 流量/月`
                  : "",
                p.port_mbps ? `${fmtPort(p.port_mbps)} 端口` : "",
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
          href="/"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm transition-colors"
        >
          <ArrowLeft aria-hidden className="h-4 w-4" />
          返回列表
        </Link>
        <CompareButton productId={p.id} />
        <DetailShareButton product={p} />
      </div>

      <footer className="text-muted-foreground text-xs leading-relaxed">
        数据定期同步自各商家官网；价格为商家原币标价，「折年」为同币种按付款周期折算。
        库存与价格以商家页面为准——最近核对于{" "}
        <time dateTime={p.last_checked_at ?? undefined}>{timeAgo(p.last_checked_at)}</time>。
      </footer>
    </div>
  );
}
