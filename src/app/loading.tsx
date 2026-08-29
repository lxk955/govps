/**
 * 根级骨架屏（App Router 约定文件）。
 *
 * 同时作为未单独声明 loading.tsx 的路由的兜底 fallback。
 *
 * 无障碍：容器标记 aria-busy 并给出 sr-only 状态文本；骨架块是纯装饰结构，
 * 用 aria-hidden 移出无障碍树，避免屏幕阅读器播报无意义的占位元素。
 */
export default function Loading() {
  return (
    <main aria-busy="true">
      <p role="status" className="sr-only">
        正在加载首页数据…
      </p>

      <section aria-hidden="true" className="border-b">
        <div className="mx-auto w-full max-w-7xl px-4 py-12 lg:py-16">
          <div className="h-8 w-2/3 animate-pulse rounded-lg bg-slate-200 lg:h-10 dark:bg-slate-800" />
          <div className="mt-4 h-4 w-full max-w-xl animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
          <div className="mt-2 h-4 w-3/4 max-w-md animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
          <div className="mt-6 flex gap-2">
            <div className="h-9 w-32 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
            <div className="h-9 w-32 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
          </div>
        </div>
      </section>

      <div aria-hidden="true" className="mx-auto w-full max-w-7xl px-4 py-8">
        <div className="mb-3 h-5 w-24 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
        <div className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-4">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="border-border h-56 animate-pulse rounded-xl border bg-slate-100 dark:bg-slate-800"
            />
          ))}
        </div>
      </div>
    </main>
  );
}
