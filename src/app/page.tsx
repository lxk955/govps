import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, BellRing, Tag } from "lucide-react";

import { BookmarkDialog } from "@/components/bookmark-dialog";
import { Button } from "@/components/ui/button";
import { VpsCard } from "@/components/vps/VpsCard";
import { getEventsSummary, listProducts, type ProductsResponse } from "@/lib/api/endpoints";

export const metadata: Metadata = {
  title: "GoVPS - VPS 库存与降价监控",
  description:
    "多商家 VPS 套餐聚合：库存监控、降价提醒、线路对比与购买推荐。精选高性价比套餐，降价补货第一时间掌握。",
  alternates: { canonical: "/" },
};

export default async function HomePage() {
  // 推荐位：精选优先；冷启动（无精选）回退为在售热榜（方案 P3 回退策略）
  let featured: ProductsResponse = await listProducts({ recommended: true, size: 8 }).catch(
    () => ({ total: 0, items: [] }),
  );
  if (featured.items.length === 0) {
    featured = await listProducts({ in_stock: true, sort: "hot", size: 8 }).catch(() => ({
      total: 0,
      items: [],
    }));
  }
  const summary = await getEventsSummary(24).catch(() => null);

  return (
    <main>
      {/* Hero */}
      <section className="border-b">
        <div className="mx-auto flex w-full max-w-7xl flex-col items-start gap-4 px-4 py-12 lg:py-16">
          <h1 className="max-w-2xl text-2xl leading-snug font-bold tracking-tight text-balance lg:text-4xl lg:leading-tight">
            盯住每一家 VPS 商家的<span className="text-sky-700 dark:text-sky-400">降价</span>与
            <span className="text-emerald-700 dark:text-emerald-400">补货</span>
          </h1>
          <p className="text-muted-foreground max-w-xl text-sm leading-relaxed lg:text-base">
            多商家套餐实时聚合：CN2 GIA、9929、CMIN2 优质线路一网打尽，
            价格与库存变动自动追踪，帮你买到值得买的那一台。
          </p>
          <div className="flex flex-wrap gap-2">
            <Button asChild>
              <Link href="/vps">
                浏览全部套餐
                <ArrowRight aria-hidden className="h-4 w-4" />
              </Link>
            </Button>
            <Button asChild variant="outline">
              <Link href="/deals">降价与补货动态</Link>
            </Button>
          </div>
        </div>
      </section>

      <div className="mx-auto w-full max-w-7xl px-4 py-8">
        {/* 动态摘要条（B7）：近 24h 事件计数 */}
        {summary && (summary.drop_count > 0 || summary.restock_count > 0) && (
          <Link
            href="/deals"
            className="bg-card hover:border-ring mb-8 flex flex-wrap items-center gap-x-6 gap-y-2 rounded-xl border px-4 py-3 text-sm transition-colors"
          >
            <span className="font-medium">近 24 小时动态</span>
            <span className="inline-flex items-center gap-1.5 text-red-700 dark:text-red-400">
              <Tag aria-hidden className="h-4 w-4" />
              <span className="font-semibold tabular-nums">{summary.drop_count}</span> 次降价
            </span>
            <span className="inline-flex items-center gap-1.5 text-emerald-700 dark:text-emerald-400">
              <BellRing aria-hidden className="h-4 w-4" />
              <span className="font-semibold tabular-nums">{summary.restock_count}</span> 次补货
            </span>
            <span className="text-muted-foreground ml-auto inline-flex items-center gap-1 text-xs">
              查看详情
              <ArrowRight aria-hidden className="h-3 w-3" />
            </span>
          </Link>
        )}

        {/* 精选推荐位 */}
        <section aria-label="精选套餐">
          <div className="mb-3 flex items-baseline justify-between gap-3">
            <h2 className="text-lg font-bold tracking-tight">
              {featured.items.some((x) => x.recommended) ? "精选推荐" : "热门在售"}
            </h2>
            <Link href="/vps" className="text-muted-foreground hover:text-foreground inline-flex items-center gap-1 text-sm transition-colors">
              全部套餐
              <ArrowRight aria-hidden className="h-3.5 w-3.5" />
            </Link>
          </div>

          {featured.items.length === 0 ? (
            <div className="text-muted-foreground rounded-xl border border-dashed p-10 text-center text-sm">
              数据同步中，稍后再来看看。
            </div>
          ) : (
            <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
              {featured.items.map((p) => (
                <li key={p.id} className="min-w-0">
                  <VpsCard product={p} />
                </li>
              ))}
            </ul>
          )}
        </section>

        {/* 工具入口 */}
        <section aria-label="实用工具" className="mt-8 grid grid-cols-1 gap-3 sm:grid-cols-3">
          {[
            {
              href: "/providers",
              title: "服务商一览",
              desc: "各商家在售款数、库存与最近抓取时间",
            },
            {
              href: "/ip",
              title: "IP 检测",
              desc: "纯净度评分、WebRTC/DNS 泄露与浏览器指纹",
            },
            {
              href: "/deals?hours=168",
              title: "一周降价榜",
              desc: "近 168 小时降幅最大的套餐排行",
            },
          ].map((t) => (
            <Link
              key={t.href}
              href={t.href}
              className="bg-card hover:border-ring block rounded-xl border p-4 transition-colors"
            >
              <p className="flex items-center gap-1 font-medium">
                {t.title}
                <ArrowRight aria-hidden className="h-3.5 w-3.5" />
              </p>
              <p className="text-muted-foreground mt-1 break-words text-xs leading-relaxed">{t.desc}</p>
            </Link>
          ))}
        </section>

        <footer className="text-muted-foreground mt-10 flex flex-wrap items-center justify-between gap-2 border-t pt-4 text-xs">
          <p>数据定期同步自各商家官网，价格库存以商家页面为准。</p>
          <BookmarkDialog />
        </footer>
      </div>
    </main>
  );
}
