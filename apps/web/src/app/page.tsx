"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

type Profile = {
  display_name: string;
  roles: string[];
  permissions: string[];
};
type ResourcePage = { items: unknown[] };
type AuditEvent = { id: string };

export default function Dashboard() {
  const profile = useQuery({ queryKey: ["profile"], queryFn: () => api<Profile>("/auth/profile") });
  const resources = useQuery({
    queryKey: ["resources", "summary"],
    queryFn: () => api<ResourcePage>("/inventory/resources?limit=200")
  });
  const audit = useQuery({
    queryKey: ["audit", "summary"],
    queryFn: () => api<AuditEvent[]>("/audit/events?limit=25")
  });
  const cards = [
    ["Discovered resources", resources.data?.items.length ?? "—"],
    ["Recent audit events", audit.data?.length ?? "—"],
    ["Effective permissions", profile.data?.permissions.length ?? "—"]
  ];
  return (
    <div>
      <p className="text-sm text-primary">Operational control plane</p>
      <h1 className="mt-1 text-3xl font-semibold">
        {profile.data ? `Welcome, ${profile.data.display_name}` : "Sentinel overview"}
      </h1>
      <p className="mt-2 text-muted">Current estate posture and governed change activity.</p>
      <div className="mt-8 grid gap-4 md:grid-cols-3">
        {cards.map(([label, value]) => (
          <section className="panel p-6" key={label}>
            <div className="text-sm text-muted">{label}</div>
            <div className="mt-3 text-3xl font-semibold">{value}</div>
          </section>
        ))}
      </div>
    </div>
  );
}

