import type { ReactNode } from "react";
import { notFound } from "next/navigation";

import { AdminShell } from "@/components/admin/admin-shell";
import { AdminAuthProvider } from "@/lib/admin/auth";

// force-dynamic so ENABLE_ADMIN_UI is read at request time, not baked in at
// build -- Pedro can flip it on a deployment without rebuilding.
export const dynamic = "force-dynamic";

// Every /admin page is a client component, which can't carry route-segment
// config itself; declaring the edge runtime here on the (server) layout applies
// it to all admin routes, satisfying @cloudflare/next-on-pages' requirement
// that every dynamic route run on the edge.
export const runtime = "edge";

// The operator admin area is a completely separate tree from /dashboard: its
// own auth (the validated ADMIN_TOKEN gate in AdminShell), its own chrome, no
// shared session with the regular user flow.
//
// ENABLE_ADMIN_UI gates whether this surface exists at all. It defaults ON
// (unset === enabled), preserving current behavior. Set it to "false" on a
// public-facing deployment to get a genuine 404 for /admin and every sub-route
// (see docs/deployment.md).
export default function AdminLayout({ children }: { children: ReactNode }) {
  if (process.env.ENABLE_ADMIN_UI === "false") notFound();

  return (
    <AdminAuthProvider>
      <AdminShell>{children}</AdminShell>
    </AdminAuthProvider>
  );
}
