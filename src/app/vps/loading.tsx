/**
 * 列表页骨架屏：筛选/翻页的 RSC 导航期间立即显示，消除「点了没反应」。
 * 结构与页面同构（桌面侧栏 + 工具条 + 卡片网格），加载完成后视觉跳动最小。
 */
export default function VpsLoading() {
  return (
    <div className="flex gap-6" aria-busy="true" aria-label="加载中">
      {/* 桌面侧栏骨架 */}
      <aside className="sticky top-20 hidden max-h-[calc(100dvh-6rem)] w-60 shrink-0 self-start space-y-3.5 lg:block">
        <div className="bg-muted h-12 animate-pulse rounded-xl" />
        <div className="bg-muted h-64 animate-pulse rounded-2xl" />
        <div className="bg-muted h-48 animate-pulse rounded-2xl" />
      </aside>

      <section className="min-w-0 flex-1">
        {/* 工具条 + 筛选胶囊行 */}
        <div className="mb-4 flex items-center justify-between gap-3">
          <div className="bg-muted h-9 flex-1 animate-pulse rounded-xl" />
          <div className="bg-muted h-9 w-24 shrink-0 animate-pulse rounded-xl" />
        </div>

        {/* 卡片网格：与列表页卡片视图同列宽节奏 */}
        <div className="grid grid-cols-[repeat(auto-fill,minmax(min(260px,100%),1fr))] gap-4">
          {Array.from({ length: 9 }, (_, i) => (
            <div key={i} className="bg-muted h-72 animate-pulse rounded-2xl" />
          ))}
        </div>
      </section>
    </div>
  );
}
