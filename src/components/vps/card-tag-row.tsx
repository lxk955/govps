"use client";

import { useState } from "react";

import type { ProductListItem } from "@/lib/api/endpoints";
import { copyPromoCode, getMerchantPromo } from "@/lib/promos";
import { cn } from "@/lib/utils";

/**
 * 卡片/列表行的标签槽（1:1 复刻旧站第 3 行：优惠码 → 最新补货 → 史低/降价 → 热门）。
 *
 * 做成客户端件的原因：优惠码胶囊点击后需写剪贴板并切换为「已复制✓」。
 * 当前 MERCHANT_PROMOS 为空字典，该胶囊不会渲染——与旧站行为保持一致。
 */
export function CardTagRow({
  product,
  variant = "card",
}: {
  product: ProductListItem;
  /** card 显示「🔥 热门」，row 显示「🔥 热门关注」（沿用旧站差异） */
  variant?: "card" | "row";
}) {
  const p = product;
  const [copied, setCopied] = useState(false);
  const promo = getMerchantPromo(p.merchant?.slug ?? "");

  const dropInfo =
    p.price_dropped && p.prev_price != null
      ? { pct: p.prev_price > 0 ? Math.round(((p.prev_price - p.price) / p.prev_price) * 100) : 0 }
      : null;
  const hot = (p.popularity_score ?? 0) >= 30;
  const hotTip = p.recommend_reasons.length
    ? `热度关注：${p.recommend_reasons.join(" · ")}`
    : "近期用户关注与点击较高";

  const copy = async () => {
    if (!promo) return;
    await copyPromoCode(promo.code);
    setCopied(true);
    setTimeout(() => setCopied(false), 2500);
  };

  return (
    <div
      className={cn(
        "flex items-center gap-1.5 overflow-hidden text-[10px]",
        // 卡片：固定 22px 专属槽；行形态：与商家名同排平铺，高度随内容
        variant === "card" ? "h-[22px]" : "min-h-[18px] flex-wrap",
      )}
    >
      {promo && (
        <button
          type="button"
          onClick={() => void copy()}
          title={`优惠码: ${promo.code} (${promo.discount}) · 点击一键复制`}
          className="inline-flex shrink-0 cursor-pointer items-center gap-0.5 rounded border border-amber-200/80 bg-amber-50 px-1.5 py-0.5 font-medium text-amber-800 transition-all hover:border-amber-300 hover:bg-amber-100 dark:border-amber-800 dark:bg-amber-950/50 dark:text-amber-300"
        >
          {copied ? (
            <span className="font-bold text-emerald-700 dark:text-emerald-400">已复制✓</span>
          ) : (
            <span>🎁 {promo.discount}</span>
          )}
        </button>
      )}

      {p.is_recent_restock && p.in_stock && (
        <span
          title="近48小时内最新补货"
          className="inline-flex shrink-0 animate-pulse items-center gap-0.5 rounded border border-emerald-200/70 bg-emerald-50 px-1.5 py-0.5 font-bold text-emerald-700 dark:border-emerald-800 dark:bg-emerald-950/60 dark:text-emerald-300"
        >
          ⚡ 最新补货
        </span>
      )}

      {p.is_lowest_price && dropInfo ? (
        <span
          title={`原价 ${p.prev_price}`}
          className="shrink-0 rounded border border-rose-200 bg-rose-50 px-1.5 py-0.5 font-bold text-rose-600 dark:border-rose-800 dark:bg-rose-950/60 dark:text-rose-300"
        >
          🏷️ 史低-{dropInfo.pct}%
        </span>
      ) : dropInfo ? (
        <span
          title={`原价 ${p.prev_price}`}
          className="shrink-0 rounded border border-orange-200 bg-orange-50 px-1.5 py-0.5 font-bold text-orange-600 dark:border-orange-800 dark:bg-orange-950/60 dark:text-orange-300"
        >
          📉 -{dropInfo.pct}%
        </span>
      ) : null}

      {hot && (
        <span
          title={hotTip}
          className="shrink-0 cursor-help rounded border border-rose-200/80 bg-rose-50 px-1.5 py-0.5 font-bold text-rose-600 dark:border-rose-800 dark:bg-rose-950/60 dark:text-rose-300"
        >
          🔥 热门{variant === "row" ? "关注" : ""}
        </span>
      )}
    </div>
  );
}
