/** 登录回跳地址：保留当前路径和筛选参数。 */

export function loginHref(pathname: string | null, search: string = ""): string {
  const path =
    pathname && pathname.startsWith("/") && !pathname.startsWith("//") && !pathname.startsWith("/login")
      ? pathname
      : "/";
  const qs = !search || search === "?" ? "" : search.startsWith("?") ? search : `?${search}`;
  return `/login?next=${encodeURIComponent(`${path}${qs}`)}`;
}

export function destinationLabel(path: string): string {
  const bare = path.split("?")[0] || "/";
  if (bare.startsWith("/admin")) return "管理后台";
  if (bare.startsWith("/watchlist")) return "我的关注";
  if (bare.startsWith("/monitor")) return "探针监控";
  if (bare.startsWith("/compare")) return "套餐对比";
  if (bare.startsWith("/deals")) return "动态";
  if (bare.startsWith("/ip")) return "IP 工具";
  if (bare.startsWith("/vps/")) return "套餐详情";
  if (bare === "/") return "网站首页";
  return "刚才的页面";
}
