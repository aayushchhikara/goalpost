"use client";

import { usePathname } from "next/navigation";
import { createContext, useContext, useMemo, useState, type ReactNode } from "react";

type Drawer = { taskId: string | null; openTask: (id: string) => void; close: () => void };

const DrawerContext = createContext<Drawer>({ taskId: null, openTask: () => {}, close: () => {} });

/** The task drawer lives in the shell, so pages kept alive by Activity never hold it open. */
export function DrawerProvider({ children }: { children: ReactNode }) {
  const pathname = usePathname();
  const [taskId, setTaskId] = useState<string | null>(null);
  const [openedOn, setOpenedOn] = useState(pathname);
  // Close on navigation (adjusting state during render instead of in an effect).
  if (openedOn !== pathname) {
    setOpenedOn(pathname);
    setTaskId(null);
  }
  const value = useMemo(
    () => ({ taskId, openTask: setTaskId, close: () => setTaskId(null) }),
    [taskId],
  );
  return <DrawerContext.Provider value={value}>{children}</DrawerContext.Provider>;
}

export function useDrawer() {
  return useContext(DrawerContext);
}
