"use client";

import { useCallback, useEffect, useState } from "react";
import Link from "next/link";
import {
  AlertTriangle,
  Bot,
  CheckCircle2,
  ExternalLink,
  Eye,
  LayoutDashboard,
  Loader2,
  MousePointerClick,
  RefreshCw,
  ShieldAlert,
  Users,
  XCircle,
  Zap,
} from "lucide-react";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { ApiError } from "@/lib/api/client";
import {
  getAdminCrawlLogs,
  getAdminMerchants,
  getAdminOverview,
  getAdminSettings,
  patchAdminMerchant,
  putAdminSettings,
  triggerAdminScan,
  type AdminCrawlLog,
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

function formatDateTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return "—";
  return d.toLocaleString("zh-CN", {
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    second: "2-digit",
    hour12: false,
  });
}

function formatDuration(ms: number): string {
  if (ms < 1000) return `${ms}ms`;
  return `${(ms / 1000).toFixed(2)}s`;
}

function StatusBadge({ status }: { status: string }) {
  if (status === "success") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-300">
        <CheckCircle2 className="h-3 w-3" />
        官方一手
      </span>
    );
  }
  if (status === "partial") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-300">
        <AlertTriangle className="h-3 w-3" />
        部分一手
      </span>
    );
  }
  if (status === "degraded") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-orange-200 bg-orange-50 px-2 py-0.5 text-[11px] font-medium text-orange-700 dark:border-orange-800/60 dark:bg-orange-950/40 dark:text-orange-300">
        <ShieldAlert className="h-3 w-3" />
        降级兜底
      </span>
    );
  }
  if (status === "failed") {
    return (
      <span className="inline-flex items-center gap-1 rounded-full border border-rose-200 bg-rose-50 px-2 py-0.5 text-[11px] font-medium text-rose-700 dark:border-rose-800/60 dark:bg-rose-950/40 dark:text-rose-300">
        <XCircle className="h-3 w-3" />
        抓取失败
      </span>
    );
  }
  return (
    <span className="inline-flex items-center gap-1 rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
      {status}
    </span>
  );
}

function StatCard({
  label,
  value,
  hint,
  icon: Icon,
  href,
}: {
  label: string;
  value: string;
  hint?: string;
  icon: typeof Eye;
  href?: string;
}) {
  const body = (
    <>
      <div className="flex items-center justify-between gap-2">
        <p className="text-[11px] font-medium tracking-wide text-slate-400 uppercase">{label}</p>
        <Icon className="h-3.5 w-3.5 text-slate-300 dark:text-slate-600" aria-hidden />
      </div>
      <p className="mt-2 text-2xl font-semibold tracking-tight text-slate-900 dark:text-slate-50">{value}</p>
      {hint ? <p className="mt-1 text-xs text-slate-400">{hint}</p> : null}
      {href ? (
        <p className="mt-2 text-[11px] font-medium text-blue-600 dark:text-blue-400">查看用户列表 →</p>
      ) : null}
    </>
  );
  const cls = "border-border bg-card rounded-2xl border p-4 shadow-sm";
  if (href) {
    return (
      <Link href={href} className={`${cls} block transition-colors hover:border-blue-300 hover:bg-blue-50/40 dark:hover:border-blue-800 dark:hover:bg-blue-950/30`}>
        {body}
      </Link>
    );
  }
  return <div className={cls}>{body}</div>;
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

function AffStatusBadge({ status }: { status: string }) {
  if (status === "active") {
    return (
      <span className="inline-flex items-center rounded-full border border-emerald-200 bg-emerald-50 px-2 py-0.5 text-[11px] font-medium text-emerald-700 dark:border-emerald-800/60 dark:bg-emerald-950/40 dark:text-emerald-300">
        已配置
      </span>
    );
  }
  if (status === "unsupported") {
    return (
      <span className="inline-flex items-center rounded-full border border-amber-200 bg-amber-50 px-2 py-0.5 text-[11px] font-medium text-amber-700 dark:border-amber-800/60 dark:bg-amber-950/40 dark:text-amber-300">
        暂不支持
      </span>
    );
  }
  return (
    <span className="inline-flex items-center rounded-full border border-slate-200 bg-slate-50 px-2 py-0.5 text-[11px] font-medium text-slate-600 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-400">
      直链无佣金
    </span>
  );
}

export function AdminDashboard() {
  const { user } = useAuth();
  const [overview, setOverview] = useState<AdminOverview | null>(null);
  const [merchants, setMerchants] = useState<AdminMerchant[]>([]);
  const [settings, setSettings] = useState<AdminSettings | null>(null);
  const [crawlLogs, setCrawlLogs] = useState<AdminCrawlLog[]>([]);
  const [latestLogs, setLatestLogs] = useState<AdminCrawlLog[]>([]);
  const [error, setError] = useState<string | null>(null);
  const [loading, setLoading] = useState(true);
  const [refreshingLogs, setRefreshingLogs] = useState(false);
  const [triggeringScan, setTriggeringScan] = useState(false);
  const [triggerMsg, setTriggerMsg] = useState<string | null>(null);
  const [saving, setSaving] = useState(false);
  const [savedMsg, setSavedMsg] = useState<string | null>(null);
  const [logViewMode, setLogViewMode] = useState<"latest" | "stream">("latest");
  const [streamMerchantFilter, setStreamMerchantFilter] = useState<string>("all");
  const [streamStatusFilter, setStreamStatusFilter] = useState<string>("all");
  const [affDrafts, setAffDrafts] = useState<Record<string, string>>({});
  const [affSaving, setAffSaving] = useState<string | null>(null);
  const [affMsg, setAffMsg] = useState<string | null>(null);

  const load = useCallback(async () => {
    setError(null);
    setLoading(true);
    try {
      const [ov, merch, conf, crawlData] = await Promise.all([
        getAdminOverview(),
        getAdminMerchants(),
        getAdminSettings(),
        getAdminCrawlLogs(100).catch(() => ({ logs: [], latest_by_merchant: [], total: 0 })),
      ]);
      setOverview(ov);
      setMerchants(merch.merchants);
      setAffDrafts(
        Object.fromEntries(merch.merchants.map((m) => [m.slug, m.aff_url_template || ""])),
      );
      setSettings(conf);
      setCrawlLogs(crawlData.logs);
      setLatestLogs(crawlData.latest_by_merchant);
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

  const reloadLogs = async () => {
    setRefreshingLogs(true);
    try {
      const [merch, crawlData] = await Promise.all([
        getAdminMerchants(),
        getAdminCrawlLogs(100),
      ]);
      setMerchants(merch.merchants);
      setAffDrafts(
        Object.fromEntries(merch.merchants.map((m) => [m.slug, m.aff_url_template || ""])),
      );
      setCrawlLogs(crawlData.logs);
      setLatestLogs(crawlData.latest_by_merchant);
    } catch {
      /* ignore */
    } finally {
      setRefreshingLogs(false);
    }
  };

  const handleTriggerScan = async (force = true) => {
    setTriggeringScan(true);
    setTriggerMsg(null);
    try {
      const res = await triggerAdminScan(force);
      setTriggerMsg(
        res.ok
          ? `爬虫扫描已触发（扫描结果将保存到执行流水中，刷新即可查阅）`
          : "触发返回异常",
      );
      await reloadLogs();
    } catch (err: unknown) {
      const msg = err instanceof Error ? err.message : "抓取触发失败";
      setTriggerMsg(msg);
    } finally {
      setTriggeringScan(false);
    }
  };

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

  const saveAff = async (slug: string, restore = false) => {
    setAffSaving(slug);
    setAffMsg(null);
    try {
      const res = await patchAdminMerchant(
        slug,
        restore ? { restore_aff_default: true } : { aff_url_template: affDrafts[slug] ?? "" },
      );
      setMerchants((prev) =>
        prev.map((m) =>
          m.slug === slug
            ? { ...m, aff_url_template: res.aff_url_template, aff_status: res.aff_status }
            : m,
        ),
      );
      setAffDrafts((prev) => ({ ...prev, [slug]: res.aff_url_template || "" }));
      setAffMsg(restore ? "已恢复代码默认" : "已保存");
    } catch {
      setAffMsg("保存失败，请检查链接是否为 http(s) 或含 {pid}/{url}");
    } finally {
      setAffSaving(null);
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
        <p className="text-muted-foreground mt-1 text-xs">这个账号没有管理权限。</p>
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

  // 流水过滤
  const filteredStreamLogs = crawlLogs.filter((log) => {
    if (streamMerchantFilter !== "all" && log.merchant_slug !== streamMerchantFilter) {
      return false;
    }
    if (streamStatusFilter !== "all" && log.status !== streamStatusFilter) {
      return false;
    }
    return true;
  });

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
        <StatCard
          label="注册用户"
          value={n(u.total)}
          hint={`今日 +${n(u.today_new)} · 近 7 日 +${n(u.d7_new)}`}
          icon={Users}
          href="/admin/users"
        />
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

      {/* ── 爬虫执行监控与近期记录 ── */}
      <section className="border-border bg-card overflow-hidden rounded-2xl border shadow-sm">
        <div className="border-border border-b p-4 sm:flex sm:items-center sm:justify-between sm:p-5">
          <div>
            <div className="flex items-center gap-2">
              <Bot className="h-5 w-5 text-blue-500" aria-hidden />
              <h2 className="text-base font-semibold text-slate-900 dark:text-slate-50">
                爬虫执行监控与近期记录
              </h2>
            </div>
            <p className="text-muted-foreground mt-1 text-xs">
              实时监控各商家官方数据抓取状态、解析方式、一手覆盖率与执行流水。
            </p>
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-2 sm:mt-0">
            <Button
              variant="outline"
              size="sm"
              className="h-8 gap-1.5 text-xs"
              disabled={refreshingLogs || triggeringScan}
              onClick={() => void reloadLogs()}
            >
              <RefreshCw className={cn("h-3.5 w-3.5", refreshingLogs && "animate-spin")} aria-hidden />
              刷新记录
            </Button>
            <Button
              variant="default"
              size="sm"
              className="h-8 gap-1.5 text-xs bg-blue-600 hover:bg-blue-700 text-white"
              disabled={triggeringScan}
              onClick={() => void handleTriggerScan(true)}
            >
              {triggeringScan ? (
                <Loader2 className="h-3.5 w-3.5 animate-spin" aria-hidden />
              ) : (
                <Zap className="h-3.5 w-3.5" aria-hidden />
              )}
              {triggeringScan ? "抓取执行中…" : "立即全量抓取"}
            </Button>
          </div>
        </div>

        {triggerMsg && (
          <div className="border-border border-b bg-blue-50/70 px-4 py-2 text-xs text-blue-700 dark:bg-blue-950/30 dark:text-blue-300">
            {triggerMsg}
          </div>
        )}

        {/* 概览指标行 */}
        <div className="grid grid-cols-2 gap-3 border-border border-b p-4 sm:grid-cols-4 sm:p-5 bg-slate-50/50 dark:bg-slate-900/20">
          <div className="rounded-xl border border-border bg-card p-3">
            <div className="text-[11px] font-medium text-slate-400">官方一手达标率</div>
            <div className="mt-1 text-lg font-bold text-slate-800 dark:text-slate-100">
              {latestLogs.length > 0
                ? `${Math.round(
                    (latestLogs.filter((l) => l.status === "success").length /
                      latestLogs.length) *
                      100,
                  )}%`
                : "—"}
            </div>
            <div className="mt-0.5 text-[11px] text-slate-500">
              {latestLogs.filter((l) => l.status === "success").length} / {latestLogs.length} 商家一手无降级
            </div>
          </div>
          <div className="rounded-xl border border-border bg-card p-3">
            <div className="text-[11px] font-medium text-slate-400">监控商家数</div>
            <div className="mt-1 text-lg font-bold text-slate-800 dark:text-slate-100">
              {merchants.length} 家
            </div>
            <div className="mt-0.5 text-[11px] text-slate-500">
              {merchants.filter((m) => m.enabled).length} 家启用抓取
            </div>
          </div>
          <div className="rounded-xl border border-border bg-card p-3">
            <div className="text-[11px] font-medium text-slate-400">平均抓取耗时</div>
            <div className="mt-1 text-lg font-bold text-slate-800 dark:text-slate-100">
              {latestLogs.length > 0
                ? formatDuration(
                    Math.round(
                      latestLogs.reduce((acc, l) => acc + (l.duration_ms || 0), 0) /
                        latestLogs.length,
                    ),
                  )
                : "—"}
            </div>
            <div className="mt-0.5 text-[11px] text-slate-500">多协程并发采集</div>
          </div>
          <div className="rounded-xl border border-border bg-card p-3">
            <div className="text-[11px] font-medium text-slate-400">最近执行批次</div>
            <div className="mt-1 text-lg font-bold text-slate-800 dark:text-slate-100">
              {latestLogs.length > 0
                ? relTime(latestLogs[0]?.created_at)
                : "暂无记录"}
            </div>
            <div className="mt-0.5 text-[11px] text-slate-500 truncate" title={latestLogs[0]?.created_at ?? ""}>
              {latestLogs[0]?.created_at ? formatDateTime(latestLogs[0].created_at) : "等待首次运行"}
            </div>
          </div>
        </div>

        {/* 视图切换与筛选 */}
        <div className="border-border border-b px-4 py-3 sm:flex sm:items-center sm:justify-between sm:px-5">
          <div className="flex items-center gap-1.5">
            <button
              type="button"
              onClick={() => setLogViewMode("latest")}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                logViewMode === "latest"
                  ? "bg-blue-600 text-white shadow-xs"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800",
              )}
            >
              各商家最新状态 ({latestLogs.length})
            </button>
            <button
              type="button"
              onClick={() => setLogViewMode("stream")}
              className={cn(
                "rounded-lg px-3 py-1.5 text-xs font-medium transition-colors",
                logViewMode === "stream"
                  ? "bg-blue-600 text-white shadow-xs"
                  : "text-slate-600 hover:bg-slate-100 dark:text-slate-400 dark:hover:bg-slate-800",
              )}
            >
              执行历史流水 ({crawlLogs.length})
            </button>
          </div>

          {logViewMode === "stream" && (
            <div className="mt-3 flex flex-wrap items-center gap-2 sm:mt-0">
              <select
                value={streamMerchantFilter}
                onChange={(e) => setStreamMerchantFilter(e.target.value)}
                className="h-8 rounded-lg border border-border bg-card px-2 text-xs text-slate-700 dark:text-slate-200"
              >
                <option value="all">所有商家</option>
                {merchants.map((m) => (
                  <option key={m.slug} value={m.slug}>
                    {m.name} ({m.slug})
                  </option>
                ))}
              </select>

              <select
                value={streamStatusFilter}
                onChange={(e) => setStreamStatusFilter(e.target.value)}
                className="h-8 rounded-lg border border-border bg-card px-2 text-xs text-slate-700 dark:text-slate-200"
              >
                <option value="all">全部状态</option>
                <option value="success">官方一手</option>
                <option value="partial">部分一手</option>
                <option value="degraded">降级兜底</option>
                <option value="failed">抓取失败</option>
              </select>
            </div>
          )}
        </div>

        {/* 内容展示 */}
        {logViewMode === "latest" ? (
          /* 各商家最新状态 */
          <div className="overflow-x-auto">
            <table className="w-full min-w-[780px] text-sm">
              <thead className="text-[11px] tracking-wide text-slate-400 uppercase bg-slate-50/50 dark:bg-slate-900/20">
                <tr className="border-border border-b">
                  <th className="px-4 py-2.5 text-left font-medium">商家 / 标识</th>
                  <th className="px-4 py-2.5 text-left font-medium">最新抓取状态</th>
                  <th className="px-4 py-2.5 text-left font-medium">抓取方式</th>
                  <th className="px-4 py-2.5 text-right font-medium">一手 / 总量 / 在售</th>
                  <th className="px-4 py-2.5 text-right font-medium">耗时</th>
                  <th className="px-4 py-2.5 text-left font-medium">最近执行</th>
                  <th className="px-4 py-2.5 text-left font-medium">执行说明</th>
                </tr>
              </thead>
              <tbody>
                {latestLogs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-muted-foreground px-4 py-12 text-center text-xs">
                      暂无爬虫执行记录。点击右上角「立即全量抓取」或等待定时扫描任务。
                    </td>
                  </tr>
                ) : (
                  latestLogs.map((log) => {
                    const merch = merchants.find((m) => m.slug === log.merchant_slug);
                    const officialRate =
                      log.products_count > 0
                        ? Math.round((log.official_count / log.products_count) * 100)
                        : 0;

                    return (
                      <tr
                        key={log.merchant_slug}
                        className="border-border border-b last:border-0 hover:bg-slate-50/60 dark:hover:bg-slate-900/40 transition-colors"
                      >
                        <td className="px-4 py-3">
                          <div className="flex items-center gap-1.5 font-medium text-slate-900 dark:text-slate-100">
                            {log.merchant_name}
                            {merch?.website && (
                              <a
                                href={merch.website}
                                target="_blank"
                                rel="noreferrer"
                                className="text-slate-400 hover:text-blue-500"
                                title="访问官网"
                              >
                                <ExternalLink className="h-3 w-3" />
                              </a>
                            )}
                          </div>
                          <div className="font-mono text-[11px] text-slate-400">
                            {log.merchant_slug}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          <StatusBadge status={log.status} />
                        </td>
                        <td className="px-4 py-3">
                          <div
                            className="max-w-[280px] truncate font-mono text-xs text-slate-600 dark:text-slate-300"
                            title={log.method || merch?.crawl_method || "官方直连"}
                          >
                            {log.method || merch?.crawl_method || "官方直连"}
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums">
                          <div className="font-medium text-slate-800 dark:text-slate-200">
                            {log.official_count} / {log.products_count}
                          </div>
                          <div className="text-[11px] text-slate-400">
                            {log.in_stock_count} 在售 · {officialRate}% 一手
                          </div>
                        </td>
                        <td className="px-4 py-3 text-right tabular-nums text-xs text-slate-600 dark:text-slate-400">
                          {formatDuration(log.duration_ms)}
                        </td>
                        <td className="px-4 py-3">
                          <div className="text-xs text-slate-700 dark:text-slate-300">
                            {relTime(log.created_at)}
                          </div>
                          <div className="text-[10px] text-slate-400">
                            {formatDateTime(log.created_at)}
                          </div>
                        </td>
                        <td className="px-4 py-3">
                          {log.error ? (
                            <div
                              className="max-w-[200px] truncate text-xs text-red-500 dark:text-red-400 font-mono"
                              title={log.error}
                            >
                              {log.error}
                            </div>
                          ) : (
                            <div
                              className="max-w-[200px] truncate text-xs text-slate-500"
                              title={log.message || "—"}
                            >
                              {log.message || "—"}
                            </div>
                          )}
                        </td>
                      </tr>
                    );
                  })
                )}
              </tbody>
            </table>
          </div>
        ) : (
          /* 流水视图 */
          <div className="overflow-x-auto">
            <table className="w-full min-w-[780px] text-sm">
              <thead className="text-[11px] tracking-wide text-slate-400 uppercase bg-slate-50/50 dark:bg-slate-900/20">
                <tr className="border-border border-b">
                  <th className="px-4 py-2.5 text-left font-medium">执行时间</th>
                  <th className="px-4 py-2.5 text-left font-medium">商家</th>
                  <th className="px-4 py-2.5 text-left font-medium">抓取状态</th>
                  <th className="px-4 py-2.5 text-left font-medium">抓取方式</th>
                  <th className="px-4 py-2.5 text-right font-medium">一手 / 总量 / 在售</th>
                  <th className="px-4 py-2.5 text-right font-medium">耗时</th>
                  <th className="px-4 py-2.5 text-left font-medium">说明 / 错误</th>
                </tr>
              </thead>
              <tbody>
                {filteredStreamLogs.length === 0 ? (
                  <tr>
                    <td colSpan={7} className="text-muted-foreground px-4 py-12 text-center text-xs">
                      无符合条件的执行流水记录
                    </td>
                  </tr>
                ) : (
                  filteredStreamLogs.map((log) => (
                    <tr
                      key={log.id}
                      className="border-border border-b last:border-0 hover:bg-slate-50/60 dark:hover:bg-slate-900/40 transition-colors"
                    >
                      <td className="px-4 py-2.5 text-xs">
                        <div className="font-mono text-slate-700 dark:text-slate-300">
                          {formatDateTime(log.created_at)}
                        </div>
                        <div className="text-[10px] text-slate-400">{relTime(log.created_at)}</div>
                      </td>
                      <td className="px-4 py-2.5">
                        <div className="font-medium text-slate-900 dark:text-slate-100">
                          {log.merchant_name}
                        </div>
                        <div className="font-mono text-[11px] text-slate-400">
                          {log.merchant_slug}
                        </div>
                      </td>
                      <td className="px-4 py-2.5">
                        <StatusBadge status={log.status} />
                      </td>
                      <td className="px-4 py-2.5">
                        <div
                          className="max-w-[240px] truncate font-mono text-xs text-slate-600 dark:text-slate-300"
                          title={log.method || "官方直连"}
                        >
                          {log.method || "官方直连"}
                        </div>
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-xs">
                        <span className="font-medium text-slate-800 dark:text-slate-200">
                          {log.official_count} / {log.products_count}
                        </span>{" "}
                        <span className="text-slate-400">({log.in_stock_count} 在售)</span>
                      </td>
                      <td className="px-4 py-2.5 text-right tabular-nums text-xs text-slate-600 dark:text-slate-400">
                        {formatDuration(log.duration_ms)}
                      </td>
                      <td className="px-4 py-2.5">
                        {log.error ? (
                          <div
                            className="max-w-[200px] truncate text-xs text-red-500 font-mono"
                            title={log.error}
                          >
                            {log.error}
                          </div>
                        ) : (
                          <div
                            className="max-w-[200px] truncate text-xs text-slate-500"
                            title={log.message || "—"}
                          >
                            {log.message || "—"}
                          </div>
                        )}
                      </td>
                    </tr>
                  ))
                )}
              </tbody>
            </table>
          </div>
        )}
      </section>

      {/* ── 商家管理 ── */}
      <section className="border-border bg-card overflow-hidden rounded-2xl border shadow-sm">
        <div className="border-border border-b px-4 py-3 sm:px-5">
          <h2 className="text-sm font-semibold">商家管理与抓取配置</h2>
          <p className="text-muted-foreground mt-0.5 text-xs">
            管理各商家的抓取开关、抓取频次与爬虫配置方式。
          </p>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[720px] text-sm">
            <thead className="text-[11px] tracking-wide text-slate-400 uppercase bg-slate-50/50 dark:bg-slate-900/20">
              <tr className="border-border border-b">
                <th className="px-4 py-2.5 text-left font-medium">商家 / 抓取方式</th>
                <th className="px-4 py-2.5 text-left font-medium">扫描开关</th>
                <th className="px-4 py-2.5 text-right font-medium">间隔（分）</th>
                <th className="px-4 py-2.5 text-right font-medium">套餐 / 有货</th>
                <th className="px-4 py-2.5 text-left font-medium">上次成功</th>
              </tr>
            </thead>
            <tbody>
              {merchants.map((m) => (
                <tr key={m.slug} className="border-border border-b last:border-0">
                  <td className="px-4 py-2.5">
                    <div className="font-medium text-slate-900 dark:text-slate-100">{m.name}</div>
                    <div className="text-[11px] font-mono text-slate-400">{m.slug}</div>
                    {m.crawl_method ? (
                      <div
                        className="mt-1 inline-block max-w-[320px] truncate rounded bg-slate-100 px-1.5 py-0.5 font-mono text-[10px] text-slate-600 dark:bg-slate-800 dark:text-slate-300"
                        title={m.crawl_method}
                      >
                        {m.crawl_method}
                      </div>
                    ) : null}
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
                        "rounded-full px-2.5 py-1 text-[11px] font-semibold cursor-pointer transition-colors",
                        m.enabled
                          ? "bg-emerald-50 text-emerald-700 dark:bg-emerald-950/50 dark:text-emerald-300 hover:bg-emerald-100"
                          : "bg-slate-100 text-slate-500 dark:bg-slate-800 hover:bg-slate-200",
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

      {/* ── 推广链接 ── */}
      <section className="border-border bg-card overflow-hidden rounded-2xl border shadow-sm">
        <div className="border-border border-b px-4 py-3 sm:px-5">
          <div className="flex flex-wrap items-start justify-between gap-2">
            <div>
              <h2 className="text-sm font-semibold">推广链接</h2>
              <p className="text-muted-foreground mt-0.5 text-xs">
                购买跳转走 <span className="font-mono">/go</span>，套用下面模板。可用{" "}
                <span className="font-mono">{"{pid}"}</span> 和 <span className="font-mono">{"{url}"}</span>
                。留空则直链、不带佣金。改完立刻生效，扫描不会覆盖。
              </p>
            </div>
            {affMsg ? <span className="text-xs text-slate-500">{affMsg}</span> : null}
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[860px] text-sm">
            <thead className="bg-slate-50/50 text-[11px] tracking-wide text-slate-400 uppercase dark:bg-slate-900/20">
              <tr className="border-border border-b">
                <th className="px-4 py-2.5 text-left font-medium">商家</th>
                <th className="px-4 py-2.5 text-left font-medium">状态</th>
                <th className="px-4 py-2.5 text-right font-medium">近 30 日点击</th>
                <th className="px-4 py-2.5 text-left font-medium">模板</th>
                <th className="px-4 py-2.5 text-left font-medium">操作</th>
              </tr>
            </thead>
            <tbody>
              {merchants.map((m) => {
                const draft = affDrafts[m.slug] ?? "";
                const dirty = draft !== (m.aff_url_template || "");
                const status = m.aff_status || "direct";
                const locked = status === "unsupported";
                return (
                  <tr key={m.slug} className="border-border border-b last:border-0 align-top">
                    <td className="px-4 py-3">
                      <div className="font-medium text-slate-900 dark:text-slate-100">{m.name}</div>
                      <div className="font-mono text-[11px] text-slate-400">{m.slug}</div>
                    </td>
                    <td className="px-4 py-3">
                      <AffStatusBadge status={status} />
                      {locked ? (
                        <p className="mt-1 max-w-[160px] text-[11px] leading-snug text-slate-400">
                          加购走 POST 表单，目前无法套推广链接
                        </p>
                      ) : null}
                    </td>
                    <td className="px-4 py-3 text-right tabular-nums">{n(m.aff_clicks_d30)}</td>
                    <td className="px-4 py-3">
                      <Input
                        value={draft}
                        disabled={locked}
                        placeholder={m.aff_code_default || "商家直链，不带推广"}
                        className="h-8 min-w-[280px] font-mono text-xs"
                        onChange={(e) => setAffDrafts((prev) => ({ ...prev, [m.slug]: e.target.value }))}
                      />
                      {m.aff_code_default && m.aff_code_default !== draft ? (
                        <p className="mt-1 max-w-[420px] truncate text-[10px] text-slate-400" title={m.aff_code_default}>
                          代码默认：{m.aff_code_default}
                        </p>
                      ) : null}
                    </td>
                    <td className="px-4 py-3">
                      <div className="flex flex-wrap gap-1.5">
                        <Button
                          type="button"
                          size="sm"
                          variant="outline"
                          className="h-8 text-xs"
                          disabled={locked || affSaving === m.slug || !dirty}
                          onClick={() => void saveAff(m.slug)}
                        >
                          {affSaving === m.slug ? "保存中" : "保存"}
                        </Button>
                        <Button
                          type="button"
                          size="sm"
                          variant="ghost"
                          className="h-8 text-xs"
                          disabled={locked || affSaving === m.slug || !m.aff_code_default}
                          onClick={() => void saveAff(m.slug, true)}
                        >
                          恢复默认
                        </Button>
                      </div>
                    </td>
                  </tr>
                );
              })}
            </tbody>
          </table>
        </div>
      </section>

      {/* ── 站点配置 ── */}
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
