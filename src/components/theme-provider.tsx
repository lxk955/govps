"use client";

import { ThemeProvider as NextThemesProvider } from "next-themes";

/** next-themes 封装：class 策略（globals.css 的 .dark 变体），跟随系统 + 手动切换。 */

export function ThemeProvider({ children }: { children: React.ReactNode }) {
  return (
    <NextThemesProvider attribute="class" defaultTheme="system" enableSystem disableTransitionOnChange>
      {children}
    </NextThemesProvider>
  );
}
