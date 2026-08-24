"use client";

import { useState } from "react";
import { Bookmark, Check, Copy } from "lucide-react";

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
      <DialogTrigger asChild>
        <Button variant="ghost" size="sm" className="text-muted-foreground gap-1.5 text-xs">
          <Bookmark aria-hidden className="h-3.5 w-3.5" />
          收藏本站
        </Button>
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
