import type { Metadata } from "next";
import Link from "next/link";

export const metadata: Metadata = {
  title: "IP 检测",
  description:
    "IP 归属、纯净度与风险检测，WebRTC 泄露、DNS 泄露与浏览器指纹检测工具集。",
  alternates: { canonical: "/ip" },
};

const TABS = [
  { href: "/ip", label: "IP 检测" },
  { href: "/ip/webrtc", label: "WebRTC 泄露" },
  { href: "/ip/dnsleak", label: "DNS 泄露" },
  { href: "/ip/fingerprint", label: "浏览器指纹" },
];

export default function IpLayout({ children }: { children: React.ReactNode }) {
  return (
    <div className="mx-auto w-full max-w-5xl px-4 py-6">
      <nav aria-label="IP 工具导航" className="-mx-1 mb-5 flex gap-1 overflow-x-auto pb-1">
        {TABS.map((t) => (
          <Link
            key={t.href}
            href={t.href}
            className="hover:bg-muted whitespace-nowrap rounded-full border px-3.5 py-1.5 text-sm transition-colors"
          >
            {t.label}
          </Link>
        ))}
      </nav>
      {children}
    </div>
  );
}
