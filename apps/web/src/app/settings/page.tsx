"use client";

import { useQuery } from "@tanstack/react-query";
import { api } from "@/lib/api";

type Profile = {
  tenant_id: string;
  entra_tenant_id: string;
  display_name: string;
  principal_name?: string;
  roles: string[];
  permissions: string[];
};

export default function SettingsPage() {
  const profile = useQuery({ queryKey: ["profile"], queryFn: () => api<Profile>("/auth/profile") });
  return (
    <div>
      <h1 className="text-3xl font-semibold">Settings</h1>
      <p className="mt-2 text-muted">Identity, tenant, and effective Sentinel access.</p>
      <section className="panel mt-7 max-w-3xl p-6">
        <dl className="grid gap-5 sm:grid-cols-2">
          <div><dt className="text-sm text-muted">Signed in as</dt><dd className="mt-1">{profile.data?.principal_name}</dd></div>
          <div><dt className="text-sm text-muted">Entra tenant</dt><dd className="mt-1 font-mono text-sm">{profile.data?.entra_tenant_id}</dd></div>
          <div><dt className="text-sm text-muted">Roles</dt><dd className="mt-1">{profile.data?.roles.join(", ")}</dd></div>
          <div><dt className="text-sm text-muted">Permissions</dt><dd className="mt-1">{profile.data?.permissions.length ?? 0}</dd></div>
        </dl>
      </section>
    </div>
  );
}

