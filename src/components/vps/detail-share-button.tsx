"use client";

import { useState } from "react";
import { Check, Share2 } from "lucide-react";

import type { ProductDetail } from "@/lib/api/endpoints";
import { formatPrice } from "@/lib/format";
import { productHref } from "@/lib/slug";
import { SITE_URL } from "@/lib/site";
import { Button } from "@/components/ui/button";

export function DetailShareButton({ product: p }: { product: ProductDetail }) {
  const [copied, setCopied] = useState(false);

  const handleShare = async () => {
    const lines = p.line_tags?.slice(0, 2).join(" / ") || "";
    const specs = [
      p.cpu_cores != null ? `${p.cpu_cores}核` : null,
      p.ram_gb != null ? `${p.ram_gb}G` : null,
      p.disk_gb != null ? `${p.disk_gb}G` : null,
      p.bandwidth_gb ? (p.bandwidth_gb < 0 ? "无限流量" : `${p.bandwidth_gb}G流量`) : null,
    ]
      .filter(Boolean)
      .join("·");

    const text = [
      `📡 【${p.merchant.name}】${p.name}`,
      `💰 ${formatPrice(p.price, p.currency)} · ${p.in_stock ? "🟢 当前有货" : "🔴 暂时缺货"}`,
      specs ? `⚙️ 配置：${specs}` : null,
      p.location || lines ? `🌐 线路机房：${[p.location, lines].filter(Boolean).join(" · ")}` : null,
      `🔗 实时监控详情：${SITE_URL}${productHref(p.id, p.name)}`,
    ]
      .filter(Boolean)
      .join("\n");

    try {
      if (typeof navigator !== "undefined" && navigator.clipboard) {
        await navigator.clipboard.writeText(text);
        setCopied(true);
        setTimeout(() => setCopied(false), 2500);
      }
    } catch {
      // 剪贴板异常兜底
    }
  };

  return (
    <Button
      type="button"
      variant="outline"
      onClick={handleShare}
      className="h-9 gap-1.5 rounded-xl border-slate-200 bg-white text-xs font-semibold text-slate-700 hover:bg-slate-50 dark:border-slate-800 dark:bg-slate-900 dark:text-slate-300 dark:hover:bg-slate-800"
      title="一键复制种草文案与链接，方便发送至群聊或论坛"
    >
      {copied ? (
        <>
          <Check className="h-3.5 w-3.5 text-emerald-600 dark:text-emerald-400" />
          <span className="text-emerald-600 dark:text-emerald-400">已复制分享卡片</span>
        </>
      ) : (
        <>
          <Share2 className="h-3.5 w-3.5 text-blue-500" />
          <span>一键分享</span>
        </>
      )}
    </Button>
  );
}
