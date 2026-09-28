"use client";

import { useCallback, useRef, useState } from "react";
import Link from "next/link";
import { ArrowRight, CheckCircle2, FileText, Upload, XCircle } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Card, CardContent, CardHeader, CardTitle } from "@/components/ui/card";
import { Label } from "@/components/ui/label";
import { Textarea } from "@/components/ui/textarea";
import {
  importChats,
  uploadChatsFile,
  type ChatImportResult,
} from "@/lib/api/imports";

type ImportStatus = "idle" | "importing" | "success" | "error";

export default function ImportPage() {
  const [status, setStatus] = useState<ImportStatus>("idle");
  const [error, setError] = useState<string | null>(null);
  const [result, setResult] = useState<ChatImportResult | null>(null);
  const [pasteContent, setPasteContent] = useState("");
  const fileInputRef = useRef<HTMLInputElement>(null);

  const handleImport = useCallback(async (content: string) => {
    if (!content.trim()) return;
    setStatus("importing");
    setError(null);
    setResult(null);

    try {
      const res = await importChats({ content, source_prefix: "chat-import" });
      setResult(res);
      setStatus("success");
      setPasteContent("");
    } catch (err) {
      setError(err instanceof Error ? err.message : "Import failed");
      setStatus("error");
    }
  }, []);

  const handleFileUpload = useCallback(
    async (e: React.ChangeEvent<HTMLInputElement>) => {
      const file = e.target.files?.[0];
      if (!file) return;

      setStatus("importing");
      setError(null);
      setResult(null);

      try {
        const res = await uploadChatsFile(file);
        setResult(res);
        setStatus("success");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
        setStatus("error");
      }

      if (fileInputRef.current) {
        fileInputRef.current.value = "";
      }
    },
    [],
  );

  const handleDrop = useCallback(
    async (e: React.DragEvent) => {
      e.preventDefault();
      const file = e.dataTransfer.files?.[0];
      if (!file) return;

      setStatus("importing");
      setError(null);
      setResult(null);

      try {
        const res = await uploadChatsFile(file);
        setResult(res);
        setStatus("success");
      } catch (err) {
        setError(err instanceof Error ? err.message : "Upload failed");
        setStatus("error");
      }
    },
    [],
  );

  const handleDragOver = useCallback((e: React.DragEvent) => {
    e.preventDefault();
  }, []);

  const reset = useCallback(() => {
    setStatus("idle");
    setError(null);
    setResult(null);
    setPasteContent("");
  }, []);

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Import Chats</h1>
        <p className="text-muted-foreground">
          Import your chat exports from ChatGPT, Claude, or other assistants to
          build your knowledge graph.
        </p>
      </div>

      {status === "success" && result ? (
        <Card>
          <CardHeader>
            <CardTitle className="flex items-center gap-2 text-green-600">
              <CheckCircle2 className="size-5" />
              Import Complete
            </CardTitle>
          </CardHeader>
          <CardContent className="space-y-4">
            <div className="grid grid-cols-2 gap-4 sm:grid-cols-4">
              <Stat label="Format" value={result.source_format} />
              <Stat
                label="Conversations"
                value={result.conversations_imported}
              />
              <Stat label="Messages" value={result.total_messages} />
              <Stat label="Entities" value={result.total_entities} />
            </div>

            {result.conversations.length > 0 && (
              <div className="space-y-2">
                <Label className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
                  Imported Conversations
                </Label>
                <ul className="divide-y divide-border rounded-lg border">
                  {result.conversations.map((conv, i) => (
                    <li
                      key={i}
                      className="flex items-center justify-between px-3 py-2 text-sm"
                    >
                      <span className="font-medium">{conv.title}</span>
                      <span className="text-muted-foreground">
                        {conv.messages_imported} messages, {conv.total_entities}{" "}
                        entities
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {result.errors.length > 0 && (
              <div className="space-y-2">
                <Label className="text-xs font-medium uppercase tracking-wide text-destructive">
                  Errors
                </Label>
                <ul className="space-y-1 text-sm text-destructive">
                  {result.errors.map((err, i) => (
                    <li key={i}>{err}</li>
                  ))}
                </ul>
              </div>
            )}

            <div className="flex gap-3 pt-2">
              <Link href="/dashboard/memories">
                <Button>
                  View Graph
                  <ArrowRight className="size-4" />
                </Button>
              </Link>
              <Button variant="outline" onClick={reset}>
                Import More
              </Button>
            </div>
          </CardContent>
        </Card>
      ) : (
        <div className="grid gap-6 lg:grid-cols-2">
          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <Upload className="size-4" />
                Upload File
              </CardTitle>
            </CardHeader>
            <CardContent>
              <div
                onDrop={handleDrop}
                onDragOver={handleDragOver}
                className="flex min-h-[200px] cursor-pointer flex-col items-center justify-center gap-3 rounded-lg border-2 border-dashed border-border bg-muted/30 p-6 text-center transition-colors hover:border-primary/50 hover:bg-muted/50"
                onClick={() => fileInputRef.current?.click()}
              >
                <FileText className="size-10 text-muted-foreground" />
                <div>
                  <p className="font-medium">Drop a file here or click to upload</p>
                  <p className="text-sm text-muted-foreground">
                    Supports .json, .txt, .md files
                  </p>
                </div>
                <input
                  ref={fileInputRef}
                  type="file"
                  accept=".json,.txt,.md,.markdown"
                  className="hidden"
                  onChange={handleFileUpload}
                  disabled={status === "importing"}
                />
              </div>
            </CardContent>
          </Card>

          <Card>
            <CardHeader>
              <CardTitle className="flex items-center gap-2">
                <FileText className="size-4" />
                Paste Content
              </CardTitle>
            </CardHeader>
            <CardContent className="space-y-3">
              <Textarea
                value={pasteContent}
                onChange={(e) => setPasteContent(e.target.value)}
                placeholder="Paste your chat export JSON or transcript here..."
                rows={8}
                disabled={status === "importing"}
              />
              <Button
                onClick={() => handleImport(pasteContent)}
                disabled={status === "importing" || !pasteContent.trim()}
                className="w-full"
              >
                {status === "importing" ? "Importing..." : "Import"}
              </Button>
            </CardContent>
          </Card>
        </div>
      )}

      {status === "error" && error && (
        <Card className="border-destructive/50 bg-destructive/5">
          <CardContent className="flex items-center gap-3 pt-6">
            <XCircle className="size-5 text-destructive" />
            <span className="text-sm text-destructive">{error}</span>
            <Button
              variant="outline"
              size="sm"
              onClick={reset}
              className="ml-auto"
            >
              Try Again
            </Button>
          </CardContent>
        </Card>
      )}

      <Card>
        <CardHeader>
          <CardTitle>Supported Formats</CardTitle>
        </CardHeader>
        <CardContent>
          <ul className="grid gap-3 text-sm sm:grid-cols-3">
            <li className="rounded-lg border bg-muted/30 p-3">
              <span className="font-medium">ChatGPT Export</span>
              <p className="mt-1 text-muted-foreground">
                JSON from Settings &rarr; Data Controls &rarr; Export
              </p>
            </li>
            <li className="rounded-lg border bg-muted/30 p-3">
              <span className="font-medium">Claude Export</span>
              <p className="mt-1 text-muted-foreground">
                JSON export of conversation history
              </p>
            </li>
            <li className="rounded-lg border bg-muted/30 p-3">
              <span className="font-medium">Text Transcript</span>
              <p className="mt-1 text-muted-foreground">
                Markdown or plain text with User:/Bot: prefixes
              </p>
            </li>
          </ul>
        </CardContent>
      </Card>
    </div>
  );
}

function Stat({ label, value }: { label: string; value: string | number }) {
  return (
    <div className="rounded-lg border bg-muted/30 p-3">
      <div className="text-xs font-medium uppercase tracking-wide text-muted-foreground">
        {label}
      </div>
      <div className="mt-0.5 text-lg font-semibold tabular-nums">{value}</div>
    </div>
  );
}
