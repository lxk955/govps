"use client";

import Link from "next/link";

import { ActiveFilterChips } from "@/components/vps/ActiveFilterChips";
import { type MerchantOption } from "@/components/vps/FilterControls";
import { useListData } from "@/components/vps/list-data-context";
import { ListToolbar } from "@/components/vps/ListToolbar";
import { NotifyBanner } from "@/components/vps/notify-banner";
import { Pagination } from "@/components/vps/Pagination";
import { VpsCard } from "@/components/vps/VpsCard";
import { VpsRow } from "@/components/vps/VpsRow";
import { ROW_ACTIONS_HEAD } from "@/lib/row-layout";
import { timeAgo } from "@/lib/format";

/**
 * 列表区客户端组件：数据来自 ListDataProvider（SWR 缓存优先），
 * 筛选交互由 store 内部处理，不再依赖 RSC 导航。
 *
 * "use client" 组件同样会被 SSR 渲染：首屏 HTML 由服务端输出（SEO 不受影响），
 * 客户端水合后交互走缓存链路。
 */
export function VpsListClient({ merchants }: { merchants: MerchantOption[] }) {
  const { state, data, loading, revalidating, error, refresh } = useListData();

  const items = data?.items ?? [];
  const total = data?.total ?? 0;
  const view = state.view ?? "card";

  // 数据新鲜度：页内产品最近一次被爬虫成功确认的时间（AGENTS.md Data Freshness）
  const freshness = items.reduce<string | null>((acc, p) => {
    if (!p.last_checked_at) return acc;
    return !acc || p.last_checked_at > acc ? p.last_checked_at : acc;
  }, null);

  /** 首屏即失败（无数据可显示）与运行时刷新失败（保留旧数据）分开处理 */
  const fatal = error !== null && data === null;

  return (
    <>
      <ListToolbar merchants={merchants} />
      <ActiveFilterChips merchants={merchants} />
      <NotifyBanner />

      {fatal ? (
        <div className="flex flex-col items-center gap-3 rounded-2xl border border-red-100 bg-red-50 px-4 py-12 text-center dark:border-red-900 dark:bg-red-950/30">
          <div className="text-3xl">📡</div>
          <p className="text-sm font-medium text-red-600 dark:text-red-400">{error}</p>
          <button
            type="button"
            onClick={refresh}
            className="cursor-pointer rounded-xl bg-red-600 px-4 py-1.5 text-xs font-bold text-white transition-colors hover:bg-red-700"
          >
            重新加载
          </button>
        </div>
      ) : items.length === 0 && !loading ? (
        /* 智能零结果状态（带推荐快捷动作） */
        <EmptyState merchants={merchants} />
      ) : (
        <div className="relative">
          {/* 后台刷新/加载指示：顶部细条 + 旧列表降透明度保留可读 */}
          {(loading || revalidating) && (
            <div
              role="status"
              aria-label={revalidating ? "正在更新结果" : "加载中"}
              className="absolute inset-x-0 top-0 z-10 h-0.5 overflow-hidden"
            >
              <div className="h-full w-1/3 animate-[list-loading_1s_ease-in-out_infinite] rounded-full bg-blue-500" />
            </div>
          )}
          <div
            className={
              loading || revalidating
                ? "pointer-events-none opacity-60 transition-opacity"
                : "transition-opacity"
            }
          >
            {items.length === 0 ? (
              /* 首次加载尚无数据：与卡片网格同构骨架 */
              <div className="grid grid-cols-[repeat(auto-fill,minmax(min(260px,100%),1fr))] gap-4" aria-hidden="true">
                {Array.from({ length: 9 }, (_, i) => (
                  <div key={i} className="bg-muted h-72 animate-pulse rounded-2xl" />
                ))}
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
                  {/* 列宽须与内容行 RowBuyZone 的 ROW_ACTIONS_ROW 一致，否则标题与内容错位 */}
                  <div className={`${ROW_ACTIONS_HEAD} shrink-0 text-right`}>操作</div>
                </div>
                {items.map((p) => (
                  <VpsRow key={p.id} product={p} />
                ))}
              </div>
            )}
          </div>
        </div>
      )}

      {items.length > 0 && (
        <Pagination freshness={timeAgo(freshness)} />
      )}

      {items.length > 0 && (
        <p className="text-muted-foreground mt-4 text-xs leading-relaxed">
          价格为商家原币标价，「折年」为同币种按付款周期折算，跨币种统一折算为美元参考价。
          数据更新时间以卡片标注为准，库存与价格以商家页面为准。
        </p>
      )}
    </>
  );
}

/** 智能零结果状态（带推荐快捷动作；重置/热门机房均走 store 瞬时切换） */
function EmptyState({ merchants }: { merchants: MerchantOption[] }) {
  const { apply } = useListData();
  return (
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
        <button
          type="button"
          onClick={() => apply({})}
          className="cursor-pointer rounded-xl bg-blue-600 px-3.5 py-1.5 text-xs font-bold text-white transition-colors hover:bg-blue-700"
        >
          ✨ 一键重置全部筛选
        </button>
        {merchants.length > 0 &&
          [
            { loc: "洛杉矶", flag: "🇺🇸" },
            { loc: "东京", flag: "🇯🇵" },
            { loc: "香港", flag: "🇭🇰" },
          ].map((q) => (
            <Link
              key={q.loc}
              href={`/vps?location=${encodeURIComponent(q.loc)}`}
              onClick={(e) => {
                e.preventDefault();
                apply({ location: [q.loc] });
              }}
              className="border-border bg-card text-foreground rounded-xl border px-3 py-1.5 text-xs font-semibold transition-colors hover:bg-slate-50 dark:hover:bg-slate-800"
            >
              {q.flag} {q.loc}热门套餐
            </Link>
          ))}
      </div>
    </div>
  );
}
