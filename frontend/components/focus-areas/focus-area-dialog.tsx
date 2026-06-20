"use client";

import { useEffect, useState } from "react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import type { FocusArea } from "@/lib/api";

export interface FocusAreaFormValues {
  name: string;
  description: string;
}

interface FocusAreaDialogProps {
  open: boolean;
  onOpenChange: (open: boolean) => void;
  initial?: FocusArea | null;
  onSubmit: (values: FocusAreaFormValues) => Promise<void>;
}

const EMPTY: FocusAreaFormValues = { name: "", description: "" };

export function FocusAreaDialog({ open, onOpenChange, initial, onSubmit }: FocusAreaDialogProps) {
  const [values, setValues] = useState<FocusAreaFormValues>(EMPTY);
  const [saving, setSaving] = useState(false);

  useEffect(() => {
    setValues(initial ? { name: initial.name, description: initial.description } : EMPTY);
  }, [initial, open]);

  async function handleSubmit() {
    if (!values.name.trim()) return;
    setSaving(true);
    try {
      await onSubmit(values);
      onOpenChange(false);
    } finally {
      setSaving(false);
    }
  }

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent>
        <DialogHeader>
          <DialogTitle>{initial ? "Edit focus area" : "New focus area"}</DialogTitle>
        </DialogHeader>
        <div className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="focus-name">Name</Label>
            <Input
              id="focus-name"
              value={values.name}
              onChange={(event) => setValues((prev) => ({ ...prev, name: event.target.value }))}
              placeholder="e.g. Sales Operations"
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="focus-description">Description</Label>
            <Textarea
              id="focus-description"
              value={values.description}
              onChange={(event) =>
                setValues((prev) => ({ ...prev, description: event.target.value }))
              }
              placeholder="What memory should be organized under this focus area?"
              rows={3}
            />
          </div>
        </div>
        <DialogFooter>
          <Button variant="outline" onClick={() => onOpenChange(false)}>
            Cancel
          </Button>
          <Button onClick={handleSubmit} disabled={saving || !values.name.trim()}>
            {saving ? "Saving..." : "Save"}
          </Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
