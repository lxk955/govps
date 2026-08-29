"use client";

import { useState } from "react";
import { Check, Copy } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";

/** 收藏本站引导（G1 轻量版）：快捷键提示 + 一键复制链接。 */

export function BookmarkDialog() {
  const [copied, setCopied] = useState(false);

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(window.location.origin);
      setCopied(true);
      setTimeout(() => setCopied(false), 2000);
    } catch {
      /* 剪贴板权限被拒时静默失败，用户仍可手动复制地址栏 */
    }
  };

  return (
    <Dialog>
      {/* 1:1 复刻旧站头部/页脚的 ⭐ 收藏胶囊（hover 转琥珀色） */}
      <DialogTrigger asChild>
        <button
          type="button"
          title="收藏 GoVPS 到浏览器书签"
          className="group flex cursor-pointer items-center gap-1.5 rounded-xl border border-slate-200/90 bg-slate-50/80 px-2.5 py-1 text-xs font-bold text-slate-700 transition-all hover:border-amber-300 hover:bg-amber-50/70 hover:text-amber-800 dark:border-slate-700 dark:bg-slate-800/60 dark:text-slate-300 dark:hover:border-amber-500/60 dark:hover:bg-amber-950/40 dark:hover:text-amber-300"
        >
          <span aria-hidden className="text-amber-500 transition-transform group-hover:scale-110">
            ⭐
          </span>
          <span className="hidden sm:inline">收藏本站</span>
        </button>
      </DialogTrigger>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>收藏 GoVPS</DialogTitle>
          <DialogDescription>
            VPS 库存与降价信息随时在变，把 GoVPS 加入书签，第一时间看到降价与补货。
          </DialogDescription>
        </DialogHeader>
        <ul className="text-muted-foreground flex flex-col gap-1.5 text-sm">
          <li className="flex items-center gap-2">
            <kbd className="bg-muted rounded border px-1.5 py-0.5 font-mono text-xs">Ctrl</kbd>
            <span>+</span>
            <kbd className="bg-muted rounded border px-1.5 py-0.5 font-mono text-xs">D</kbd>
            <span>（Mac 为 ⌘ + D）快速加入书签</span>
          </li>
        </ul>
        <div className="flex items-center gap-2">
          <Button onClick={copy} size="sm" variant="outline">
            {copied ? (
              <>
                <Check aria-hidden className="h-4 w-4 text-emerald-600" />
                已复制
              </>
            ) : (
              <>
                <Copy aria-hidden className="h-4 w-4" />
                复制网址
              </>
            )}
          </Button>
          <span className="text-muted-foreground truncate font-mono text-xs">
            govps.xyz
          </span>
        </div>
      </DialogContent>
    </Dialog>
  );
}
