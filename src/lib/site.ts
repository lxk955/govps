/**
 * 站点规范域名（SEO 基准 URL）：全站 metadataBase / canonical / og:url /
 * sitemap / robots 的唯一来源。集中定义，避免同一常量散落多处后改一处漏两处，
 * 导致 canonical 与 sitemap 指向不同域名。
 *
 * 正式域名为 https://govps.xyz；测试或过渡域名（如 https://vps.govps.xyz）
 * 通过构建期环境变量 NEXT_PUBLIC_SITE_URL 覆盖。
 *
 * 注意：NEXT_PUBLIC_* 会在 next build 时内联为字面量，部署后单独修改
 * 环境变量不生效，必须重新构建部署。
 */
export const SITE_URL = (process.env.NEXT_PUBLIC_SITE_URL ?? "https://govps.xyz").replace(
  /\/+$/,
  "",
);
