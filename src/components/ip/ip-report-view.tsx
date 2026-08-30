import { AlertTriangle, CheckCircle2, Info, ShieldCheck, XCircle } from "lucide-react";

import type { IpCheckResult } from "@/lib/api/endpoints";

/**
 * IP 检测报告渲染（/api/ip/check 响应 → 分区面板）。
 * 纯展示组件；状态一律「颜色 + 图标 + 文字」三通道，不单靠颜色传达。
 */

const RISK_STYLES: Record<string, string> = {
  emerald: "bg-emerald-600",
  blue: "bg-sky-600",
  amber: "bg-amber-500",
  rose: "bg-rose-600",
};

function Panel({
  title,
  children,
}: {
  title: string;
  children: React.ReactNode;
}) {
  return (
    <section className="bg-card rounded-xl border p-4">
      <h2 className="mb-3 text-sm font-semibold">{title}</h2>
      {children}
    </section>
  );
}

function KV({ k, v }: { k: string; v: React.ReactNode }) {
  return (
    <div className="flex min-w-0 items-baseline justify-between gap-3 py-1.5">
      <dt className="text-muted-foreground shrink-0 text-xs">{k}</dt>
      <dd className="min-w-0 truncate text-right text-sm">{v}</dd>
    </div>
  );
}

export function IpReportView({
  r,
  isSelf = false,
}: {
  r: IpCheckResult;
  /**
   * 结果 IP 是否为访客自己的公网 IP。
   * 不能靠 query_target 与 ip 是否相等来判断——查询域名时二者本就不同，
   * 而直接输入一个 IP 时二者相等，会把「查别人的 IP」误判成自己的。
   */
  isSelf?: boolean;
}) {
  return (
    <div className="flex flex-col gap-4">
      {/* 概要卡 */}
      <section className="bg-card rounded-xl border p-5">
        <div className="flex flex-wrap items-start justify-between gap-4">
          <div className="min-w-0">
            <p className="text-muted-foreground text-xs">
              {isSelf
                ? "你的公网 IP"
                : // 查询域名时 query_target 与解析后的 ip 不同，标出原始输入；
                  // 直接输入 IP 时二者相同，不再重复展示同一个值
                  r.query_target !== r.ip
                  ? `指定查询 · ${r.query_target}`
                  : "指定查询的 IP"}
            </p>
            <p className="mt-1 break-all text-2xl font-bold tabular-nums">
              {r.flag} {r.ip}
            </p>
            <p className="text-muted-foreground mt-1 text-sm">
              {r.country || "未知"}
              {r.city ? ` · ${r.city}` : ""}
              {r.region ? ` · ${r.region}` : ""}
            </p>
            {(r.continent || r.rir) && (
              <p className="text-muted-foreground mt-0.5 text-xs">
                {[r.continent, r.rir].filter(Boolean).join(" · ")}
              </p>
            )}
          </div>
          <div className="text-center">
            <div className={`inline-flex h-16 w-16 items-center justify-center rounded-full text-white ${RISK_STYLES[r.risk_color] ?? "bg-sky-600"}`}>
              <span className="text-xl font-bold tabular-nums">{r.clean_score}</span>
            </div>
            <p className="text-muted-foreground mt-1.5 max-w-36 text-xs leading-snug">{r.risk_level}</p>
          </div>
        </div>

        <dl className="mt-4 grid grid-cols-1 gap-x-6 border-t pt-2 sm:grid-cols-2">
          <KV k="IP 类型" v={r.ip_type} />
          <KV k="运营商 (ISP)" v={r.isp} />
          <KV k="组织 (Org)" v={r.org} />
          <KV k="AS 信息" v={r.as_raw || "—"} />
          {r.vendor_brand && <KV k="主机商识别" v={r.vendor_brand} />}
          {r.reverse_dns && <KV k="rDNS" v={r.reverse_dns} />}
          {r.timezone && <KV k="时区" v={r.timezone} />}
          {r.lat != null && r.lon != null && (
            <KV k="经纬度" v={<span className="tabular-nums">{Number(r.lat).toFixed(2)}, {Number(r.lon).toFixed(2)}</span>} />
          )}
        </dl>
      </section>

      {/* 风险因素 */}
      {r.risk_factors.length > 0 && (
        <Panel title={`纯净度分析（欺诈分 ${r.fraud_score}/100 · ${r.scamalytics_rating}）`}>
          <ul className="flex flex-col gap-2">
            {r.risk_factors.map((f) => {
              const positive = f.impact.startsWith("+");
              return (
                <li key={f.title} className="flex items-start gap-2 text-sm">
                  {positive ? (
                    <CheckCircle2 aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-emerald-600" />
                  ) : (
                    <AlertTriangle aria-hidden className="mt-0.5 h-4 w-4 shrink-0 text-amber-500" />
                  )}
                  <div className="min-w-0">
                    <p className="font-medium">
                      {f.title}
                      <span className={`ml-1.5 tabular-nums ${positive ? "text-emerald-600 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                        {f.impact}
                      </span>
                    </p>
                    <p className="text-muted-foreground text-xs leading-relaxed">{f.desc}</p>
                  </div>
                </li>
              );
            })}
          </ul>
        </Panel>
      )}

      <div className="grid grid-cols-1 gap-4 lg:grid-cols-2">
        {/* 安全检查 */}
        <Panel title="安全与黑名单检查">
          <ul className="flex flex-col divide-y">
            {r.security_checks.map((c) => (
              <li key={c.name} className="flex items-center justify-between gap-3 py-2 text-sm">
                <span className="min-w-0">{c.name}</span>
                <span className={`inline-flex shrink-0 items-center gap-1 text-xs ${c.pass ? "text-emerald-700 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                  {c.pass ? <CheckCircle2 aria-hidden className="h-3.5 w-3.5" /> : <XCircle aria-hidden className="h-3.5 w-3.5" />}
                  {c.status}
                </span>
              </li>
            ))}
          </ul>
        </Panel>

        {/* 多源比对 */}
        <Panel title="多数据库比对">
          <ul className="flex flex-col gap-3">
            {r.source_comparison.map((s) => (
              <li key={s.source} className="text-sm">
                <p className="flex items-center gap-1.5 font-medium">
                  <Info aria-hidden className="text-muted-foreground h-3.5 w-3.5" />
                  {s.source}
                  <span className="text-muted-foreground text-xs">（{s.status}）</span>
                </p>
                <p className="text-muted-foreground mt-0.5 break-words text-xs leading-relaxed">
                  {s.isp} · {s.as} · {s.type} · {s.country}
                </p>
              </li>
            ))}
          </ul>
        </Panel>
      </div>

      {/* 平台解锁预测 */}
      {r.unlock_predictions.length > 0 && (
        <Panel title="平台可用性预测">
          <ul className="grid grid-cols-1 gap-2 sm:grid-cols-2">
            {r.unlock_predictions.map((u) => (
              <li key={u.name} className="rounded-lg bg-muted/50 p-3">
                <p className="flex items-center justify-between gap-2 text-sm font-medium">
                  <span className="min-w-0 truncate">{u.name}</span>
                  <span className={`inline-flex shrink-0 items-center gap-1 text-xs ${u.level === "pass" ? "text-emerald-700 dark:text-emerald-400" : "text-amber-600 dark:text-amber-400"}`}>
                    {u.level === "pass" ? <CheckCircle2 aria-hidden className="h-3.5 w-3.5" /> : <AlertTriangle aria-hidden className="h-3.5 w-3.5" />}
                    {u.status}
                  </span>
                </p>
                <p className="text-muted-foreground mt-1 text-xs leading-relaxed">{u.note}</p>
              </li>
            ))}
          </ul>
          <p className="text-muted-foreground mt-3 flex items-start gap-1 text-xs leading-relaxed">
            <ShieldCheck aria-hidden className="mt-0.5 h-3.5 w-3.5 shrink-0" />
            以上为基于 IP 属性的模型预测，实际可用性以平台实时风控为准。
          </p>
        </Panel>
      )}
    </div>
  );
}
