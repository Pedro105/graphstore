"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import { cn } from "@/lib/utils";

interface IngestPanelProps {
  onIngest: (content: string, source: string) => Promise<void>;
  ingesting: boolean;
  error: string | null;
  // Registered agent names, offered as quick-picks for the Source field so a
  // write is attributed to a real agent rather than a typo'd free-text value.
  agents: string[];
}

const FALLBACK_SOURCE = "dashboard-demo";

export function IngestPanel({
  onIngest,
  ingesting,
  error,
  agents,
}: IngestPanelProps) {
  const [content, setContent] = useState("");
  const [source, setSource] = useState(FALLBACK_SOURCE);

  async function handleSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = content.trim();
    if (!trimmed) return;
    await onIngest(trimmed, source.trim() || FALLBACK_SOURCE);
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
            {agents.length > 0 && (
              <div className="flex flex-wrap gap-1.5">
                <span className="text-xs text-muted-foreground">Write as:</span>
                {agents.map((name) => (
                  <button
                    key={name}
                    type="button"
                    onClick={() => setSource(name)}
                    className={cn(
                      "rounded-full border px-2 py-0.5 font-mono text-[11px] transition-colors",
                      source === name
                        ? "border-transparent bg-data-accent text-data-accent-foreground"
                        : "border-border text-muted-foreground hover:bg-muted hover:text-foreground",
                    )}
                    aria-pressed={source === name}
                  >
                    {name}
                  </button>
                ))}
              </div>
            )}
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
