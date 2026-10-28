"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useBacklog } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();
  const backlog = useBacklog();
  const nav = [
    { href: "/today", label: "Today" },
    { href: "/week", label: "Week" },
    { href: "/inbox", label: "Proof Inbox" },
    { href: "/backlog", label: "Backlog", count: backlog.data?.items.length },
    { href: "/connectors", label: "Connectors" },
  ];

  return (
    <nav
      aria-label="Main"
      className="flex shrink-0 grow-0 basis-[216px] flex-col gap-0.5 border-r border-border bg-sidebar px-3 py-6"
    >
      <div className="px-3 pb-5 text-base font-semibold tracking-tight">goalpost</div>
      {nav.map(({ href, label, count }) => {
        const current = pathname.startsWith(href);
        return (
          <Link
            key={href}
            href={href}
            aria-current={current ? "page" : undefined}
            className={cn(
              "flex items-center justify-between rounded-md px-3 py-2 hover:text-white",
              current ? "bg-accent text-foreground" : "text-subtle",
            )}
          >
            {label}
            {count ? (
              <span className="font-mono text-xs text-muted-foreground">{count}</span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
