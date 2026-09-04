"use client";

import { useCurrency } from "@/components/currency-provider";

/** 跟随全站币种开关的价格文本；换算过默认附带原币。 */
export function PriceText({
  price,
  currency,
  className,
  showOriginal = true,
}: {
  price: number;
  currency: string;
  className?: string;
  showOriginal?: boolean;
}) {
  const { convert } = useCurrency();
  const info = convert(price, currency);
  return (
    <span className={className}>
      {info.displayPrice}
      {showOriginal && info.isConverted && (
        <span className="text-slate-400 dark:text-slate-500 font-normal"> 原 {info.originalPrice}</span>
      )}
    </span>
  );
}
