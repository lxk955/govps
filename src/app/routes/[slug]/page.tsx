import type { Metadata } from "next";
import Link from "next/link";
import { notFound } from "next/navigation";
import { ArrowRight, CheckCircle2, ChevronRight, HelpCircle, Zap } from "lucide-react";

import { VpsCard } from "@/components/vps/VpsCard";
import { listProducts } from "@/lib/api/endpoints";
import { ROUTE_TOPICS } from "@/lib/route-topics";
import { SITE_URL } from "@/lib/site";

interface PageProps {
  params: Promise<{ slug: string }>;
}

export function generateStaticParams() {
  return Object.keys(ROUTE_TOPICS).map((slug) => ({ slug }));
}

export async function generateMetadata({ params }: PageProps): Promise<Metadata> {
  const { slug } = await params;
  const topic = ROUTE_TOPICS[slug];
  if (!topic) return {};

  const url = `${SITE_URL}/routes/${topic.slug}`;

  return {
    title: topic.title,
    description: topic.seoDescription,
    alternates: {
      canonical: url,
    },
    openGraph: {
      title: topic.title,
      description: topic.seoDescription,
      url,
      type: "website",
    },
    twitter: {
      card: "summary_large_image",
      title: topic.title,
      description: topic.seoDescription,
    },
  };
}

export default async function RouteTopicPage({ params }: PageProps) {
  const { slug } = await params;
  const topic = ROUTE_TOPICS[slug];
  if (!topic) notFound();

  // 获取该线路下收录的全部套餐
  const data = await listProducts({
    line: [topic.lineKey],
    size: 60,
    sort: "hot",
  }).catch(() => ({ total: 0, items: [] }));

  const inStockItems = data.items.filter((p) => p.in_stock);
  const outOfStockItems = data.items.filter((p) => !p.in_stock);

  // 构造 Google / Bing 结构化数据 (JSON-LD)
  const faqSchema = {
    "@context": "https://schema.org",
    "@type": "FAQPage",
    mainEntity: topic.faqList.map((faq) => ({
      "@type": "Question",
      name: faq.question,
      acceptedAnswer: {
        "@type": "Answer",
        text: faq.answer,
      },
    })),
  };

  const itemListSchema = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: `${topic.name} 在售 VPS 推荐列表`,
    itemListElement: data.items.slice(0, 10).map((p, index) => ({
      "@type": "ListItem",
      position: index + 1,
      name: `${p.merchant.name} - ${p.name}`,
      url: `${SITE_URL}/vps/${p.id}`,
    })),
  };

  const otherTopics = Object.values(ROUTE_TOPICS).filter((t) => t.slug !== topic.slug);

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(faqSchema) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListSchema) }}
      />

      <div className="mx-auto max-w-6xl space-y-10 py-2">
        {/* 面包屑导航 */}
        <nav aria-label="Breadcrumb" className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
          <Link href="/" className="hover:text-blue-600 transition-colors">
            首页
          </Link>
          <ChevronRight className="h-3 w-3" />
          <Link href="/routes" className="hover:text-blue-600 transition-colors">
            线路专题
          </Link>
          <ChevronRight className="h-3 w-3" />
          <span className="text-foreground font-semibold">{topic.name}</span>
        </nav>

        {/* 专题 Hero 区 */}
        <div className="border-border bg-gradient-to-b from-blue-50/60 via-card to-card dark:from-blue-950/20 dark:via-card dark:to-card rounded-3xl border p-6 sm:p-10 shadow-xs">
          <div className="flex flex-wrap items-center gap-2.5">
            <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-600 px-3 py-1 text-xs font-bold text-white shadow-xs">
              <Zap className="h-3.5 w-3.5" />
              {topic.badge}
            </span>
            <span className="rounded-full bg-slate-100 px-2.5 py-0.5 text-xs font-semibold text-slate-600 dark:bg-slate-800 dark:text-slate-300">
              主要适用：{topic.carrier}宽带
            </span>
            <span className="rounded-full bg-emerald-50 px-2.5 py-0.5 text-xs font-bold text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300">
              当前有货：{inStockItems.length} 款
            </span>
          </div>

          <h1 className="mt-4 text-2xl font-black tracking-tight text-slate-900 sm:text-4xl dark:text-slate-100">
            {topic.name} 选购与库存监测
          </h1>

          <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-600 dark:text-slate-300">
            {topic.summary}
          </p>

          <div className="mt-6 grid gap-2.5 sm:grid-cols-3">
            {topic.highlights.map((h, i) => (
              <div
                key={i}
                className="flex items-start gap-2 rounded-2xl border border-slate-200/60 bg-card/80 p-3 text-xs text-slate-700 shadow-2xs dark:border-slate-800 dark:text-slate-200"
              >
                <CheckCircle2 className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600 dark:text-emerald-400" />
                <span>{h}</span>
              </div>
            ))}
          </div>

          <div className="mt-6 flex flex-wrap items-center justify-between gap-3 border-t border-slate-200/80 pt-4 dark:border-slate-800">
            <div className="text-xs text-slate-500 dark:text-slate-400">
              <strong className="text-slate-700 dark:text-slate-200">推荐人群：</strong>
              {topic.recommendFor}
            </div>
            <Link
              href={`/?line=${topic.lineKey}`}
              className="inline-flex items-center gap-1.5 rounded-xl bg-blue-600 px-3.5 py-2 text-xs font-bold text-white shadow-xs hover:bg-blue-700 transition-colors"
            >
              在雷达首页高级筛选
              <ArrowRight className="h-3.5 w-3.5" />
            </Link>
          </div>
        </div>

        {/* 核心产品列表 */}
        <div className="space-y-6">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-2">
              <h2 className="text-lg font-black text-slate-900 sm:text-xl dark:text-slate-100">
                精选在售套餐
              </h2>
              <span className="rounded-full bg-blue-100 px-2 py-0.5 text-xs font-bold text-blue-700 dark:bg-blue-950 dark:text-blue-300">
                {inStockItems.length} 款现货
              </span>
            </div>
            <span className="text-xs text-slate-400 dark:text-slate-500">
              数据每 5 分钟自动巡检更新
            </span>
          </div>

          {inStockItems.length > 0 ? (
            <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3">
              {inStockItems.map((p) => (
                <VpsCard key={p.id} product={p} />
              ))}
            </div>
          ) : (
            <div className="border-border rounded-2xl border border-dashed py-12 text-center text-sm text-slate-400">
              当前暂无在售现货，您可以关注以下缺货款，到货时邮件即时提醒
            </div>
          )}

          {/* 缺货补货观察区 */}
          {outOfStockItems.length > 0 && (
            <div className="space-y-4 pt-6 border-t border-slate-100 dark:border-slate-800">
              <div className="flex items-center justify-between">
                <h3 className="text-sm font-bold text-slate-700 dark:text-slate-300">
                  缺货监控中（支持一键开启补货通知）
                </h3>
                <span className="text-xs text-slate-400">{outOfStockItems.length} 款待补货</span>
              </div>
              <div className="grid gap-4 sm:grid-cols-2 lg:grid-cols-3 opacity-80 hover:opacity-100 transition-opacity">
                {outOfStockItems.slice(0, 6).map((p) => (
                  <VpsCard key={p.id} product={p} />
                ))}
              </div>
            </div>
          )}
        </div>

        {/* 权威问答与技术 FAQ (SEO Rich Snippets) */}
        <div className="border-border bg-card rounded-3xl border p-6 sm:p-8 shadow-xs">
          <div className="flex items-center gap-2">
            <HelpCircle className="h-5 w-5 text-blue-600 dark:text-blue-400" />
            <h2 className="text-base font-bold text-slate-900 dark:text-slate-100">
              {topic.name} 常见问题与线路科普
            </h2>
          </div>
          <div className="mt-6 divide-y divide-slate-100 dark:divide-slate-800">
            {topic.faqList.map((faq, i) => (
              <div key={i} className="py-4 first:pt-0 last:pb-0">
                <h3 className="text-sm font-bold text-slate-900 dark:text-slate-100">
                  {faq.question}
                </h3>
                <p className="mt-1.5 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
                  {faq.answer}
                </p>
              </div>
            ))}
          </div>
        </div>

        {/* 探索其他线路专题 */}
        <div className="space-y-3 pt-4">
          <div className="text-xs font-bold text-slate-400 dark:text-slate-500 uppercase tracking-wider">
            浏览其他跨境优质线路专题
          </div>
          <div className="grid gap-3 sm:grid-cols-3">
            {otherTopics.map((other) => (
              <Link
                key={other.slug}
                href={`/routes/${other.slug}`}
                className="border-border bg-card flex items-center justify-between rounded-2xl border p-4 shadow-2xs hover:border-blue-400 transition-all dark:hover:border-blue-700"
              >
                <div>
                  <div className="text-xs font-bold text-slate-900 dark:text-slate-100">
                    {other.name}
                  </div>
                  <div className="text-[11px] text-slate-400 dark:text-slate-500 mt-0.5">
                    {other.badge}
                  </div>
                </div>
                <ArrowRight className="h-4 w-4 text-slate-400 shrink-0" />
              </Link>
            ))}
          </div>
        </div>
      </div>
    </>
  );
}
