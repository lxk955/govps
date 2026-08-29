"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

/** IP 板块二级导航（1:1 复刻旧站 IpLayout.vue 的 .nav / .nav__item 胶囊组）。 */
const NAVS = [
  { href: "/ip", label: "IP 检测", exact: true },
  { href: "/ip/webrtc", label: "WebRTC 泄露检测" },
  { href: "/ip/dnsleak", label: "DNS 泄露检测" },
  { href: "/ip/fingerprint", label: "浏览器指纹检测" },
] as const;

export function IpNav() {
  const pathname = usePathname();

  return (
    <nav className="nav" aria-label="IP 检测导航">
      {NAVS.map((n) => {
        const active = "exact" in n ? pathname === n.href : pathname.startsWith(n.href);
        return (
          <Link
            key={n.href}
            href={n.href}
            aria-current={active ? "page" : undefined}
            className={active ? "nav__item is-active" : "nav__item"}
          >
            {n.label}
          </Link>
        );
      })}
    </nav>
  );
}
