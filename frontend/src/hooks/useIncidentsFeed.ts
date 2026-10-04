"use client";

import { useCallback } from "react";
import { useQuery, useQueryClient } from "@tanstack/react-query";
import type { Incident } from "@/types";
import { fetchIncidents } from "@/lib/api";
import { mergeIncident } from "@/lib/sort";
import { useSSE } from "@/hooks/useSSE";

export const INCIDENTS_KEY = ["incidents"] as const;

export function useIncidentsFeed(limit = 200) {
  const qc = useQueryClient();
  const query = useQuery({ queryKey: INCIDENTS_KEY, queryFn: () => fetchIncidents(limit) });

  const onIncident = useCallback(
    (incoming: Incident) => {
      qc.setQueryData<{ items: Incident[] }>(INCIDENTS_KEY, (prev) => {
        if (!prev) return { items: [incoming] };
        return { items: mergeIncident(prev.items, incoming) };
      });
    },
    [qc]
  );

  const { status: stream, reconnects } = useSSE(
    onIncident,
    useCallback(() => qc.invalidateQueries({ queryKey: INCIDENTS_KEY }), [qc])
  );

  const all = query.data?.items ?? [];

  return { qc, query, all, stream, reconnects, onIncident };
}

export function formatTime(iso: string | null): string {
  if (!iso) return "—";
  const d = new Date(iso);
  return Number.isNaN(d.getTime()) ? iso : d.toLocaleString();
}

export function formatRelative(iso: string | null): string {
  if (!iso) return "—";
  const t = new Date(iso).getTime();
  if (Number.isNaN(t)) return iso;
  const diff = Date.now() - t;
  if (diff < 0) return "just now";
  const s = Math.floor(diff / 1000);
  if (s < 60) return `${s}s ago`;
  const m = Math.floor(s / 60);
  if (m < 60) return `${m}m ago`;
  const h = Math.floor(m / 60);
  if (h < 24) return `${h}h ago`;
  const d = Math.floor(h / 24);
  return `${d}d ago`;
}
