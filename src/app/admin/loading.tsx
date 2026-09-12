export default function AdminLoading() {
  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div className="h-7 w-32 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
        <div className="h-8 w-16 animate-pulse rounded-lg bg-slate-100 dark:bg-slate-800" />
      </div>
      <div className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        {Array.from({ length: 4 }).map((_, i) => (
          <div key={i} className="border-border bg-card h-24 animate-pulse rounded-2xl border" />
        ))}
      </div>
      <div className="border-border bg-card h-64 animate-pulse rounded-2xl border" />
    </div>
  );
}
