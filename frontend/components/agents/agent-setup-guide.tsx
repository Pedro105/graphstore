"use client";

import { useState } from "react";
import { Check, Copy, ExternalLink } from "lucide-react";

import { Button } from "@/components/ui/button";
import {
  Dialog,
  DialogContent,
  DialogFooter,
  DialogHeader,
  DialogTitle,
} from "@/components/ui/dialog";
import { API_BASE_URL, DOCS_MCP_URL } from "@/lib/links";

function CopyButton({ value }: { value: string }) {
  const [copied, setCopied] = useState(false);
  return (
    <Button
      type="button"
      variant="outline"
      size="sm"
      onClick={() => {
        void navigator.clipboard.writeText(value).then(() => {
          setCopied(true);
          setTimeout(() => setCopied(false), 1500);
        });
      }}
    >
      {copied ? <Check className="size-3.5" /> : <Copy className="size-3.5" />}
      {copied ? "Copied" : "Copy"}
    </Button>
  );
}

function Snippet({
  title,
  hint,
  code,
}: {
  title: string;
  hint: string;
  code: string;
}) {
  return (
    <div className="space-y-2">
      <div className="flex items-center justify-between gap-2">
        <div>
          <p className="text-sm font-medium">{title}</p>
          <p className="text-xs text-muted-foreground">{hint}</p>
        </div>
        <CopyButton value={code} />
      </div>
      <pre className="overflow-x-auto rounded-lg border border-border bg-muted p-3 font-mono text-xs leading-relaxed">
        {code}
      </pre>
    </div>
  );
}

// Shown right after an agent is created: how to actually write *as* this agent.
// The agent name is just the `source` value on each write — so the guide is
// concrete (real endpoint, real field) rather than a vague "you're all set".
export function AgentSetupGuide({
  agentName,
  open,
  onOpenChange,
}: {
  agentName: string | null;
  open: boolean;
  onOpenChange: (open: boolean) => void;
}) {
  const name = agentName ?? "your_agent";

  const apiSnippet = [
    `curl -X POST ${API_BASE_URL}/v1/memories \\`,
    `  -H "Authorization: Bearer $CONTEXTSTORE_API_KEY" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '{`,
    `    "content": "Acme Corp ordered 500 units of Product Y.",`,
    `    "source": "${name}"`,
    `  }'`,
  ].join("\n");

  const mcpSnippet = JSON.stringify(
    {
      mcpServers: {
        contextstore: {
          command: "uvx",
          args: ["contextstore-mcp"],
          env: {
            CONTEXTSTORE_API_KEY: "csk_live_your_key_here",
            CONTEXTSTORE_API_URL: API_BASE_URL,
          },
        },
      },
    },
    null,
    2,
  );

  return (
    <Dialog open={open} onOpenChange={onOpenChange}>
      <DialogContent className="max-h-[85vh] overflow-y-auto sm:max-w-xl">
        <DialogHeader>
          <DialogTitle>
            <span className="font-mono">{name}</span> is ready
          </DialogTitle>
        </DialogHeader>

        <div className="flex flex-col gap-5">
          <p className="text-sm text-muted-foreground">
            An agent is identified by the{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
              source
            </code>{" "}
            field on each write. Set it to{" "}
            <code className="rounded bg-muted px-1 py-0.5 font-mono text-xs">
              {name}
            </code>{" "}
            and its writes will be attributed here automatically.
          </p>

          <Snippet
            title="Write as this agent (HTTP API)"
            hint='The "source" field attributes the write to this agent.'
            code={apiSnippet}
          />

          <Snippet
            title="Connect via MCP (Claude Code / Desktop)"
            hint="Add to your MCP config, then your agent can call the remember / recall tools."
            code={mcpSnippet}
          />
        </div>

        <DialogFooter className="sm:justify-between">
          <a
            href={DOCS_MCP_URL}
            target="_blank"
            rel="noopener noreferrer"
            className="inline-flex items-center gap-1 text-xs font-medium text-muted-foreground hover:text-foreground"
          >
            MCP setup docs
            <ExternalLink className="size-3" />
          </a>
          <Button onClick={() => onOpenChange(false)}>Done</Button>
        </DialogFooter>
      </DialogContent>
    </Dialog>
  );
}
