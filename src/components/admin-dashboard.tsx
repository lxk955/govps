"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  Eye,
  LayoutDashboard,
  MousePointerClick,
  RefreshCw,
  Users,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import {
  getAdminMerchants,
  getAdminOverview,
  getAdminSettings,
  patchAdminMerchant,
  putAdminSettings,
  type AdminMerchant,
  type AdminOverview,
  type AdminSettings,
} from "@/lib/api/endpoints";
import { cn } from "@/lib/utils";

function n(v: number | null | undefined): string {
  return (v ?? 0).toLocaleString("zh-CN");
}

function relTime(iso: string | null): string {
  if (!iso) return "从未成功";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return "—";
  const mins = Math.round((Date.now() - t) / 60000);
  if (mins < 1) return "刚刚";
  if (mins < 60) return `${mins} 分钟前`;
  const hours = Math.round(mins / 60);
  if (hours < 48) return `${hours} 小时前`;
  return `${Math.round(hours / 24)} 天前`;
}

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
}: {
  label: string;
  value: string;
  hint?: string;
  icon: typeof Eye;
}) {
  return (
    <div className="border-border bg-card rounded-2xl border p-4 shadow-sm">
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">{label}</p>
        <Icon className="h-3.5 w-3.5 text-slate-300 dark:text-slate-600" aria-hidden />
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-400">{hint}</p> : null}
    </div>
  );
}

function SparkBars({
  data,
  field,
}: {
  data: AdminOverview["daily"];
  field: "pv" | "uv" | "aff";
}) {
  const max = Math.max(1, ...data.map((d) => d[field]));
  return (
    <div className="flex h-24 items-end gap-0.5">
      {data.map((d) => (
        <div
          key={d.date}
          title={`${d.date} ${field.toUpperCase()} ${d[field]}`}
          className="bg-blue-500/80 hover:bg-blue-600 min-w-0 flex-1 rounded-t-sm transition-colors dark:bg-blue-400/70"
          style={{ height: `${Math.max(4, Math.round((d[field] / max) * 100))}%` }}
        />
      ))}
    </div>
  );
}

export function AdminDashboard() {
  const { user } = useAuth();
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [merchants, setMerchants] = useState<AdminMerchant[]>([]);
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [ov, merch, conf] = await Promise.all([
        getAdminOverview(),
        getAdminMerchants(),
        getAdminSettings(),
      ]);
      setOverview(ov);
      setMerchants(merch.merchants);
      setSettings(conf);
    } catch (e) {
      if (e instanceof ApiError && e.status === 403) setError("forbidden");
      else if (e instanceof ApiError && e.status === 401) setError("auth");
      else setError("load");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    if (user) void load();
  }, [user, load]);

  const saveSettings = async (e: React.FormEvent) => {
    e.preventDefault();
    if (!settings) return;
    setSaving(true);
    setSavedMsg(null);
    try {
      const next = await putAdminSettings(settings);
      setSettings(next);
      setSavedMsg("已保存");
    } catch {
      setSavedMsg("保存失败");
    } finally {
      setSaving(false);
    }
  };

  const toggleMerchant = async (slug: string, enabled: boolean) => {
    try {
      const res = await patchAdminMerchant(slug, { enabled });
      setMerchants((prev) => prev.map((m) => (m.slug === slug ? { ...m, enabled: res.enabled } : m)));
    } catch {
      /* ignore */
    }
  };

  const saveInterval = async (slug: string, minutes: number) => {
    try {
      const res = await patchAdminMerchant(slug, { crawl_interval_minutes: minutes });
      setMerchants((prev) =>
        prev.map((m) => (m.slug === slug ? { ...m, crawl_interval_minutes: res.crawl_interval_minutes } : m)),
      );
    } catch {
      /* ignore */
    }
  };

  if (user === undefined || (user && loading && !overview && !error)) {
    return <div className="bg-muted h-64 animate-pulse rounded-2xl" aria-hidden />;
  }

  if (user === null) {
    return (
      <div className="border-border rounded-2xl border border-dashed p-12 text-center">
        <LayoutDashboard className="text-muted-foreground mx-auto h-8 w-8" aria-hidden />
        <p className="text-muted-foreground mt-3 text-sm">登录后才能进入管理后台。</p>
        <Button asChild size="sm" className="mt-3">
          <Link href="/login?next=%2Fadmin">登录</Link>
        </Button>
      </div>
    );
  }

  if (error === "forbidden" || (user && !user.is_admin && error !== "load")) {
    return (
      <div className="border-border rounded-2xl border p-12 text-center">
        <p className="text-sm font-medium text-slate-700 dark:text-slate-200">当前账号没有管理权限。</p>
        <p className="text-muted-foreground mt-1 text-xs">如需开通，把邮箱加入服务器 ADMIN_EMAILS。</p>
      </div>
    );
  }

  if (error === "load" || !overview || !settings) {
    return (
      <div className="rounded-2xl border border-red-100 bg-red-50 p-12 text-center dark:border-red-900 dark:bg-red-950/30">
        <p className="text-sm font-medium text-red-600 dark:text-red-400">数据加载失败</p>
        <Button size="sm" className="mt-3" onClick={() => void load()}>
          重试
        </Button>
      </div>
    );
  }

  const v = overview.visits;
  const u = overview.users;
  const a = overview.activity;

  return (
    <div className="space-y-8">
      <div className="flex items-start justify-between gap-3">
        <div>
          <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-50">管理后台</h1>
          <p className="text-muted-foreground mt-1 text-sm">访问量、用户与返利点击，以及站点基本配置。</p>
        </div>
        <Button variant="outline" size="sm" className="h-8 gap-1.5 text-xs" onClick={() => void load()}>
          <RefreshCw className="h-3.5 w-3.5" aria-hidden />
          刷新
        </Button>
      </div>

      <section className="grid grid-cols-2 gap-3 lg:grid-cols-4">
        <StatCard label="今日浏览" value={n(v.today_pv)} hint={`UV ${n(v.today_uv)} · 近 7 日 ${n(v.d7_pv)}`} icon={Eye} />
        <StatCard label="日活 / 月活" value={`${n(a.dau)} / ${n(a.mau)}`} hint="按独立会话计" icon={Eye} />
        <StatCard label="注册用户" value={n(u.total)} hint={`今日 +${n(u.today_new)} · 近 7 日 +${n(u.d7_new)}`} icon={Users} />
        <StatCard
          label="AFF 点击"
          value={n(overview.aff.today)}
          hint={`近 7 日 ${n(overview.aff.d7)} · 近 30 日 ${n(overview.aff.d30)}`}
          icon={MousePointerClick}
        />
      </section>

      <section className="border-border bg-card rounded-2xl border p-4 shadow-sm sm:p-5">
        <div className="mb-3 flex items-baseline justify-between">
          <h2 className="text-sm font-semibold text-slate-800 dark:text-slate-100">近 30 日浏览</h2>
          <p className="text-[11px] text-slate-400">柱高为当日 PV</p>
        </div>
        <SparkBars data={overview.daily} field="pv" />
      </section>

      <div className="grid gap-6 lg:grid-cols-2">
        <section className="border-border bg-card overflow-hidden rounded-2xl border shadow-sm">
          <h2 className="border-border border-b px-4 py-3 text-sm font-semibold">近 7 日页面</h2>
          <table className="w-full text-sm">
            <thead className="text-[11px] tracking-wide text-slate-400 uppercase">
              <tr className="border-border border-b">
                <th className="px-4 py-2 text-left font-medium">路由</th>
                <th className="px-4 py-2 text-right font-medium">PV</th>
                <th className="px-4 py-2 text-right font-medium">UV</th>
              </tr>
            </thead>
            <tbody>
              {overview.pages.length === 0 ? (
                <tr>
                  <td colSpan={3} className="text-muted-foreground px-4 py-8 text-center text-xs">
                    暂无访问记录
                  </td>
                </tr>
              ) : (
                overview.pages.map((p) => (
                  <tr key={p.route} className="border-border border-b last:border-0">
                    <td className="px-4 py-2 font-mono text-xs">{p.route}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{n(p.pv)}</td>
                    <td className="px-4 py-2 text-right tabular-nums text-slate-500">{n(p.uv)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>

        <section className="border-border bg-card overflow-hidden rounded-2xl border shadow-sm">
          <h2 className="border-border border-b px-4 py-3 text-sm font-semibold">近 30 日 AFF</h2>
          <table className="w-full text-sm">
            <thead className="text-[11px] tracking-wide text-slate-400 uppercase">
              <tr className="border-border border-b">
                <th className="px-4 py-2 text-left font-medium">商家</th>
                <th className="px-4 py-2 text-right font-medium">点击</th>
              </tr>
            </thead>
            <tbody>
              {overview.aff.by_merchant.length === 0 ? (
                <tr>
                  <td colSpan={2} className="text-muted-foreground px-4 py-8 text-center text-xs">
                    暂无点击
                  </td>
                </tr>
              ) : (
                overview.aff.by_merchant.map((m) => (
                  <tr key={m.slug} className="border-border border-b last:border-0">
                    <td className="px-4 py-2">{m.name}</td>
                    <td className="px-4 py-2 text-right tabular-nums">{n(m.clicks)}</td>
                  </tr>
                ))
              )}
            </tbody>
          </table>
        </section>
      </div>

      <section className="border-border bg-card overflow-hidden rounded-2xl border shadow-sm">
        <h2 className="border-border border-b px-4 py-3 text-sm font-semibold">商家</h2>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[640px] text-sm">
            <thead className="text-[11px] tracking-wide text-slate-400 uppercase">
              <tr className="border-border border-b">
                <th className="px-4 py-2 text-left font-medium">名称</th>
                <th className="px-4 py-2 text-left font-medium">扫描</th>
                <th className="px-4 py-2 text-right font-medium">间隔（分）</th>
                <th className="px-4 py-2 text-right font-medium">套餐 / 有货</th>
                <th className="px-4 py-2 text-left font-medium">上次成功</th>
              </tr>
            </thead>
            <tbody>
              {merchants.map((m) => (
                <tr key={m.slug} className="border-border border-b last:border-0">
                  <td className="px-4 py-2.5">
                    <div className="font-medium">{m.name}</div>
                    <div className="text-[11px] text-slate-400">{m.slug}</div>
                    {m.last_error ? (
                      <div className="mt-0.5 max-w-xs truncate text-[11px] text-red-500" title={m.last_error}>
                        {m.last_error}
                      </div>
                    ) : null}
                  </td>
                  <td className="px-4 py-2.5">
                    <button
                      type="button"
                      onClick={() => void toggleMerchant(m.slug, !m.enabled)}
                      className={cn(
                        "rounded-full px-2.5 py-1 text-[11px] font-semibold",
                        m.enabled
                          ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300"
                          : "bg-slate-100 text-slate-500 dark:bg-slate-800",
                      )}
                    >
                      {m.enabled ? "开启" : "停用"}
                    </button>
                  </td>
                  <td className="px-4 py-2.5 text-right">
                    <Input
                      type="number"
                      min={1}
                      max={1440}
                      defaultValue={m.crawl_interval_minutes ?? 5}
                      className="ml-auto h-8 w-20 text-right"
                      onBlur={(e) => {
                        const v = Number(e.target.value);
                        if (Number.isFinite(v) && v !== m.crawl_interval_minutes) {
                          void saveInterval(m.slug, v);
                        }
                      }}
                    />
                  </td>
                  <td className="px-4 py-2.5 text-right tabular-nums">
                    {n(m.products)} / {n(m.in_stock)}
                  </td>
                  <td className="px-4 py-2.5 text-xs text-slate-500">{relTime(m.last_success_at)}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </section>

      <section className="border-border bg-card rounded-2xl border p-4 shadow-sm sm:p-5">
        <h2 className="text-sm font-semibold">站点配置</h2>
        <p className="text-muted-foreground mt-1 mb-4 text-xs">
          改这里立刻生效，不必重启。未填过的项沿用服务器环境变量默认值。
        </p>
        <form onSubmit={saveSettings} className="grid gap-4 sm:grid-cols-2">
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium text-slate-500">事件去重窗口（分钟）</span>
            <Input
              type="number"
              min={1}
              max={10080}
              value={settings.event_dedup_minutes}
              onChange={(e) =>
                setSettings({ ...settings, event_dedup_minutes: Number(e.target.value) || 0 })
              }
            />
          </label>
          <label className="block text-sm">
            <span className="mb-1 block text-xs font-medium text-slate-500">每用户每日邮件上限</span>
            <Input
              type="number"
              min={0}
              max={1000}
              value={settings.daily_mail_cap}
              onChange={(e) => setSettings({ ...settings, daily_mail_cap: Number(e.target.value) || 0 })}
            />
          </label>
          <label className="flex items-center gap-2 text-sm sm:col-span-2">
            <input
              type="checkbox"
              checked={settings.indexnow_enabled}
              onChange={(e) => setSettings({ ...settings, indexnow_enabled: e.target.checked })}
              className="h-4 w-4 rounded border-slate-300"
            />
            向搜索引擎提交 IndexNow
          </label>
          <div className="flex items-center gap-3 sm:col-span-2">
            <Button type="submit" size="sm" disabled={saving}>
              {saving ? "保存中…" : "保存配置"}
            </Button>
            {savedMsg ? <span className="text-xs text-slate-500">{savedMsg}</span> : null}
          </div>
        </form>
      </section>
    </div>
  );
}
