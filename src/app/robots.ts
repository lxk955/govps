import type { MetadataRoute } from "next";

import { SITE_URL } from "@/lib/site";

export default function robots(): MetadataRoute.Robots {
  return {
    rules: [
      {
        userAgent: "*",
        allow: "/",
        // API 与购买跳转不进索引
        disallow: ["/api/", "/go/"],
      },
    ],
    sitemap: `${SITE_URL}/sitemap.xml`,
  };
}
