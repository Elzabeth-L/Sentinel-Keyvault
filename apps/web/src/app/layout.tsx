import type { Metadata } from "next";
import "./globals.css";
import { AppProviders } from "@/providers/app-providers";
import { AuthGate } from "@/components/auth-gate";
import { Shell } from "@/components/shell";

export const metadata: Metadata = {
  title: "Sentinel",
  description: "Azure Change Intelligence Platform"
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <AppProviders>
          <AuthGate>
            <Shell>{children}</Shell>
          </AuthGate>
        </AppProviders>
      </body>
    </html>
  );
}

