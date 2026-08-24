import Link from "next/link";

import type { ListQueryState } from "@/lib/query-state";
import { queryToString } from "@/lib/query-state";

/** URL 驱动的分页（服务端渲染 Link，无额外 JS）。 */

function pageHref(state: ListQueryState, page: number): string {
  const qs = queryToString({ ...state, page });
  return `/vps${qs ? `?${qs}` : ""}`;
}

export function Pagination({
  state,
  total,
}: {
  state: ListQueryState;
  total: number;
}) {
  const pages = Math.max(1, Math.ceil(total / state.size));
  if (pages <= 1) return null;

  const current = Math.min(state.page, pages);
  // 最多显示 5 个页码，超出用省略号
  const windowStart = Math.max(1, Math.min(current - 2, pages - 4));
  const windowPages = Array.from({ length: Math.min(5, pages) }, (_, i) => windowStart + i);

  return (
    <nav aria-label="分页" className="mt-6 flex items-center justify-center gap-1">
      {current > 1 && (
        <Link
          href={pageHref(state, current - 1)}
          className="border-input hover:bg-muted rounded-md border px-3 py-1.5 text-sm"
          prefetch={false}
        >
          上一页
        </Link>
      )}
      {windowStart > 1 && (
        <>
          <PageLink href={pageHref(state, 1)} page={1} active={current === 1} />
          <span className="text-muted-foreground px-1">…</span>
        </>
      )}
      {windowPages.map((p) => (
        <PageLink key={p} href={pageHref(state, p)} page={p} active={p === current} />
      ))}
      {windowStart + 4 < pages && (
        <>
          <span className="text-muted-foreground px-1">…</span>
          <PageLink href={pageHref(state, pages)} page={pages} active={current === pages} />
        </>
      )}
      {current < pages && (
        <Link
          href={pageHref(state, current + 1)}
          className="border-input hover:bg-muted rounded-md border px-3 py-1.5 text-sm"
          prefetch={false}
        >
          下一页
        </Link>
      )}
    </nav>
  );
}

function PageLink({ href, page, active }: { href: string; page: number; active: boolean }) {
  return (
    <Link
      href={href}
      aria-current={active ? "page" : undefined}
      aria-label={`第 ${page} 页`}
      className={
        active
          ? "bg-primary text-primary-foreground rounded-md px-3 py-1.5 text-sm font-medium"
          : "border-input hover:bg-muted rounded-md border px-3 py-1.5 text-sm"
      }
      prefetch={false}
    >
      {page}
    </Link>
  );
}
