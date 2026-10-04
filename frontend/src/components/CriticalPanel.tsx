"use client";

import Link from "next/link";
import type { Incident } from "@/types";
import SeverityBadge, { StatusPill } from "@/components/SeverityBadge";
import { formatRelative, formatTime } from "@/hooks/useIncidentsFeed";

export default function CriticalPanel({
  incidents,
  selectedId = null,
  onSelect,
}: {
  incidents: Incident[];
  selectedId?: number | null;
  onSelect: (id: number) => void;
}) {
  const critical = incidents
    .filter((i) => i.severity === "critical" && i.status !== "resolved")
    .sort((a, b) => b.timestamp.localeCompare(a.timestamp));

  return (
    <section
      aria-label="Critical alerts"
      aria-live="assertive"
      className="overflow-hidden rounded-md border border-red-900/80 bg-red-950/10"
    >
      <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1 border-b border-red-900/60 px-4 py-3">
        <h3 className="flex items-center gap-2 text-sm font-semibold text-red-100">
          <span aria-hidden="true">▲</span> Critical alerts
          <span className="rounded-full border border-red-800 bg-red-950/60 px-2 py-px text-xs font-bold tabular-nums text-red-200">
            {critical.length} active
          </span>
        </h3>
        <p className="text-xs text-red-200/60">Requires immediate review — newest first</p>
        <Link
          href="/incidents?severity=critical"
          className="ml-auto text-xs text-red-200/80 underline-offset-2 hover:text-red-100 hover:underline focus:outline-none focus-visible:ring-2 focus-visible:ring-red-400 rounded"
        >
          View all →
        </Link>
      </div>
      {critical.length === 0 ? (
        <p className="px-4 py-5 text-sm text-slate-400">
          <span aria-hidden="true">✓ </span>No active critical incidents. Monitoring continues.
        </p>
      ) : (
        <ul className="divide-y divide-red-900/40">
          {critical.slice(0, 5).map((i) => {
            const selected = selectedId === i.id;
            return (
              <li key={i.id}>
                <button
                  onClick={() => onSelect(i.id)}
                  aria-label={`Critical: ${i.type} at ${i.site_id} ${i.zone}, ${i.status}, ${formatRelative(i.timestamp)}`}
                  aria-current={selected ? "true" : undefined}
                  className={[
                    "group flex w-full items-center gap-3 px-4 py-2.5 text-left transition-colors duration-150",
                    "hover:bg-red-950/40 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-500",
                    selected
                      ? "bg-sky-950/40 shadow-[inset_3px_0_0_0_#38bdf8]"
                      : "shadow-[inset_3px_0_0_0_transparent]",
                  ].join(" ")}
                >
                  <SeverityBadge severity={i.severity} />
                  <span className="min-w-0 flex-1">
                    <span className="block truncate font-mono text-sm font-medium text-slate-100">
                      {i.type} — {i.site_id} / {i.zone}
                    </span>
                    <span className="mt-0.5 block text-[11px] text-slate-500">
                      <time dateTime={i.timestamp} title={formatTime(i.timestamp)}>
                        {formatRelative(i.timestamp)}
                      </time>
                      {i.escalated ? <span className="ml-2 font-semibold text-orange-300">[ESCALATED]</span> : null}
                      <span className="ml-2">{i.source === "camera" ? "◉ camera" : "○ sensor"}</span>
                    </span>
                  </span>
                  <StatusPill status={i.status} />
                  <span
                    aria-hidden="true"
                    className={`text-slate-600 transition-transform duration-150 ${selected ? "translate-x-0 text-sky-400" : "-translate-x-0.5 group-hover:translate-x-0 group-hover:text-slate-400"}`}
                  >
                    ›
                  </span>
                </button>
              </li>
            );
          })}
        </ul>
      )}
    </section>
  );
}
