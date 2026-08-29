import { IpCheckPanel } from "@/components/ip/ip-check-panel";

export default function IpHomePage() {
  return (
    <>
      <section className="hero">
        <h1 className="hero__title">IP 归属与威胁情报查询</h1>
        <p className="hero__lede">
          输入任意 IPv4 / IPv6 / 域名，或留空直接检测你当前的公网出口：
          归属地、ISP、ASN、数据中心属性、威胁与代理情报、纯净度评分一次给全。
        </p>
      </section>
      <IpCheckPanel />
    </>
  );
}
