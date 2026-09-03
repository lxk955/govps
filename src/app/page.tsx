import type { Metadata } from "next";
import Link from "next/link";

import { ActiveFilterChips } from "@/components/vps/ActiveFilterChips";
import { FilterControls, type MerchantOption } from "@/components/vps/FilterControls";
import { ListToolbar } from "@/components/vps/ListToolbar";
import { NotifyBanner } from "@/components/vps/notify-banner";
import { Pagination } from "@/components/vps/Pagination";
import { VpsCard } from "@/components/vps/VpsCard";
import { VpsRow } from "@/components/vps/VpsRow";
import {
  getEventsSummary,
  listMerchants,
  listProducts,
  type ProductsResponse,
} from "@/lib/api/endpoints";
import { parseListQuery } from "@/lib/query-state";
import { ROW_ACTIONS_HEAD } from "@/lib/row-layout";

export const metadata: Metadata = {
  title: { absolute: "GoVPS · VPS雷达 - 实时 VPS 库存、降价监控与线路对比" },
  description:
    "多商家 VPS 套餐实时聚合：按商家、机房、线路、价格与配置极速筛选，支持 CN2 GIA / 9929 / CMIN2 优质线路、降价与补货自动监控。",
  alternates: { canonical: "/" },
};

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function HomePage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const state = parseListQuery(sp);

  const [merchants, productResult, summary] = await Promise.all([
    listMerchants().catch(() => []),
    listProducts({
      merchant: state.merchant,
      location: state.location,
      line: state.line,
      keyword: state.keyword || undefined,
      sort: state.sort === "hot" ? undefined : state.sort,
      page: state.page,
      size: state.size,
      min_price: state.min_price,
      max_price: state.max_price,
      min_cpu: state.min_cpu,
      min_ram: state.min_ram,
      min_bw: state.min_bw,
      min_port: state.min_port,
      in_stock: state.in_stock,
      price_drop: state.price_drop,
      lowest_price: state.lowest_price,
      recent_restock: state.recent_restock,
      recommended: state.recommended,
    })
      .then((data) => ({ data, error: null as string | null }))
      .catch((e) => ({
        data: null as ProductsResponse | null,
        error: e instanceof Error ? e.message : "列表加载失败",
      })),
    getEventsSummary(24).catch(() => null),
  ]);
  const data = productResult.data;
  const error = productResult.error;

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const merchantOptions: MerchantOption[] = merchants.map((m) => ({
    slug: m.slug,
    name: m.name,
    count: m.count,
    in_stock_count: m.in_stock_count,
  }));

  const view = state.view ?? "card";

  // 数据新鲜度：页内产品最近一次被爬虫成功确认的时间（AGENTS.md Data Freshness）
  const freshness = items.reduce<string | null>((acc, p) => {
    if (!p.last_checked_at) return acc;
    return !acc || p.last_checked_at > acc ? p.last_checked_at : acc;
  }, null);

  return (
    <>
      {/* 顶部紧凑定位区：兼顾品牌与 SEO，开门见山 */}
      <header className="mb-4">
        <h1 className="text-xl font-bold tracking-tight text-foreground lg:text-2xl">
          VPS 实时雷达
        </h1>
        <p className="text-muted-foreground mt-0.5 text-xs sm:text-sm">
          全网多商家套餐实时监控 · CN2 GIA / 9929 / CMIN2 优质线路聚合 · 价格与库存变动秒级感知
        </p>
      </header>

      <div className="flex gap-6">
        {/* 桌面端侧栏筛选 */}
        <aside className="sticky top-20 hidden max-h-[calc(100dvh-6rem)] w-60 shrink-0 self-start overflow-y-auto lg:block">
          <FilterControls state={state} merchants={merchantOptions} />
        </aside>

        {/* 主列表区 */}
        <section className="border-border bg-card min-w-0 flex-1 lg:rounded-2xl lg:border lg:p-5">
          {/* 补货/降价动态聚合条（有事件才展示） */}
          {summary && (summary.restock_count > 0 || summary.drop_count > 0) && (
            <Link
              href="/deals"
              className="mb-4 flex flex-wrap items-center gap-x-4 gap-y-1 rounded-xl border border-blue-100 bg-gradient-to-r from-blue-50/90 to-indigo-50/70 px-3.5 py-2 text-xs text-slate-600 transition-all hover:border-blue-300 dark:border-blue-900 dark:from-blue-950/50 dark:to-indigo-950/40 dark:text-slate-300"
            >
              <span className="flex items-center gap-1.5 font-bold text-slate-800 dark:text-slate-100">
                📡 实时动态
              </span>
              {summary.restock_count > 0 && (
                <span className="flex items-center gap-1 font-medium text-emerald-700 dark:text-emerald-400">
                  ⚡ 近 24h 补货 <b className="font-black">{summary.restock_count}</b> 个
                </span>
              )}
              {summary.drop_count > 0 && (
                <span className="flex items-center gap-1 font-medium text-orange-600 dark:text-orange-400">
                  📉 降价 <b className="font-black">{summary.drop_count}</b> 个
                </span>
              )}
              <span className="ml-auto flex items-center gap-1 font-bold text-blue-600 dark:text-blue-400">
                查看动态 →
              </span>
            </Link>
          )}

          {/* 顶部操作区：搜索 + 视图切换 + 快捷筛选胶囊 */}
          <ListToolbar state={state} merchants={merchantOptions} total={total} />
          <ActiveFilterChips state={state} merchants={merchantOptions} />

          {/* 未登录通知引导横幅 */}
          <NotifyBanner />

          {error ? (
            <div className="flex flex-col items-center gap-3 rounded-2xl border border-red-100 bg-red-50 px-4 py-12 text-center dark:border-red-900 dark:bg-red-950/30">
              <div className="text-3xl">📡</div>
              <p className="text-sm font-medium text-red-600 dark:text-red-400">{error}</p>
              <Link
                href="/"
                className="rounded-xl bg-red-600 px-4 py-1.5 text-xs font-bold text-white transition-colors hover:bg-red-700"
              >
                重新加载
              </Link>
            </div>
          ) : items.length === 0 ? (
            /* 智能零结果状态（带推荐快捷动作） */
            <div className="border-border flex flex-col items-center justify-center rounded-2xl border border-dashed px-4 py-16 text-center">
              <svg
                aria-hidden
                className="text-muted-foreground/50 h-10 w-10"
                viewBox="0 0 24 24"
                fill="none"
                stroke="currentColor"
                strokeWidth="1.5"
              >
                <path
                  strokeLinecap="round"
                  strokeLinejoin="round"
                  d="m21 21-5.197-5.197m0 0A7.5 7.5 0 1 0 5.196 5.196a7.5 7.5 0 0 0 10.607 10.607z"
                />
              </svg>
              <p className="text-foreground mt-3 text-sm font-bold">未找到符合条件的套餐</p>
              <p className="text-muted-foreground mt-1 max-w-sm text-xs leading-relaxed">
                当前筛选条件组合过于严格，建议尝试放宽限制或清除部分条件。
              </p>
              <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
                <Link
                  href="/"
                  className="bg-primary text-primary-foreground hover:bg-primary/90 rounded-xl px-3.5 py-1.5 text-xs font-bold transition-colors"
                >
                  清空全部筛选
                </Link>
                {state.in_stock && (
                  <Link
                    href="/?in_stock=false"
                    className="border-border bg-card text-foreground hover:bg-accent rounded-xl border px-3 py-1.5 text-xs font-medium transition-colors"
                  >
                    包含缺货套餐
                  </Link>
                )}
              </div>
            </div>
          ) : view === "card" ? (
            /* 卡片视图 */
            <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 xl:grid-cols-3">
              {items.map((p) => (
                <VpsCard key={p.id} product={p} />
              ))}
            </div>
          ) : (
            /* 列表视图：移动端卡片式展示（消除表格挤压），桌面端 6 列标准表 */
            <>
              {/* 移动端卡片式条目 */}
              <div className="flex flex-col gap-2.5 sm:hidden">
                {items.map((p) => (
                  <VpsCard key={p.id} product={p} />
                ))}
              </div>

              {/* 桌面端标准表格 */}
              <div className="border-border hidden overflow-hidden rounded-xl border sm:block">
                <div className="overflow-x-auto">
                  <table className="w-full text-left text-xs">
                    <thead className="bg-muted/60 text-muted-foreground border-b font-medium">
                      <tr>
                        <th className="px-3 py-2.5">商家 / 套餐</th>
                        <th className="px-3 py-2.5">机房</th>
                        <th className="px-3 py-2.5">线路</th>
                        <th className="px-3 py-2.5">配置 / 流量</th>
                        <th className="px-3 py-2.5 text-right">价格</th>
                        <th className={ROW_ACTIONS_HEAD}>操作</th>
                      </tr>
                    </thead>
                    <tbody className="divide-y">
                      {items.map((p) => (
                        <VpsRow key={p.id} product={p} />
                      ))}
                    </tbody>
                  </table>
                </div>
              </div>
            </>
          )}

          {/* 底部统计与翻页 */}
          <Pagination state={state} total={total} freshness={freshness} />
        </section>
      </div>
    </>
  );
}
