"use client";

import Link from "next/link";
import { usePathname } from "next/navigation";
import { useQuery } from "@tanstack/react-query";
import { fetchIncidents } from "@/lib/api";
import { INCIDENTS_KEY } from "@/hooks/useIncidentsFeed";
import SummaryCounts from "@/components/SummaryCounts";

const NAV = [
  { href: "/", label: "Overview", exact: true },
  { href: "/incidents", label: "Incidents", exact: false },
  { href: "/sites", label: "Sites", exact: false },
] as const;

function isActive(pathname: string, href: string, exact: boolean) {
  if (exact) return pathname === href;
  return pathname === href || pathname.startsWith(href + "/");
}

export default function AppShell({ children }: { children: React.ReactNode }) {
  const pathname = usePathname() ?? "/";
  const query = useQuery({ queryKey: INCIDENTS_KEY, queryFn: () => fetchIncidents(200) });
  const all = query.data?.items ?? [];

  return (
    <div className="flex min-h-screen flex-col lg:flex-row">
      <a
        href="#main-content"
        className="sr-only focus:not-sr-only focus:absolute focus:left-2 focus:top-2 focus:z-50 focus:rounded focus:bg-sky-700 focus:px-3 focus:py-2 focus:text-sm focus:text-white"
      >
        Skip to main content
      </a>
      <aside
        aria-label="Primary"
        className="w-full shrink-0 border-b border-slate-800 bg-slate-950/80 p-4 lg:sticky lg:top-0 lg:h-screen lg:w-60 lg:border-b-0 lg:border-r"
      >
        <div className="flex items-center justify-between gap-3 lg:block">
          <div>
            <p className="text-lg font-bold tracking-wide text-slate-50">SENTINEL</p>
            <p className="text-xs text-slate-400">Security Operations</p>
          </div>
          <nav aria-label="Sections" className="flex gap-1 lg:mt-6 lg:flex-col lg:space-y-1">
            {NAV.map((item) => {
              const active = isActive(pathname, item.href, item.exact);
              return (
                <Link
                  key={item.href}
                  href={item.href}
                  aria-current={active ? "page" : undefined}
                  className={[
                    "rounded px-3 py-2 text-sm transition-colors duration-150",
                    "focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500",
                    active
                      ? "bg-slate-800 font-medium text-slate-50 shadow-[inset_2px_0_0_0_#38bdf8]"
                      : "text-slate-400 hover:bg-slate-900 hover:text-slate-100",
                  ].join(" ")}
                >
                  {item.label}
                </Link>
              );
            })}
          </nav>
        </div>
        <div className="mt-4 hidden lg:block">
          <SummaryCounts incidents={all} />
        </div>
        {/* Compact summary for small screens: horizontal, still readable */}
        <div className="mt-3 lg:hidden">
          <SummaryCounts incidents={all} compact />
        </div>
      </aside>

      <div className="min-w-0 flex-1">{children}</div>
    </div>
  );
}
