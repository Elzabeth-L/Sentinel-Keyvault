"use client";

import { useQuery } from "@tanstack/react-query";
import { PropsWithChildren, useState } from "react";
import { Button } from "@/components/ui/button";
import { api, startLogin } from "@/lib/api";

export function AuthGate({ children }: PropsWithChildren) {
  const [tenantId, setTenantId] = useState("");
  const profile = useQuery({
    queryKey: ["session-profile"],
    queryFn: () => api("/auth/profile"),
    retry: false
  });

  if (profile.isLoading) {
    return <div className="grid min-h-screen place-items-center text-muted">Checking session...</div>;
  }

  if (profile.isError) {
    return (
      <main className="grid min-h-screen place-items-center px-6">
        <section className="panel max-w-xl p-10">
          <div className="mb-3 text-xs font-semibold uppercase tracking-[0.24em] text-primary">
            Azure Change Intelligence
          </div>
          <h1 className="text-4xl font-semibold">Understand the blast radius before the change.</h1>
          <p className="mt-5 leading-7 text-muted">
            Sentinel maps dependencies, assesses risk, governs execution, and preserves audit
            evidence across your Azure estate.
          </p>
          <label className="mt-7 block text-sm font-medium" htmlFor="tenant-id">
            Microsoft Entra tenant ID
          </label>
          <input
            id="tenant-id"
            className="mt-2 w-full rounded-lg border border-border bg-slate-950/70 px-3 py-2 outline-none focus:border-primary"
            placeholder="Optional for multi-tenant account selection"
            value={tenantId}
            onChange={(event) => setTenantId(event.target.value)}
          />
          <Button
            className="mt-5 w-full"
            onClick={() => startLogin(tenantId.trim() || undefined)}
          >
            Sign in with Microsoft
          </Button>
        </section>
      </main>
    );
  }
  return children;
}
