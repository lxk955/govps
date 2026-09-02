"use client";

import { useCallback, useState } from "react";
import {
  Globe,
  Info,
  Loader2,
  Server,
  ShieldAlert,
  ShieldCheck,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  checkIp,
  getDnsLeakResults,
  type DnsLeakResults,
  type IpCheckResult,
} from "@/lib/api/endpoints";

type LeakSeverity = "safe" | "leak" | "direct" | "unknown";

interface LeakEvaluation {
  severity: LeakSeverity;
  title: string;
  summary: string;
  advice: string | null;
  badge: string;
}

function evaluateDnsLeak(
  exit: IpCheckResult | null,
  resolvers: DnsLeakResults["resolvers"],
): LeakEvaluation {
  if (!resolvers || resolvers.length === 0) {
    return {
      severity: "unknown",
      title: "未捕获到有效解析记录",
      summary: "未能在时限内捕获到递归服务器的请求，请稍后重试。",
      advice: "可能是网络暂时中断或浏览器插件拦截了后台探针查询。",
      badge: "未获取",
    };
  }

  // 判断出口是否为海外（非中国大陆地区或识别为数据中心代理）
  const isOverseasExit = exit ? exit.country_code !== "CN" : false;
  const isDomesticExit = exit ? exit.country_code === "CN" : false;

  // 过滤出国内/中国大陆本地解析器
  const domesticResolvers = resolvers.filter((r) => {
    const text = `${r.resolver} ${r.country ?? ""}`.toLowerCase();
    return (
      text.includes("中国") ||
      text.includes("china") ||
      text.includes("cn") ||
      text.includes("电信") ||
      text.includes("联通") ||
      text.includes("移动") ||
      text.includes("ali") ||
      text.includes("tencent") ||
      text.includes("114.114")
    );
  });

  // 1. 严重泄露：挂了海外代理，但 DNS 解析请求却走国内本地运营商
  if (isOverseasExit && domesticResolvers.length > 0) {
    return {
      severity: "leak",
      title: "发现严重 DNS 泄露（代理未完全接管）",
      summary: `你的 HTTP 出口位于海外（${exit?.country ?? "海外"} · ${exit?.isp ?? "代理节点"}），但检测到有 ${domesticResolvers.length} 台国内本地运营商的 DNS 服务器正在为你解析域名！`,
      advice:
        "风险提示：本地运营商与监管方可直接获悉你访问的全部海外域名与服务。建议在代理软件（Clash / Surge / Sing-box 等）中开启「远程 DNS 解析 (Remote DNS)」或「TUN 全局虚拟网卡模式」，彻底杜绝本地旁路泄露。",
      badge: "严重泄露 ⚠️",
    };
  }

  // 2. 安全无泄露：出口海外，DNS 全部也是海外或加密节点
  if (isOverseasExit && domesticResolvers.length === 0) {
    return {
      severity: "safe",
      title: "安全 · 未发现 DNS 泄露",
      summary: `你的 HTTP 出口与 DNS 解析器保持一致（均为境外节点，共 ${resolvers.length} 台）。`,
      advice:
        "防护状态良好：所有域名解析均由境外受保护节点（如 Cloudflare / Google 等）代为处理，真实域名请求未绕行国内本地网络。",
      badge: "安全无泄露 🛡️",
    };
  }

  // 3. 本地直连状态：未开启代理
  if (isDomesticExit) {
    return {
      severity: "direct",
      title: "本地物理直连状态（未检测到代理）",
      summary: `当前处于国内本地宽带直连网络（${exit?.isp ?? "本地运营商"}），捕获到的 ${resolvers.length} 台解析服务器均为本地网络正常分配。`,
      advice:
        "日常使用无需担心：若你在此时开启了 VPN 或代理，请刷新重测以确认代理是否完整接管 DNS 流量。",
      badge: "本地直连",
    };
  }

  // 4. 通用判定兜底
  if (domesticResolvers.length > 0 && domesticResolvers.length < resolvers.length) {
    return {
      severity: "leak",
      title: "检测到分流/混合 DNS 节点",
      summary: "解析节点中同时混杂了国内与海外服务器，部分敏感域名解析可能发生本地旁路泄露。",
      advice: "建议检查分流规则，对海外规则启用远端代理 DNS 解析。",
      badge: "潜在分流风险",
    };
  }

  return {
    severity: "safe",
    title: "未发现明显泄露面",
    summary: `成功捕获到 ${resolvers.length} 台 DNS 递归解析节点，请求均在可信节点内完成。`,
    advice: null,
    badge: "解析正常",
  };
}

export function DnsleakPanel() {
  const [state, setState] = useState<"idle" | "running" | "done">("idle");
  const [result, setResult] = useState<DnsLeakResults | null>(null);
  const [exitInfo, setExitInfo] = useState<IpCheckResult | null>(null);

  const run = useCallback(async () => {
    setState("running");
    setResult(null);

    // 1) 并行请求当前 HTTP 出口 IP 作为比对基准
    checkIp()
      .then((r) => setExitInfo(r))
      .catch(() => setExitInfo(null));

    const token = Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    // 2) 触发一系列随机子域解析（浏览器经本机 resolver 出网）
    const probes = Array.from({ length: 4 }, (_, i) => `${token}${i}.dnstest.govps.xyz`);
    await Promise.allSettled(
      probes.map((h) => fetch(`https://${h}/probe.txt`, { mode: "no-cors", cache: "no-store" })),
    );

    // 3) 稍候轮询回收接口
    await new Promise((r) => setTimeout(r, 2500));
    try {
      const r = await getDnsLeakResults(token);
      setResult(r);
    } catch {
      setResult({ configured: false, resolvers: [], token });
    }
    setState("done");
  }, []);

  const evaluation =
    result && result.configured && result.resolvers.length > 0
      ? evaluateDnsLeak(exitInfo, result.resolvers)
      : null;

  return (
    <>
      <header className="mb-4">
        <h1 className="text-xl font-bold tracking-tight lg:text-2xl">DNS 泄露检测</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          使用 VPN 或代理时，若域名解析依然走本地运营商，你的真实访问足迹依然会一览无余。
          本工具通过向可编程权威 DNS 发射动态探针，自动比对 HTTP 出口与 DNS 解析节点。
        </p>
      </header>

      <Button onClick={run} disabled={state === "running"} className="mb-4">
        {state === "running" ? (
          <>
            <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
            正在检测 DNS 节点与出口…
          </>
        ) : (
          "开始检测"
        )}
      </Button>

      {state === "idle" && (
        <div className="bg-card text-muted-foreground rounded-xl border p-6 text-sm leading-relaxed">
          点击「开始检测」后，页面会向一组随机子域发起请求并对照你的 HTTP 出口 IP。整个过程约需 3~5 秒，
          仅用于识别为你做递归解析的 DNS 运营商分布，绝不收集其他隐私信息。
        </div>
      )}

      {result && (
        <div role="status" className="space-y-4">
          {result.configured ? (
            result.resolvers.length > 0 ? (
              <>
                {/* 1. 醒目的红/绿/蓝大结论卡片 */}
                {evaluation && (
                  <div
                    className={`rounded-xl border p-5 transition-all ${
                      evaluation.severity === "leak"
                        ? "border-destructive/40 bg-destructive/5 text-destructive"
                        : evaluation.severity === "safe"
                          ? "border-emerald-500/40 bg-emerald-500/5 text-emerald-950 dark:text-emerald-200"
                          : "border-sky-500/40 bg-sky-500/5 text-sky-950 dark:text-sky-200"
                    }`}
                  >
                    <div className="flex items-start justify-between gap-3">
                      <div className="flex items-start gap-3">
                        {evaluation.severity === "leak" ? (
                          <ShieldAlert className="h-6 w-6 shrink-0 text-destructive mt-0.5" />
                        ) : evaluation.severity === "safe" ? (
                          <ShieldCheck className="h-6 w-6 shrink-0 text-emerald-600 dark:text-emerald-400 mt-0.5" />
                        ) : (
                          <Info className="h-6 w-6 shrink-0 text-sky-600 dark:text-sky-400 mt-0.5" />
                        )}
                        <div>
                          <div className="flex flex-wrap items-center gap-2">
                            <h2 className="text-base font-bold sm:text-lg">
                              {evaluation.title}
                            </h2>
                            <span
                              className={`rounded-full px-2.5 py-0.5 text-xs font-semibold ${
                                evaluation.severity === "leak"
                                  ? "bg-destructive text-destructive-foreground"
                                  : evaluation.severity === "safe"
                                    ? "bg-emerald-600 text-white dark:bg-emerald-500"
                                    : "bg-sky-600 text-white dark:bg-sky-500"
                              }`}
                            >
                              {evaluation.badge}
                            </span>
                          </div>
                          <p className="mt-2 text-sm leading-relaxed opacity-90">
                            {evaluation.summary}
                          </p>
                          {evaluation.advice && (
                            <p className="mt-2.5 rounded-lg bg-background/60 p-3 text-xs leading-relaxed border border-border/50">
                              {evaluation.advice}
                            </p>
                          )}
                        </div>
                      </div>
                    </div>
                  </div>
                )}

                {/* 2. 出口 IP 与 DNS 服务器双栏比对 */}
                <div className="grid grid-cols-1 gap-4 md:grid-cols-2">
                  {/* 左侧：HTTP 出口对照 */}
                  <div className="bg-card rounded-xl border p-4">
                    <div className="flex items-center gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
                      <Globe className="h-4 w-4" />
                      HTTP 出口基准（访问网页所用 IP）
                    </div>
                    {exitInfo ? (
                      <div className="space-y-2 text-sm">
                        <div className="flex items-baseline justify-between gap-2">
                          <span className="font-mono text-base font-semibold">
                            {exitInfo.ip}
                          </span>
                          <span className="text-xs text-muted-foreground">
                            {exitInfo.flag} {exitInfo.country} {exitInfo.region}
                          </span>
                        </div>
                        <div className="text-xs text-muted-foreground flex items-center justify-between border-t pt-2">
                          <span>网络运营商 / ASN：</span>
                          <span className="font-medium text-foreground">
                            {exitInfo.isp}
                          </span>
                        </div>
                        <div className="text-xs text-muted-foreground flex items-center justify-between">
                          <span>线路类型：</span>
                          <span className="font-medium text-foreground">
                            {exitInfo.ip_type}
                          </span>
                        </div>
                      </div>
                    ) : (
                      <div className="text-sm text-muted-foreground py-2">
                        出口 IP 获取中或受浏览器策略保护
                      </div>
                    )}
                  </div>

                  {/* 右侧：DNS 递归解析集群概览 */}
                  <div className="bg-card rounded-xl border p-4">
                    <div className="flex items-center justify-between gap-2 text-xs font-medium text-muted-foreground uppercase tracking-wider mb-3">
                      <span className="flex items-center gap-2">
                        <Server className="h-4 w-4" />
                        为你解析的 DNS 递归服务器
                      </span>
                      <span className="rounded bg-muted px-1.5 py-0.5 text-xs font-bold text-foreground">
                        共 {result.resolvers.length} 台
                      </span>
                    </div>
                    <p className="text-xs text-muted-foreground leading-relaxed">
                      当浏览器解析网页域名时，系统将请求投递给以下服务器处理。以下列表中若出现你不想暴露的国内宽带 IP，即代表发生泄露。
                    </p>
                  </div>
                </div>

                {/* 3. 详细解析服务器清单 */}
                <div className="bg-card rounded-xl border overflow-hidden">
                  <div className="bg-muted/40 px-4 py-3 border-b text-xs font-semibold text-muted-foreground flex items-center justify-between">
                    <span>捕获到的 DNS 解析器 IP</span>
                    <span>归属地与服务商</span>
                  </div>
                  <div className="divide-y max-h-80 overflow-y-auto">
                    {result.resolvers.map((x, idx) => {
                      const isDomestic =
                        (x.country || "").includes("中国") ||
                        (x.country || "").includes("China") ||
                        (x.country || "").includes("电信") ||
                        (x.country || "").includes("联通");
                      return (
                        <div
                          key={`${x.resolver}-${idx}`}
                          className="px-4 py-2.5 flex items-center justify-between gap-3 text-sm hover:bg-muted/30 transition-colors"
                        >
                          <div className="flex items-center gap-2 min-w-0">
                            <span className="font-mono text-xs font-medium text-foreground truncate">
                              {x.resolver}
                            </span>
                            {isDomestic ? (
                              <span className="rounded bg-destructive/10 text-destructive text-[10px] px-1.5 py-0.5 font-medium shrink-0">
                                本地节点
                              </span>
                            ) : (
                              <span className="rounded bg-emerald-500/10 text-emerald-600 dark:text-emerald-400 text-[10px] px-1.5 py-0.5 font-medium shrink-0">
                                境外节点
                              </span>
                            )}
                          </div>
                          <span className="text-xs text-muted-foreground shrink-0 text-right">
                            {x.country ?? "公共递归解析器"}
                          </span>
                        </div>
                      );
                    })}
                  </div>
                </div>
              </>
            ) : (
              <div className="bg-card rounded-xl border p-5 text-sm text-muted-foreground">
                未捕获到解析记录，请点击上方按钮重试。
              </div>
            )
          ) : (
            <div className="bg-card rounded-xl border p-5 text-sm leading-relaxed">
              <p className="flex items-center gap-2 font-medium">
                <Info aria-hidden className="h-5 w-5 text-sky-600" />
                DNS 泄露回收服务尚未部署
              </p>
              <p className="text-muted-foreground mt-2">
                检测协议已就绪，但站点侧还需完成两步配置才能给出结论：
              </p>
              <ol className="text-muted-foreground mt-2 list-decimal space-y-1 pl-5">
                <li>将 <code className="rounded bg-muted px-1">*.dnstest.govps.xyz</code> 通配子域指向可编程权威 DNS</li>
                <li>权威侧记录每个检测 token 命中的 resolver IP 并开放给回收接口</li>
              </ol>
            </div>
          )}

          <p className="text-muted-foreground border-t pt-3 break-all text-xs flex items-center justify-between">
            <span>本次检测令牌：<span className="tabular-nums font-mono">{result.token}</span></span>
            <span className="text-[11px] text-muted-foreground">实时权威捕获 · 零日志缓存</span>
          </p>
        </div>
      )}
    </>
  );
}
