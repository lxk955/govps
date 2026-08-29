import type { Metadata } from "next";

import { FingerprintPanel } from "@/components/ip/fingerprint-panel";

export const metadata: Metadata = {
  title: "浏览器指纹检测",
  description: "查看你的浏览器暴露了哪些可用于跨站追踪的设备与软件特征。",
  alternates: { canonical: "/ip/fingerprint" },
};

export default function FingerprintPage() {
  return (
    <>
      <section className="hero">
        <h1 className="hero__title">浏览器指纹检测</h1>
        <p className="hero__lede">
          网站不需要 Cookie 也能认出你。分辨率、字体度量、显卡型号、时区、音频处理特征……
          单独看每一项都不稀奇，凑在一起却足以在几亿台设备里锁定一台。
          下面把这些信号算成一个指纹值，看看你的浏览器有多好认。
        </p>
      </section>
      <FingerprintPanel />
    </>
  );
}
