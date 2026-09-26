/**
 * 安全地给指定 YYYY-MM-DD 日期增加指定月数，自动处理大小月/平闰年天数截断。
 * 
 * 例如：
 * - 2026-01-31 + 1 个月 => 2026-02-28（而不是 JavaScript 原生 Date 溢出的 2026-03-03）
 * - 2024-01-31 + 1 个月 => 2024-02-29（闰年）
 * - 2026-03-31 + 1 个月 => 2026-04-30
 */
export function addMonthsClamped(dateStr: string, months: number): string {
  let y: number;
  let m: number;
  let d: number;

  if (!dateStr || !dateStr.includes("-")) {
    const now = new Date();
    y = now.getFullYear();
    m = now.getMonth() + 1;
    d = now.getDate();
  } else {
    const parts = dateStr.slice(0, 10).split("-").map(Number);
    y = parts[0];
    m = parts[1];
    d = parts[2];
    if (isNaN(y) || isNaN(m) || isNaN(d)) {
      const now = new Date();
      y = now.getFullYear();
      m = now.getMonth() + 1;
      d = now.getDate();
    }
  }

  const targetMonthIndex = (m - 1) + months;
  const targetYear = y + Math.floor(targetMonthIndex / 12);
  const targetMonth = ((targetMonthIndex % 12) + 12) % 12 + 1; // 1-12
  // 利用 new Date(year, month, 0).getDate() 获取该月天数（month 为 1-indexed）
  const daysInTargetMonth = new Date(targetYear, targetMonth, 0).getDate();
  const targetDay = Math.min(d, daysInTargetMonth);

  return `${targetYear}-${String(targetMonth).padStart(2, "0")}-${String(targetDay).padStart(2, "0")}`;
}
