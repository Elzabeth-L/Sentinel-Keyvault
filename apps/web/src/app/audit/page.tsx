"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

type Event = {
  id: string;
  occurred_at: string;
  actor_id: string;
  action: string;
  entity_type: string;
  entity_id?: string;
  outcome: string;
  source_service: string;
  record_hash: string;
};

export default function AuditPage() {
  const query = useQuery({
    queryKey: ["audit"],
    queryFn: () => api<Event[]>("/audit/events?limit=250")
  });
  return (
    <div>
      <h1 className="text-3xl font-semibold">Audit Center</h1>
      <p className="mt-2 text-muted">Append-only evidence for identity, inventory, and operations.</p>
      <div className="panel mt-7 overflow-x-auto">
        <table className="w-full min-w-[900px] text-left text-sm">
          <thead className="text-muted">
            <tr>
              {["Time", "Action", "Entity", "Outcome", "Source", "Integrity"].map((item) => (
                <th className="border-b border-border px-5 py-3 font-medium" key={item}>{item}</th>
              ))}
            </tr>
          </thead>
          <tbody>
            {query.data?.map((event) => (
              <tr className="border-b border-border/60" key={event.id}>
                <td className="px-5 py-3">{new Date(event.occurred_at).toLocaleString()}</td>
                <td className="px-5 py-3 font-medium">{event.action}</td>
                <td className="px-5 py-3 text-muted">{event.entity_type}:{event.entity_id}</td>
                <td className="px-5 py-3 text-success">{event.outcome}</td>
                <td className="px-5 py-3">{event.source_service}</td>
                <td className="px-5 py-3 font-mono text-xs text-muted">{event.record_hash.slice(0, 12)}</td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
    </div>
  );
}

