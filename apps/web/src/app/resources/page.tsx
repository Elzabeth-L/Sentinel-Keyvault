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
  last_sync_at?: string;
};

export default function ResourcesPage() {
  const [search, setSearch] = useState("");
  const [selectedSubscriptionId, setSelectedSubscriptionId] = useState<string | null>(null);
  const queryClient = useQueryClient();
  const query = useQuery({
    queryKey: ["resources", selectedSubscriptionId, search],
    queryFn: () => {
      const parameters = new URLSearchParams({limit: "200", search});
      if (selectedSubscriptionId) {
        parameters.set("subscription_id", selectedSubscriptionId);
      }
      return api<ResourcePage>(`/inventory/resources?${parameters.toString()}`);
    }
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
  const operationError = discover.error ?? synchronize.error ?? subscriptions.error ?? query.error;
  const selectedSubscription = subscriptions.data?.find(
    (subscription) => subscription.id === selectedSubscriptionId
  );
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
      {operationError ? (
        <p className="mt-3 text-sm text-red-400">
          {operationError instanceof Error ? operationError.message : "Azure inventory request failed"}
        </p>
      ) : null}
      <div className="panel mt-5 overflow-hidden">
        <div className="border-b border-border px-5 py-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="text-lg font-semibold">Azure subscriptions</h2>
              <p className="mt-1 text-sm text-muted">
                Select a subscription to filter the resource inventory.
              </p>
            </div>
            <Button
              variant={selectedSubscriptionId === null ? "primary" : "secondary"}
              onClick={() => setSelectedSubscriptionId(null)}
            >
              All subscriptions
            </Button>
          </div>
        </div>
        <div className="overflow-x-auto">
          <table className="w-full min-w-[760px] text-left text-sm">
            <thead className="text-muted">
              <tr>
                {["Name", "Subscription ID", "State", "Last inventory sync"].map((item) => (
                  <th className="border-b border-border px-5 py-3 font-medium" key={item}>
                    {item}
                  </th>
                ))}
              </tr>
            </thead>
            <tbody>
              {subscriptions.data?.map((subscription) => (
                <tr
                  className={`cursor-pointer border-b border-border/60 transition hover:bg-slate-800/50 ${
                    selectedSubscriptionId === subscription.id
                      ? "bg-sky-500/10 ring-1 ring-inset ring-primary/50"
                      : ""
                  }`}
                  key={subscription.id}
                  onClick={() => setSelectedSubscriptionId(subscription.id)}
                >
                  <td className="px-5 py-3 font-medium">
                    <button
                      className="text-left hover:text-primary"
                      onClick={() => setSelectedSubscriptionId(subscription.id)}
                      type="button"
                    >
                      {subscription.display_name}
                    </button>
                  </td>
                  <td className="px-5 py-3 font-mono text-xs text-muted">
                    {subscription.azure_subscription_id}
                  </td>
                  <td className="px-5 py-3 text-success">{subscription.state}</td>
                  <td className="px-5 py-3 text-muted">
                    {subscription.last_sync_at
                      ? new Date(subscription.last_sync_at).toLocaleString()
                      : "Not synchronized"}
                  </td>
                </tr>
              ))}
              {!subscriptions.isLoading && !subscriptions.data?.length ? (
                <tr>
                  <td className="px-5 py-5 text-muted" colSpan={4}>
                    No subscriptions discovered yet.
                  </td>
                </tr>
              ) : null}
            </tbody>
          </table>
        </div>
      </div>
      <div className="panel mt-5 overflow-hidden">
        <div className="border-b border-border p-4">
          <div className="flex flex-wrap items-center justify-between gap-3">
            <div>
              <h2 className="font-semibold">
                {selectedSubscription?.display_name ?? "All subscription resources"}
              </h2>
              <p className="mt-1 text-sm text-muted">
                {query.data?.items.length ?? 0} resources shown
              </p>
            </div>
            <input
              className="w-full max-w-md rounded-lg border border-border bg-slate-950/70 px-3 py-2 outline-none focus:border-primary"
              placeholder="Search name or Azure resource ID"
              value={search}
              onChange={(event) => setSearch(event.target.value)}
            />
          </div>
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
