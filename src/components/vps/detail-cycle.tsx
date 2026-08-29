"use client";

import { createContext, useContext, useState } from "react";

import { Button } from "@/components/ui/button";
import { WatchButton } from "@/components/vps/watch-button";
import type { ProductDetail } from "@/lib/api/endpoints";
import { cycleLabel, formatPrice } from "@/lib/format";

/**
 * 详情页付款周期共享状态（1:1 复刻旧站 ProductDetail.vue）。
 *
 * 旧站里「头部购买按钮」与「概览价格卡」同用一个 selectedIndex，
 * 二者在 DOM 上并不相邻，故用 Context 跨位置共享；
 * Provider 是客户端件，但 children 仍可由服务端渲染后传入。
 */

interface CycleCtx {
  options: { billing_cycle: string; price: number; currency: string; purchase_url?: string }[];
  idx: number;
  setIdx: (i: number) => void;
}

const DetailCycleCtx = createContext<CycleCtx | null>(null);

export function DetailCycleProvider({
  product,
  children,
}: {
  product: ProductDetail;
  children: React.ReactNode;
}) {
  const [idx, setIdx] = useState(0);
  const options =
    product.price_options && product.price_options.length > 0
      ? product.price_options
      : [
          {
            billing_cycle: product.billing_cycle,
            price: product.price,
            currency: product.currency,
            purchase_url: product.purchase_url,
          },
        ];
  return (
    <DetailCycleCtx.Provider value={{ options, idx, setIdx }}>{children}</DetailCycleCtx.Provider>
  );
}

function useCycle(): CycleCtx {
  const ctx = useContext(DetailCycleCtx);
  if (!ctx) throw new Error("明细周期组件必须位于 DetailCycleProvider 内");
  return ctx;
}

/** 头部购买区：购买链接随所选周期变化；缺货时弱化按钮并提示关注 */
export function DetailBuyButton({ product }: { product: ProductDetail }) {
  const { options, idx } = useCycle();
  const cur = options[idx] ?? options[0];

  return (
    <div className="flex flex-col items-end gap-2">
      <div className="flex items-center gap-3">
        <WatchButton productId={product.id} />
        <Button
          asChild
          className={
            product.in_stock
              ? "hover:shadow h-auto rounded-xl bg-blue-600 px-6 py-2.5 font-bold text-white shadow-sm hover:bg-blue-700"
              : "hover:bg-slate-50 dark:hover:bg-slate-800 h-auto rounded-xl border px-6 py-2.5 font-bold"
          }
        >
          <a
            href={`/go/${product.id}?src=detail&cycle=${encodeURIComponent(cur.billing_cycle)}`}
            target="_blank"
            rel="nofollow sponsored noopener"
          >
            前往官网购买
          </a>
        </Button>
      </div>
      {!product.in_stock && (
        <p className="text-xs font-medium text-rose-500 dark:text-rose-400">
          当前缺货，点击「关注」后到货第一时间邮件提醒你
        </p>
      )}
    </div>
  );
}

/** 概览卡之一：当前在售价格 + 付款周期切换（价格与周期均取自共享 Context） */
export function DetailPriceCard() {
  const { options, idx, setIdx } = useCycle();
  const cur = options[idx] ?? options[0];

  return (
    <div className="border-border bg-card flex flex-col justify-between rounded-2xl border p-5 shadow-sm">
      <div>
        <div className="text-xs font-medium text-slate-400 dark:text-slate-500">当前在售价格</div>
        <div className="text-slate-900 mt-1 text-2xl font-black dark:text-slate-100">
          {formatPrice(cur.price, cur.currency)}
          <span className="text-xs font-normal text-slate-400 dark:text-slate-500">
            {" "}
            / {cycleLabel(cur.billing_cycle)}
          </span>
        </div>
      </div>
      {options.length > 1 && (
        <div className="mt-3">
          <select
            value={idx}
            onChange={(e) => setIdx(Number(e.target.value))}
            aria-label="付款周期"
            className="border-border bg-muted text-foreground w-full cursor-pointer rounded-xl border px-2.5 py-1.5 text-xs font-bold transition-colors focus:border-blue-500 focus:bg-white focus:outline-none dark:focus:bg-slate-900"
          >
            {options.map((opt, i) => (
              <option key={`${opt.billing_cycle}-${opt.price}`} value={i}>
                {cycleLabel(opt.billing_cycle)}付 · {formatPrice(opt.price, opt.currency)}
              </option>
            ))}
          </select>
        </div>
      )}
    </div>
  );
}
