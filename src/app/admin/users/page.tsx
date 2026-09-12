import type { Metadata } from "next";

import { AdminUsersPage } from "@/components/admin-users-page";

export const metadata: Metadata = {
  title: "用户",
  robots: { index: false, follow: false },
};

export default function Page() {
  return <AdminUsersPage />;
}
