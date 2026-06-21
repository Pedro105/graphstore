"use client";

import { useState, type FormEvent } from "react";
import { Loader2, ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAdminAuth } from "@/lib/admin/auth";

// The only thing rendered for an unauthenticated/unvalidated visit. Collects the
// ADMIN_TOKEN and hands it to the auth context, which validates it against the
// backend before any data page is allowed to mount. The token never goes to
// localStorage.
export function TokenGate() {
  const { submit, status, error } = useAdminAuth();
  const [value, setValue] = useState("");
  const validating = status === "validating";

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (trimmed && !validating) submit(trimmed);
  }

  return (
    <div className="flex min-h-screen items-center justify-center bg-background p-6">
      <form
        onSubmit={onSubmit}
        className="w-full max-w-sm rounded-xl border border-amber-500/40 bg-card p-6 shadow-sm"
      >
        <div className="mb-4 flex items-center gap-2 text-amber-600 dark:text-amber-500">
          <ShieldAlert className="size-5" />
          <span className="text-sm font-semibold tracking-wide uppercase">
            Operator Admin
          </span>
        </div>
        <p className="mb-4 text-sm text-muted-foreground">
          Enter the operator <code className="font-mono">ADMIN_TOKEN</code> to
          access the cross-tenant admin console. It is held for this session
          only.
        </p>
        <Label htmlFor="admin-token" className="mb-1.5 block text-sm">
          Admin token
        </Label>
        <Input
          id="admin-token"
          type="password"
          autoComplete="off"
          value={value}
          onChange={(e) => setValue(e.target.value)}
          placeholder="paste ADMIN_TOKEN"
          disabled={validating}
          className="mb-2"
        />
        {error ? (
          <p className="mb-3 text-sm text-destructive">{error}</p>
        ) : (
          <div className="mb-3" />
        )}
        <Button
          type="submit"
          className="w-full"
          disabled={!value.trim() || validating}
        >
          {validating ? (
            <>
              <Loader2 className="size-4 animate-spin" />
              Validating…
            </>
          ) : (
            "Enter console"
          )}
        </Button>
      </form>
    </div>
  );
}
