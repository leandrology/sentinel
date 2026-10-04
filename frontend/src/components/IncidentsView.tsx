"use client";

import { useEffect, useMemo, useRef, useState } from "react";
import { useSearchParams } from "next/navigation";
import ConnectionBadge from "@/components/ConnectionBadge";
import Filters from "@/components/Filters";
import IncidentDetail from "@/components/IncidentDetail";
import IncidentList from "@/components/IncidentList";
import Pagination from "@/components/Pagination";
import { useIncidentsFeed } from "@/hooks/useIncidentsFeed";
import { useIncidentActions } from "@/hooks/useIncidentActions";
import { sortIncidents } from "@/lib/sort";

const VALID_SEVERITY = new Set(["critical", "warning", "info"]);
const VALID_STATUS = new Set(["open", "acknowledged", "resolved"]);
const PAGE_SIZE = 20;

export default function IncidentsView() {
  const params = useSearchParams();
  const { qc, query, all, stream, reconnects } = useIncidentsFeed(200);

  const [site, setSite] = useState(() => params.get("site") ?? "");
  const [zone, setZone] = useState(() => params.get("zone") ?? "");
  const [status, setStatus] = useState(() => {
    const s = params.get("status") ?? "";
    return VALID_STATUS.has(s) ? s : "";
  });
  const [severity, setSeverity] = useState(() => {
    const s = params.get("severity") ?? "";
    return VALID_SEVERITY.has(s) ? s : "";
  });
  const [search, setSearch] = useState(() => params.get("q") ?? "");
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

  const openCount = all.filter((i) => i.status === "open").length;

  return (
    <div id="main-content" className="min-w-0">
      <header className="flex flex-wrap items-center gap-x-4 gap-y-1 border-b border-slate-800 px-4 py-3 sm:px-6">
        <div>
          <h2 className="text-base font-semibold text-slate-50">
            Incidents{" "}
            <span className="ml-1 rounded-full border border-slate-700 px-2 py-px text-xs font-bold tabular-nums text-slate-300">
              {all.length} total · {openCount} open
            </span>
          </h2>
          <p className="text-xs text-slate-500">Triage queue — acknowledge to claim, resolve to close</p>
        </div>
        <div className="ml-auto">
          <ConnectionBadge status={stream} reconnects={reconnects} />
        </div>
      </header>

      <main className="grid gap-4 p-4 sm:p-6 xl:grid-cols-[minmax(0,1fr)_360px]">
        <section ref={feedRef} aria-label="Incident queue" className="min-w-0 scroll-mt-4 overflow-hidden rounded-md border border-slate-800 bg-slate-900/20">
          <div className="border-b border-slate-800 px-4 py-3">
            <Filters
              site={site} zone={zone} status={status} severity={severity} search={search}
              onSite={setSite} onZone={setZone} onStatus={setStatus}
              onSeverity={setSeverity} onSearch={setSearch}
              onClear={clearFilters}
              shown={visible.length} total={all.length}
            />
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
              label="Incident queue pagination"
            />
          )}
        </section>
        <div
          aria-label="Investigation panel"
          className="min-w-0 xl:sticky xl:top-4 xl:max-h-[calc(100vh-2rem)] xl:self-start xl:overflow-y-auto xl:overscroll-contain xl:pb-2 xl:pr-1 [scrollbar-width:thin]"
        >
          <IncidentDetail
            incident={selected}
            onAck={() => selected && ack.mutate(selected.id)}
            onResolve={() => selected && resolve.mutate(selected.id)}
            pending={pending}
            actionError={actionError}
          />
          {!selected && visible.length > 0 && (
            <p className="mt-2 text-xs text-slate-500">Tip: select a row to load it into this investigation panel.</p>
          )}
        </div>
      </main>
    </div>
  );
}
