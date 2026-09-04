/** 桌面顶栏 / 移动底栏的导航口径。图标只在底栏用，留在组件里。 */

export type NavItem = {
  href: string;
  label: string;
  /** 子路径也算当前项（/ip、/routes） */
  prefix?: boolean;
};

export const MOBILE_NAV: readonly NavItem[] = [
  { href: "/", label: "雷达" },
  { href: "/deals", label: "动态" },
  { href: "/ip", label: "IP工具", prefix: true },
  { href: "/watchlist", label: "关注" },
];

export const DESKTOP_NAV: readonly NavItem[] = [
  { href: "/", label: "雷达" },
  { href: "/deals", label: "动态" },
  { href: "/routes", label: "线路专题", prefix: true },
  { href: "/providers", label: "服务商" },
  { href: "/ip", label: "IP 工具", prefix: true },
  { href: "/watchlist", label: "我的关注" },
];

export function navItemActive(pathname: string, item: NavItem): boolean {
  if (item.prefix) return pathname === item.href || pathname.startsWith(`${item.href}/`);
  return pathname === item.href;
}
