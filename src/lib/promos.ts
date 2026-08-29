/**
 * 商家优惠码（1:1 移植自旧站 web/src/promos.ts）。
 *
 * 仅维护经官网实测可用的折扣码，杜绝失效/占位假码——当前各大促节点均无有效码，
 * 字典为空时卡片与列表行不渲染优惠码胶囊（与旧站行为一致）。
 */
export interface PromoInfo {
  code: string;
  discount: string;
  tip?: string;
}

export const MERCHANT_PROMOS: Record<string, PromoInfo> = {
  // 注：搬瓦工历史 6.77% 常驻码已全线下线，DMIT/V.PS 仅在大促期间限时发放。
};

export function getMerchantPromo(slug: string): PromoInfo | null {
  return MERCHANT_PROMOS[slug] || null;
}

export async function copyPromoCode(code: string): Promise<boolean> {
  try {
    await navigator.clipboard.writeText(code);
    return true;
  } catch {
    // 剪贴板权限被拒（非 HTTPS / 用户拒绝）时静默失败，用户仍可手动记录
    return false;
  }
}
