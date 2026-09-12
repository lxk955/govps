export default function WatchlistLoading() {
  return (
    <div className="border-border bg-card rounded-xl border p-5 shadow-sm">
      <div className="mb-5 space-y-2">
        <div className="h-6 w-28 animate-pulse rounded bg-slate-200 dark:bg-slate-800" />
        <div className="h-4 w-64 animate-pulse rounded bg-slate-100 dark:bg-slate-800/60" />
      </div>
      <div className="grid grid-cols-[repeat(auto-fill,minmax(min(300px,100%),1fr))] gap-4">
        {Array.from({ length: 3 }).map((_, i) => (
          <div key={i} className="bg-muted h-72 animate-pulse rounded-2xl" />
        ))}
      </div>
    </div>
  );
}
