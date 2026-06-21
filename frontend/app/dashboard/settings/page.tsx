"use client";

import Link from "next/link";
import { useState } from "react";
import {
  AlertTriangle,
  Check,
  Copy,
  CreditCard,
  ExternalLink,
  FileText,
  KeyRound,
  Loader2,
  SlidersHorizontal,
  UserRound,
} from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useWorkspace } from "@/lib/dashboard/workspace";
import { API_BASE_URL, DOCS_URL } from "@/lib/links";
import { cn } from "@/lib/utils";

type SectionId = "general" | "api" | "account" | "billing" | "danger";

const SECTIONS: { id: SectionId; label: string; icon: typeof SlidersHorizontal }[] = [
  { id: "general", label: "General", icon: SlidersHorizontal },
  { id: "api", label: "API & Integrations", icon: KeyRound },
  { id: "account", label: "Account", icon: UserRound },
  { id: "billing", label: "Billing", icon: CreditCard },
  { id: "danger", label: "Danger Zone", icon: AlertTriangle },
];

function CopyButton({ value, label = "Copy" }: { value: string; label?: string }) {
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
      {copied ? "Copied" : label}
    </Button>
  );
}

function Panel({
  title,
  description,
  children,
}: {
  title: string;
  description?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-xl border border-border bg-card p-6">
      <h2 className="text-base font-semibold">{title}</h2>
      {description ? (
        <p className="mt-1 text-sm text-muted-foreground">{description}</p>
      ) : null}
      <div className="mt-5">{children}</div>
    </section>
  );
}

function ComingSoon({ children }: { children: React.ReactNode }) {
  return (
    <div className="rounded-lg border border-dashed border-border bg-muted/40 px-4 py-6 text-center">
      <span className="inline-flex items-center rounded-full bg-secondary px-2.5 py-0.5 text-xs font-medium text-muted-foreground">
        Coming soon
      </span>
      <p className="mx-auto mt-3 max-w-md text-sm text-muted-foreground">{children}</p>
    </div>
  );
}

export default function SettingsPage() {
  const { activeProject, loading, renameProject, deleteProject } = useWorkspace();
  const [section, setSection] = useState<SectionId>("general");

  return (
    <div>
      <header className="mb-8">
        <h1 className="text-2xl font-semibold tracking-tight">Settings</h1>
        <p className="mt-1 text-sm text-muted-foreground">
          Manage this project and how you connect to ContextStore.
        </p>
      </header>

      <div className="grid gap-8 lg:grid-cols-[200px_1fr]">
        <nav className="flex gap-1 overflow-x-auto lg:flex-col lg:overflow-visible">
          {SECTIONS.map(({ id, label, icon: Icon }) => (
            <button
              key={id}
              type="button"
              onClick={() => setSection(id)}
              className={cn(
                "flex items-center gap-2.5 rounded-lg px-3 py-2 text-left text-sm font-medium whitespace-nowrap transition-colors",
                section === id
                  ? "bg-accent text-accent-foreground"
                  : "text-muted-foreground hover:bg-muted hover:text-foreground",
              )}
            >
              <Icon className="size-4 shrink-0" />
              {label}
            </button>
          ))}
        </nav>

        <div className="min-w-0 space-y-6">
          {section === "general" ? (
            <GeneralSection
              loading={loading}
              project={activeProject}
              onRename={renameProject}
            />
          ) : null}
          {section === "api" ? <ApiSection project={activeProject} /> : null}
          {section === "account" ? (
            <Panel title="Account">
              <ComingSoon>
                Personal accounts, sign-in, and team management are in development.
              </ComingSoon>
            </Panel>
          ) : null}
          {section === "billing" ? (
            <Panel title="Billing">
              <ComingSoon>
                ContextStore is currently self-hosted / free during early access.
              </ComingSoon>
            </Panel>
          ) : null}
          {section === "danger" ? (
            <DangerSection
              loading={loading}
              project={activeProject}
              onDelete={deleteProject}
            />
          ) : null}
        </div>
      </div>
    </div>
  );
}

function GeneralSection({
  loading,
  project,
  onRename,
}: {
  loading: boolean;
  project: ReturnType<typeof useWorkspace>["activeProject"];
  onRename: (tenantId: string, name: string) => Promise<void>;
}) {
  const [name, setName] = useState(project?.name ?? "");
  const [saving, setSaving] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [saved, setSaved] = useState(false);

  // Keep the input in sync once the project loads (it's null on first render).
  const [syncedFor, setSyncedFor] = useState<string | null>(null);
  if (project && syncedFor !== project.tenant_id) {
    setSyncedFor(project.tenant_id);
    setName(project.name);
  }

  if (loading) return <Panel title="General">{<Skeleton />}</Panel>;
  if (!project)
    return (
      <Panel title="General">
        <p className="text-sm text-muted-foreground">
          No project selected. Create one from the workspace switcher.
        </p>
      </Panel>
    );

  const trimmed = name.trim();
  const dirty = trimmed.length > 0 && trimmed !== project.name;

  async function save() {
    if (!project || !dirty || saving) return;
    setSaving(true);
    setError(null);
    setSaved(false);
    try {
      await onRename(project.tenant_id, trimmed);
      setSaved(true);
      setTimeout(() => setSaved(false), 2000);
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not rename the project.");
    } finally {
      setSaving(false);
    }
  }

  return (
    <Panel title="General" description="Details for the currently selected project.">
      <div className="space-y-5">
        <div className="space-y-2">
          <Label htmlFor="project-name">Project name</Label>
          <div className="flex items-center gap-2">
            <Input
              id="project-name"
              value={name}
              onChange={(e) => setName(e.target.value)}
              className="max-w-sm"
            />
            <Button type="button" size="sm" onClick={save} disabled={!dirty || saving}>
              {saving ? <Loader2 className="size-3.5 animate-spin" /> : null}
              {saved ? "Saved" : "Save"}
            </Button>
          </div>
          {error ? <p className="text-sm text-destructive">{error}</p> : null}
        </div>

        <div className="space-y-2">
          <Label>Tenant ID</Label>
          <div className="flex items-center gap-2">
            <code className="rounded-md border border-border bg-muted px-2.5 py-1.5 font-mono text-xs">
              {project.tenant_id}
            </code>
            <CopyButton value={project.tenant_id} />
          </div>
          <p className="text-xs text-muted-foreground">
            The graph this project writes to. Useful when debugging API calls.
          </p>
        </div>

        <div className="space-y-1.5">
          <Label>Created</Label>
          <p className="text-sm text-muted-foreground">
            {new Date(project.created_at).toLocaleDateString(undefined, {
              year: "numeric",
              month: "long",
              day: "numeric",
            })}
          </p>
        </div>
      </div>
    </Panel>
  );
}

function ApiSection({
  project,
}: {
  project: ReturnType<typeof useWorkspace>["activeProject"];
}) {
  const tenantNote = project
    ? `# Scoped to "${project.name}" (tenant ${project.tenant_id}) by the API key.`
    : "# Scoped to your project by the API key.";

  const snippet = [
    `curl -X POST ${API_BASE_URL}/v1/recall \\`,
    `  -H "Authorization: Bearer $CONTEXTSTORE_API_KEY" \\`,
    `  -H "Content-Type: application/json" \\`,
    `  -d '{"query": "What do we know so far?"}'`,
    tenantNote,
  ].join("\n");

  return (
    <Panel
      title="API & Integrations"
      description="Connect agents and jobs to this project."
    >
      <div className="space-y-6">
        <div className="flex flex-wrap gap-3">
          <Button variant="outline" size="sm" render={<Link href="/dashboard/api-keys" />}>
            <KeyRound className="size-3.5" />
            API keys
          </Button>
          <Button
            variant="outline"
            size="sm"
            render={
              <a href={DOCS_URL} target="_blank" rel="noopener noreferrer" />
            }
          >
            <FileText className="size-3.5" />
            Documentation
            <ExternalLink className="size-3 opacity-60" />
          </Button>
        </div>

        <div className="space-y-2">
          <div className="flex items-center justify-between">
            <Label>Recall from this project</Label>
            <CopyButton value={snippet} label="Copy snippet" />
          </div>
          <pre className="overflow-x-auto rounded-lg border border-border bg-muted p-4 font-mono text-xs leading-relaxed">
            {snippet}
          </pre>
          <p className="text-xs text-muted-foreground">
            Create a key for this project on the{" "}
            <Link href="/dashboard/api-keys" className="underline hover:text-foreground">
              API keys
            </Link>{" "}
            page — the tenant is derived from the key, never sent in the body.
          </p>
        </div>
      </div>
    </Panel>
  );
}

function DangerSection({
  loading,
  project,
  onDelete,
}: {
  loading: boolean;
  project: ReturnType<typeof useWorkspace>["activeProject"];
  onDelete: (tenantId: string, confirm: string) => Promise<void>;
}) {
  const [confirm, setConfirm] = useState("");
  const [deleting, setDeleting] = useState(false);
  const [error, setError] = useState<string | null>(null);

  if (loading) return <Panel title="Danger Zone">{<Skeleton />}</Panel>;
  if (!project)
    return (
      <Panel title="Danger Zone">
        <p className="text-sm text-muted-foreground">No project selected.</p>
      </Panel>
    );

  const matches = confirm === project.tenant_id;

  async function remove() {
    if (!project || !matches || deleting) return;
    setDeleting(true);
    setError(null);
    try {
      await onDelete(project.tenant_id, project.tenant_id);
      // onDelete navigates away on success; nothing more to do here.
    } catch (e) {
      setError(e instanceof Error ? e.message : "Could not delete the project.");
      setDeleting(false);
    }
  }

  return (
    <section className="rounded-xl border border-destructive/40 bg-card p-6">
      <h2 className="flex items-center gap-2 text-base font-semibold text-destructive">
        <AlertTriangle className="size-4" />
        Delete this project
      </h2>
      <p className="mt-1 text-sm text-muted-foreground">
        Permanently deletes <span className="font-medium text-foreground">{project.name}</span>,
        its entire knowledge graph, API keys, and history. This cannot be undone.
      </p>
      <div className="mt-5 space-y-2">
        <Label htmlFor="confirm-delete">
          Type{" "}
          <code className="font-mono text-xs text-foreground">{project.tenant_id}</code> to
          confirm
        </Label>
        <div className="flex items-center gap-2">
          <Input
            id="confirm-delete"
            value={confirm}
            onChange={(e) => setConfirm(e.target.value)}
            placeholder={project.tenant_id}
            className="max-w-sm"
            autoComplete="off"
          />
          <Button
            type="button"
            variant="destructive"
            size="sm"
            onClick={remove}
            disabled={!matches || deleting}
          >
            {deleting ? <Loader2 className="size-3.5 animate-spin" /> : null}
            Delete project
          </Button>
        </div>
        {error ? <p className="text-sm text-destructive">{error}</p> : null}
      </div>
    </section>
  );
}

function Skeleton() {
  return <div className="h-20 animate-pulse rounded-lg bg-muted" />;
}
