import type { ReactNode } from "react";

import { SidebarNav } from "@/components/dashboard/sidebar-nav";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <div className="flex min-h-screen bg-background text-foreground">
      <aside className="flex w-60 shrink-0 flex-col border-r border-border p-4">
        <div className="mb-6 px-2 text-lg font-semibold tracking-tight">ContextStore</div>
        <SidebarNav />
      </aside>
      <main className="min-w-0 flex-1 overflow-y-auto">
        <div className="mx-auto max-w-6xl p-8">{children}</div>
      </main>
    </div>
  );
}
