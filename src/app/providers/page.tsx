import type { Metadata } from "next";
import Link from "next/link";
import { ArrowUpRight, PackageSearch } from "lucide-react";

import { listMerchants, type MerchantSummary } from "@/lib/api/endpoints";
import { timeAgo } from "@/lib/format";

export const metadata: Metadata = {
  title: "服务商一览",
  description:
    "GoVPS 收录的 VPS 服务商：在售套餐数、库存状态与数据抓取新鲜度一览，点击查看各商家全部套餐。",
  alternates: { canonical: "/providers" },
};

function Freshness({ at }: { at: string | null }) {
  const fresh = at != null && Date.now() - new Date(at).getTime() < 60 * 60 * 1000;
  return (
    <span className="inline-flex items-center gap-1.5 text-xs">
      <span
        aria-hidden
        className={`h-2 w-2 shrink-0 rounded-full ${fresh ? "bg-emerald-500" : at ? "bg-amber-500" : "bg-muted-foreground/40"}`}
      />
      {at ? (
        <>
          数据更新于 <time dateTime={at}>{timeAgo(at)}</time>
        </>
      ) : (
        "暂无成功抓取记录"
      )}
    </span>
  );
}

function MerchantCard({ m }: { m: MerchantSummary }) {
  const soldOut = Math.max(0, m.count - m.in_stock_count);
  return (
    <li className="border-border bg-card flex min-w-0 flex-col gap-3 rounded-2xl border p-5 shadow-sm">
      <header className="flex min-w-0 items-start justify-between gap-2">
        <div className="min-w-0">
          <h2 className="break-words text-base font-semibold">{m.name}</h2>
          <p className="text-muted-foreground mt-0.5 text-xs">{m.slug}</p>
        </div>
        <Freshness at={m.last_success_at} />
      </header>

      <dl className="grid grid-cols-3 gap-2 text-center">
        <div className="bg-muted/50 rounded-lg py-2">
          <dt className="text-muted-foreground text-xs">在售</dt>
          <dd className="text-lg font-bold tabular-nums text-emerald-700 dark:text-emerald-400">
            {m.in_stock_count}
          </dd>
        </div>
        <div className="bg-muted/50 rounded-lg py-2">
          <dt className="text-muted-foreground text-xs">缺货</dt>
          <dd className="text-lg font-bold tabular-nums">{soldOut}</dd>
        </div>
        <div className="bg-muted/50 rounded-lg py-2">
          <dt className="text-muted-foreground text-xs">总款数</dt>
          <dd className="text-lg font-bold tabular-nums">{m.count}</dd>
        </div>
      </dl>

      <footer className="mt-auto flex items-center gap-2">
        <Link
          href={`/vps?merchant=${encodeURIComponent(m.slug)}`}
          className="inline-flex items-center gap-1 rounded-md border px-2.5 py-1.5 text-sm transition-colors hover:bg-muted"
        >
          <PackageSearch aria-hidden className="h-3.5 w-3.5" />
          查看套餐
        </Link>
        <a
          href={m.website}
          target="_blank"
          rel="noopener noreferrer nofollow"
          className="text-muted-foreground hover:text-foreground inline-flex items-center gap-0.5 px-1 text-sm hover:underline"
        >
          官网
          <ArrowUpRight aria-hidden className="h-3 w-3" />
          <span className="sr-only">（新窗口打开）</span>
        </a>
      </footer>
    </li>
  );
}

export default async function ProvidersPage() {
  let merchants: MerchantSummary[] = [];
  let error = false;
  try {
    merchants = await listMerchants();
  } catch {
    error = true;
  }

  return (
    <div className="border-border bg-card rounded-xl border p-5 shadow-sm">
      <header className="mb-5">
        <h1 className="text-slate-900 text-xl font-bold dark:text-slate-100">服务商一览</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          套餐款数按聚合后唯一 SKU 卡片口径统计，与列表页卡片数量一致；
          抓取时间为 GoVPS 最近一次成功同步该商家数据的时刻。
        </p>
      </header>

      {error ? (
        <div
          role="alert"
          className="flex flex-col items-center gap-3 rounded-xl border border-red-100 bg-red-50 p-12 text-center dark:border-red-900 dark:bg-red-950/30"
        >
          <div className="text-3xl">📡</div>
          <p className="text-sm font-medium text-red-600 dark:text-red-400">
            服务商数据加载失败，请稍后重试。
          </p>
        </div>
      ) : merchants.length === 0 ? (
        <div className="border-border rounded-xl border border-dashed p-12 text-center text-sm text-slate-400 dark:text-slate-500">
          暂无已收录的服务商。
        </div>
      ) : (
        <ul className="grid grid-cols-1 gap-3 sm:grid-cols-2 lg:grid-cols-3">
          {merchants.map((m) => (
            <MerchantCard key={m.slug} m={m} />
          ))}
        </ul>
      )}
    </div>
  );
}
