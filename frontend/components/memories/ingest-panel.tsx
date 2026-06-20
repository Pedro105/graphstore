"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";

interface IngestPanelProps {
  onIngest: (content: string, source: string) => Promise<void>;
  ingesting: boolean;
  error: string | null;
}

export function IngestPanel({ onIngest, ingesting, error }: IngestPanelProps) {
  const [content, setContent] = useState("");
  const [source, setSource] = useState("dashboard-demo");

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = content.trim();
    if (!trimmed) return;
    await onIngest(trimmed, source.trim() || "dashboard-demo");
    setContent("");
  }

  return (
    <Card>
      <CardHeader>
        <CardTitle>Remember</CardTitle>
      </CardHeader>
      <CardContent>
        <form onSubmit={handleSubmit} className="flex flex-col gap-3">
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="memory-content">Content</Label>
            <Textarea
              id="memory-content"
              placeholder="e.g. Acme Corp is expecting a shipment of 500 units of Product Y."
              value={content}
              onChange={(event) => setContent(event.target.value)}
              rows={3}
            />
          </div>
          <div className="flex flex-col gap-1.5">
            <Label htmlFor="memory-source">Source</Label>
            <Input
              id="memory-source"
              value={source}
              onChange={(event) => setSource(event.target.value)}
              className="font-mono"
            />
          </div>
          <Button type="submit" disabled={ingesting || !content.trim()}>
            {ingesting ? "Extracting..." : "Remember"}
          </Button>
          {error && <p className="text-sm text-destructive">{error}</p>}
        </form>
      </CardContent>
    </Card>
  );
}
