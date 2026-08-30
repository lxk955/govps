/**
 * 商家机房测试 IP。
 *
 * 用途有二：
 * 1) IP 检测页的「快捷测试」预设；
 * 2) 详情页「检测该机房 IP 纯净度」入口——用机房测试 IP 而非购买页域名，
 *    因为购买域名通常是商家官网，并不代表机房出口线路。
 *
 * 数据纪律（宁缺毋错）：每条的归属都必须与 /api/ip/check 的实测结果一致，
 * 不符的一律移除，不留「大致对」的条目——错误的测试 IP 比没有更糟，用户会
 * 据此判断机房线路质量。2026-08-30 逐条实测核对，移除 3 条归属已变更的：
 * - 瓦工 日本 GIA（标注东京，实测美国堪萨斯城）
 * - V.PS 圣何塞（标注圣何塞，实测美国阿什本）
 * - 66云 英国 9929（标注伦敦，实测荷兰）
 *
 * 商家更换 IP 段后本表会再次失真，新增/修改条目时请重新实测。
 */

export interface MerchantTestIp {
  label: string;
  ip: string;
  slug: string;
  location: string;
}

export const MERCHANT_TEST_IP_LIST: MerchantTestIp[] = [
  { label: "瓦工 DC6 GIA", ip: "162.244.241.102", slug: "bandwagon", location: "洛杉矶" },
  { label: "瓦工 香港 GIA", ip: "93.179.124.1", slug: "bandwagon", location: "香港" },
  { label: "DMIT 洛杉矶", ip: "154.17.12.22", slug: "dmit", location: "洛杉矶" },
  { label: "DMIT 香港", ip: "103.117.100.20", slug: "dmit", location: "香港" },
  { label: "ZgoCloud 洛杉矶", ip: "154.29.158.1", slug: "zgocloud", location: "洛杉矶" },
  { label: "66云 香港 CMI", ip: "154.213.16.1", slug: "66yun", location: "香港" },
  // 非商家条目：作为「你的网络到公网」的基准对照——先看 1.1.1.1 再看商家 IP，
  // 可区分问题出在本地网络还是机房出口。
  { label: "Cloudflare DNS", ip: "1.1.1.1", slug: "", location: "" },
];

/**
 * 按商家 + 机房精确匹配，没有则返回 null。
 *
 * 刻意不做「同商家任意机房」回退：那会让洛杉矶的测试 IP 顶替东京机房，
 * 用户以为在测目标机房，实际测的是另一个——宁可不展示入口，也不给出张冠李戴
 * 的结果。调用方在返回 null 时应隐藏入口，不要用购买页域名兜底（官网域名不
 * 代表机房出口线路）。
 */
export function testIpFor(slug: string, location: string | null): string | null {
  const exact = MERCHANT_TEST_IP_LIST.find((x) => x.slug === slug && x.location === location);
  return exact ? exact.ip : null;
}
