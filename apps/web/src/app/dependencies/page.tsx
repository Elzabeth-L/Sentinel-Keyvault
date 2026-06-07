"use client";

import { useQuery } from "@tanstack/react-query";
import { useState } from "react";
import { DependencyGraph } from "@/components/topology/dependency-graph";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

export default function DependenciesPage() {
  const [input, setInput] = useState("");
  const [root, setRoot] = useState("");
  const graph = useQuery({
    queryKey: ["graph", root],
    queryFn: () =>
      api<any>(`/relationships/graph?root_resource_id=${root}&max_depth=4&max_nodes=1500`),
    enabled: Boolean(root)
  });
  return (
    <div>
      <h1 className="text-3xl font-semibold">Dependency Explorer</h1>
      <p className="mt-2 text-muted">Bounded, evidence-backed Azure dependency topology.</p>
      <div className="mt-5 flex max-w-3xl gap-3">
        <input
          className="min-w-0 flex-1 rounded-lg border border-border bg-slate-950/70 px-3 py-2"
          placeholder="Sentinel resource UUID"
          value={input}
          onChange={(event) => setInput(event.target.value)}
        />
        <Button onClick={() => setRoot(input.trim())}>Explore</Button>
      </div>
      <section className="panel mt-5 h-[70vh] overflow-hidden">
        {graph.data ? (
          <DependencyGraph graph={graph.data} />
        ) : (
          <div className="grid h-full place-items-center text-muted">
            {graph.isFetching ? "Building graph..." : "Choose a resource to inspect its blast radius."}
          </div>
        )}
      </section>
    </div>
  );
}

