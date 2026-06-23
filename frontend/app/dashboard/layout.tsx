import type { ReactNode } from "react";

import { AccountMenu } from "@/components/dashboard/account-menu";
import { SidebarNav } from "@/components/dashboard/sidebar-nav";
import { WorkspaceSwitcher } from "@/components/dashboard/workspace-switcher";
import { WorkspaceProvider } from "@/lib/dashboard/workspace";

export default function DashboardLayout({ children }: { children: ReactNode }) {
  return (
    <WorkspaceProvider>
      {/* h-screen + overflow-hidden pins the shell to the viewport so the page
          itself never scrolls; only <main> scrolls. That keeps the sidebar
          fixed at full screen height instead of scrolling away with content. */}
      <div className="dashboard-theme flex h-screen overflow-hidden bg-background font-sans text-foreground">
        <aside className="flex h-screen w-60 shrink-0 flex-col overflow-y-auto border-r border-border bg-sidebar p-4">
          <div className="mb-4 px-2 text-lg font-semibold tracking-tight text-foreground">
            ContextStore
          </div>
          {/* Workspace switcher above the nav: switching it changes which
              project's graph every page below reflects. */}
          <WorkspaceSwitcher />
          <SidebarNav />
          {/* Account affordance pinned to the bottom (mt-auto), the slot the
              common dashboard pattern uses for the user menu. */}
          <AccountMenu />
        </aside>
        <main className="min-w-0 flex-1 overflow-y-auto bg-background">
          <div className="mx-auto max-w-6xl p-8">{children}</div>
        </main>
      </div>
    </WorkspaceProvider>
  );
}
