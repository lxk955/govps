"use client";

import { Suspense, useCallback, useEffect, useState } from "react";
import { useSearchParams } from "next/navigation";

import { checkIp, type IpCheckResult } from "@/lib/api/endpoints";
import { MERCHANT_TEST_IP_LIST } from "@/lib/merchant-test-ips";
import { IpReportView } from "./ip-report-view";

/**
 * IP 检测面板（1:1 复刻旧站 IpHome.vue 的查询表单与状态区）：
 * .query 输入行 + 商家机房「快捷测试」预设 + 纯文本加载态 + .verdict 错误卡。
 * 样式由板块的 ipcx.css 提供。
 */

function Panel({ clientIp }: { clientIp?: string }) {
  const sp = useSearchParams();
  const [result, setResult] = useState<IpCheckResult | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  const [query, setQuery] = useState(sp.get("q") ?? "");
  // ?q= 预填目标优先（详情页「检测机房 IP」入口带商家测试 IP 进来）；
  // 否则用服务端读到的访客真实公网 IP。不能留空让后端自己判断——经
  // Next.js rewrite 转发后后端只看到前端服务的出口 IP。
  const initialTarget = sp.get("q") ?? clientIp;

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
      <form onSubmit={onSubmit} className="query" role="search">
        <div className="query__line">
          <span className="query__icon" aria-hidden="true">
            <svg
              width="18"
              height="18"
              viewBox="0 0 24 24"
              fill="none"
              stroke="currentColor"
              strokeWidth="2"
              strokeLinecap="round"
            >
              <circle cx="10.5" cy="10.5" r="6.5" />
              <path d="m20 20-4.9-4.9" />
            </svg>
          </span>
          <input
            className="query__input mono"
            type="text"
            placeholder="8.8.8.8"
            autoComplete="off"
            autoCapitalize="off"
            spellCheck={false}
            enterKeyHint="search"
            aria-label="要查询的 IP 地址或域名"
            value={query}
            onChange={(e) => setQuery(e.target.value)}
          />
          <button className="query__submit" type="submit" disabled={loading}>
            {loading ? "查询中…" : "查询"}
          </button>
        </div>
        <div className="presets">
          <span className="faint text-[12.5px]">快捷测试：</span>
          {MERCHANT_TEST_IP_LIST.map((preset) => (
            <button
              key={preset.ip}
              type="button"
              className="preset mono"
              onClick={() => void run(preset.ip)}
            >
              {preset.label}
            </button>
          ))}
        </div>
      </form>

      {error ? (
        <div className="verdict verdict--danger mt-[26px]" role="alert">
          <span className="verdict__dot" />
          <div>
            <p className="verdict__title">查询失败</p>
            <p className="verdict__note">{error}</p>
          </div>
        </div>
      ) : loading && !result ? (
        <div className="dim mt-[26px]" role="status">
          正在查询…
        </div>
      ) : (
        result && <IpReportView r={result} />
      )}
    </>
  );
}

export function IpCheckPanel({ clientIp }: { clientIp?: string } = {}) {
  return (
    <Suspense fallback={<div className="dim mt-[26px]">加载中…</div>}>
      <Panel clientIp={clientIp} />
    </Suspense>
  );
}
