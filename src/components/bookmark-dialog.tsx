"use client";

import { useEffect, useState } from "react";
import { Check, Copy, Share2 } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from "@/components/ui/dialog";
import { SITE_URL } from "@/lib/site";

/**
 * 收藏本站引导（1:1 复刻旧站 web/src/components/BookmarkModal.vue）：
 * - 桌面：Ctrl + D（Mac 为 ⌘ + D）快捷键卡片
 * - 移动：⋮ → ★ 加为书签 / 添加到主屏幕 分步指引
 * - 复制失败给出「长按地址栏手动复制」兜底提示（旧站用 toast，本站无 toast 依赖，
 *   改为按钮下方内联，避免为一个提示引入新组件）
 *
 * 平台判断放在 useEffect：userAgent 只存在于浏览器，服务端渲染保持桌面形态，
 * 挂载后再切换，避免水合不一致。
 *
 * 展示域名取自 SITE_URL（SEO 基准域名唯一来源），不再硬编码。
 */

type Platform = "ios" | "android" | "mac" | "other";

/** 展示用域名（去掉协议前缀） */
const DISPLAY_HOST = SITE_URL.replace(/^https?:\/\//, "");

function detectPlatform(ua: string): Platform {
  if (/iPhone|iPad|iPod/i.test(ua)) return "ios";
  if (/Android/i.test(ua)) return "android";
  // Mac 需排除 iOS（iPad 请求桌面站点时 UA 也含 Macintosh）
  if (/Mac/i.test(ua)) return "mac";
  return "other";
}

export function BookmarkDialog() {
  const [copied, setCopied] = useState(false);
  const [failed, setFailed] = useState(false);
  const [platform, setPlatform] = useState<Platform>("other");
  const [canShare, setCanShare] = useState(false);

  useEffect(() => {
    setPlatform(detectPlatform(navigator.userAgent));
    setCanShare(typeof navigator.share === "function");
  }, []);

  const isMobile = platform === "ios" || platform === "android";
  const modKey = platform === "mac" ? "⌘" : "Ctrl";

  const copy = async () => {
    try {
      await navigator.clipboard.writeText(SITE_URL);
      setCopied(true);
      setFailed(false);
      setTimeout(() => setCopied(false), 2500);
    } catch {
      // 剪贴板权限被拒（非 HTTPS / 用户拒绝）：改为可手动复制的兜底提示
      setFailed(true);
    }
  };

  const share = async () => {
    try {
      await navigator.share({ title: "GoVPS - VPS 库存与降价监控", url: SITE_URL });
    } catch {
      /* 用户取消分享：无需处理 */
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

        {isMobile ? (
          /* 移动端：右上角菜单 → 加为书签 / 添加到主屏幕 */
          <ol className="text-muted-foreground flex flex-col gap-1.5 text-sm">
            <li>
              点击右上角菜单 <strong className="text-foreground">「⋮」</strong>；
            </li>
            <li>
              点击顶部 <strong className="text-foreground">「★ 加为书签」</strong> 或{" "}
              <strong className="text-foreground">「添加到主屏幕」</strong>；
            </li>
            <li>保存后即可随时一键访问 GoVPS！</li>
          </ol>
        ) : (
          /* 桌面端：快捷键卡片 */
          <div className="flex flex-col gap-1.5">
            <div className="flex items-center justify-between text-xs font-bold">
              <span>快捷键收藏</span>
              <div className="flex items-center gap-1.5">
                <kbd className="bg-muted rounded-md border px-2 py-1 font-mono text-xs font-bold shadow-sm">
                  {modKey}
                </kbd>
                <span className="text-muted-foreground">+</span>
                <kbd className="bg-muted rounded-md border px-2 py-1 font-mono text-xs font-bold shadow-sm">
                  D
                </kbd>
              </div>
            </div>
            <p className="text-muted-foreground text-xs leading-relaxed">
              在浏览器中按下{" "}
              <strong className="text-foreground">
                {modKey} + D
              </strong>{" "}
              即可将本站添加至书签栏。
            </p>
          </div>
        )}

        <div className="flex flex-col gap-1.5">
          <div className="flex items-center gap-2">
            <Button onClick={copy} size="sm" variant="outline">
              {copied ? (
                <>
                  <Check aria-hidden className="h-4 w-4 text-emerald-600" />
                  已复制 ✓
                </>
              ) : (
                <>
                  <Copy aria-hidden className="h-4 w-4" />
                  复制网址
                </>
              )}
            </Button>
            {canShare && (
              <Button onClick={share} size="sm" variant="outline">
                <Share2 aria-hidden className="h-4 w-4" />
                分享本站
              </Button>
            )}
            <span className="text-muted-foreground truncate font-mono text-xs">
              {DISPLAY_HOST}
            </span>
          </div>
          {failed && (
            <p className="text-xs text-amber-600 dark:text-amber-500">
              复制失败，请长按地址栏手动复制。
            </p>
          )}
        </div>
      </DialogContent>
    </Dialog>
  );
}
