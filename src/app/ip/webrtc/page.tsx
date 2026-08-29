import type { Metadata } from "next";

import { WebrtcPanel } from "@/components/ip/webrtc-panel";

export const metadata: Metadata = {
  title: "WebRTC 泄露检测",
  description: "检测浏览器 WebRTC 是否绕过代理暴露你的真实公网 IP 与本机局域网地址。",
  alternates: { canonical: "/ip/webrtc" },
};

export default function WebRTCPage() {
  return (
    <>
      <section className="hero">
        <h1 className="hero__title">WebRTC 泄露检测</h1>
        <p className="hero__lede">
          浏览器的 WebRTC 会绕过代理与 VPN，直接向 STUN 服务器打听「我在公网上长什么样」。
          这条通道拿到的地址往往是你的<strong>真实地址</strong>，而不是代理出口的地址。
          下面用多台公开 STUN 服务器逐个探测，把它们看到的地址和本站在 HTTP
          层看到的地址摆在一起对照。
        </p>
      </section>
      <WebrtcPanel />
    </>
  );
}
