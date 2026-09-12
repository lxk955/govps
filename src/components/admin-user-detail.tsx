"use client";

import { useEffect, useState } from "react";
import Link from "next/link";
import { useParams } from "next/navigation";
import { ArrowLeft, Shield, Star } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { ApiError } from "@/lib/api/client";
import { getAdminUser, type AdminUserDetail } from "@/lib/api/endpoints";
import { productHref } from "@/lib/slug";

const CURRENCY_LABEL: Record<string, string> = {
  original: "原币",
  CNY: "人民币",
  USD: "美元",
};

const VIEW_LABEL: Record<string, string> = { card: "卡片", list: "列表" };

const EVENT_LABEL: Record<string, string> = {
  RESTOCK: "补货",
  PRICE_DROP: "降价",
};

function n(v: number | null | undefined): string {
  return (v ?? 0).toLocaleString("zh-CN");
}

function formatDate(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("zh-CN", {
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hour12: false,
  });
}

export function AdminUserDetailPage() {
  const { user } = useAuth();
  const params = useParams<{ id: string }>();
  const id = Number(params?.id);
  const [data, setData] = useState<AdminUserDetail | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [errorMessage, setErrorMessage] = useState<string | null>(null);

  useEffect(() => {
    if (!user?.is_admin || !Number.isFinite(id) || id <= 0) return;
    let cancelled = false;
    (async () => {
      setError(null);
      setErrorMessage(null);
      try {
        const d = await getAdminUser(id);
        if (!cancelled) setData(d);
      } catch (e) {
        if (cancelled) return;
        if (e instanceof ApiError && e.status === 404) {
          setError("missing");
        } else if (e instanceof ApiError && e.status === 403) {
          setError("forbidden");
        } else if (e instanceof ApiError && e.status === 401) {
          setError("auth");
        } else {
          setError("load");
          setErrorMessage(e instanceof ApiError ? e.detail : e instanceof Error ? e.message : "加载失败");
        }
      }
    })();
    return () => {
      cancelled = true;
    };
  }, [user, id]);

  if (user === undefined || (user?.is_admin && !data && !error)) {
    return <div className="bg-muted h-64 animate-pulse rounded-2xl" aria-hidden />;
  }

  if (user === null) {
    return (
      <div className="border-border rounded-2xl border border-dashed p-12 text-center">
        <p className="text-muted-foreground text-sm">登录后才能查看用户。</p>
        <Button asChild size="sm" className="mt-3">
          <Link href={`/login?next=${encodeURIComponent(`/admin/users/${id}`)}`}>登录</Link>
        </Button>
      </div>
    );
  }

  if (error === "auth") {
    return (
      <div className="border-border rounded-2xl border border-dashed p-12 text-center">
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">登录状态已失效</p>
        <p className="text-muted-foreground mt-1 text-xs">登录凭证已过期或未授权，请重新登录。</p>
        <Button asChild size="sm" className="mt-4">
          <Link href={`/login?next=${encodeURIComponent(`/admin/users/${id}`)}`}>重新登录</Link>
        </Button>
      </div>
    );
  }

  if (error === "forbidden" || !user.is_admin) {
    return (
      <div className="border-border rounded-2xl border p-12 text-center">
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">当前账号没有管理权限</p>
        <p className="text-muted-foreground mt-1 text-xs">当前登录账号为 {user.email}，无权访问用户详情。</p>
        <div className="mt-4 flex items-center justify-center gap-3">
          <Button asChild variant="outline" size="sm">
            <Link href="/">返回首页</Link>
          </Button>
          <Button asChild size="sm">
            <Link href={`/login?next=${encodeURIComponent(`/admin/users/${id}`)}`}>切换账号</Link>
          </Button>
        </div>
      </div>
    );
  }

  if (error === "missing") {
    return (
      <div className="border-border rounded-2xl border p-12 text-center">
        <p className="text-sm">用户不存在。</p>
        <Button asChild size="sm" variant="outline" className="mt-3">
          <Link href="/admin/users">返回列表</Link>
        </Button>
      </div>
    );
  }

  if (error === "load" || !data) {
    return (
      <div className="rounded-2xl border border-red-100 bg-red-50 p-12 text-center dark:border-red-900 dark:bg-red-950/30">
        <p className="text-sm font-medium text-red-600 dark:text-red-400">加载失败</p>
        {errorMessage && (
          <p className="text-muted-foreground mt-1 text-xs font-mono">{errorMessage}</p>
        )}
      </div>
    );
  }

  const u = data.user;

  return (
    <div className="space-y-6">
      <div>
        <Link
          href="/admin/users"
          className="text-muted-foreground mb-2 inline-flex items-center gap-1 text-xs hover:text-blue-600"
        >
          <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
          用户列表
        </Link>
        <h1 className="flex flex-wrap items-center gap-2 text-xl font-bold tracking-tight text-slate-900 dark:text-slate-50">
          {u.email}
          {u.is_admin ? (
            <span className="inline-flex items-center gap-1 rounded-full bg-blue-50 px-2 py-0.5 text-[11px] font-semibold text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
              <Shield className="h-3 w-3" aria-hidden />
              管理员
            </span>
          ) : null}
        </h1>
        <p className="text-muted-foreground mt-1 text-sm">#{u.id} · 注册于 {formatDate(u.created_at)}</p>
      </div>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <InfoCard label="币种偏好" value={CURRENCY_LABEL[u.currency_mode] || u.currency_mode} />
        <InfoCard label="列表视图" value={VIEW_LABEL[u.view_mode] || u.view_mode} />
        <InfoCard label="关注套餐" value={n(u.watch_count)} />
        <InfoCard label="最近访问" value={formatDate(u.last_seen_at)} hint={`登录 PV ${n(u.pageviews)}`} />
      </section>

      <section className="border-border bg-card overflow-hidden rounded-2xl border shadow-sm">
        <h2 className="border-border flex items-center gap-1.5 border-b px-4 py-3 text-sm font-semibold">
          <Star className="h-3.5 w-3.5 text-amber-500" aria-hidden />
          关注列表
        </h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-[11px] tracking-wide text-slate-400 uppercase">
              <tr className="border-border border-b">
                <th className="px-4 py-2 text-left font-medium">套餐</th>
                <th className="px-4 py-2 text-left font-medium">商家</th>
                <th className="px-4 py-2 text-left font-medium">库存</th>
                <th className="px-4 py-2 text-left font-medium">通知</th>
                <th className="px-4 py-2 text-left font-medium">关注时间</th>
              </tr>
            </thead>
            <tbody>
              {data.watchlist.length === 0 ? (
                <tr>
                  <td colSpan={5} className="text-muted-foreground px-4 py-10 text-center text-xs">
                    还没有关注任何套餐
                  </td>
                </tr>
              ) : (
                data.watchlist.map((w) => (
                  <tr key={w.product_id} className="border-border border-b last:border-0">
                    <td className="px-4 py-2.5">
                      <Link href={productHref(w.product_id, w.name)} className="font-medium hover:text-blue-600">
                        {w.name}
                      </Link>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-500">{w.merchant}</td>
                    <td className="px-4 py-2.5">
                      <span className={w.in_stock ? "text-emerald-600" : "text-slate-400"}>
                        {w.in_stock ? "有货" : "缺货"}
                      </span>
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-500">
                      {[w.notify_restock ? "补货" : null, w.notify_price_drop ? `降价≥${w.min_drop_percent}%` : null]
                        .filter(Boolean)
                        .join(" · ") || "关闭"}
                    </td>
                    <td className="px-4 py-2.5 text-xs text-slate-400">{formatDate(w.created_at)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="border-border bg-card overflow-hidden rounded-2xl border shadow-sm">
          <h2 className="border-border border-b px-4 py-3 text-sm font-semibold">最近访问</h2>
          <table className="w-full text-sm">
            <tbody>
              {data.recent_views.length === 0 ? (
                <tr>
                  <td className="text-muted-foreground px-4 py-10 text-center text-xs">暂无登录态访问记录</td>
                </tr>
              ) : (
                data.recent_views.map((v, i) => (
                  <tr key={`${v.path}-${v.created_at}-${i}`} className="border-border border-b last:border-0">
                    <td className="px-4 py-2 font-mono text-xs">{v.path}</td>
                    <td className="px-4 py-2 text-right text-xs whitespace-nowrap text-slate-400">
                      {formatDate(v.created_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>

        <section className="border-border bg-card overflow-hidden rounded-2xl border shadow-sm">
          <h2 className="border-border border-b px-4 py-3 text-sm font-semibold">通知记录</h2>
          <table className="w-full text-sm">
            <tbody>
              {data.recent_notifies.length === 0 ? (
                <tr>
                  <td className="text-muted-foreground px-4 py-10 text-center text-xs">还没有发过通知</td>
                </tr>
              ) : (
                data.recent_notifies.map((nlog, i) => (
                  <tr key={`${nlog.sent_at}-${i}`} className="border-border border-b last:border-0">
                    <td className="px-4 py-2">
                      <div className="text-xs font-medium">
                        {EVENT_LABEL[nlog.event_type || ""] || nlog.event_type || "通知"}
                        {nlog.product_name ? ` · ${nlog.product_name}` : ""}
                      </div>
                      <div className="text-[11px] text-slate-400">
                        {nlog.status}
                        {nlog.error ? ` · ${nlog.error}` : ""}
                      </div>
                    </td>
                    <td className="px-4 py-2 text-right text-xs whitespace-nowrap text-slate-400">
                      {formatDate(nlog.sent_at)}
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      </div>
    </div>
  );
}

function InfoCard({ label, value, hint }: { label: string; value: string; hint?: string }) {
  return (
    <div className="border-border bg-card rounded-2xl border p-4 shadow-sm">
      <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">{label}</p>
      <p className="mt-2 text-lg font-semibold tracking-tight text-slate-900 dark:text-slate-50">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-400">{hint}</p> : null}
    </div>
  );
}
