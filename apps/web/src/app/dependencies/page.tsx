"use client";

import { useQuery } from "@tanstack/react-query";
import { useEffect, useState } from "react";
import { DependencyGraph } from "@/components/topology/dependency-graph";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

type Resource = {
  id: string;
  name: string;
  azure_resource_id: string;
  resource_type: string;
  resource_group: string;
};

type ResourcePage = {
  items: Resource[];
};

type Graph = {
  root_resource_id: string;
  truncated: boolean;
  nodes: {
    id: string;
    label: string;
    resource_type: string;
    resource_group: string;
  }[];
  edges: {
    id: string;
    source: string;
    target: string;
    relationship_type: string;
  }[];
};

export default function DependenciesPage() {
  const [input, setInput] = useState("");
  const [root, setRoot] = useState("");
  useEffect(() => {
    const initialRoot = new URLSearchParams(window.location.search).get("root") ?? "";
    setInput(initialRoot);
    setRoot(initialRoot);
  }, []);
  const resources = useQuery({
    queryKey: ["dependency-resources"],
    queryFn: () => api<ResourcePage>("/inventory/resources?limit=200")
  });
  const graph = useQuery({
    queryKey: ["graph", root],
    queryFn: () =>
      api<Graph>(
        `/relationships/graph?root_resource_id=${encodeURIComponent(root)}&max_depth=4&max_nodes=1500`
      ),
    enabled: Boolean(root)
  });
  const selectedResource = resources.data?.items.find((resource) => resource.id === root);
  const explore = () => {
    const value = input.trim();
    const normalizedValue = value.toLowerCase();
    const resource = resources.data?.items.find(
      (item) =>
        item.id.toLowerCase() === normalizedValue ||
        item.azure_resource_id.toLowerCase() === normalizedValue
    );
    setRoot(resource?.id ?? value);
  };

  return (
    <div>
      <h1 className="text-3xl font-semibold">Dependency Explorer</h1>
      <p className="mt-2 text-muted">Bounded, evidence-backed Azure dependency topology.</p>
      <div className="mt-5 flex max-w-3xl gap-3">
        <input
          list="dependency-resources"
          className="min-w-0 flex-1 rounded-lg border border-border bg-slate-950/70 px-3 py-2"
          placeholder="Paste an Azure resource ID or select an inventoried resource"
          value={input}
          onChange={(event) => setInput(event.target.value)}
          onKeyDown={(event) => {
            if (event.key === "Enter") explore();
          }}
        />
        <datalist id="dependency-resources">
          {resources.data?.items.map((resource) => (
            <option key={resource.id} value={resource.azure_resource_id}>
              {resource.name} - {resource.resource_type}
            </option>
          ))}
        </datalist>
        <Button onClick={explore} disabled={!input.trim() || graph.isFetching}>
          Explore
        </Button>
      </div>
      <p className="mt-2 max-w-3xl text-xs text-muted">
        Azure ARM resource IDs and Sentinel inventory UUIDs are both supported.
      </p>
      {selectedResource ? (
        <p className="mt-3 text-sm text-muted">
          Showing dependencies for{" "}
          <span className="font-medium text-slate-200">{selectedResource.name}</span>
          {" · "}
          {selectedResource.resource_type}
        </p>
      ) : null}
      {resources.error || graph.error ? (
        <p className="mt-3 text-sm text-red-400">
          {(graph.error ?? resources.error) instanceof Error
            ? (graph.error ?? resources.error)?.message
            : "Unable to load dependency data"}
        </p>
      ) : null}
      <section className="panel mt-5 h-[70vh] overflow-hidden">
        {graph.data ? (
          graph.data.nodes.length ? (
            <div className="relative h-full">
              <DependencyGraph graph={graph.data} />
              {!graph.data.edges.length ? (
                <div className="pointer-events-none absolute bottom-4 left-1/2 -translate-x-1/2 rounded-lg border border-border bg-slate-950/90 px-4 py-2 text-center text-xs text-muted shadow-lg">
                  This resource is inventoried, but no explicit Azure resource references were
                  discovered for it.
                </div>
              ) : null}
            </div>
          ) : (
            <div className="grid h-full place-items-center px-6 text-center text-muted">
              No relationship projection exists for this resource yet. Refresh inventory and try
              again.
            </div>
          )
        ) : (
          <div className="grid h-full place-items-center text-muted">
            {graph.isFetching ? "Building graph..." : "Choose a resource to inspect its blast radius."}
          </div>
        )}
      </section>
    </div>
  );
}
