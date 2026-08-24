import type { Metadata } from "next";
import Link from "next/link";
import { AlertTriangle, SearchX } from "lucide-react";

import { Button } from "@/components/ui/button";
import { ActiveFilterChips } from "@/components/vps/ActiveFilterChips";
import { FilterControls } from "@/components/vps/FilterControls";
import { ListToolbar } from "@/components/vps/ListToolbar";
import { Pagination } from "@/components/vps/Pagination";
import { VpsCard } from "@/components/vps/VpsCard";
import { VpsRow } from "@/components/vps/VpsRow";
import { listMerchants, listProducts, type ProductsResponse } from "@/lib/api/endpoints";
import { parseListQuery } from "@/lib/query-state";

export const metadata: Metadata = {
  title: "VPS 套餐列表",
  description:
    "多商家 VPS 套餐聚合列表：按商家、机房、线路、价格与配置筛选，支持降价、补货与史低价监控。",
  alternates: { canonical: "/vps" },
};

interface PageProps {
  searchParams: Promise<Record<string, string | string[] | undefined>>;
}

export default async function VpsListPage({ searchParams }: PageProps) {
  const sp = await searchParams;
  const state = parseListQuery(sp);

  let data: ProductsResponse | null = null;
  let error: string | null = null;
  const merchants = await listMerchants().catch(() => []);
  try {
    data = await listProducts({
      merchant: state.merchant,
      location: state.location,
      line: state.line,
      keyword: state.keyword || undefined,
      sort: state.sort,
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
    });
  } catch (e) {
    error = e instanceof Error ? e.message : "列表加载失败";
  }

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const merchantOptions = merchants.map((m) => ({
    slug: m.slug,
    name: m.name,
    in_stock_count: m.in_stock_count,
  }));

  return (
    <div className="mx-auto w-full max-w-7xl px-4 py-6 lg:py-8">
      <header className="mb-4">
        <h1 className="text-xl font-bold tracking-tight lg:text-2xl">VPS 套餐</h1>
        <p className="text-muted-foreground mt-1 text-sm">
          {error
            ? "数据加载失败，请稍后重试"
            : total > 0
              ? `共 ${total} 款套餐（聚合同配置不同付款周期）`
              : "暂无匹配的套餐"}
        </p>
      </header>

      <div className="flex flex-col gap-4">
        <ActiveFilterChips state={state} />
        <ListToolbar state={state} merchants={merchantOptions} />
      </div>

      <div className="mt-4 flex flex-col gap-6 lg:mt-6 lg:flex-row lg:gap-8">
        {/* 桌面侧栏筛选（lg+ 显示；移动端走 ListToolbar 里的 Sheet） */}
        <aside className="hidden w-64 shrink-0 lg:block" aria-label="筛选侧栏">
          <FilterControls state={state} merchants={merchantOptions} />
        </aside>

        <section className="min-w-0 flex-1" aria-label="套餐列表" aria-busy={error ? undefined : false}>
          {error ? (
            <div
              role="alert"
              className="border-destructive/30 bg-destructive/5 text-destructive flex flex-col items-center gap-3 rounded-xl border p-10 text-center"
            >
              <AlertTriangle aria-hidden className="h-8 w-8" />
              <p className="text-sm">{error}</p>
              <Button asChild variant="outline" size="sm">
                <Link href="/vps">重置筛选并重试</Link>
              </Button>
            </div>
          ) : items.length === 0 ? (
            <div className="text-muted-foreground flex flex-col items-center gap-3 rounded-xl border border-dashed p-12 text-center">
              <SearchX aria-hidden className="h-8 w-8" />
              <p className="text-sm">没有符合当前筛选的套餐</p>
              <Button asChild variant="outline" size="sm">
                <Link href="/vps">清空筛选</Link>
              </Button>
            </div>
          ) : (
            <>
              {/* 移动/平板：卡片形态 */}
              <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:hidden">
                {items.map((p) => (
                  <li key={p.id} className="min-w-0">
                    <VpsCard product={p} />
                  </li>
                ))}
              </ul>
              {/* 桌面：表格行形态（外层包裹 overflow-x-auto 防止 1024px 视口撑破页面） */}
              <div className="hidden lg:block overflow-x-auto rounded-xl border">
                <table className="w-full min-w-[680px] border-separate border-spacing-0 text-left">
                  <caption className="sr-only">VPS 套餐列表</caption>
                  <thead>
                    <tr className="bg-muted/40 text-muted-foreground text-xs">
                      <th scope="col" className="border-b px-3 py-2.5 font-medium">套餐 / 商家</th>
                      <th scope="col" className="border-b px-3 py-2.5 font-medium">配置</th>
                      <th scope="col" className="border-b px-3 py-2.5 font-medium">流量 / 带宽</th>
                      <th scope="col" className="border-b px-3 py-2.5 font-medium">机房 / 线路</th>
                      <th scope="col" className="border-b px-3 py-2.5 font-medium">状态</th>
                      <th scope="col" className="border-b px-3 py-2.5 text-right font-medium">价格</th>
                      <th scope="col" className="border-b px-3 py-2.5 font-medium">
                        <span className="sr-only">购买</span>
                      </th>
                    </tr>
                  </thead>
                  <tbody className="divide-y">
                    {items.map((p) => (
                      <VpsRow key={p.id} product={p} />
                    ))}
                  </tbody>
                </table>
              </div>
              <Pagination state={state} total={total} />
              <p className="text-muted-foreground mt-4 text-xs">
                价格为商家原币标价；「折年 ≈」为同币种按付款周期折算，跨币种统一换算将在后续版本提供。
                数据更新时间以卡片标注为准，库存与价格以商家页面为准。
              </p>
            </>
          )}
        </section>
      </div>
    </div>
  );
}
