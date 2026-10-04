"use client";

import type { Incident } from "@/types";
import { sortIncidents } from "@/lib/sort";
import SeverityBadge, { StatusPill } from "@/components/SeverityBadge";
import { formatRelative, formatTime } from "@/hooks/useIncidentsFeed";

export default function IncidentList({
  incidents,
  selectedId,
  onSelect,
  loading,
  error,
  onRetry,
}: {
  incidents: Incident[];
  selectedId: number | null;
  onSelect: (id: number) => void;
  loading: boolean;
  error: unknown;
  onRetry: () => void;
}) {
  if (loading)
    return (
      <div className="space-y-2 p-4" aria-label="Loading incidents" role="status">
        {[0, 1, 2].map((k) => (
          <div key={k} className="animate-pulse rounded border border-slate-800 bg-slate-900/60 px-4 py-3">
            <div className="h-4 w-1/3 rounded bg-slate-800" />
            <div className="mt-2 h-3 w-2/3 rounded bg-slate-800/80" />
          </div>
        ))}
        <p className="sr-only">Loading incidents…</p>
      </div>
    );
  if (error)
    return (
      <div className="p-4 text-sm" role="alert">
        <p className="font-medium text-red-300">Failed to load incidents.</p>
        <p className="mt-1 text-xs text-slate-500">Check the API connection, then retry.</p>
        <button
          onClick={onRetry}
          className="mt-3 rounded border border-slate-600 px-3 py-1.5 text-sm transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
        >
          Retry
        </button>
      </div>
    );
  if (incidents.length === 0)
    return (
      <div className="px-4 py-8 text-center">
        <p className="text-sm text-slate-300">No incidents match these filters.</p>
        <p className="mt-1 text-xs text-slate-500">Try widening the site, zone, status, or search.</p>
      </div>
    );

  const sorted = [...incidents].sort(sortIncidents);
  return (
    <ol aria-label="Incident feed" className="divide-y divide-slate-800/80">
      {sorted.map((i) => {
        const selected = selectedId === i.id;
        return (
          <li key={i.id}>
            <button
              onClick={() => onSelect(i.id)}
              aria-pressed={selected}
              aria-label={`${i.severity} ${i.type} at ${i.site_id} ${i.zone}, ${i.status}`}
              className={[
                "block w-full px-4 py-3 text-left transition-colors duration-150",
                "hover:bg-slate-900/80 focus:outline-none focus-visible:ring-2 focus-visible:ring-inset focus-visible:ring-sky-500",
                selected ? "bg-sky-950/30 shadow-[inset_3px_0_0_0_#38bdf8]" : "",
              ].join(" ")}
            >
              <span className="flex items-center gap-2">
                <SeverityBadge severity={i.severity} />
                {i.escalated && (
                  <span className="rounded border border-orange-500/50 bg-orange-950/40 px-1.5 py-px text-[10px] font-bold tracking-wide text-orange-200">
                    ▲ ESCALATED
                  </span>
                )}
                <span className="ml-auto shrink-0 text-[11px] tabular-nums text-slate-500">
                  <time dateTime={i.timestamp} title={formatTime(i.timestamp)}>
                    {formatRelative(i.timestamp)}
                  </time>
                </span>
                <span className="shrink-0 text-[11px] text-slate-500" title={i.source === "camera" ? "Camera detection" : "Sensor event"}>
                  {i.source === "camera" ? "◉ camera" : "○ sensor"}
                </span>
              </span>
              <span className="mt-1.5 block truncate font-mono text-sm font-medium text-slate-100">
                {i.type} — {i.site_id} / {i.zone}
              </span>
              <span className="mt-0.5 line-clamp-2 block text-xs leading-relaxed text-slate-400">{i.summary}</span>
              <span className="mt-1.5 flex flex-wrap items-center gap-x-2 gap-y-1 text-[11px] text-slate-500">
                <time dateTime={i.timestamp}>{formatTime(i.timestamp)}</time>
                <span aria-hidden="true">·</span>
                <StatusPill status={i.status} />
                {i.fallback && <span title="AI unavailable — rule-based triage">· fallback triage</span>}
              </span>
            </button>
          </li>
        );
      })}
    </ol>
  );
}
