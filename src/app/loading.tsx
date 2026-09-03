/**
 * 列表页骨架屏（App Router 约定文件）。
 *
 * 列表页是 RSC 每请求回源（no-store），后端冷启动时用与真实布局同构的占位块，
 * 让首屏立刻有内容、避免布局跳变（CLS）。
 *
 * 列宽规则与真实列表一致：grid-cols-[repeat(auto-fill,minmax(min(260px,100%),1fr))]
 */
export default function Loading() {
  return (
    <div className="flex gap-6" aria-busy="true">
      <p role="status" className="sr-only">
        正在加载套餐列表…
      </p>

      {/* 桌面端侧栏筛选占位 */}
      <aside aria-hidden="true" className="hidden w-60 shrink-0 lg:block">
        <div className="border-border bg-card space-y-2.5 rounded-2xl border p-3.5 shadow-sm">
          <div className="h-4 w-16 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
          <div className="h-9 w-full animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
          {Array.from({ length: 7 }).map((_, i) => (
            <div
              key={i}
              className="h-8 w-full animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800"
            />
          ))}
        </div>
      </aside>

      <section
        aria-hidden="true"
        className="border-border bg-card min-w-0 flex-1 lg:rounded-2xl lg:border lg:p-5"
      >
        {/* 顶部工具栏占位 */}
        <div className="mb-4 flex flex-wrap items-center gap-2">
          <div className="h-9 w-full max-w-xs animate-pulse rounded-xl bg-slate-100 sm:w-64 dark:bg-slate-800" />
          <div className="h-8 w-40 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
        </div>

        {/* 卡片网格占位：列宽规则与真实列表一致 */}
        <div className="grid grid-cols-[repeat(auto-fill,minmax(min(260px,100%),1fr))] gap-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="border-border h-56 animate-pulse rounded-2xl border bg-slate-100 dark:bg-slate-800"
            />
          ))}
        </div>
      </section>
    </div>
  );
}
