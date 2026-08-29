/**
 * 商家机房测试 IP（1:1 移植自旧站 web/src/merchants.ts）。
 *
 * 用途有二：
 * 1) IP 检测页的「快捷测试」预设；
 * 2) 详情页「检测该机房 IP 纯净度」入口——旧站用机房测试 IP 而非购买页域名，
 *    因为购买域名通常是商家官网，并不代表机房出口线路。
 */

export interface MerchantTestIp {
  label: string;
  ip: string;
  slug: string;
  location: string;
}

export const MERCHANT_TEST_IP_LIST: MerchantTestIp[] = [
  { label: "瓦工 DC6 GIA", ip: "162.244.241.102", slug: "bandwagon", location: "洛杉矶" },
  { label: "瓦工 日本 GIA", ip: "185.199.226.1", slug: "bandwagon", location: "东京" },
  { label: "瓦工 香港 GIA", ip: "93.179.124.1", slug: "bandwagon", location: "香港" },
  { label: "DMIT 洛杉矶", ip: "154.17.12.22", slug: "dmit", location: "洛杉矶" },
  { label: "DMIT 香港", ip: "103.117.100.20", slug: "dmit", location: "香港" },
  { label: "V.PS 圣何塞", ip: "142.4.240.1", slug: "vps", location: "圣何塞" },
  { label: "ZgoCloud 洛杉矶", ip: "154.29.158.1", slug: "zgocloud", location: "洛杉矶" },
  { label: "66云 香港 CMI", ip: "154.213.16.1", slug: "66yun", location: "香港" },
  { label: "66云 英国 9929", ip: "185.182.193.1", slug: "66yun", location: "伦敦" },
  { label: "Cloudflare DNS", ip: "1.1.1.1", slug: "", location: "" },
];

/** 按商家 + 机房精确匹配，回退同商家任意机房，都没有则返回 null。 */
export function testIpFor(slug: string, location: string | null): string | null {
  const exact = MERCHANT_TEST_IP_LIST.find((x) => x.slug === slug && x.location === location);
  if (exact) return exact.ip;
  const any = MERCHANT_TEST_IP_LIST.find((x) => x.slug === slug);
  return any ? any.ip : null;
}
