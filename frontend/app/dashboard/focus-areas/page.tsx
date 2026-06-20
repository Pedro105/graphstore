"use client";

import { useState } from "react";
import { Loader2, PlusIcon, Trash2Icon } from "lucide-react";

import {
  FocusAreaDialog,
  type FocusAreaFormValues,
} from "@/components/focus-areas/focus-area-dialog";
import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent, CardDescription, CardHeader, CardTitle } from "@/components/ui/card";
import { useFocusAreas } from "@/lib/hooks/use-focus-areas";
import type { FocusArea } from "@/lib/api";

export default function FocusAreasPage() {
  const { focusAreas, loading, create, update, remove } = useFocusAreas();
  const [dialogOpen, setDialogOpen] = useState(false);
  const [editing, setEditing] = useState<FocusArea | null>(null);

  function openCreate() {
    setEditing(null);
    setDialogOpen(true);
  }

  function openEdit(focusArea: FocusArea) {
    setEditing(focusArea);
    setDialogOpen(true);
  }

  async function handleSubmit(values: FocusAreaFormValues) {
    if (editing) {
      await update(editing.id, values);
    } else {
      await create(values);
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <div className="flex items-center gap-2">
            <h1 className="text-2xl font-semibold">Focus Areas</h1>
            <Badge variant="outline">Saved locally · backend coming soon</Badge>
          </div>
          <p className="text-muted-foreground">Domains memory can be organized around.</p>
        </div>
        <Button onClick={openCreate}>
          <PlusIcon />
          New focus area
        </Button>
      </div>

      {loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Loading focus areas...
        </div>
      ) : focusAreas.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
            <p className="font-medium">No focus areas yet</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Create one to organize memory around a domain, like &quot;Sales
              Operations&quot; or &quot;Supplier Relationships&quot;.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {focusAreas.map((focusArea) => (
            <Card key={focusArea.id}>
              <CardHeader>
                <div className="flex items-center justify-between">
                  <CardTitle>{focusArea.name}</CardTitle>
                  <Button variant="ghost" size="icon-sm" onClick={() => remove(focusArea.id)}>
                    <Trash2Icon />
                  </Button>
                </div>
                <CardDescription>{focusArea.description}</CardDescription>
              </CardHeader>
              <CardContent>
                <Button variant="outline" size="sm" onClick={() => openEdit(focusArea)}>
                  Edit
                </Button>
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <FocusAreaDialog
        open={dialogOpen}
        onOpenChange={setDialogOpen}
        initial={editing}
        onSubmit={handleSubmit}
      />
    </div>
  );
}
