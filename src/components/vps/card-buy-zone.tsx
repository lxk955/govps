"use client";

import { useState } from "react";
import { usePathname, useRouter } from "next/navigation";

import { useAuth } from "@/components/auth-provider";
import { useCurrency } from "@/components/currency-provider";
import { Button } from "@/components/ui/button";
import { watchProduct, type ProductListItem } from "@/lib/api/endpoints";
import { cycleLabel, currencySymbol, monthlyEquivalent } from "@/lib/format";

/**
 * 卡片底部价格与购买区（1:1 复刻旧站 ProductCard.vue 第 4 段）。
 *
 * 做成客户端件的原因：付款周期下拉要实时切换价格与购买链接。
 * 卡片其余部分（标题/规格/线路）保持服务端渲染，减少不必要的客户端 JS。
 */
export function CardBuyZone({ product }: { product: ProductListItem }) {
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
  const cycleCn = cycleLabel(current.billing_cycle);
  const monthly = monthlyEquivalent(current.price, current.billing_cycle);
  const purchaseUrl = `/go/${p.id}?src=card&cycle=${encodeURIComponent(current.billing_cycle)}`;

  /** 缺货时的「到货提醒」：幂等订阅关注（已关注不会反向取消），未登录先去登录 */
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

  const { convert } = useCurrency();
  const priceInfo = convert(current.price, current.currency);

  return (
    <div className="border-border mt-auto flex items-end justify-between gap-2 border-t pt-3">
      <div className="min-w-0 flex-1">
        <div className="flex flex-col">
          <div className="flex items-baseline gap-1">
            <span className="text-foreground text-xl leading-none font-bold">
              {priceInfo.displayPrice}
            </span>
            <span className="text-xs text-slate-400 dark:text-slate-500">/ {cycleCn}</span>
          </div>
          {priceInfo.isConverted && (
            <span
              className="text-[10.5px] font-normal text-slate-400 dark:text-slate-500 mt-0.5 leading-tight"
              title={priceInfo.rateNotice}
            >
              原 {priceInfo.originalPrice}
            </span>
          )}
        </div>

        {/* 周期下拉 / 折算月价（保持高度一致，避免卡片错位） */}
        <div className="mt-1.5 flex h-6 items-center">
          {options.length > 1 ? (
            <select
              value={idx}
              onChange={(e) => setIdx(Number(e.target.value))}
              aria-label={`${p.name} 付款周期`}
              className="border-border bg-muted text-foreground cursor-pointer rounded-lg border py-0.5 pr-2 pl-1.5 text-xs font-semibold transition-colors focus:border-blue-500 focus:bg-white focus:outline-none dark:focus:bg-slate-900"
            >
              {options.map((opt, i) => {
                const optInfo = convert(opt.price, opt.currency);
                return (
                  <option key={`${opt.billing_cycle}-${opt.price}`} value={i}>
                    {cycleLabel(opt.billing_cycle)}付 · {optInfo.displayPrice}
                    {optInfo.isConverted ? ` (原 ${optInfo.originalPrice})` : ""}
                  </option>
                );
              })}
            </select>
          ) : monthly ? (
            <span className="text-[11px] text-slate-400 dark:text-slate-500">
              ≈ {sym}
              {monthly}/月
            </span>
          ) : (
            <span className="text-[11px] text-slate-300 dark:text-slate-600">—</span>
          )}
        </div>
      </div>

      <div className="flex shrink-0 flex-col items-end gap-1.5">
        <span
          className={`rounded-full px-2 py-0.5 text-xs font-medium ${
            p.in_stock
              ? "bg-emerald-100 text-emerald-700 dark:bg-emerald-950/60 dark:text-emerald-300"
              : "bg-rose-100 text-rose-600 dark:bg-rose-950/60 dark:text-rose-300"
          }`}
        >
          {p.in_stock ? "有货" : "缺货"}
        </span>
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
            {notifying ? "已开启提醒 ✓" : "到货提醒"}
          </Button>
        )}
      </div>
    </div>
  );
}
