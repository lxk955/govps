import type { Metadata } from "next";
import { headers } from "next/headers";

import { IpCheckPanel } from "@/components/ip/ip-check-panel";

export const metadata: Metadata = {
  title: "IP 归属与威胁情报查询 - 纯净度检测",
  description:
    "在线 IP 纯净度检测、IP 欺诈分查询、机房/原生/双 ISP 识别、ASN 与地理位置精准解析。",
  alternates: { canonical: "/ip" },
  openGraph: {
    title: "IP 归属与威胁情报查询 - GoVPS 工具箱",
    description:
      "在线 IP 纯净度检测、IP 欺诈分查询、机房/原生/双 ISP 识别、ASN 与地理位置精准解析。",
    url: "/ip",
  },
};

/**
 * 取访客真实公网 IP。
 *
 * Cloudflare 直连本服务时会注入 cf-connecting-ip，Next.js 服务端能读到；
 * 但请求一旦经 rewrite 转发给后端，该头就会丢失，后端只能看到本容器
 * 的出口 IP。因此在这里读出后显式传给检测面板，由前端带在
 * ?ip= 上查询，而不是留空让后端猜。
 */
async function getClientIp(): Promise<string | undefined> {
  const h = await headers();
  const candidates = [
    h.get("cf-connecting-ip"),
    h.get("x-real-ip"),
    h.get("x-forwarded-for")?.split(",")[0],
  ];
  for (const raw of candidates) {
    const ip = raw?.trim();
    if (ip) return ip;
  }
  return undefined;
}

export default async function IpHomePage() {
  const clientIp = await getClientIp();

  return (
    <>
      <section className="hero">
        <h1 className="hero__title">IP 归属与威胁情报查询</h1>
        <p className="hero__lede">
          输入任意 IPv4 / IPv6 / 域名，或留空直接检测你当前的公网出口：
          归属地、ISP、ASN、数据中心属性、威胁与代理情报、纯净度评分一次给全。
        </p>
      </section>
      <IpCheckPanel clientIp={clientIp} />
    </>
  );
}
