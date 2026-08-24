import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import {
  ArrowLeft,
  ArrowUpRight,
  CheckCircle2,
  Cpu,
  Gauge,
  HardDrive,
  MemoryStick,
  ShieldCheck,
  Tag,
  Wifi,
  XCircle,
} from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { CompareButton } from "@/components/compare/compare-button";
import { PriceHistoryChart } from "@/components/vps/price-history-chart";
import { StockTimeline } from "@/components/vps/stock-timeline";
import { WatchButton } from "@/components/vps/watch-button";
import {
  getProductDetail,
  getRateSnapshots,
  listProducts,
  type ProductDetail,
} from "@/lib/api/endpoints";
import { currencySymbol, formatCycle, formatPrice, timeAgo } from "@/lib/format";
import { parseSlugId, productHref } from "@/lib/slug";

interface PageProps {
  params: Promise<{ slug: string }>;
}

async function fetchProduct(slug: string): Promise<ProductDetail | null> {
  const id = parseSlugId(slug);
  if (id == null) return null;
  try {
    return await getProductDetail(id);
  } catch {
    return null;
  }
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const p = await fetchProduct(slug);
  if (!p) return { title: "套餐不存在" };

  const specBits = [
    p.cpu_cores != null ? `${p.cpu_cores}核` : null,
    p.ram_gb != null ? `${p.ram_gb}G内存` : null,
    p.disk_gb != null ? `${p.disk_gb}G盘` : null,
    p.location,
    ...p.line_tags.slice(0, 2),
  ]
    .filter(Boolean)
    .join(" · ");

  const description = `${p.merchant.name} ${p.name}：${specBits}，${formatPrice(p.price, p.currency)}${formatCycle(p.billing_cycle)}（折年 ≈ ${formatPrice(p.price_yearly, p.currency)}），${p.in_stock ? "当前有货" : "暂时缺货"}。GoVPS 监控价格与库存变动。`;

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
  const p = await fetchProduct(slug);
  if (!p) notFound();

  // P5：历史价格换算使用「对应日期」的汇率快照（缺失日期宁缺毋滥）
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

  let host = "";
  try {
    host = new URL(p.purchase_url).hostname;
  } catch {
    /* 购买链接异常时不展示 IP 检测入口 */
  }

  const specs: { icon: React.ReactNode; label: string; value: string }[] = [
    { icon: <Cpu aria-hidden className="h-4 w-4" />, label: "CPU", value: p.cpu_cores != null ? `${p.cpu_cores} 核` : "—" },
    { icon: <MemoryStick aria-hidden className="h-4 w-4" />, label: "内存", value: p.ram_gb != null ? `${p.ram_gb} GB` : "—" },
    { icon: <HardDrive aria-hidden className="h-4 w-4" />, label: "硬盘", value: p.disk_gb != null ? `${p.disk_gb} GB` : "—" },
    {
      icon: <Wifi aria-hidden className="h-4 w-4" />,
      label: "月流量",
      value: p.bandwidth_gb == null ? "—" : p.bandwidth_gb < 0 ? "不限" : `${p.bandwidth_gb.toLocaleString("zh-CN")} GB`,
    },
    { icon: <Gauge aria-hidden className="h-4 w-4" />, label: "带宽", value: p.port_mbps != null ? `${p.port_mbps} Mbps` : "—" },
    { icon: <Tag aria-hidden className="h-4 w-4" />, label: "机房", value: p.location || "—" },
  ];

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
    <div className="mx-auto w-full max-w-5xl px-4 py-6">
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(jsonLd) }}
      />

      <Link
        href="/vps"
        className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm transition-colors"
      >
        <ArrowLeft aria-hidden className="h-4 w-4" />
        返回列表
      </Link>

      {/* 头部：商家 / 名称 / 状态徽标 */}
      <header className="mt-3 flex min-w-0 flex-wrap items-start justify-between gap-3">
        <div className="min-w-0">
          <p className="text-muted-foreground text-sm">{p.merchant.name}</p>
          <h1 className="mt-0.5 break-words text-xl font-bold tracking-tight lg:text-2xl">
            {p.name}
          </h1>
          <div className="mt-2 flex flex-wrap items-center gap-1.5">
            {p.in_stock ? (
              <Badge className="gap-1 bg-emerald-600 text-white hover:bg-emerald-600">
                <CheckCircle2 aria-hidden className="h-3 w-3" /> 有货
              </Badge>
            ) : (
              <Badge variant="secondary" className="gap-1 text-muted-foreground">
                <XCircle aria-hidden className="h-3 w-3" /> 缺货
              </Badge>
            )}
            {p.recommended && (
              <Badge className="bg-amber-500 text-white hover:bg-amber-500">精选推荐</Badge>
            )}
            {p.is_lowest_price && <Badge variant="outline">史低价</Badge>}
            {p.line_tags.map((t) => (
              <Badge key={t} variant="outline" className="text-sky-700 dark:text-sky-300">
                {t}
              </Badge>
            ))}
          </div>
        </div>

        {/* 推荐指数 */}
        {p.hot_score != null && (
          <div className="bg-card shrink-0 rounded-xl border px-4 py-3 text-center">
            <ShieldCheck aria-hidden className="mx-auto h-4 w-4 text-orange-500" />
            <p className="text-xl font-bold tabular-nums">{p.hot_score}</p>
            <p className="text-muted-foreground text-xs">综合推荐指数</p>
          </div>
        )}
      </header>

      {/* 价格块 + 全周期购买选项 */}
      <section aria-label="价格与购买" className="bg-card mt-5 rounded-xl border p-4 lg:p-5">
        <div className="flex flex-wrap items-end justify-between gap-4">
          <div>
            <p className="text-2xl font-bold tabular-nums">
              {formatPrice(p.price, p.currency)}
              <span className="text-muted-foreground text-sm font-normal">
                {formatCycle(p.billing_cycle)}
              </span>
            </p>
            <p className="text-muted-foreground mt-0.5 text-xs">
              折年 ≈ {formatPrice(p.price_yearly, p.currency)}
              {p.currency !== "USD" && p.price_yearly_converted != null && (
                <span className="ml-1">≈ ${p.price_yearly_converted.toFixed(2)}</span>
              )}
              {p.prev_price != null && (
                <span className={p.price_dropped ? "ml-2 text-red-600 dark:text-red-400" : "ml-2"}>
                  原价 {formatPrice(p.prev_price, p.currency)}
                  {p.price_dropped ? " ↓" : ""}
                </span>
              )}
              <span className="ml-2">{timeAgo(p.updated_at)}更新</span>
            </p>
            {p.recommend_reasons.length > 0 && (
              <ul className="text-muted-foreground mt-2 flex flex-wrap gap-x-3 gap-y-1 text-xs" aria-label="推荐理由">
                {p.recommend_reasons.map((r) => (
                  <li key={r}>· {r}</li>
                ))}
              </ul>
            )}
          </div>
          <div className="flex shrink-0 items-center gap-2">
            <CompareButton productId={p.id} />
            <WatchButton productId={p.id} hydrate />
            <Button asChild disabled={!p.in_stock} size="lg"
              className={p.in_stock ? "" : "pointer-events-none opacity-60"}>
              <a href={`/go/${p.id}?src=detail`} aria-disabled={!p.in_stock}>
                前往购买
                <ArrowUpRight aria-hidden className="h-4 w-4" />
              </a>
            </Button>
          </div>
        </div>

        {p.price_options.length > 1 && (
          <ul className="mt-4 grid grid-cols-1 gap-2 border-t pt-4 sm:grid-cols-2 lg:grid-cols-3" aria-label="其他付款周期">
            {p.price_options.map((o) => (
              <li key={`${o.billing_cycle}-${o.price}`} className="flex items-center justify-between gap-2 rounded-lg bg-muted/50 px-3 py-2 text-sm">
                <span className="min-w-0">
                  {formatPrice(o.price, o.currency)}
                  <span className="text-muted-foreground">{formatCycle(o.billing_cycle)}</span>
                </span>
                <a
                  href={`/go/${p.id}?src=detail&cycle=${encodeURIComponent(o.billing_cycle)}`}
                  className="inline-flex shrink-0 items-center gap-0.5 text-sky-700 hover:underline dark:text-sky-400"
                >
                  购买 <ArrowUpRight aria-hidden className="h-3 w-3" />
                </a>
              </li>
            ))}
          </ul>
        )}

        {host && (
          <p className="text-muted-foreground mt-4 border-t pt-3 text-xs">
            打算入手？先检查一下你到机房线路的质量：
            <Link href={`/ip?q=${encodeURIComponent(host)}`} className="ml-1 text-sky-700 hover:underline dark:text-sky-400">
              检测机房 IP（{host}）
            </Link>
          </p>
        )}
      </section>

      {/* 规格矩阵 */}
      <section aria-label="配置规格" className="mt-5">
        <h2 className="mb-2 text-base font-semibold">配置规格</h2>
        <dl className="grid grid-cols-2 gap-2 sm:grid-cols-3 lg:grid-cols-6">
          {specs.map((s) => (
            <div key={s.label} className="bg-card rounded-lg border p-3">
              <dt className="text-muted-foreground flex items-center gap-1.5 text-xs">
                {s.icon}
                {s.label}
              </dt>
              <dd className="mt-1 break-words text-sm font-medium">{s.value}</dd>
            </div>
          ))}
        </dl>
      </section>

      <div className="mt-5 grid grid-cols-1 gap-5 lg:grid-cols-2">
        {/* 价格历史 */}
        <section aria-label="价格历史" className="bg-card rounded-xl border p-4">
          <h2 className="mb-2 text-base font-semibold">价格历史</h2>
          {p.price_snapshots.length > 0 ? (
            <PriceHistoryChart
              points={p.price_snapshots}
              currency={p.currency}
              snapshots={rateSnapshots}
            />
          ) : (
            <p className="text-muted-foreground py-6 text-center text-sm">暂无价格快照记录</p>
          )}
        </section>

        {/* 库存时间线 */}
        <section aria-label="库存时间线" className="bg-card rounded-xl border p-4">
          <h2 className="mb-2 text-base font-semibold">库存时间线</h2>
          {p.stock_snapshots.length > 0 ? (
            <StockTimeline points={p.stock_snapshots} />
          ) : (
            <p className="text-muted-foreground py-6 text-center text-sm">暂无库存快照记录</p>
          )}
        </section>
      </div>

      {/* 相似推荐 */}
      {similar.length > 0 && (
        <section aria-label="相似套餐推荐" className="mt-5">
          <h2 className="mb-2 text-base font-semibold">相似套餐</h2>
          <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
            {similar.map((s) => (
              <li key={s.id} className="min-w-0">
                <Link
                  href={productHref(s.id, s.name)}
                  className="bg-card hover:border-ring block h-full rounded-xl border p-3 transition-colors"
                >
                  <p className="text-muted-foreground text-xs">{s.merchant.name}</p>
                  <p className="mt-0.5 break-words text-sm font-medium">{s.name}</p>
                  <p className="mt-1.5 text-sm font-bold tabular-nums">
                    {currencySymbol(s.currency)}
                    {s.price.toFixed(2)}
                    <span className="text-muted-foreground text-xs font-normal">{formatCycle(s.billing_cycle)}</span>
                  </p>
                  <p className="text-muted-foreground mt-0.5 text-xs">
                    {s.location || ""} {s.in_stock ? "· 有货" : "· 缺货"}
                  </p>
                </Link>
              </li>
            ))}
          </ul>
        </section>
      )}

      <footer className="text-muted-foreground mt-6 border-t pt-4 text-xs leading-relaxed">
        数据定期同步自各商家官网；价格为商家原币标价，「折年」为同币种按付款周期折算。
        库存与价格以商家页面为准——最近核对于{" "}
        <time dateTime={p.last_checked_at ?? undefined}>{timeAgo(p.last_checked_at)}</time>。
      </footer>
    </div>
  );
}
