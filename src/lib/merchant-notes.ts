/**
 * 商家简介与侧栏排序（1:1 移植自旧站 web/src/components/FilterBar.vue）。
 *
 * 简介在旧站用作服务商按钮的 title（悬停 tooltip），内容为对各商家定位的
 * 人工总结，非爬虫数据，因此固化在此而非取自 API。
 *
 * 排序：旧站侧栏按固定权重排列（bandwagon 起、66yun 止），权重相同时按套餐数
 * 降序。权重体现的是「商家主推次序」而非数据量，故不按 count 直接排。
 */

export const MERCHANT_NOTES: Record<string, string> = {
  bandwagon:
    "搬瓦工：长期口碑标杆，核心优势是三网 CN2 GIA/CTGNet 与多机房自由迁移，稳定性极高，价格偏高。",
  dmit: "DMIT：Pro/EB/Lite 分层明确，美西/日本/香港精品专线，三网各自直连优化，高防与高品质首选。",
  vps: "V.PS (xTom)：日本东京/大阪、美西圣何塞三网 CN2 GIA / 9929 / CMIN2 精品优化，配置高性价比突出。",
  zgocloud: "ZgoCloud：突出 IP 纯净度、流媒体解锁能力与双网优化，配备 AMD Ryzen 7950X 顶级性能核心。",
  dedione: "DediOne：提供中国直连、双网与 CN2 GIA 优化线路，特惠年付低价神机，入门成本低。",
  vmiss:
    "VMiss：主打高性价比优化线路（洛杉矶 CN2 GIA/9929/CMIN2、香港与日本 BGP），全系 CAD 计费，价格优势明显。",
  "66yun":
    "66云：主打原生 IP、流媒体解锁及双 ISP 住宅属性，覆盖美西/英国 9929、香港 CMI 与日本软银。",
  gomami:
    "GoMami：主打亚太高端精品专线与极致单核性能，覆盖香港/日本/新加坡/洛杉矶，三网各自直连优化（CN2 GIA/9929/CMIN2），配备 AMD 9575F 顶级硬件。",
  evoxt:
    "Evoxt：马来西亚知名高频云主机商，主打全球多机房弹性部署（美/英/加/德/波/荷/日/马/澳）与高频 CPU（最高 6.0 GHz），提供优质三网优化线路（CTG GIA/9929/CMI），支持周备份与微信/支付宝付款。",
  vmrack:
    "VMRack：主打洛杉矶自建机房（LAX-DC1/DC2），提供三网精品优化（CN2 GIA/9929/CMIN2）、三网优化（163/10099/CMI）与原生 BGP 线路，包含限量与不限流量 VPS 及独立裸金属服务器。",
  greencloud:
    "GreenCloud（绿云）：只收录官网 CN Premium 专线。东京为 CN2 GIA / 9929 / CMIN2，新加坡为 CN2 GIA / 9929 / CMI，廉价 KVM 不收录。",
};

export const MERCHANT_ORDER: Record<string, number> = {
  bandwagon: 1,
  dmit: 2,
  vps: 3,
  zgocloud: 4,
  dedione: 5,
  vmiss: 6,
  "66yun": 7,
  gomami: 8,
  evoxt: 9,
  vmrack: 10,
  greencloud: 11,
};

/** 服务商按钮的悬停提示：优先用商家简介，缺失时回退通用文案（与旧站一致）。 */
export function merchantTitle(slug: string, name: string): string {
  return MERCHANT_NOTES[slug] ?? `${name} VPS 套餐与库存`;
}

/** 侧栏服务商排序：固定权重优先，权重相同按套餐数降序（旧站同款规则）。 */
export function sortMerchants<T extends { slug: string; count?: number }>(list: T[]): T[] {
  return [...list].sort((a, b) => {
    const wa = MERCHANT_ORDER[a.slug] ?? 99;
    const wb = MERCHANT_ORDER[b.slug] ?? 99;
    if (wa !== wb) return wa - wb;
    return (b.count ?? 0) - (a.count ?? 0);
  });
}
