import type { Metadata } from "next";

import { FingerprintPanel } from "@/components/ip/fingerprint-panel";

export const metadata: Metadata = {
  title: "浏览器指纹检测",
  description: "查看你的浏览器暴露了哪些可用于跨站追踪的设备与软件特征。",
  alternates: { canonical: "/ip/fingerprint" },
};

export default function FingerprintPage() {
  return <FingerprintPanel />;
}
