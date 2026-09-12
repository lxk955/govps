"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import { ArrowLeft, ChevronRight, Search, Shield, Users } from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import { getAdminUsers, type AdminUserListItem } from "@/lib/api/endpoints";

const CURRENCY_LABEL: Record<string, string> = {
  original: "原币",
  CNY: "人民币",
  USD: "美元",
};

function n(v: number | null | undefined): string {
  return (v ?? 0).toLocaleString("zh-CN");
}

function relTime(iso: string | null): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const mins = Math.round((Date.now() - t) / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} 小时前`;
  return `${Math.round(hours / 24)} 天前`;
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

export function AdminUsersPage() {
  const { user } = useAuth();
  const [q, setQ] = useState("");
  const [applied, setApplied] = useState("");
  const [rows, setRows] = useState<AdminUserListItem[]>([]);
  const [total, setTotal] = useState(0);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);

  const load = useCallback(async (query: string) => {
    setLoading(true);
    setError(null);
    try {
      const data = await getAdminUsers({ q: query || undefined, limit: 100 });
      setRows(data.users);
      setTotal(data.total);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setError("forbidden");
      else if (e instanceof ApiError && e.status === 401) setError("auth");
      else setError("load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) void load(applied);
  }, [user, applied, load]);

  if (user === undefined || (user && loading && rows.length === 0 && !error)) {
    return <div className="bg-muted h-64 animate-pulse rounded-2xl" aria-hidden />;
  }

  if (user === null) {
    return (
      <div className="border-border rounded-2xl border border-dashed p-12 text-center">
        <Users className="text-muted-foreground mx-auto h-8 w-8" aria-hidden />
        <p className="text-muted-foreground mt-3 text-sm">登录后才能查看用户。</p>
        <Button asChild size="sm" className="mt-3">
          <Link href="/login?next=%2Fadmin%2Fusers">登录</Link>
        </Button>
      </div>
    );
  }

  if (error === "forbidden" || (user && !user.is_admin && error !== "load")) {
    return (
      <div className="border-border rounded-2xl border p-12 text-center">
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">当前账号没有管理权限。</p>
      </div>
    );
  }

  if (error === "load") {
    return (
      <div className="rounded-2xl border border-red-100 bg-red-50 p-12 text-center dark:border-red-900 dark:bg-red-950/30">
        <p className="text-sm font-medium text-red-600 dark:text-red-400">加载失败</p>
        <Button size="sm" className="mt-3" onClick={() => void load(applied)}>
          重试
        </Button>
      </div>
    );
  }

  return (
    <div className="space-y-5">
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <Link
            href="/admin"
            className="text-muted-foreground mb-2 inline-flex items-center gap-1 text-xs hover:text-blue-600"
          >
            <ArrowLeft className="h-3.5 w-3.5" aria-hidden />
            管理后台
          </Link>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-50">用户</h1>
          <p className="text-muted-foreground mt-1 text-sm">共 {n(total)} 人，点某一行查看关注与访问记录。</p>
        </div>
        <form
          className="flex w-full max-w-xs items-center gap-2 sm:w-auto"
          onSubmit={(e) => {
            e.preventDefault();
            setApplied(q.trim());
          }}
        >
          <div className="relative flex-1">
            <Search className="text-muted-foreground pointer-events-none absolute top-1/2 left-2.5 h-3.5 w-3.5 -translate-y-1/2" aria-hidden />
            <Input
              value={q}
              onChange={(e) => setQ(e.target.value)}
              placeholder="搜索邮箱"
              className="h-8 pl-8 text-sm"
            />
          </div>
          <Button type="submit" size="sm" variant="outline" className="h-8 text-xs">
            搜索
          </Button>
        </form>
      </div>

      <section className="border-border bg-card overflow-hidden rounded-2xl border shadow-sm">
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="bg-slate-50/50 text-[11px] tracking-wide text-slate-400 uppercase dark:bg-slate-900/20">
              <tr className="border-border border-b">
                <th className="px-4 py-2.5 text-left font-medium">邮箱</th>
                <th className="px-4 py-2.5 text-left font-medium">注册</th>
                <th className="px-4 py-2.5 text-left font-medium">币种</th>
                <th className="px-4 py-2.5 text-right font-medium">关注</th>
                <th className="px-4 py-2.5 text-left font-medium">最近访问</th>
                <th className="w-8 px-3 py-2.5" />
              </tr>
            </thead>
            <tbody>
              {rows.length === 0 ? (
                <tr>
                  <td colSpan={6} className="text-muted-foreground px-4 py-12 text-center text-xs">
                    {applied ? "没有匹配的用户" : "还没有注册用户"}
                  </td>
                </tr>
              ) : (
                rows.map((u) => (
                  <tr key={u.id} className="border-border hover:bg-slate-50/70 border-b last:border-0 dark:hover:bg-slate-900/40">
                    <td className="px-4 py-3">
                      <Link href={`/admin/users/${u.id}`} className="block">
                        <span className="font-medium text-slate-900 dark:text-slate-100">{u.email}</span>
                        {u.is_admin ? (
                          <span className="ml-2 inline-flex items-center gap-0.5 rounded-full bg-blue-50 px-1.5 py-0.5 text-[10px] font-semibold text-blue-700 dark:bg-blue-950/50 dark:text-blue-300">
                            <Shield className="h-2.5 w-2.5" aria-hidden />
                            管理员
                          </span>
                        ) : null}
                      </Link>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-500">
                      <div>{relTime(u.created_at)}</div>
                      <div className="text-[10px] text-slate-400">{formatDate(u.created_at)}</div>
                    </td>
                    <td className="px-4 py-3 text-xs text-slate-600 dark:text-slate-300">
                      {CURRENCY_LABEL[u.currency_mode] || u.currency_mode}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{n(u.watch_count)}</td>
                    <td className="px-4 py-3 text-xs text-slate-500">{relTime(u.last_seen_at)}</td>
                    <td className="px-3 py-3">
                      <Link href={`/admin/users/${u.id}`} className="text-slate-400 hover:text-blue-600" aria-label={`查看 ${u.email}`}>
                        <ChevronRight className="h-4 w-4" />
                      </Link>
                    </td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </div>
      </section>
    </div>
  );
}
