"use client";

import { QueryClient, QueryClientProvider } from "@tanstack/react-query";
import { useState } from "react";

export const queryClientDefaults = {
  queries: { staleTime: 30_000, retry: 2, refetchOnWindowFocus: false },
  mutations: { retry: false },
} as const;

export function QueryProvider({ children }: { children: React.ReactNode }) {
  const [client] = useState(() => new QueryClient({
    defaultOptions: queryClientDefaults,
  }));
  return <QueryClientProvider client={client}>{children}</QueryClientProvider>;
}
