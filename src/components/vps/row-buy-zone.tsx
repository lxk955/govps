"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { Button } from "@/components/ui/button";
import { WatchButton } from "@/components/vps/watch-button";
import { watchProduct, type ProductListItem, type WatchPrefs } from "@/lib/api/endpoints";
import { cycleLabel, currencySymbol, formatPrice, monthlyEquivalent } from "@/lib/format";

/**
 * 行形态的价格 / 状态 / 操作三段（1:1 复刻旧站 ProductRow.vue 右半部分）。
 *
 * 三段合一的原因：购买链接随所选付款周期变化，状态与操作需与价格共享同一状态。
 * 桌面端外层 `sm:contents` 让三段直接参与父级 flex 行布局（旧站同款写法）。
 */
export function RowBuyZone({
  product,
  unwatchPrefs,
  onUnwatched,
  watchHydrate = false,
}: {
  product: ProductListItem;
  /** 转发给 WatchButton：取关时随撤销事件带上原偏好（关注页列表视图用） */
  unwatchPrefs?: WatchPrefs;
  /** 转发给 WatchButton：取关后回调（关注页用于刷新列表） */
  onUnwatched?: () => void;
  /**
   * 挂载后查询真实关注状态。产品页列表不逐个查询（条目多且多为未关注）；
   * 关注页必须开启——该页条目全部已关注，不查询会错误显示成未关注的空心形。
   */
  watchHydrate?: boolean;
}) {
  const p = product;
  const { user } = useAuth();
  const router = useRouter();
  const pathname = usePathname();
  const [idx, setIdx] = useState(0);
  const [notifying, setNotifying] = useState(false);
  const [busy, setBusy] = useState(false);

  const options =
    p.price_options && p.price_options.length > 0
      ? p.price_options
      : [
          {
            billing_cycle: p.billing_cycle,
            price: p.price,
            currency: p.currency,
            purchase_url: p.purchase_url,
          },
        ];
  const current = options[idx] ?? options[0];
  const sym = currencySymbol(current.currency);
  const monthly = monthlyEquivalent(current.price, current.billing_cycle);
  const purchaseUrl = `/go/${p.id}?src=row&cycle=${encodeURIComponent(current.billing_cycle)}`;

  const restockNotify = async () => {
    if (user === null) {
      router.push(`/login?next=${encodeURIComponent(pathname || "/")}`);
      return;
    }
    setBusy(true);
    try {
      await watchProduct(p.id, {
        notify_restock: true,
        notify_price_drop: true,
        min_drop_percent: 0,
      });
      setNotifying(true);
    } catch {
      /* 失败保持原状态；401 已由统一处理登出 */
    } finally {
      setBusy(false);
    }
  };

  return (
    <div className="flex items-center justify-between gap-3 sm:contents">
      {/* 价格：桌面固定 125px 右对齐 */}
      <div className="min-w-0 text-left sm:w-[125px] sm:shrink-0 sm:text-right">
        <div className="flex items-baseline justify-start gap-1 sm:justify-end">
          <span className="text-foreground text-base font-bold">
            {formatPrice(current.price, current.currency)}
          </span>
          {options.length <= 1 && (
            <span className="text-xs text-slate-400 dark:text-slate-500">
              / {cycleLabel(current.billing_cycle)}
            </span>
          )}
        </div>

        {options.length > 1 && (
          <div className="mt-0.5 flex justify-start sm:justify-end">
            <select
              value={idx}
              onChange={(e) => setIdx(Number(e.target.value))}
              aria-label={`${p.name} 付款周期`}
              className="border-border bg-muted text-foreground cursor-pointer rounded border py-0.5 pr-1 pl-1 text-[11px] font-semibold transition-colors focus:border-blue-500 focus:bg-white focus:outline-none dark:focus:bg-slate-900"
            >
              {options.map((opt, i) => (
                <option key={`${opt.billing_cycle}-${opt.price}`} value={i}>
                  {cycleLabel(opt.billing_cycle)}付 · {formatPrice(opt.price, opt.currency)}
                </option>
              ))}
            </select>
          </div>
        )}

        {monthly && (
          <div className="text-[11px] text-slate-400 dark:text-slate-500">
            ≈ {sym}
            {monthly}/月
          </div>
        )}
      </div>

      {/* 状态：固定 64px，居中（xl+ 显示；更窄视口由左侧摘要行/操作区承担） */}
      <span
        className={`hidden w-16 shrink-0 rounded-full px-1.5 py-0.5 text-center text-xs font-medium xl:inline-block ${
          p.in_stock
            ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
            : "bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-300"
        }`}
      >
        {p.in_stock ? "有货" : "缺货"}
      </span>

      {/*
        操作：移动端贴右侧，桌面端固定 176px 列。
        宽度须容纳最宽组合：关注胶囊 76px + 间距 8px + 「到货提醒」约 84px
        （缺货时文案比「购买」长不少）。原 144px 是按 36px 图标定的，关注按钮
        换成旧站的 76px 胶囊后装不下，多出约 24px 会向左溢出压住状态标签。
      */}
      <div className="flex shrink-0 items-center justify-end gap-2 sm:w-[176px]">
        <WatchButton
          productId={p.id}
          hydrate={watchHydrate}
          unwatchPrefs={unwatchPrefs}
          onUnwatched={onUnwatched}
        />
        {p.in_stock ? (
          <Button
            asChild
            className="h-auto rounded-lg bg-blue-600 px-3.5 py-1.5 text-sm font-medium text-white hover:bg-blue-700"
          >
            <a href={purchaseUrl} target="_blank" rel="nofollow sponsored noopener">
              购买
            </a>
          </Button>
        ) : (
          <Button
            type="button"
            variant="outline"
            disabled={busy || notifying}
            onClick={() => void restockNotify()}
            title="关注此套餐，补货后第一时间邮件提醒你"
            className="hover:border-rose-300 hover:text-rose-500 h-auto rounded-lg px-3.5 py-1.5 text-sm font-medium"
          >
            {notifying ? "已开启 ✓" : "到货提醒"}
          </Button>
        )}
      </div>
    </div>
  );
}
