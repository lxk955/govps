"use client";

import { cn } from "@/lib/utils";

export function ReloadButton({ className, children }: { className?: string; children?: React.ReactNode }) {
  return (
    <button type="button" onClick={() => window.location.reload()} className={cn(className)}>
      {children ?? "重新加载"}
    </button>
  );
}
