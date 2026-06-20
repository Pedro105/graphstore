"use client";

import { useState, type FormEvent } from "react";

import { Button } from "@/components/ui/button";
import { Input } from "@/components/ui/input";

const EMAIL_PATTERN = /^[^\s@]+@[^\s@]+\.[^\s@]+$/;

export function WaitlistFooter() {
  const [email, setEmail] = useState("");
  const [error, setError] = useState<string | null>(null);
  const [submitted, setSubmitted] = useState(false);

  function handleSubmit(event: FormEvent) {
    event.preventDefault();
    if (!EMAIL_PATTERN.test(email)) {
      setError("Enter a valid email address.");
      return;
    }
    setError(null);
    setSubmitted(true);
  }

  return (
    <footer className="bg-background">
      <div className="mx-auto max-w-5xl px-6 py-20">
        <div className="mx-auto max-w-lg text-center">
          <h2 className="text-4xl font-light leading-tight text-foreground">
            Give your agents memory.
            <br />
            <span className="italic">Start today.</span>
          </h2>
          <p className="mt-3 text-muted-foreground">
            No infrastructure to manage. Free tier available. Join the waitlist
            for early access to hosted ContextStore.
          </p>
          {submitted ? (
            <p className="mt-6 rounded-lg border border-border bg-card px-4 py-3 text-sm">
              You&apos;re on the list -- we&apos;ll be in touch.
            </p>
          ) : (
            <form onSubmit={handleSubmit} className="mt-6 flex flex-col gap-2 sm:flex-row">
              <Input
                type="email"
                placeholder="you@company.com"
                value={email}
                onChange={(event) => setEmail(event.target.value)}
                aria-invalid={error ? true : undefined}
                className="sm:flex-1"
              />
              <Button type="submit">Join waitlist</Button>
            </form>
          )}
          {error && <p className="mt-2 text-sm text-destructive">{error}</p>}
        </div>
        <p className="mt-12 text-center text-xs text-muted-foreground">
          contextstore — a GraphRAG memory layer for AI workflows
        </p>
      </div>
    </footer>
  );
}
