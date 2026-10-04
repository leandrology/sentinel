"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchIngestionStatus, ingestionStart, ingestionStop } from "@/lib/api";

export default function IngestionToggle() {
  const qc = useQueryClient();
  const query = useQuery({
    queryKey: ["ingestion"],
    queryFn: fetchIngestionStatus,
    refetchInterval: 10000,
  });
  const start = useMutation({
    mutationFn: ingestionStart,
    onSettled: () => qc.invalidateQueries({ queryKey: ["ingestion"] }),
  });
  const stop = useMutation({
    mutationFn: ingestionStop,
    onSettled: () => qc.invalidateQueries({ queryKey: ["ingestion"] }),
  });

  const s = query.data;
  const active = !!s?.connected || !!s?.enabled;
  const busy = start.isPending || stop.isPending;

  return (
    <section
      aria-label="Sensor simulator ingestion"
      className="rounded-md border border-slate-800 bg-slate-900/30 p-4"
    >
      <div className="flex items-center gap-2">
        <span
          aria-hidden="true"
          className={`inline-block h-2 w-2 rounded-full ${active ? "bg-emerald-400 animate-pulse" : "bg-slate-500"}`}
        />
        <h3 className="text-sm font-semibold text-slate-200">Sensor simulator</h3>
        <span
          className={`ml-auto rounded border px-1.5 py-px text-[10px] font-bold tracking-wide ${
            active
              ? "border-emerald-500/60 bg-emerald-950/40 text-emerald-200"
              : "border-slate-600 bg-slate-900 text-slate-300"
          }`}
        >
          {query.isPending ? "… LOADING" : active ? "● INGESTING" : "○ OPTED OUT"}
        </span>
      </div>
      <p className="mt-2 text-[13px] leading-relaxed text-slate-400">
        {active
          ? "Synthetic sensor events are flowing. Opt out to run video-only triage."
          : "Sensor events paused — video-only mode. Camera detections still enter the pipeline."}
      </p>
      {s && (
        <p className="mt-1 tabular-nums text-xs text-slate-500">
          Queue: <span className="text-slate-300">{s.queue_size}/{s.queue_max}</span>
          {typeof s.reconnects === "number" && (
            <> · Reconnects: <span className="text-slate-300">{s.reconnects}</span></>
          )}
        </p>
      )}
      {(start.isError || stop.isError) && (
        <p role="alert" className="mt-1 text-xs text-red-300">Ingestion control failed — retry.</p>
      )}
      <div className="mt-2.5 flex gap-2">
        <button
          onClick={() => stop.mutate()}
          disabled={busy || !active}
          title={active ? "Stop sensor simulator ingestion" : "Already opted out"}
          className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {stop.isPending ? "Opting out…" : "Opt out"}
        </button>
        <button
          onClick={() => start.mutate()}
          disabled={busy || active}
          title={active ? "Already ingesting" : "Resume sensor simulator ingestion"}
          className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
        >
          {start.isPending ? "Resuming…" : "Resume"}
        </button>
      </div>
    </section>
  );
}
