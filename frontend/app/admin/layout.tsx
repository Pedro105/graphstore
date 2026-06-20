import type { ReactNode } from "react";

import { AdminShell } from "@/components/admin/admin-shell";
import { AdminAuthProvider } from "@/lib/admin/auth";

// The operator admin area is a completely separate tree from /dashboard: its
// own auth (the ADMIN_TOKEN gate in AdminShell), its own chrome, no shared
// session with the regular user flow.
export default function AdminLayout({ children }: { children: ReactNode }) {
  return (
    <AdminAuthProvider>
      <AdminShell>{children}</AdminShell>
    </AdminAuthProvider>
  );
}
