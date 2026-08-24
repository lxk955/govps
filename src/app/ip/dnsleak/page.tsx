import type { Metadata } from "next";

import { DnsleakPanel } from "@/components/ip/dnsleak-panel";

export const metadata: Metadata = {
  title: "DNS 泄露检测",
  description: "检测使用 VPN/代理时 DNS 解析是否仍经由本地运营商泄露访问足迹。",
  alternates: { canonical: "/ip/dnsleak" },
};

export default function DnsLeakPage() {
  return <DnsleakPanel />;
}
