/**
 * 探针监控页骨架屏（App Router 约定文件）。
 */
export default function MonitorLoading() {
  return (
    <div
      aria-busy="true"
      className="mx-auto max-w-7xl px-4 sm:px-6 py-6"
    >
      <p role="status" className="sr-only">
        正在加载探针监控看板…
      </p>

      <div aria-hidden="true" className="space-y-6">
        {/* 顶部标题骨架 */}
        <div className="flex items-center justify-between">
          <div className="h-7 w-36 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
          <div className="h-7 w-24 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
        </div>

        {/* 4 个概览卡片骨架 */}
        <div className="grid grid-cols-1 sm:grid-cols-2 lg:grid-cols-4 gap-3.5">
          {[1, 2, 3, 4].map((i) => (
            <div
              key={i}
              className="h-28 animate-pulse rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 p-4"
            />
          ))}
        </div>

        {/* 工具栏骨架 */}
        <div className="flex items-center justify-between">
          <div className="h-8 w-48 animate-pulse rounded-xl bg-slate-200 dark:bg-slate-800" />
          <div className="h-8 w-32 animate-pulse rounded-xl bg-slate-100 dark:bg-slate-800" />
        </div>

        {/* 节点卡片网格骨架 */}
        <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4">
          {[1, 2, 3, 4, 5, 6].map((i) => (
            <div
              key={i}
              className="h-96 animate-pulse rounded-2xl bg-white dark:bg-slate-900 border border-slate-200/80 dark:border-slate-800 p-5"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
