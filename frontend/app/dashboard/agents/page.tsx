"use client";

import { useState } from "react";
import { Loader2, PlusIcon, Trash2Icon } from "lucide-react";

import { AgentDialog, type AgentFormValues } from "@/components/agents/agent-dialog";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { useAgents } from "@/lib/hooks/use-agents";

export default function AgentsPage() {
  const { agents, loading, error, create, remove, reload } = useAgents();
  const [dialogOpen, setDialogOpen] = useState(false);

  async function handleSubmit(values: AgentFormValues) {
    await create({ name: values.name.trim(), description: values.description.trim() || null });
  }

  return (
    <div className="flex flex-col gap-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-semibold">Agents</h1>
          <p className="text-muted-foreground">
            The registry of named agents that write into shared memory.
          </p>
        </div>
        <Button onClick={() => setDialogOpen(true)}>
          <PlusIcon />
          New agent
        </Button>
      </div>

      {error ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-3 py-10 text-center">
            <p className="max-w-sm text-sm text-destructive">{error}</p>
            <Button size="sm" variant="outline" onClick={() => void reload()}>
              Retry
            </Button>
          </CardContent>
        </Card>
      ) : loading ? (
        <div className="flex items-center gap-2 text-muted-foreground">
          <Loader2 className="size-4 animate-spin" /> Loading agents...
        </div>
      ) : agents.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
            <p className="font-medium">No agents yet</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Register the agents that write into your shared memory graph.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
          {agents.map((agent) => (
            <Card key={agent.id}>
              <CardContent className="flex flex-col gap-2">
                <div className="flex items-center justify-between">
                  <span className="font-medium">{agent.name}</span>
                  <Button variant="ghost" size="icon-sm" onClick={() => remove(agent.id)}>
                    <Trash2Icon />
                  </Button>
                </div>
                {agent.description && (
                  <p className="text-sm text-muted-foreground">{agent.description}</p>
                )}
              </CardContent>
            </Card>
          ))}
        </div>
      )}

      <AgentDialog open={dialogOpen} onOpenChange={setDialogOpen} onSubmit={handleSubmit} />
    </div>
  );
}
