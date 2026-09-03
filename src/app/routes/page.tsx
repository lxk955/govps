import type { Metadata } from "next";
import Link from "next/link";
import { ArrowRight, CheckCircle2, ShieldCheck, Zap } from "lucide-react";
import { ROUTE_TOPICS } from "@/lib/route-topics";
import { SITE_URL } from "@/lib/site";

export const metadata: Metadata = {
  title: "VPS 优质网络线路专题大全 - CN2 GIA / 9929 / CMIN2 / 4837 选购指南 | GoVPS",
  description:
    "全面解析电信 CN2 GIA、联通 AS9929、移动 CMIN2、联通 AS4837 等主流跨境 VPS 线路。实时监测各大机房在售库存与价格变动，助力选出晚高峰不卡顿的理想云主机。",
  alternates: {
    canonical: `${SITE_URL}/routes`,
  },
  openGraph: {
    title: "VPS 优质网络线路专题大全 - GoVPS",
    description: "全面对比 CN2 GIA、9929、CMIN2、4837 线路特性，实时追踪各线路在售现货。",
    url: `${SITE_URL}/routes`,
    type: "website",
  },
};

export default function RoutesHubPage() {
  const topics = Object.values(ROUTE_TOPICS);

  return (
    <div className="mx-auto max-w-6xl space-y-10 py-2">
      {/* 顶部面包屑与引导 */}
      <div className="space-y-3">
        <div className="flex items-center gap-2 text-xs text-slate-400 dark:text-slate-500">
          <Link href="/" className="hover:text-blue-600 transition-colors">
            首页
          </Link>
          <span>/</span>
          <span className="text-foreground font-semibold">线路专题</span>
        </div>
        <div className="flex flex-col gap-2 md:flex-row md:items-end md:justify-between">
          <div>
            <h1 className="text-2xl font-black tracking-tight text-slate-900 sm:text-3xl dark:text-slate-100">
              跨境 VPS 优质线路指南
            </h1>
            <p className="mt-1.5 max-w-3xl text-sm text-slate-500 dark:text-slate-400 leading-relaxed">
              出海网络体验的关键在于「回国线路」。不同运营商（电信、联通、移动）在晚高峰的出口瓶颈截然不同，选对针对性专线（CN2 GIA、9929、CMIN2）是告别丢包与卡顿的唯一解法。
            </p>
          </div>
          <Link
            href="/"
            className="inline-flex shrink-0 items-center gap-1 text-xs font-bold text-blue-600 hover:text-blue-700 dark:text-blue-400"
          >
            查看全站雷达
            <ArrowRight className="h-3.5 w-3.5" />
          </Link>
        </div>
      </div>

      {/* 4 大核心线路卡片矩阵 */}
      <div className="grid gap-5 md:grid-cols-2">
        {topics.map((t) => (
          <div
            key={t.slug}
            className="border-border bg-card group relative flex flex-col justify-between rounded-3xl border p-6 shadow-xs transition-all hover:border-blue-300 hover:shadow-md dark:hover:border-blue-800"
          >
            <div>
              <div className="flex items-center justify-between gap-3">
                <span className="inline-flex items-center gap-1.5 rounded-full bg-blue-50 px-3 py-1 text-xs font-bold text-blue-700 dark:bg-blue-950/70 dark:text-blue-300">
                  <Zap className="h-3.5 w-3.5" />
                  {t.badge}
                </span>
                <span className="text-xs font-semibold text-slate-400 dark:text-slate-500">
                  主适宽带：{t.carrier}
                </span>
              </div>

              <h2 className="mt-4 text-xl font-bold text-slate-900 dark:text-slate-100 group-hover:text-blue-600 dark:group-hover:text-blue-400 transition-colors">
                <Link href={`/routes/${t.slug}`} className="before:absolute before:inset-0">
                  {t.name}
                </Link>
              </h2>
              <p className="mt-2 text-xs leading-relaxed text-slate-500 dark:text-slate-400 line-clamp-3">
                {t.summary}
              </p>

              <div className="mt-4 space-y-1.5 border-t border-slate-100 pt-3 dark:border-slate-800">
                {t.highlights.slice(0, 2).map((h, i) => (
                  <div key={i} className="flex items-start gap-2 text-xs text-slate-600 dark:text-slate-300">
                    <CheckCircle2 className="mt-0.5 h-3.5 w-3.5 shrink-0 text-emerald-600 dark:text-emerald-400" />
                    <span>{h}</span>
                  </div>
                ))}
              </div>
            </div>

            <div className="mt-6 flex items-center justify-between pt-2 border-t border-dashed border-slate-200 dark:border-slate-800">
              <span className="text-xs font-medium text-slate-400 dark:text-slate-500">
                {t.recommendFor}
              </span>
              <span className="inline-flex items-center gap-1 text-xs font-bold text-blue-600 group-hover:translate-x-0.5 transition-transform dark:text-blue-400">
                专题机型
                <ArrowRight className="h-3 w-3" />
              </span>
            </div>
          </div>
        ))}
      </div>

      {/* 快速决策指南 */}
      <div className="border-border bg-slate-50/70 dark:bg-slate-900/60 rounded-3xl border p-6 sm:p-8">
        <h3 className="flex items-center gap-2 text-base font-bold text-slate-900 dark:text-slate-100">
          <ShieldCheck className="h-5 w-5 text-blue-600 dark:text-blue-400" />
          小白 3 秒选线决策指南
        </h3>
        <div className="mt-4 grid gap-4 sm:grid-cols-3 text-xs leading-relaxed text-slate-600 dark:text-slate-300">
          <div className="rounded-2xl border border-slate-200/80 bg-card p-4 dark:border-slate-800">
            <div className="font-bold text-blue-600 dark:text-blue-400 mb-1">电信宽带用户</div>
            首选 <strong>CN2 GIA</strong>；预算充足直接上双程 GIA；若预算有限可考虑 <strong>联通 9929</strong>（多数省份电信去回程互联也极佳）。
          </div>
          <div className="rounded-2xl border border-slate-200/80 bg-card p-4 dark:border-slate-800">
            <div className="font-bold text-blue-600 dark:text-blue-400 mb-1">联通宽带用户</div>
            高要求选 <strong>联通 9929</strong>；追求性价比与大带宽直接选 <strong>联通 4837</strong>，日常千兆狂飙且年付极其实惠。
          </div>
          <div className="rounded-2xl border border-slate-200/80 bg-card p-4 dark:border-slate-800">
            <div className="font-bold text-blue-600 dark:text-blue-400 mb-1">移动宽带用户</div>
            务必认准 <strong>移动 CMIN2</strong> 或三网回程专线，彻底告别普通 CMI 晚高峰的丢包与波动，享受对标 GIA 的专线体验。
          </div>
        </div>
      </div>
    </div>
  );
}
