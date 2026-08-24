"use client";

import { useEffect, useState } from "react";
import { useTheme } from "next-themes";
import { Moon, Sun } from "lucide-react";

import { Button } from "@/components/ui/button";

/** 明暗主题切换按钮（图标随主题切换，挂载前渲染占位避免水合不一致）。 */

export function ThemeToggle() {
  const { resolvedTheme, setTheme } = useTheme();
  const [mounted, setMounted] = useState(false);

  useEffect(() => setMounted(true), []);

  if (!mounted) {
    // 主题仅在客户端可知：挂载前渲染等尺寸占位，保持头部布局稳定
    return (
      <Button variant="ghost" size="icon" aria-label="切换主题" disabled className="h-9 w-9">
        <Sun className="h-4 w-4 opacity-0" />
      </Button>
    );
  }

  const isDark = resolvedTheme === "dark";

  return (
    <Button
      variant="ghost"
      size="icon"
      aria-label={isDark ? "切换到亮色模式" : "切换到暗色模式"}
      title={isDark ? "切换到亮色模式" : "切换到暗色模式"}
      className="h-9 w-9"
      onClick={() => setTheme(isDark ? "light" : "dark")}
    >
      {isDark ? <Sun className="h-4 w-4" /> : <Moon className="h-4 w-4" />}
    </Button>
  );
}
