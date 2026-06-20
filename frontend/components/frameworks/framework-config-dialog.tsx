"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import type { Framework } from "@/lib/api";

interface FrameworkConfigDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  framework: Framework | null;
  onSave: (config: Record<string, string>) => Promise<void>;
}

export function FrameworkConfigDialog({
  open,
  onOpenChange,
  framework,
  onSave,
}: FrameworkConfigDialogProps) {
  const [endpoint, setEndpoint] = useState("");
  const [apiKey, setApiKey] = useState("");
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setEndpoint(framework?.config.endpoint ?? "");
    setApiKey(framework?.config.api_key ?? "");
  }, [framework, open]);

  async function handleSave() {
    setSaving(true);
    try {
      await onSave({ endpoint, api_key: apiKey });
      onOpenChange(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>Configure {framework?.label}</DialogTitle>
          <DialogDescription>
            Not wired up yet -- this stores connection settings locally so the
            shape is ready when a real integration lands.
          </DialogDescription>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="framework-endpoint">Endpoint</Label>
            <Input
              id="framework-endpoint"
              value={endpoint}
              onChange={(event) => setEndpoint(event.target.value)}
              placeholder="https://..."
              className="font-mono"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="framework-api-key">API key</Label>
            <Input
              id="framework-api-key"
              value={apiKey}
              onChange={(event) => setApiKey(event.target.value)}
              placeholder="sk-..."
              className="font-mono"
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSave} disabled={saving}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
