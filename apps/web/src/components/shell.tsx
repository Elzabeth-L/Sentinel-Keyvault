"use client";

import {
  Boxes,
  FileClock,
  Gauge,
  GitFork,
  LogOut,
  Settings,
  ShieldCheck
} from "lucide-react";
import Link from "next/link";
import { usePathname } from "next/navigation";
import { PropsWithChildren } from "react";
import { logout } from "@/lib/api";
import { cn } from "@/lib/utils";

const links = [
  ["/", "Dashboard", Gauge],
  ["/resources", "Resource Explorer", Boxes],
  ["/dependencies", "Dependency Explorer", GitFork],
  ["/audit", "Audit Center", FileClock],
  ["/settings", "Settings", Settings]
] as const;

export function Shell({ children }: PropsWithChildren) {
  const pathname = usePathname();
  return (
    <div className="min-h-screen lg:grid lg:grid-cols-[260px_1fr]">
      <aside className="border-r border-border bg-slate-950/55 p-5">
        <div className="mb-9 flex items-center gap-3">
          <div className="grid size-10 place-items-center rounded-xl bg-primary/15 text-primary">
            <ShieldCheck />
          </div>
          <div>
            <div className="font-semibold">Sentinel</div>
            <div className="text-xs text-muted">Change Intelligence</div>
          </div>
        </div>
        <nav className="space-y-1">
          {links.map(([href, label, Icon]) => (
            <Link
              key={href}
              href={href}
              className={cn(
                "flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted transition hover:bg-slate-800/70 hover:text-white",
                pathname === href && "bg-primary/10 text-primary"
              )}
            >
              <Icon size={18} />
              {label}
            </Link>
          ))}
        </nav>
        <button
          className="mt-8 flex items-center gap-3 rounded-lg px-3 py-2.5 text-sm text-muted hover:text-white"
          onClick={() => void logout()}
        >
          <LogOut size={18} /> Sign out
        </button>
      </aside>
      <main className="min-w-0 p-5 md:p-8">{children}</main>
    </div>
  );
}
