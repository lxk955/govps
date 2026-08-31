import type { Metadata } from "next";
import Link from "next/link";

import { FilterControls, type MerchantOption } from "@/components/vps/FilterControls";
import { ListDataProvider } from "@/components/vps/list-data-context";
import { getEventsSummary, listMerchants, listProducts, type ProductsResponse } from "@/lib/api/endpoints";
import { parseListQuery, toProductParams } from "@/lib/query-state";
import { VpsListClient } from "@/components/vps/vps-list-client";

export const metadata: Metadata = {
  title: "VPS 套餐列表",
  description:
    "多商家 VPS 套餐聚合列表：按商家、机房、线路、价格与配置筛选，支持降价、补货与史低价监控。",
  alternates: { canonical: "/vps" },
};

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

/**
 * RSC 首屏：服务端取数保证 SEO 与首屏完整性；
 * 数据注入 ListDataProvider 后，客户端筛选走 SWR 缓存链路（不触发 RSC 导航）。
 */
export default async function VpsListPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const state = parseListQuery(sp);

  const [merchants, productResult, summary] = await Promise.all([
    listMerchants().catch(() => []),
    listProducts(toProductParams(state))
      .then((data) => ({ data, error: null as string | null }))
      .catch((e) => ({
        data: null as ProductsResponse | null,
        error: e instanceof Error ? e.message : "列表加载失败",
      })),
    getEventsSummary(24).catch(() => null),
  ]);

  const merchantOptions: MerchantOption[] = merchants.map((m) => ({
    slug: m.slug,
    name: m.name,
    count: m.count,
    in_stock_count: m.in_stock_count,
  }));

  return (
    <ListDataProvider
      initialState={state}
      initialData={productResult.data}
      initialError={productResult.error}
    >
      <div className="flex gap-6">
        {/* 桌面端侧栏筛选 */}
        <aside className="sticky top-20 hidden max-h-[calc(100dvh-6rem)] w-60 shrink-0 self-start overflow-y-auto lg:block">
          <FilterControls merchants={merchantOptions} />
        </aside>

        {/*
         * 这层卡片外框服务于桌面端「左筛选栏 + 右列表区」的两栏布局。移动端侧栏
         * 已改为抽屉，外框就成了多余的第二层框：它与内部产品卡片的边框叠加，左右
         * 各吃掉 21px，390px 屏上内容区由 358px 缩到 316px（浪费约 12%）。
         * 移动端去掉边框/圆角/背景/内边距，lg 以上（侧栏出现的断点）恢复原样。
         */}
        <section className="border-border bg-card min-w-0 flex-1 lg:rounded-2xl lg:border lg:p-5">
          {/* 补货/降价动态聚合条（与筛选无关，RSC 静态渲染） */}
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

          <VpsListClient merchants={merchantOptions} />
        </section>
      </div>
    </ListDataProvider>
  );
}
