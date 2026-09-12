"use client";

import { useEffect } from "react";
import { AlertCircle, Home, RefreshCw, RotateCcw } from "lucide-react";

import { Button } from "@/components/ui/button";

/**
 * 页面级全局错误边界（App Router 约定文件）。
 *
 * 兜住所有未在子级处理的服务端或客户端异常。
 * 生产构建下服务端详情仅保留 digest，客户端错误可能含有 message。
 * 提供行之有效的恢复出口：内存重试、页面硬刷新、返回首页。
 */
export default function PageError({
  error,
  reset,
}: {
  error: Error & { digest?: string };
  reset: () => void;
}) {
  useEffect(() => {
    console.error("[page error]", error);
  }, [error]);

  const handleHardRefresh = () => {
    window.location.reload();
  };

  const handleGoHome = () => {
    window.location.href = "/";
  };

  return (
    <main className="flex min-h-[60dvh] flex-col items-center justify-center gap-3 px-4 text-center">
      <div
        className="flex h-12 w-12 items-center justify-center rounded-2xl bg-amber-50 text-amber-600 dark:bg-amber-950/50 dark:text-amber-400"
        aria-hidden
      >
        <AlertCircle className="h-6 w-6" />
      </div>
      <h1 className="text-xl font-bold tracking-tight text-slate-900 dark:text-slate-100">
        页面加载遇到问题
      </h1>
      <p className="text-muted-foreground max-w-md text-sm leading-relaxed">
        服务响应超时或页面状态暂时不同步，请尝试重试或刷新。若持续失败，可返回首页重新进入。
      </p>
      <div className="mt-2 flex flex-wrap items-center justify-center gap-2">
        <Button size="sm" onClick={() => reset()} className="gap-1.5">
          <RotateCcw className="h-3.5 w-3.5" />
          重试
        </Button>
        <Button variant="outline" size="sm" onClick={handleHardRefresh} className="gap-1.5">
          <RefreshCw className="h-3.5 w-3.5" />
          刷新页面
        </Button>
        <Button variant="outline" size="sm" onClick={handleGoHome} className="gap-1.5">
          <Home className="h-3.5 w-3.5" />
          返回首页
        </Button>
      </div>
      {error.digest && (
        <p className="text-muted-foreground/70 mt-2 font-mono text-xs">错误编号 {error.digest}</p>
      )}
    </main>
  );
}

