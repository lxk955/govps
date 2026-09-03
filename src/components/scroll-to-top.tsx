"use client";

import { useEffect, useState } from "react";
import { ArrowUp } from "lucide-react";

import { useCompareIds } from "@/lib/compare-store";
import { cn } from "@/lib/utils";
import { usePathname } from "next/navigation";

export function ScrollToTop() {
  const [visible, setVisible] = useState(false);
  const { ids, ready } = useCompareIds();
  const pathname = usePathname();

  const hasCompareBar = ready && ids.length > 0 && pathname !== "/compare";

  useEffect(() => {
    const handleScroll = () => {
      // 滚动超过 300px 时浮现
      setVisible(window.scrollY > 300);
    };

    window.addEventListener("scroll", handleScroll, { passive: true });
    return () => window.removeEventListener("scroll", handleScroll);
  }, []);

  const scrollToTop = () => {
    window.scrollTo({
      top: 0,
      behavior: "smooth",
    });
  };

  return (
    <button
      type="button"
      onClick={scrollToTop}
      aria-label="返回顶部"
      title="返回顶部"
      className={cn(
        "border-border bg-card/90 fixed z-20 flex h-10 w-10 cursor-pointer items-center justify-center rounded-full border text-slate-600 shadow-md backdrop-blur transition-all duration-300 hover:border-blue-300 hover:bg-blue-50 hover:text-blue-600 active:scale-90 sm:h-11 sm:w-11 dark:text-slate-300 dark:hover:border-blue-800 dark:hover:bg-blue-950 dark:hover:text-blue-400",
        // 移动端若同时浮起 CompareBar 则自动抬升避让（bottom-36 vs bottom-20）
        hasCompareBar
          ? "bottom-36 right-4 sm:bottom-20 sm:right-6"
          : "bottom-20 right-4 sm:bottom-6 sm:right-6",
        visible
          ? "translate-y-0 scale-100 opacity-100 pointer-events-auto"
          : "translate-y-4 scale-75 opacity-0 pointer-events-none",
      )}
    >
      <ArrowUp className="h-5 w-5" />
    </button>
  );
}
