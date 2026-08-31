"use client";

import { usePathname, useSearchParams } from "next/navigation";
import { useEffect, useRef, useState } from "react";

/**
 * 全局路由加载进度条。
 *
 * 监听 URL 变化（筛选改 searchParams 的软导航、翻页、页面切换均会触发），
 * 在视口顶部显示一条细进度条，短暂停留后消失。纯装饰组件，不参与数据链路；
 * 首次挂载不显示（硬加载/刷新已有 loading.tsx 骨架兜底）。
 *
 * 注意：useSearchParams 必须包在 <Suspense> 内使用（layout 中已处理），
 * 否则静态预渲染时会导致整页退化为客户端渲染（CSR bailout）。
 */
export function RouteProgress() {
  const pathname = usePathname();
  const search = useSearchParams().toString();
  const [visible, setVisible] = useState(false);
  const mounted = useRef(false);

  useEffect(() => {
    if (!mounted.current) {
      mounted.current = true; // 跳过首次挂载，避免进入页面就闪进度条
      return;
    }
    setVisible(true);
    const timer = setTimeout(() => setVisible(false), 700);
    return () => clearTimeout(timer);
  }, [pathname, search]);

  if (!visible) return null;

  return (
    <div
      aria-hidden="true"
      className="pointer-events-none fixed inset-x-0 top-0 z-[100] h-0.5 animate-pulse bg-blue-500"
    />
  );
}
