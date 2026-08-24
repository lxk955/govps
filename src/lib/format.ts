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

/** 原币价格展示（不换算币种；跨币种换算属 P5 汇率机制） */
export function formatPrice(price: number, currency: string): string {
  const formatted = price.toLocaleString("zh-CN", {
    minimumFractionDigits: 2,
    maximumFractionDigits: 2,
  });
  return `${currencySymbol(currency)}${formatted}`;
}

export function formatCycle(cycle: string): string {
  const labels: Record<string, string> = {
    monthly: "/月",
    quarterly: "/季",
    "semi-annually": "/半年",
    semi_annually: "/半年",
    annually: "/年",
    biennially: "/两年",
    triennially: "/三年",
  };
  return labels[cycle] ?? `/${cycle}`;
}

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
