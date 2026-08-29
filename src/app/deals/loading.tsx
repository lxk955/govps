/**
 * 动态页骨架屏（App Router 约定文件）：事件流按行占位。
 *
 * 无障碍：容器标记 aria-busy 并给出 sr-only 状态文本；骨架块是纯装饰结构，
 * 用 aria-hidden 移出无障碍树，避免屏幕阅读器播报无意义的占位元素。
 */
export default function Loading() {
  return (
    <div
      aria-busy="true"
      className="border-border bg-card rounded-xl border p-5 shadow-sm"
    >
      <p role="status" className="sr-only">
        正在加载降价与补货动态…
      </p>

      <div aria-hidden="true">
        <div className="mb-5 flex flex-wrap items-center justify-between gap-3">
          <div className="h-6 w-28 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
          <div className="h-9 w-52 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
        </div>
        <div className="space-y-3">
          {Array.from({ length: 8 }).map((_, i) => (
            <div
              key={i}
              className="border-border h-20 animate-pulse rounded-xl border bg-slate-100 dark:bg-slate-800"
            />
          ))}
        </div>
      </div>
    </div>
  );
}
