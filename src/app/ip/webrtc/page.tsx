import type { Metadata } from "next";

import { WebrtcPanel } from "@/components/ip/webrtc-panel";

export const metadata: Metadata = {
  title: "WebRTC 泄露检测",
  description: "检测浏览器 WebRTC 是否绕过代理暴露你的真实公网 IP 与本机局域网地址。",
  alternates: { canonical: "/ip/webrtc" },
};

export default function WebRTCPage() {
  return <WebrtcPanel />;
}
