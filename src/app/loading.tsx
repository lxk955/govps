/**
 * 根级骨架屏（App Router 约定文件）。
 *
 * 同时作为未单独声明 loading.tsx 的路由的兜底 fallback。
 */
export default function Loading() {
  return (
    <main>
      <section className="border-b">
        <div className="mx-auto w-full max-w-7xl px-4 py-12 lg:py-16">
          <div className="h-8 w-2/3 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800 lg:h-10" />
          <div className="mt-4 h-4 w-full max-w-xl animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
          <div className="mt-2 h-4 w-3/4 max-w-md animate-pulse rounded bg-slate-100 dark:bg-slate-800" />
          <div className="mt-6 flex gap-2">
            <div className="h-9 w-32 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
            <div className="h-9 w-32 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
          </div>
        </div>
      </section>

      <div className="mx-auto w-full max-w-7xl px-4 py-8">
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
