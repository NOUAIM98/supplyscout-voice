import type { Metadata } from "next";
import Link from "next/link";
import { Compass } from "lucide-react";
import { QueryProvider } from "@/providers/query-provider";
import "./globals.css";

export const metadata: Metadata = {
  title: "SupplyScout Voice",
  description: "Structured supplier quotes for confident procurement decisions.",
};

export default function RootLayout({ children }: Readonly<{ children: React.ReactNode }>) {
  return (
    <html lang="en">
      <body>
        <QueryProvider>
          <header className="border-b border-border bg-background/95">
            <div className="mx-auto flex h-16 max-w-7xl items-center justify-between px-5 lg:px-8">
              <Link href="/" className="flex items-center gap-2 font-semibold tracking-tight">
                <span className="grid size-8 place-items-center rounded-md bg-foreground text-background"><Compass className="size-4" /></span>
                SupplyScout <span className="text-muted-foreground">Voice</span>
              </Link>
              <div className="flex items-center gap-3 text-sm"><span className="status-dot" /> Demo workspace</div>
            </div>
          </header>
          {children}
        </QueryProvider>
      </body>
    </html>
  );
}
