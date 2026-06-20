"use client";

import { useEffect, useState } from "react";
import Link from "next/link";

import {
  Card,
  CardContent,
  CardDescription,
  CardHeader,
  CardTitle,
} from "@/components/ui/card";
import { fetchGraph } from "@/lib/api";
import { useAgents } from "@/lib/hooks/use-agents";
import { useApiKeys } from "@/lib/hooks/use-api-keys";
import { useFocusAreas } from "@/lib/hooks/use-focus-areas";
import { useFrameworks } from "@/lib/hooks/use-frameworks";
import { useWorkspace } from "@/lib/dashboard/workspace";

export default function DashboardPage() {
  const { activeProject } = useWorkspace();
  const { agents } = useAgents();
  const { frameworks } = useFrameworks();
  const { focusAreas } = useFocusAreas();
  const { apiKeys } = useApiKeys();
  const [graphCounts, setGraphCounts] = useState<{
    entities: number;
    relations: number;
  } | null>(null);

  useEffect(() => {
    fetchGraph()
      .then((snapshot) =>
        setGraphCounts({
          entities: snapshot.entities.length,
          relations: snapshot.relations.length,
        }),
      )
      .catch(() => setGraphCounts(null));
  }, []);

  const connectedFrameworks = frameworks.filter(
    (framework) => framework.connected,
  ).length;

  const stats = [
    {
      label: "Entities in graph",
      value: graphCounts ? graphCounts.entities : "--",
      href: "/dashboard/memories",
    },
    {
      label: "Relations in graph",
      value: graphCounts ? graphCounts.relations : "--",
      href: "/dashboard/memories",
    },
    {
      label: "Agents registered",
      value: agents.length,
      href: "/dashboard/agents",
    },
    {
      label: "Frameworks connected",
      value: `${connectedFrameworks}/${frameworks.length}`,
      href: "/dashboard/frameworks",
    },
    {
      label: "Focus areas",
      value: focusAreas.length,
      href: "/dashboard/focus-areas",
    },
    { label: "API keys", value: apiKeys.length, href: "/dashboard/api-keys" },
  ];

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">Overview</h1>
        <p className="text-muted-foreground">
          {activeProject ? (
            <>
              A summary of{" "}
              <span className="font-medium text-foreground">
                {activeProject.name}
              </span>
              .
            </>
          ) : (
            "A summary of your memory workspace."
          )}
        </p>
      </div>

      <div className="grid grid-cols-1 gap-4 sm:grid-cols-2 lg:grid-cols-3">
        {stats.map((stat) => (
          <Link key={stat.label} href={stat.href}>
            <Card className="transition-colors hover:bg-muted/40">
              <CardHeader>
                <CardDescription>{stat.label}</CardDescription>
                <CardTitle className="text-3xl font-semibold">
                  {stat.value}
                </CardTitle>
              </CardHeader>
            </Card>
          </Link>
        ))}
      </div>

      <Card>
        <CardHeader>
          <CardTitle>Get started</CardTitle>
          <CardDescription>
            Head to Memories to write a fact and watch the graph grow, or set up
            the Agents that will write into it.
          </CardDescription>
        </CardHeader>
        <CardContent className="flex gap-2">
          <Link
            href="/dashboard/memories"
            className="text-sm font-medium text-primary underline-offset-4 hover:underline"
          >
            Open Memories workspace
          </Link>
        </CardContent>
      </Card>
    </div>
  );
}
