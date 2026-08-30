import type { Metadata } from "next";
import Link from "next/link";

import { ActiveFilterChips } from "@/components/vps/ActiveFilterChips";
import { FilterControls, type MerchantOption } from "@/components/vps/FilterControls";
import { ListToolbar } from "@/components/vps/ListToolbar";
import { NotifyBanner } from "@/components/vps/notify-banner";
import { Pagination } from "@/components/vps/Pagination";
import { VpsCard } from "@/components/vps/VpsCard";
import { VpsRow } from "@/components/vps/VpsRow";
import { getEventsSummary, listMerchants, listProducts, type ProductsResponse } from "@/lib/api/endpoints";
import { timeAgo } from "@/lib/format";
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
    });
  } catch (e) {
    error = e instanceof Error ? e.message : "列表加载失败";
  }

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const merchantOptions: MerchantOption[] = merchants.map((m) => ({
    slug: m.slug,
    name: m.name,
    count: m.count,
    in_stock_count: m.in_stock_count,
  }));

  const summary = await getEventsSummary(24).catch(() => null);
  const view = state.view ?? "card";

  // 数据新鲜度：页内产品最近一次被爬虫成功确认的时间（AGENTS.md Data Freshness）
  const freshness = items.reduce<string | null>((acc, p) => {
    if (!p.last_checked_at) return acc;
    return !acc || p.last_checked_at > acc ? p.last_checked_at : acc;
  }, null);

  return (
    <div className="flex gap-6">
      {/* 桌面端侧栏筛选 */}
      <aside className="sticky top-20 hidden max-h-[calc(100dvh-6rem)] w-60 shrink-0 self-start overflow-y-auto lg:block">
        <FilterControls state={state} merchants={merchantOptions} />
      </aside>

      {/*
       * 这层卡片外框服务于桌面端「左筛选栏 + 右列表区」的两栏布局。移动端侧栏
       * 已改为抽屉，外框就成了多余的第二层框：它与内部产品卡片的边框叠加，左右
       * 各吃掉 21px，390px 屏上内容区由 358px 缩到 316px（浪费约 12%）。
       * 移动端去掉边框/圆角/背景/内边距，lg 以上（侧栏出现的断点）恢复原样。
       */}
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
              href="/vps"
              className="rounded-xl bg-red-600 px-4 py-1.5 text-xs font-bold text-white transition-colors hover:bg-red-700"
            >
              重新加载
            </Link>
          </div>
        ) : items.length === 0 ? (
          /* 智能零结果状态（带推荐快捷动作） */
          <div className="border-border flex flex-col items-center justify-center rounded-2xl border border-dashed px-4 py-16 text-center">
            <svg
              className="mb-3 h-12 w-12 text-slate-300 dark:text-slate-600"
              fill="none"
              stroke="currentColor"
              strokeWidth="1.5"
              viewBox="0 0 24 24"
              aria-hidden="true"
            >
              <circle cx="11" cy="11" r="7" />
              <path strokeLinecap="round" d="m20 20-3.5-3.5" />
            </svg>
            <h3 className="text-slate-800 text-base font-bold dark:text-slate-100">
              未找到符合当前多重筛选条件的套餐
            </h3>
            <p className="text-slate-400 mt-1 max-w-sm text-xs dark:text-slate-500">
              可能是某些限制（如预算、最低内存或特定机房）过于严苛，建议尝试放宽限制或浏览热门机房：
            </p>
            <div className="mt-4 flex flex-wrap items-center justify-center gap-2">
              <Link
                href="/vps"
                className="rounded-xl bg-blue-600 px-3.5 py-1.5 text-xs font-bold text-white transition-colors hover:bg-blue-700"
              >
                ✨ 一键重置全部筛选
              </Link>
              {[
                { loc: "洛杉矶", flag: "🇺🇸", label: "洛杉矶热门套餐" },
                { loc: "东京", flag: "🇯🇵", label: "日本东京精品套餐" },
                { loc: "香港", flag: "🇭🇰", label: "香港低延迟套餐" },
              ].map((q) => (
                <Link
                  key={q.loc}
                  href={`/vps?location=${encodeURIComponent(q.loc)}`}
                  className="border-border bg-card text-foreground rounded-xl border px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-slate-50 dark:hover:bg-slate-800"
                >
                  {q.flag} {q.label}
                </Link>
              ))}
            </div>
          </div>
        ) : view === "card" ? (
          /*
           * 卡片视图：列宽随容器自适应。
           * 下限由 312px 降到 280px：312px 时 1280px 视口只排得下 2 列（卡片被
           * 拉到 463px），1920px 下仍是 3 列（410px），大屏空间被浪费。降到
           * 280px 后 1280px 排 3 列、1920px 排 4 列，单卡约 300px——与首页精选
           * 位的 295~303px 相当，内容不会被挤坏。
           */
          <div className="grid grid-cols-[repeat(auto-fill,minmax(min(260px,100%),1fr))] gap-4">
            {items.map((p) => (
              <VpsCard key={p.id} product={p} />
            ))}
          </div>
        ) : (
          /* 列表视图：表头仅桌面端显示，移动端行内已自解释 */
          <div>
            <div className="border-border/60 bg-slate-50/80 text-muted-foreground mb-1 hidden items-center gap-3 rounded-xl px-4 py-2 text-xs font-bold sm:flex dark:bg-slate-800/60">
              <div className="min-w-0 flex-1">套餐名称与商家</div>
              <div className="hidden w-[220px] shrink-0 lg:block">配置 / 流量</div>
              <div className="hidden w-[100px] shrink-0 md:block">机房位置</div>
              <div className="hidden w-[168px] shrink-0 lg:block">网络与线路</div>
              <div className="w-[125px] shrink-0 text-right">价格与周期</div>
              <div className="hidden w-16 shrink-0 text-center xl:block">现货状态</div>
              <div className="w-[144px] shrink-0 text-right">操作</div>
            </div>
            {items.map((p) => (
              <VpsRow key={p.id} product={p} />
            ))}
          </div>
        )}

        {items.length > 0 && (
          <Pagination state={state} total={total} freshness={timeAgo(freshness)} />
        )}

        {items.length > 0 && (
          <p className="text-muted-foreground mt-4 text-xs leading-relaxed">
            价格为商家原币标价，「折年」为同币种按付款周期折算，跨币种统一折算为美元参考价。
            数据更新时间以卡片标注为准，库存与价格以商家页面为准。
          </p>
        )}
      </section>
    </div>
  );
}
