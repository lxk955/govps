"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";
import { Loader2, Search } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { checkIp, type IpCheckResult } from "@/lib/api/endpoints";
import { IpReportView } from "./ip-report-view";

/** IP 检测面板：挂载时自动检测当前出口 IP；支持手动查询 IPv4/IPv6/域名。 */

function Panel() {
  const sp = useSearchParams();
  const [result, setResult] = useState<IpCheckResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState(sp.get("q") ?? "");
  // ?q= 预填目标：详情页「检测机房 IP」入口带商家域名进来
  const initialTarget = sp.get("q");

  const run = useCallback(async (target?: string) => {
    setLoading(true);
    setError(null);
    try {
      const r = await checkIp(target);
      setResult(r);
    } catch (e) {
      setError(e instanceof Error ? e.message : "检测失败，请稍后重试");
    } finally {
      setLoading(false);
    }
  }, []);

  useEffect(() => {
    run(initialTarget ?? undefined);
  }, [run, initialTarget]);

  const onSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    run(query.trim() || undefined);
  };

  return (
    <>
      <form onSubmit={onSubmit} className="mb-4 flex gap-2" role="search">
        <Input
          type="search"
          inputMode="url"
          placeholder="输入 IPv4 / IPv6 / 域名查询（留空检测当前 IP）"
          aria-label="要检测的 IP 或域名"
          className="text-base"
          value={query}
          onChange={(e) => setQuery(e.target.value)}
        />
        <Button type="submit" disabled={loading}>
          {loading ? (
            <Loader2 aria-hidden className="h-4 w-4 animate-spin" />
          ) : (
            <Search aria-hidden className="h-4 w-4" />
          )}
          查询
        </Button>
      </form>

      {error && (
        <div role="alert" className="border-destructive/30 bg-destructive/5 text-destructive rounded-xl border p-6 text-center text-sm">
          {error}
        </div>
      )}
      {!error && loading && !result && (
        <div className="bg-card flex items-center justify-center gap-2 rounded-xl border p-10 text-sm" role="status">
          <Loader2 aria-hidden className="animate-spin" />
          正在检测…
        </div>
      )}
      {!error && result && <IpReportView r={result} />}
    </>
  );
}

export function IpCheckPanel() {
  return (
    <Suspense
      fallback={
        <div className="bg-card text-muted-foreground flex items-center justify-center rounded-xl border p-10 text-sm" role="status">
          加载中…
        </div>
      }
    >
      <Panel />
    </Suspense>
  );
}
