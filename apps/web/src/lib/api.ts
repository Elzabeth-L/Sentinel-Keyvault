"use client";

const baseUrl = process.env.NEXT_PUBLIC_API_BASE_URL;

function publicOrigin(): string {
  if (!baseUrl) throw new Error("NEXT_PUBLIC_API_BASE_URL is required");
  return baseUrl.replace(/\/api\/v1\/?$/, "");
}

export async function api<T>(path: string, init?: RequestInit): Promise<T> {
  if (!baseUrl) throw new Error("NEXT_PUBLIC_API_BASE_URL is required");
  const response = await fetch(`${baseUrl}${path}`, {
    ...init,
    credentials: "include",
    headers: {
      "Content-Type": "application/json",
      "X-Correlation-ID": crypto.randomUUID(),
      ...init?.headers
    }
  });
  if (response.status === 401) {
    throw new Error("AUTHENTICATION_REQUIRED");
  }
  if (!response.ok) {
    const problem = await response.json().catch(() => ({ detail: response.statusText }));
    throw new Error(problem.detail ?? "Sentinel API request failed");
  }
  return response.status === 204 ? (undefined as T) : response.json();
}

export async function startLogin(tenantId?: string): Promise<void> {
  const query = tenantId ? `?tenant=${encodeURIComponent(tenantId)}` : "";
  const response = await fetch(`${publicOrigin()}/auth/login${query}`, {
    credentials: "include",
    cache: "no-store"
  });
  if (!response.ok) throw new Error("Unable to start Microsoft sign-in");
  const payload = (await response.json()) as { authorization_url: string };
  window.location.assign(payload.authorization_url);
}

export async function logout(): Promise<void> {
  await fetch(`${publicOrigin()}/auth/logout`, {
    method: "POST",
    credentials: "include"
  });
  window.location.assign("/");
}
