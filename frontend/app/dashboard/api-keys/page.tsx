"use client";

import { KeyRound, Trash2Icon } from "lucide-react";

import { Badge } from "@/components/ui/badge";
import { Button } from "@/components/ui/button";
import { Card, CardContent } from "@/components/ui/card";
import { Skeleton } from "@/components/ui/skeleton";
import { useApiKeys } from "@/lib/hooks/use-api-keys";

function formatDate(value: string | null): string {
  if (!value) return "never";
  const date = new Date(value);
  return Number.isNaN(date.getTime()) ? "unknown" : date.toLocaleDateString();
}

export default function ApiKeysPage() {
  const { apiKeys, loading, error, remove, reload } = useApiKeys();

  return (
    <div className="flex flex-col gap-6">
      <div>
        <h1 className="text-2xl font-semibold">API Keys</h1>
        <p className="text-muted-foreground">
          Keys that grant programmatic access to your tenant. New keys are
          issued by an operator; you can review and revoke existing keys here.
        </p>
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
        <div className="flex flex-col gap-2">
          {Array.from({ length: 3 }).map((_, i) => (
            <Card key={i} size="sm">
              <CardContent className="flex items-center justify-between gap-3">
                <div className="flex flex-col gap-1.5">
                  <Skeleton className="h-4 w-32" />
                  <Skeleton className="h-3 w-56" />
                </div>
              </CardContent>
            </Card>
          ))}
        </div>
      ) : apiKeys.length === 0 ? (
        <Card>
          <CardContent className="flex flex-col items-center gap-2 py-10 text-center">
            <KeyRound className="size-6 text-muted-foreground" />
            <p className="font-medium">No keys yet</p>
            <p className="max-w-sm text-sm text-muted-foreground">
              Ask an operator to issue an API key for this tenant -- it&apos;ll
              show up here.
            </p>
          </CardContent>
        </Card>
      ) : (
        <div className="flex flex-col gap-2">
          {apiKeys.map((apiKey) => {
            const revoked = apiKey.revoked_at !== null;
            return (
              <Card key={apiKey.id} size="sm">
                <CardContent className="flex items-center justify-between gap-3">
                  <div className="flex flex-col gap-0.5">
                    <div className="flex items-center gap-2">
                      <span className="text-sm font-medium">
                        {apiKey.name ?? "Unnamed key"}
                      </span>
                      {revoked && <Badge variant="outline">Revoked</Badge>}
                    </div>
                    <span className="font-mono text-xs text-muted-foreground">
                      created {formatDate(apiKey.created_at)} · last used{" "}
                      {formatDate(apiKey.last_used_at)}
                    </span>
                  </div>
                  {!revoked && (
                    <Button
                      variant="ghost"
                      size="icon-sm"
                      onClick={() => remove(apiKey.id)}
                    >
                      <Trash2Icon />
                    </Button>
                  )}
                </CardContent>
              </Card>
            );
          })}
        </div>
      )}
    </div>
  );
}
