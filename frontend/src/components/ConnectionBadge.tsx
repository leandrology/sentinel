"use client";

import type { StreamStatus } from "@/hooks/useSSE";

const LABEL: Record<StreamStatus, string> = {
  connecting: "Connecting…",
  connected: "Connected — live",
  reconnecting: "Reconnecting…",
  error: "Stream error — retrying",
};

const DOT: Record<StreamStatus, string> = {
  connecting: "bg-amber-400",
  connected: "bg-emerald-400",
  reconnecting: "bg-amber-400 animate-pulse",
  error: "bg-red-400",
};

export default function ConnectionBadge({
  status,
  reconnects,
}: {
  status: StreamStatus;
  reconnects: number;
}) {
  return (
    <div
      role="status"
      aria-label={`stream ${LABEL[status]}`}
      className="flex items-center gap-2 text-sm"
    >
      <span aria-hidden className={`inline-block h-2.5 w-2.5 rounded-full ${DOT[status]}`} />
      <span>{LABEL[status]}</span>
      {reconnects > 0 && (
        <span className="text-xs text-slate-400">(reconnects: {reconnects})</span>
      )}
    </div>
  );
}
