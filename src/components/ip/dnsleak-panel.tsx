"use client";

import { useCallback, useState } from "react";
import { CheckCircle2, Info, Loader2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import { getDnsLeakResults, type DnsLeakResults } from "@/lib/api/endpoints";

/**
 * DNS 泄露检测面板。
 * 完整链路需要权威 DNS 侧部署（B12 注释：*.dnstest.govps.xyz 通配子域 +
 * 可编程权威 DNS 记录命中 resolver）。前端按协议先行实现：
 * 生成随机 token → 浏览器请求 <token>.dnstest.govps.xyz 触发解析 →
 * 轮询回收接口；接口返回 configured=false 时如实展示部署状态，不伪造结果。
 */

export function DnsleakPanel() {
  const [state, setState] = useState<"idle" | "running" | "done">("idle");
  const [result, setResult] = useState<DnsLeakResults | null>(null);

  const run = useCallback(async () => {
    setState("running");
    const token = Math.random().toString(36).slice(2, 10) + Date.now().toString(36);
    // 1) 触发一系列随机子域解析（浏览器经本机 resolver 出网）
    const probes = Array.from({ length: 4 }, (_, i) => `${token}${i}.dnstest.govps.xyz`);
    await Promise.allSettled(
      probes.map((h) => fetch(`https://${h}/probe.txt`, { mode: "no-cors", cache: "no-store" })),
    );
    // 2) 稍候轮询回收接口
    await new Promise((r) => setTimeout(r, 2500));
    try {
      const r = await getDnsLeakResults(token);
      setResult(r);
    } catch {
      setResult({ configured: false, resolvers: [], token });
    }
    setState("done");
  }, []);

  return (
    <>
      <header className="mb-4">
        <h1 className="text-xl font-bold tracking-tight lg:text-2xl">DNS 泄露检测</h1>
        <p className="text-muted-foreground mt-1 text-sm leading-relaxed">
          使用 VPN/代理时，若 DNS 解析仍走本地运营商，你的真实访问足迹就会泄露。
          检测原理：让浏览器解析一组随机子域，权威 DNS 侧记录实际代为解析的递归服务器 IP。
        </p>
      </header>

      <Button onClick={run} disabled={state === "running"} className="mb-4">
        {state === "running" ? (
          <>
            <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
            正在检测…
          </>
        ) : (
          "开始检测"
        )}
      </Button>

      {state === "idle" && (
        <div className="bg-card text-muted-foreground rounded-xl border p-6 text-sm leading-relaxed">
          点击「开始检测」后，页面会向一组随机子域发起请求。整个过程约需 5 秒，
          仅用于识别为你做递归解析的 DNS 服务器，不收集其他信息。
        </div>
      )}

      {result && (
        <div role="status" className="bg-card rounded-xl border p-5">
          {result.configured ? (
            result.resolvers.length > 0 ? (
              <>
                <p className="flex items-center gap-2 text-sm font-medium">
                  <CheckCircle2 aria-hidden className="h-5 w-5 text-emerald-600" />
                  检测完成：为你提供递归解析的服务器共 {result.resolvers.length} 台
                </p>
                <ul className="mt-3 flex flex-col gap-1.5 text-sm">
                  {result.resolvers.map((x) => (
                    <li key={x.resolver} className="flex items-center justify-between gap-3">
                      <span className="break-all tabular-nums">{x.resolver}</span>
                      <span className="text-muted-foreground shrink-0 text-xs">{x.country ?? ""}</span>
                    </li>
                  ))}
                </ul>
              </>
            ) : (
              <p className="text-sm">未捕获到解析记录，请重试。</p>
            )
          ) : (
            <div className="text-sm leading-relaxed">
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
              <p className="text-muted-foreground mt-2">
                在此之前，可先用「IP 检测」页观察出口 IP 与运营商是否与 VPN 提供商一致作为替代判断。
              </p>
            </div>
          )}
          <p className="text-muted-foreground mt-4 border-t pt-3 break-all text-xs">
            本次检测令牌：<span className="tabular-nums">{result.token}</span>
          </p>
        </div>
      )}
    </>
  );
}
