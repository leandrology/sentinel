"use client";

import { useMemo } from "react";
import Link from "next/link";
import ConnectionBadge from "@/components/ConnectionBadge";
import SeverityBadge from "@/components/SeverityBadge";
import { useIncidentsFeed, formatRelative } from "@/hooks/useIncidentsFeed";

function worstSeverity(counts: { critical: number; warning: number; info: number }): "critical" | "warning" | "info" | null {
  if (counts.critical > 0) return "critical";
  if (counts.warning > 0) return "warning";
  if (counts.info > 0) return "info";
  return null;
}

export default function SitesView() {
  const { query, all, stream, reconnects } = useIncidentsFeed(200);

  const sites = useMemo(() => {
    const groups: Record<string, typeof all> = {};
    for (const i of all) {
      if (!groups[i.site_id]) groups[i.site_id] = [];
      (groups[i.site_id] as typeof all).push(i);
    }
    return Object.entries(groups)
      .map(([site_id, items]) => {
        const open = (items as typeof all).filter((i) => i.status !== "resolved");
        const counts = {
          critical: open.filter((i) => i.severity === "critical").length,
          warning: open.filter((i) => i.severity === "warning").length,
          info: open.filter((i) => i.severity === "info").length,
        };
        const zoneSet: Record<string, true> = {};
        for (const i of items as typeof all) zoneSet[i.zone] = true;
        const zones = Object.keys(zoneSet).sort();
        const latest = (items as typeof all).slice().sort((a, b) => b.timestamp.localeCompare(a.timestamp))[0];
        const resolved = (items as typeof all).filter((i) => i.status === "resolved").length;
        return { site_id, items, open: open.length, counts, zones, latest, resolved, worst: worstSeverity(counts) };
      })
      .sort((a, b) => {
        const rank = (w: string | null) => (w === "critical" ? 0 : w === "warning" ? 1 : w === "info" ? 2 : 3);
        if (rank(a.worst) !== rank(b.worst)) return rank(a.worst) - rank(b.worst);
        return b.open - a.open || a.site_id.localeCompare(b.site_id);
      });
  }, [all]);

  return (
    <div id="main-content" className="min-w-0">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-slate-800 px-4 py-3 sm:px-6">
        <div>
          <h2 className="text-base font-semibold text-slate-50">
            Sites{" "}
            <span className="ml-1 rounded-full border border-slate-700 px-2 py-px text-xs font-bold tabular-nums text-slate-300">
              {sites.length} monitored
            </span>
          </h2>
          <p className="text-xs text-slate-500">Monitored estate — worst-severity first. Select a site to triage its queue.</p>
        </div>
        <div className="ml-auto">
          <ConnectionBadge status={stream} reconnects={reconnects} />
        </div>
      </header>

      <main className="p-4 sm:p-6">
        {query.isPending ? (
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" role="status" aria-label="Loading sites">
            {[0, 1, 2].map((k) => (
              <div key={k} className="animate-pulse rounded-md border border-slate-800 bg-slate-900/50 p-4">
                <div className="h-4 w-1/2 rounded bg-slate-800" />
                <div className="mt-3 h-8 w-full rounded bg-slate-800/70" />
              </div>
            ))}
            <span className="sr-only">Loading sites…</span>
          </div>
        ) : query.isError ? (
          <div role="alert" className="rounded-md border border-red-900 bg-red-950/30 p-4 text-sm">
            <p className="font-medium text-red-200">Failed to load sites.</p>
            <button
              onClick={() => query.refetch()}
              className="mt-2 rounded border border-slate-600 px-3 py-1.5 text-sm transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              Retry
            </button>
          </div>
        ) : sites.length === 0 ? (
          <p className="rounded-md border border-dashed border-slate-800 px-4 py-8 text-center text-sm text-slate-500">
            No sites observed yet — waiting for the first events.
          </p>
        ) : (
          <ul className="grid gap-3 sm:grid-cols-2 xl:grid-cols-3" aria-label="Site list">
            {sites.map((s) => (
              <li key={s.site_id}>
                <Link
                  href={`/incidents?site=${encodeURIComponent(s.site_id)}`}
                  aria-label={`${s.site_id}: ${s.open} open incidents${s.worst ? `, worst ${s.worst}` : ""}. View queue.`}
                  className={[
                    "block rounded-md border bg-slate-900/30 p-4 transition-colors duration-150",
                    "hover:border-slate-600 hover:bg-slate-900/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500",
                    s.worst === "critical"
                      ? "border-red-900/70"
                      : s.worst === "warning"
                        ? "border-amber-900/60"
                        : "border-slate-800",
                  ].join(" ")}
                >
                  <span className="flex items-center gap-2">
                    <span
                      aria-hidden="true"
                      className={`inline-block h-2 w-2 rounded-full ${s.worst === "critical" ? "bg-red-400" : s.worst === "warning" ? "bg-amber-400" : s.open > 0 ? "bg-sky-400" : "bg-emerald-400"}`}
                    />
                    <span className="font-mono text-sm font-semibold text-slate-100">{s.site_id}</span>
                    <span className="ml-auto text-xs tabular-nums text-slate-400">
                      {s.open} open · {s.resolved} resolved
                    </span>
                  </span>
                  <span className="mt-2.5 flex flex-wrap gap-1.5">
                    {s.worst ? (
                      <SeverityBadge severity={s.worst} size="sm" />
                    ) : (
                      <span className="rounded border border-emerald-600/50 bg-emerald-950/30 px-1.5 py-px text-[10px] font-bold tracking-wide text-emerald-200">
                        ✓ CLEAR
                      </span>
                    )}
                    {s.counts.critical > 0 && <span className="text-[11px] tabular-nums text-red-300">▲{s.counts.critical}</span>}
                    {s.counts.warning > 0 && <span className="text-[11px] tabular-nums text-amber-300">◆{s.counts.warning}</span>}
                    {s.counts.info > 0 && <span className="text-[11px] tabular-nums text-slate-400">●{s.counts.info}</span>}
                  </span>
                  <span className="mt-2 block text-xs text-slate-500">
                    Zones: <span className="text-slate-400">{s.zones.join(", ")}</span>
                  </span>
                  {s.latest && (
                    <span className="mt-1 block truncate text-xs text-slate-500">
                      Latest: <span className="font-mono text-slate-400">{s.latest.type}</span> / {s.latest.zone} · {formatRelative(s.latest.timestamp)}
                    </span>
                  )}
                  <span className="mt-2.5 block text-xs text-sky-300/80">Open queue →</span>
                </Link>
              </li>
            ))}
          </ul>
        )}
      </main>
    </div>
  );
}
