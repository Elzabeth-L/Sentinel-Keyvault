"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { useState } from "react";
import { Button } from "@/components/ui/button";
import { api } from "@/lib/api";

type Resource = {
  id: string;
  name: string;
  resource_type: string;
  resource_group: string;
  location?: string;
  state: string;
};
type ResourcePage = { items: Resource[]; page: { next_cursor?: string } };
type Subscription = {
  id: string;
  azure_subscription_id: string;
  display_name: string;
  state: string;
};

export default function ResourcesPage() {
  const [search, setSearch] = useState("");
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["resources", search],
    queryFn: () =>
      api<ResourcePage>(`/inventory/resources?limit=200&search=${encodeURIComponent(search)}`)
  });
  const subscriptions = useQuery({
    queryKey: ["subscriptions"],
    queryFn: () => api<Subscription[]>("/inventory/subscriptions")
  });
  const discover = useMutation({
    mutationFn: () =>
      api<Subscription[]>("/inventory/subscriptions/discover", { method: "POST" }),
    onSuccess: (items) => queryClient.setQueryData(["subscriptions"], items)
  });
  const synchronize = useMutation({
    mutationFn: () =>
      api("/inventory/sync-jobs", {
        method: "POST",
        headers: { "Idempotency-Key": crypto.randomUUID() },
        body: JSON.stringify({
          mode: "incremental",
          scope: {
            subscription_ids: subscriptions.data?.map((item) => item.azure_subscription_id) ?? []
          }
        })
      })
  });
  return (
    <div>
      <h1 className="text-3xl font-semibold">Resource Explorer</h1>
      <p className="mt-2 text-muted">Tenant-scoped Azure inventory from Resource Graph.</p>
      <div className="mt-5 flex flex-wrap gap-3">
        <Button variant="secondary" onClick={() => discover.mutate()} disabled={discover.isPending}>
          Discover subscriptions
        </Button>
        <Button
          onClick={() => synchronize.mutate()}
          disabled={synchronize.isPending || !subscriptions.data?.length}
        >
          Refresh inventory
        </Button>
        <span className="self-center text-sm text-muted">
          {subscriptions.data?.length ?? 0} subscriptions registered
        </span>
      </div>
      <div className="panel mt-5 overflow-hidden">
        <div className="border-b border-border p-4">
          <input
            className="w-full max-w-md rounded-lg border border-border bg-slate-950/70 px-3 py-2 outline-none focus:border-primary"
            placeholder="Search name or Azure resource ID"
            value={search}
            onChange={(event) => setSearch(event.target.value)}
          />
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[800px] text-left text-sm">
            <thead className="text-muted">
              <tr>
                {["Name", "Type", "Resource group", "Location", "State"].map((item) => (
                  <th className="border-b border-border px-5 py-3 font-medium" key={item}>{item}</th>
                ))}
              </tr>
            </thead>
            <tbody>
              {query.data?.items.map((resource) => (
                <tr className="border-b border-border/60 hover:bg-slate-800/30" key={resource.id}>
                  <td className="px-5 py-3 font-medium">{resource.name}</td>
                  <td className="px-5 py-3 text-muted">{resource.resource_type}</td>
                  <td className="px-5 py-3">{resource.resource_group}</td>
                  <td className="px-5 py-3">{resource.location ?? "global"}</td>
                  <td className="px-5 py-3 text-success">{resource.state}</td>
                </tr>
              ))}
            </tbody>
          </table>
        </div>
      </div>
    </div>
  );
}
