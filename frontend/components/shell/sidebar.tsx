"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";

import { useStatus } from "@/lib/api/hooks";
import { cn } from "@/lib/utils";

export function Sidebar() {
  const pathname = usePathname();
  const status = useStatus();
  const nav = [
    { href: "/today", label: "Today" },
    { href: "/week", label: "Week" },
    // Suggestions are waiting on you, so the inbox count stands out.
    { href: "/inbox", label: "Proof Inbox", count: status.data?.inbox_count, urgent: true },
    { href: "/backlog", label: "Backlog", count: status.data?.backlog_count },
    { href: "/connectors", label: "Connectors" },
  ];

  return (
    <nav
      aria-label="Main"
      className="flex shrink-0 grow-0 basis-[216px] flex-col gap-0.5 border-r border-border bg-sidebar px-3 py-6"
    >
      <div className="px-3 pb-5 text-base font-semibold tracking-tight">goalpost</div>
      {nav.map(({ href, label, count, urgent }) => {
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
              <span
                className={cn(
                  "font-mono text-xs",
                  urgent
                    ? "rounded-[10px] bg-primary px-[7px] text-primary-foreground"
                    : "text-muted-foreground",
                )}
              >
                {count}
              </span>
            ) : null}
          </Link>
        );
      })}
    </nav>
  );
}
