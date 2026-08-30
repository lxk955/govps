"use client";

import { useEffect, useRef } from "react";
import { usePathname } from "next/navigation";

import { trackPageView } from "@/lib/track";

/**
 * 路由变化时上报页面访问（PV/UV 统计，落库到后端 page_views）。
 *
 * 依赖只取 pathname：筛选条件变化（仅查询串改变）不重复计 PV，后端也会剥离
 * 查询串再归一化，两者口径一致。查询串本身仍随上报带上，便于分析来源。
 *
 * lastRef 用于抑制重复上报：React StrictMode 下 effect 会挂载两次，若不去重
 * 开发环境每条 PV 都会翻倍，统计口径失真。
 */
export function PageViewTracker() {
  const pathname = usePathname();
  const lastRef = useRef<string | null>(null);

  useEffect(() => {
    if (!pathname) return;
    // 直接读 window.location.search 而非 useSearchParams：后者在 App Router
    // 中会要求 Suspense 边界，不值得为一个埋点组件影响整棵树的渲染策略。
    const full = pathname + window.location.search;
    if (full === lastRef.current) return;
    lastRef.current = full;
    trackPageView(full);
  }, [pathname]);

  return null;
}
