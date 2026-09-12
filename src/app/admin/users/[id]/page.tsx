import type { Metadata } from "next";

import { AdminUserDetailPage } from "@/components/admin-user-detail";

export const metadata: Metadata = {
  title: "用户详情",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <AdminUserDetailPage />;
}
