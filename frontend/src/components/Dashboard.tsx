"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import ConnectionBadge from "@/components/ConnectionBadge";
import CriticalPanel from "@/components/CriticalPanel";
import Filters from "@/components/Filters";
import IncidentDetail from "@/components/IncidentDetail";
import IncidentList from "@/components/IncidentList";
import Pagination from "@/components/Pagination";
import { HistoryList } from "@/components/SummaryCounts";
import IngestionToggle from "@/components/IngestionToggle";
import VideoStudio from "@/components/VideoStudio";
import { useIncidentsFeed } from "@/hooks/useIncidentsFeed";
import { useIncidentActions } from "@/hooks/useIncidentActions";
import { sortIncidents } from "@/lib/sort";

const PAGE_SIZE = 20;

export default function Dashboard() {
  const { qc, query, all, stream, reconnects } = useIncidentsFeed(200);
  const [site, setSite] = useState("");
  const [zone, setZone] = useState("");
  const [status, setStatus] = useState("open");
  const [severity, setSeverity] = useState("");
  const [search, setSearch] = useState("");
  const [selectedId, setSelectedId] = useState<number | null>(null);
  const [actionError, setActionError] = useState<string | null>(null);
  const [page, setPage] = useState(1);
  const feedRef = useRef<HTMLElement | null>(null);

  const visible = useMemo(() => {
    const q = search.trim().toLowerCase();
    return all.filter(
      (i) =>
        (!site || i.site_id === site) &&
        (!zone || i.zone === zone) &&
        (!status || i.status === status) &&
        (!severity || i.severity === severity) &&
        (!q ||
          i.type.toLowerCase().includes(q) ||
          i.site_id.toLowerCase().includes(q) ||
          i.zone.toLowerCase().includes(q) ||
          i.summary.toLowerCase().includes(q) ||
          i.event_id.toLowerCase().includes(q))
    );
  }, [all, site, zone, status, severity, search]);

  const sorted = useMemo(() => [...visible].sort(sortIncidents), [visible]);
  const totalPages = Math.max(1, Math.ceil(sorted.length / PAGE_SIZE));

  useEffect(() => {
    setPage(1);
  }, [site, zone, status, severity, search]);

  useEffect(() => {
    if (page > totalPages) setPage(totalPages);
  }, [page, totalPages]);

  const paged = useMemo(
    () => sorted.slice((page - 1) * PAGE_SIZE, page * PAGE_SIZE),
    [sorted, page]
  );

  const handlePageChange = (next: number) => {
    setPage(Math.min(Math.max(1, next), totalPages));
    feedRef.current?.scrollIntoView({ block: "start", behavior: "smooth" });
  };

  const selected = useMemo(
    () => all.find((i) => i.id === selectedId) ?? null,
    [all, selectedId]
  );

  const { ack, resolve, pending } = useIncidentActions(qc, setActionError);

  const clearFilters = () => {
    setSite("");
    setZone("");
    setStatus("");
    setSeverity("");
    setSearch("");
  };

  return (
    <div id="main-content" className="min-w-0">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-slate-800 px-4 py-3 sm:px-6">
        <div>
          <h2 className="text-base font-semibold text-slate-50">Live Operations</h2>
          <p className="text-xs text-slate-500">What needs attention, where it is, and what to do next</p>
        </div>
        <div className="ml-auto">
          <ConnectionBadge status={stream} reconnects={reconnects} />
        </div>
      </header>

      <main className="grid gap-4 p-4 sm:p-6 xl:grid-cols-3">
        <div className="min-w-0 space-y-4 xl:col-span-2">
          <CriticalPanel incidents={all} selectedId={selectedId} onSelect={setSelectedId} />
          <section ref={feedRef} aria-label="Live event feed" className="scroll-mt-4 overflow-hidden rounded-md border border-slate-800 bg-slate-900/20">
            <div className="border-b border-slate-800 px-4 py-3">
              <div className="flex flex-wrap items-baseline gap-x-3 gap-y-1">
                <h3 className="text-sm font-semibold text-slate-100">Live event feed</h3>
                <p className="text-xs text-slate-500">Triage queue — severity-ordered, newest first</p>
              </div>
              <div className="mt-2.5">
                <Filters
                  site={site} zone={zone} status={status} severity={severity} search={search}
                  onSite={setSite} onZone={setZone} onStatus={setStatus}
                  onSeverity={setSeverity} onSearch={setSearch}
                  onClear={clearFilters}
                  shown={visible.length} total={all.length}
                />
              </div>
            </div>
            <IncidentList
              incidents={paged}
              selectedId={selectedId}
              onSelect={setSelectedId}
              loading={query.isPending}
              error={query.error}
              onRetry={() => query.refetch()}
            />
            {!query.isPending && !query.error && visible.length > 0 && (
              <Pagination
                page={page}
                totalPages={totalPages}
                totalItems={visible.length}
                pageSize={PAGE_SIZE}
                onChange={handlePageChange}
                label="Live event feed pagination"
              />
            )}
          </section>
        </div>

        <div
          aria-label="Details and controls"
          className="min-w-0 space-y-4 xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:self-start xl:overflow-y-auto xl:overscroll-contain xl:pb-2 xl:pr-1 [scrollbar-width:thin]"
        >
          <IncidentDetail
            incident={selected}
            onAck={() => selected && ack.mutate(selected.id)}
            onResolve={() => selected && resolve.mutate(selected.id)}
            pending={pending}
            actionError={actionError}
          />
          <VideoStudio />
          <IngestionToggle />
          <HistoryList incidents={all} />
        </div>
      </main>
    </div>
  );
}
