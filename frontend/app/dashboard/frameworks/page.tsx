"use client";

import { useState } from "react";
import { Loader2 } from "lucide-react";

import { FrameworkConfigDialog } from "@/components/frameworks/framework-config-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useFrameworks } from "@/lib/hooks/use-frameworks";
import type { Framework } from "@/lib/api";

export default function FrameworksPage() {
  const { frameworks, loading, update } = useFrameworks();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [active, setActive] = useState<Framework | null>(null);

  function openConfig(framework: Framework) {
    setActive(framework);
    setDialogOpen(true);
  }

  async function handleSave(config: Record<string, string>) {
    if (!active) return;
    await update(active.id, { config, connected: true });
  }

  return (
    <div className="flex flex-col gap-6">
      <div>
        <div className="flex items-center gap-2">
          <h1 className="text-2xl font-semibold">Frameworks</h1>
          <Badge variant="outline">Saved locally · backend coming soon</Badge>
        </div>
        <p className="text-muted-foreground">
          Connect the agent framework your agents already run on.
        </p>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Loading frameworks...
        </div>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2">
          {frameworks.map((framework) => (
            <Card key={framework.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{framework.label}</CardTitle>
                  <Badge variant={framework.connected ? "default" : "outline"}>
                    {framework.connected ? "Connected" : "Not connected"}
                  </Badge>
                </div>
                <CardDescription>{framework.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="outline" size="sm" onClick={() => openConfig(framework)}>
                  {framework.connected ? "Edit configuration" : "Connect"}
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <FrameworkConfigDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        framework={active}
        onSave={handleSave}
      />
    </div>
  );
}
