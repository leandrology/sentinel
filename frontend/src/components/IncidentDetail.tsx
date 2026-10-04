"use client";

import { useEffect, useState } from "react";
import type { Incident } from "@/types";
import SeverityBadge, { StatusPill } from "@/components/SeverityBadge";
import { formatTime } from "@/hooks/useIncidentsFeed";

function MetaRow({ label, children }: { label: string; children: React.ReactNode }) {
  return (
    <div className="grid grid-cols-[9.5rem_1fr] gap-2 py-1 text-[13px] leading-snug">
      <dt className="text-slate-500">{label}</dt>
      <dd className="min-w-0 text-slate-200">{children}</dd>
    </div>
  );
}

export default function IncidentDetail({
  incident,
  onAck,
  onResolve,
  pending,
  actionError,
}: {
  incident: Incident | null;
  onAck: () => void;
  onResolve: () => void;
  pending: boolean;
  actionError: string | null;
}) {
  const [confirming, setConfirming] = useState(false);
  useEffect(() => setConfirming(false), [incident?.id, incident?.status]);

  if (!incident) {
    return (
      <section aria-label="Incident details" className="rounded-md border border-slate-800 bg-slate-900/30 p-4">
        <h3 className="text-sm font-semibold text-slate-200">Incident details</h3>
        <p className="mt-2 rounded border border-dashed border-slate-800 px-3 py-4 text-center text-sm text-slate-500">
          Select an incident from the feed or critical queue to investigate.
        </p>
      </section>
    );
  }

  const ackDisabled = pending || incident.status !== "open";
  const resolveDisabled = pending || incident.status === "resolved";

  return (
    <section
      aria-label="Incident details"
      className="rounded-md border border-slate-700 bg-slate-900/40 p-4 shadow-[inset_3px_0_0_0_#38bdf8]"
    >
      <div className="flex flex-wrap items-center gap-2">
        <SeverityBadge severity={incident.severity} />
        <StatusPill status={incident.status} />
        {incident.escalated ? (
          <span className="rounded border border-orange-500/50 bg-orange-950/40 px-1.5 py-px text-[10px] font-bold tracking-wide text-orange-200">
            ▲ ESCALATED
          </span>
        ) : null}
        <span className="ml-auto text-[11px] text-slate-500" title={incident.source === "camera" ? "Camera detection" : "Sensor event"}>
          {incident.source === "camera" ? "◉ camera" : "○ sensor"}
        </span>
      </div>

      <h3 className="mt-2.5 text-base font-semibold leading-snug text-slate-50">
        <span className="font-mono">{incident.type}</span>
        <span className="block text-sm font-normal text-slate-400">
          {incident.site_id} / {incident.zone}
        </span>
      </h3>

      <dl className="mt-3 divide-y divide-slate-800/70 border-y border-slate-800/70">
        <MetaRow label="Event ID">
          <span className="break-all font-mono text-xs">{incident.event_id}</span>
        </MetaRow>
        <MetaRow label="Detected">
          <time dateTime={incident.timestamp}>{formatTime(incident.timestamp)}</time>
        </MetaRow>
        <MetaRow label="Detector confidence">
          <span className="tabular-nums">{incident.confidence.toFixed(2)}</span>
        </MetaRow>
        <MetaRow label="AI assessment">
          {incident.threat_assessment} <span className="text-slate-400">(certainty {Number(incident.certainty).toFixed(2)})</span>
        </MetaRow>
        <MetaRow label="Provider">
          <span className="font-mono text-xs">
            {incident.provider}/{incident.model}
          </span>
          {incident.fallback ? <span className="ml-1 text-[11px] text-amber-300">· fallback triage</span> : null}
        </MetaRow>
      </dl>

      <div className="mt-3 rounded border border-slate-800 bg-slate-950/70 p-3">
        <h4 className="text-[11px] font-semibold uppercase tracking-wider text-slate-400">AI assessment</h4>
        <p className="mt-1 text-[13px] leading-relaxed text-slate-200">
          <span className="text-slate-500">AI summary: </span>{incident.summary}
        </p>
        <p className="mt-2 border-t border-slate-800/80 pt-2 text-[13px] leading-relaxed">
          <span className="text-slate-500">Recommended action: </span>
          <strong className="font-semibold text-amber-100">{incident.recommended_action}</strong>
        </p>
      </div>

      {(incident.acknowledged_by || incident.resolved_by) && (
        <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
          {incident.acknowledged_by && (
            <>Acked by <span className="text-slate-300">{incident.acknowledged_by}</span> at {formatTime(incident.acknowledged_at)}<br /></>
          )}
          {incident.resolved_by && (
            <>Resolved by <span className="text-slate-300">{incident.resolved_by}</span> at {formatTime(incident.resolved_at)}</>
          )}
        </p>
      )}

      {actionError && (
        <p role="alert" className="mt-2 rounded border border-red-900 bg-red-950/40 px-2.5 py-1.5 text-[13px] text-red-200">
          {actionError}
        </p>
      )}

      {!confirming ? (
        <div className="mt-3 flex gap-2">
          <button
            onClick={onAck}
            disabled={ackDisabled}
            title={incident.status !== "open" ? `Only open incidents can be acknowledged (now ${incident.status})` : "Mark as acknowledged"}
            className="flex-1 rounded border border-sky-600/70 px-3 py-2 text-sm font-medium text-sky-100 transition-colors duration-150 hover:bg-sky-900/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
          >
            {pending ? "Working…" : "Acknowledge"}
          </button>
          <button
            onClick={() => setConfirming(true)}
            disabled={resolveDisabled}
            title={incident.status === "resolved" ? "Already resolved" : "Close this incident — requires confirmation"}
            className="flex-1 rounded border border-emerald-600/70 bg-emerald-950/30 px-3 py-2 text-sm font-medium text-emerald-100 transition-colors duration-150 hover:bg-emerald-900/60 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-40 disabled:hover:bg-transparent"
          >
            {pending ? "Working…" : "Resolve"}
          </button>
        </div>
      ) : (
        <div className="mt-3 rounded border border-amber-700/60 bg-amber-950/20 p-3" role="alertdialog" aria-label="Confirm resolve">
          <p className="text-[13px] text-amber-100">
            Resolve <span className="font-mono">{incident.type}</span> at {incident.site_id}/{incident.zone}? This closes the incident.
          </p>
          <div className="mt-2 flex gap-2">
            <button
              onClick={() => setConfirming(false)}
              disabled={pending}
              className="flex-1 rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-slate-400 disabled:opacity-40"
            >
              Cancel
            </button>
            <button
              onClick={onResolve}
              disabled={pending}
              className="flex-1 rounded border border-emerald-500 bg-emerald-900/60 px-3 py-1.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-400 disabled:opacity-40"
            >
              {pending ? "Resolving…" : "Confirm resolve"}
            </button>
          </div>
        </div>
      )}
      <p className="mt-2 text-[11px] text-slate-600">Resolve is permanent and requires confirmation.</p>
    </section>
  );
}
