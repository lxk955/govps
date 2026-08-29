import type { Metadata } from "next";

import { DnsleakPanel } from "@/components/ip/dnsleak-panel";

export const metadata: Metadata = {
  title: "DNS 泄露检测",
  description: "检测使用 VPN/代理时 DNS 解析是否仍经由本地运营商泄露访问足迹。",
  alternates: { canonical: "/ip/dnsleak" },
};

export default function DnsLeakPage() {
  return (
    <>
      <section className="hero">
        <h1 className="hero__title">DNS 泄露检测</h1>
        <p className="hero__lede">
          你访问的每一个网址，都要先由某台 DNS 服务器翻译成 IP
          才能连上——那台服务器因此拿到了一份<strong>你访问过的域名清单</strong>。
          代理和 VPN 常常只接管了网页流量，把这一步留在了原地：
          网站看到的是代理出口，运营商看到的却是你的浏览历史。
          下面向本站的权威 DNS 发起 8 个一次性随机子域解析，把真正替你查询的那几台服务器揪出来。
        </p>
      </section>
      <DnsleakPanel />
    </>
  );
}
