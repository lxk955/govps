/** 展示格式化工具（纯函数，服务端/客户端通用）。 */

const CURRENCY_SYMBOLS: Record<string, string> = {
  USD: "$",
  EUR: "€",
  CNY: "¥",
  CAD: "C$",
  GBP: "£",
  JPY: "JP¥",
  HKD: "HK$",
};

export function currencySymbol(code: string): string {
  return CURRENCY_SYMBOLS[code] ?? `${code} `;
}

/** 原币价格展示（不换算币种；跨币种换算属 P5 汇率机制）。
 *  1:1 对齐旧站 fmtPrice：整数不带小数、非整数补两位、大额加千分位
 *  （$49 / $49.90 / $1,699）。 */
export function formatPrice(price: number, currency: string): string {
  const formatted = price.toLocaleString("en-US", {
    minimumFractionDigits: Number.isInteger(price) ? 0 : 2,
    maximumFractionDigits: 2,
  });
  return `${currencySymbol(currency)}${formatted}`;
}

/** 周期中文简称（旧站 CYCLE_CN：月/季/半年/年/两年/三年；不含斜杠） */
export function cycleLabel(cycle: string): string {
  const labels: Record<string, string> = {
    monthly: "月",
    quarterly: "季",
    "semi-annually": "半年",
    semi_annually: "半年",
    annually: "年",
    biennially: "两年",
    triennially: "三年",
  };
  return labels[cycle] ?? cycle;
}

/** 折算月价（旧站 currentMonthlyEquiv）：按所选周期摊到每月，月付返回 null */
export function monthlyEquivalent(price: number, cycle: string): string | null {
  const divisors: Record<string, number> = {
    quarterly: 3,
    "semi-annually": 6,
    semi_annually: 6,
    annually: 12,
    biennially: 24,
    triennially: 36,
  };
  const d = divisors[cycle];
  return d ? (price / d).toFixed(2) : null;
}

// 说明：曾存在 formatCycle()（返回带斜杠的「/月」），与 cycleLabel 是同一张
// 映射表写两遍。已统一为 cycleLabel，需要斜杠前缀时在调用处拼接即可
// （如 /{cycleLabel(cycle)}），避免改映射时漏改一处。

/** 相对时间（数据新鲜度提示，AGENTS.md Data Freshness） */
export function timeAgo(iso: string | null | undefined): string {
  if (!iso) return "未知";
  const then = new Date(iso).getTime();
  if (Number.isNaN(then)) return "未知";
  const seconds = Math.max(0, Math.floor((Date.now() - then) / 1000));
  if (seconds < 60) return "刚刚";
  const minutes = Math.floor(seconds / 60);
  if (minutes < 60) return `${minutes} 分钟前`;
  const hours = Math.floor(minutes / 60);
  if (hours < 24) return `${hours} 小时前`;
  const days = Math.floor(hours / 24);
  if (days < 30) return `${days} 天前`;
  return `${Math.floor(days / 30)} 个月前`;
}
