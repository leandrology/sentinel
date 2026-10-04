"use client";

import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import { fetchVideoStatus, videoStart, videoStop } from "@/lib/api";

type VideoState = "loading" | "error" | "no-source" | "stopped" | "running";

export default function VideoPanel() {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: ["video"], queryFn: fetchVideoStatus, refetchInterval: 10000 });
  const start = useMutation({
    mutationFn: videoStart,
    onSettled: () => qc.invalidateQueries({ queryKey: ["video"] }),
  });
  const stop = useMutation({
    mutationFn: videoStop,
    onSettled: () => qc.invalidateQueries({ queryKey: ["video"] }),
  });

  const s = query.data;
  let state: VideoState = "loading";
  if (query.isPending) state = "loading";
  else if (query.isError) state = "error";
  else if (s) state = s.running ? "running" : s.source ? "stopped" : "no-source";

  const dot =
    state === "running"
      ? "bg-emerald-400 animate-pulse"
      : state === "error"
        ? "bg-red-400"
        : state === "no-source"
          ? "bg-slate-500"
          : "bg-amber-400";

  const badge =
    state === "running"
      ? { label: "● STREAMING", cls: "border-emerald-500/60 bg-emerald-950/40 text-emerald-200" }
      : state === "stopped"
        ? { label: "○ STOPPED — SOURCE READY", cls: "border-amber-500/50 bg-amber-950/30 text-amber-200" }
        : state === "no-source"
          ? { label: "○ IDLE — NO SOURCE", cls: "border-slate-600 bg-slate-900 text-slate-300" }
          : state === "error"
            ? { label: "! UNAVAILABLE", cls: "border-red-500/60 bg-red-950/40 text-red-200" }
            : { label: "… LOADING", cls: "border-slate-700 text-slate-400" };

  return (
    <section aria-label="Video monitoring" className="rounded-md border border-slate-800 bg-slate-900/30 p-4">
      <div className="flex items-center gap-2">
        <span aria-hidden="true" className={`inline-block h-2 w-2 rounded-full ${dot}`} />
        <h3 className="text-sm font-semibold text-slate-200">Video monitoring</h3>
        <span className={`ml-auto rounded border px-1.5 py-px text-[10px] font-bold tracking-wide ${badge.cls}`}>
          {badge.label}
        </span>
      </div>
      {query.isPending ? (
        <p className="mt-2 text-sm text-slate-500" role="status">Loading video status…</p>
      ) : query.isError ? (
        <p className="mt-2 text-sm text-red-300" role="alert">
          Video status unavailable — the API may be down. Monitoring continues for sensor events.
        </p>
      ) : s ? (
        <div className="mt-2 text-[13px] leading-relaxed" aria-live="polite">
          {state === "no-source" && (
            <p className="text-slate-400">
              No video source configured. Video monitoring is <strong className="text-slate-200">idle</strong> (not an error).
              Set <code className="rounded bg-slate-800 px-1 font-mono text-[11px]">VIDEO_SOURCE</code> on the server, then press Start.
            </p>
          )}
          {state === "stopped" && (
            <p className="text-slate-400">
              Stopped — source ready (<code className="rounded bg-slate-800 px-1 font-mono text-[11px]">{s.source}</code>). Press Start to resume sampling.
            </p>
          )}
          {state === "running" && (
            <p className="text-slate-300">
              Actively sampling <code className="rounded bg-slate-800 px-1 font-mono text-[11px]">{s.source}</code>. Detections enter the common event pipeline.
            </p>
          )}
          <p className="mt-1 tabular-nums text-slate-500">
            Frames: <span className="text-slate-300">{s.frames_read}</span> · Detections: <span className="text-slate-300">{s.detections}</span>
          </p>
          {s.last_error && (
            <p className="mt-1 rounded border border-amber-800/60 bg-amber-950/20 px-2 py-1 text-xs text-amber-200">
              Note: {s.last_error}
            </p>
          )}
          {(start.isError || stop.isError) && (
            <p role="alert" className="mt-1 text-xs text-red-300">Video control failed — retry.</p>
          )}
          <div className="mt-2.5 flex gap-2">
            <button
              onClick={() => start.mutate()}
              disabled={start.isPending || s.running || !s.source}
              title={!s.source ? "No source configured (set VIDEO_SOURCE on the server)" : s.running ? "Already running" : "Start video sampling"}
              className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {start.isPending ? "Starting…" : "Start"}
            </button>
            <button
              onClick={() => stop.mutate()}
              disabled={stop.isPending || !s.running}
              title={!s.running ? "Video is not running" : "Stop video sampling"}
              className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {stop.isPending ? "Stopping…" : "Stop"}
            </button>
          </div>
        </div>
      ) : null}
    </section>
  );
}
