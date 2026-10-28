"use client";

import type { ReactNode } from "react";
import { SWRConfig } from "swr";

import { DrawerProvider } from "./drawer-context";
import { ToastProvider } from "./toaster";

export function Providers({ children }: { children: ReactNode }) {
  return (
    <SWRConfig value={{ revalidateOnFocus: true, shouldRetryOnError: false }}>
      <ToastProvider>
        <DrawerProvider>{children}</DrawerProvider>
      </ToastProvider>
    </SWRConfig>
  );
}
