export default function LoginLoading() {
  return (
    <div className="mx-auto flex min-h-[60dvh] w-full max-w-7xl flex-col justify-center px-4 py-8">
      <header className="mb-5 text-center">
        <div className="mx-auto h-7 w-36 animate-pulse rounded-lg bg-slate-200 dark:bg-slate-800" />
        <div className="mx-auto mt-2 h-4 w-64 animate-pulse rounded bg-slate-100 dark:bg-slate-800/60" />
      </header>
      <div className="mx-auto w-full max-w-sm">
        <div className="border-border bg-card h-64 animate-pulse rounded-2xl border p-6 shadow-sm" />
      </div>
    </div>
  );
}
