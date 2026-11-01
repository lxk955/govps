import { BlockList, isIP } from "node:net";
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

const CLOUDFLARE_RANGES = (() => {
  const list = new BlockList();
  for (const cidr of [
    "173.245.48.0/20",
    "103.21.244.0/22",
    "103.22.200.0/22",
    "103.31.4.0/22",
    "141.101.64.0/18",
    "108.162.192.0/18",
    "190.93.240.0/20",
    "188.114.96.0/20",
    "197.234.240.0/22",
    "198.41.128.0/17",
    "162.158.0.0/15",
    "104.16.0.0/13",
    "104.24.0.0/14",
    "172.64.0.0/13",
    "131.0.72.0/22",
  ]) {
    const [net, prefix] = cidr.split("/");
    list.addSubnet(net, Number(prefix), "ipv4");
  }
  for (const cidr of [
    "2400:cb00::/32",
    "2606:4700::/32",
    "2803:f800::/32",
    "2405:b500::/32",
    "2405:8100::/32",
    "2a06:98c0::/29",
    "2c0f:f248::/32",
  ]) {
    const [net, prefix] = cidr.split("/");
    list.addSubnet(net, Number(prefix), "ipv6");
  }
  return list;
})();

const PRIVATE_RANGES = (() => {
  const list = new BlockList();
  for (const cidr of [
    "127.0.0.0/8",
    "10.0.0.0/8",
    "172.16.0.0/12",
    "192.168.0.0/16",
    "169.254.0.0/16",
    "100.64.0.0/10",
    "0.0.0.0/8",
  ]) {
    const [net, prefix] = cidr.split("/");
    list.addSubnet(net, Number(prefix), "ipv4");
  }
  for (const cidr of ["::1/128", "fc00::/7", "fe80::/10", "::/128"]) {
    const [net, prefix] = cidr.split("/");
    list.addSubnet(net, Number(prefix), "ipv6");
  }
  return list;
})();

function normalizeIp(raw: string | null | undefined): { ip: string; family: "ipv4" | "ipv6" } | null {
  const trimmed = raw?.trim();
  if (!trimmed) return null;
  const unmapped = trimmed.toLowerCase().startsWith("::ffff:") ? trimmed.slice(7) : trimmed;
  const ver = isIP(unmapped);
  if (ver === 4) return { ip: unmapped, family: "ipv4" };
  if (ver === 6) return { ip: unmapped, family: "ipv6" };
  return null;
}

/**
 * 取访客真实公网 IP（与后端 services/client_ip 保持一致的信任链规则）。
 *
 * Caddy 总是将 TCP 对端地址覆写到 x-real-ip：
 * - 若 x-real-ip 属于 Cloudflare 官方回源网段，才信任 cf-connecting-ip；
 * - 若 x-real-ip 是非 Cloudflare 公网地址（绕过 CDN 直连源站），忽略可伪造的 cf-connecting-ip。
 */
async function getClientIp(): Promise<string | undefined> {
  const h = await headers();
  const cf = normalizeIp(h.get("cf-connecting-ip"));
  const real = normalizeIp(h.get("x-real-ip"));

  if (real && !PRIVATE_RANGES.check(real.ip, real.family)) {
    if (CLOUDFLARE_RANGES.check(real.ip, real.family)) {
      return cf ? cf.ip : real.ip;
    }
    return real.ip;
  }

  if (cf) return cf.ip;

  const fwd = h.get("x-forwarded-for");
  if (fwd) {
    for (const part of fwd.split(",")) {
      const parsed = normalizeIp(part);
      if (parsed && !PRIVATE_RANGES.check(parsed.ip, parsed.family)) {
        return parsed.ip;
      }
    }
  }

  return real?.ip;
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
