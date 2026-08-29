/**
 * 详情页骨架屏（App Router 约定文件）。
 *
 * 详情页一次要取详情 + 汇率快照 + 相似推荐三组数据，冷启动下最慢，
 * 用同构占位避免白屏与布局跳变。
 *
 * 无障碍：容器标记 aria-busy 并给出 sr-only 状态文本；骨架块是纯装饰结构，
 * 用 aria-hidden 移出无障碍树，避免屏幕阅读器播报无意义的占位元素。
 */
export default function Loading() {
  return (
    <div className="space-y-6" aria-busy="true">
      <p role="status" className="sr-only">
        正在加载套餐详情…
      </p>

      {/* 头部信息卡 */}
      <div
        aria-hidden="true"
        className="border-border bg-card rounded-2xl border p-6 shadow-sm"
      >
        <div className="h-4 w-28 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
        <div className="mt-3 h-7 w-2/3 max-w-xl animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
        <div className="mt-3 h-4 w-1/2 max-w-sm animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
        <div className="mt-5 flex flex-wrap gap-2">
          {Array.from({ length: 4 }).map((_, i) => (
            <div
              key={i}
              className="h-7 w-20 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800"
            />
          ))}
        </div>
      </div>

      {/* 概览 + 价格走势 */}
      <div aria-hidden="true" className="grid gap-4 lg:grid-cols-3">
        <div className="border-border bg-card h-64 animate-pulse rounded-2xl border lg:col-span-2" />
        <div className="border-border bg-card h-64 animate-pulse rounded-2xl border" />
      </div>
    </div>
  );
}
