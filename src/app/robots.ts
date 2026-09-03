import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // API、外链跳转与登录/个人关注等私有状态页不进索引，节省搜索引擎抓取预算
        disallow: ["/api/", "/go/", "/watchlist", "/login"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
