"use client";

import Link from "next/link";
import type { Incident } from "@/types";
import SeverityBadge from "@/components/SeverityBadge";
import { formatRelative } from "@/hooks/useIncidentsFeed";

export default function SummaryCounts({
  incidents,
  compact = false,
}: {
  incidents: Incident[];
  compact?: boolean;
}) {
  const counts = {
    critical: incidents.filter((i) => i.severity === "critical" && i.status !== "resolved").length,
    warning: incidents.filter((i) => i.severity === "warning" && i.status !== "resolved").length,
    info: incidents.filter((i) => i.severity === "info" && i.status !== "resolved").length,
    resolved: incidents.filter((i) => i.status === "resolved").length,
  };

  const cards = [
    { key: "critical", label: "Critical", icon: "▲", href: "/incidents?severity=critical", value: counts.critical, text: "text-red-200" },
    { key: "warning", label: "Warning", icon: "◆", href: "/incidents?severity=warning", value: counts.warning, text: "text-amber-200" },
    { key: "info", label: "Info", icon: "●", href: "/incidents?severity=info", value: counts.info, text: "text-slate-200" },
    { key: "resolved", label: "Resolved", icon: "✓", href: "/incidents?status=resolved", value: counts.resolved, text: "text-emerald-200" },
  ] as const;

  return (
    <section aria-label="Incident priority summary" className="rounded-md border border-slate-800 bg-slate-900/40 p-3">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-xs font-semibold uppercase tracking-wider text-slate-300">
          Priority summary
        </h3>
        <span className="text-[11px] text-slate-500">select to filter</span>
      </div>
      <div className={`mt-2 grid gap-1.5 ${compact ? "grid-cols-4" : "grid-cols-2"}`}>
        {cards.map((c) => (
          <Link
            key={c.key}
            href={c.href}
            aria-label={`${c.value} ${c.label} incidents — view in Incidents`}
            title={`View ${c.label.toLowerCase()} incidents`}
            className="group rounded border border-transparent px-2 py-1.5 transition-colors duration-150 hover:border-slate-700 hover:bg-slate-800/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            <span className={`block text-[11px] font-medium uppercase tracking-wide text-slate-400 group-hover:text-slate-300`}>
              <span aria-hidden="true" className={c.text}>{c.icon}</span> {c.label}
            </span>
            <span className={`block text-2xl font-bold tabular-nums leading-tight ${c.text}`}>
              {c.value}
            </span>
          </Link>
        ))}
      </div>
    </section>
  );
}

export function HistoryList({ incidents }: { incidents: Incident[] }) {
  const resolved = incidents
    .filter((i) => i.status === "resolved")
    .sort((a, b) => b.updated_at.localeCompare(a.updated_at))
    .slice(0, 8);
  return (
    <section aria-label="Recent incident history" className="rounded-md border border-slate-800 bg-slate-900/30 p-4">
      <div className="flex items-baseline justify-between gap-2">
        <h3 className="text-sm font-semibold text-slate-200">Recent history</h3>
        <span className="rounded border border-slate-700 px-1.5 py-px text-[10px] font-medium uppercase tracking-wide text-slate-400">
          Resolved
        </span>
      </div>
      <p className="mt-0.5 text-[11px] text-slate-500">Closed incidents — distinct from active queue</p>
      {resolved.length === 0 ? (
        <p className="mt-3 rounded border border-dashed border-slate-800 px-3 py-4 text-center text-sm text-slate-500">
          No resolved incidents yet.
        </p>
      ) : (
        <ul className="mt-2 space-y-1.5">
          {resolved.map((i) => (
            <li
              key={i.id}
              className="flex items-start gap-2 rounded border border-slate-800/80 bg-slate-950/60 px-2 py-1.5 opacity-90"
            >
              <SeverityBadge severity={i.severity} size="sm" />
              <div className="min-w-0 flex-1">
                <p className="truncate text-[13px] text-slate-300">
                  {i.type} — {i.site_id}/{i.zone}
                </p>
                <p className="mt-0.5 text-[11px] text-slate-500">
                  Resolved · {formatRelative(i.resolved_at ?? i.updated_at)}
                </p>
              </div>
            </li>
          ))}
        </ul>
      )}
    </section>
  );
}
