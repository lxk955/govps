"use client";

import { useEffect } from "react";
import Link from "next/link";

import { Button } from "@/components/ui/button";

/**
 * 页面级错误边界（App Router 约定文件）。
 *
 * 兜住所有未逐页 catch 的服务端取数失败，
 * 避免直接落到 Next.js 默认错误页——后者在生产只显示一行 "Application error"，
 * 用户既不知道发生了什么，也没有任何可操作出口。
 *
 * 注意：生产构建下服务端错误详情不会传给客户端（仅保留 digest），
 * 因此这里不做错误类型分支，只给通用可操作提示 + reset 重试。
 * 需要区分错误类型的页面（如 /vps 列表）应在页面内自行 catch 渲染。
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

  return (
    <main className="flex min-h-[60dvh] flex-col items-center justify-center gap-3 px-4 text-center">
      <div className="text-3xl" aria-hidden>
        📡
      </div>
      <h1 className="text-xl font-bold">数据加载失败</h1>
      <p className="text-muted-foreground max-w-md text-sm leading-relaxed">
        套餐数据暂时取不到，请稍后重试。若连续失败，可先浏览首页或稍后再来。
      </p>
      <div className="mt-1 flex flex-wrap items-center justify-center gap-2">
        <Button size="sm" onClick={reset}>
          重试
        </Button>
        <Button asChild variant="outline" size="sm">
          <Link href="/">浏览在售套餐</Link>
        </Button>
      </div>
      {error.digest && (
        <p className="text-muted-foreground/70 mt-2 font-mono text-xs">错误编号 {error.digest}</p>
      )}
    </main>
  );
}
