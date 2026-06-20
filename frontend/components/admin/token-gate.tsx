"use client";

import { useState, type FormEvent } from "react";
import { ShieldAlert } from "lucide-react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";
import { Label } from "@/components/ui/label";
import { useAdminAuth } from "@/lib/admin/auth";

// Shown whenever there is no admin token in the session (first visit, or after a
// 401 cleared it). Collects the ADMIN_TOKEN and hands it to the auth context;
// the token never goes to localStorage.
export function TokenGate() {
  const { setToken } = useAdminAuth();
  const [value, setValue] = useState("");

  function onSubmit(event: FormEvent) {
    event.preventDefault();
    const trimmed = value.trim();
    if (trimmed) setToken(trimmed);
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
          className="mb-4"
        />
        <Button type="submit" className="w-full" disabled={!value.trim()}>
          Enter console
        </Button>
      </form>
    </div>
  );
}
