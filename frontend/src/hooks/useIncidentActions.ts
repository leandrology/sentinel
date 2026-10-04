"use client";

import { useMutation, type QueryClient } from "@tanstack/react-query";
import type { Incident } from "@/types";
import { ackIncident, resolveIncident } from "@/lib/api";
import { INCIDENTS_KEY } from "@/hooks/useIncidentsFeed";

export function useIncidentActions(
  qc: QueryClient,
  setActionError: (msg: string | null) => void
) {
  const ack = useMutation({
    mutationFn: (id: number) => ackIncident(id),
    onMutate: async (id: number) => {
      setActionError(null);
      await qc.cancelQueries({ queryKey: INCIDENTS_KEY });
      const prev = qc.getQueryData<{ items: Incident[] }>(INCIDENTS_KEY);
      qc.setQueryData<{ items: Incident[] }>(INCIDENTS_KEY, (p) =>
        p ? { items: p.items.map((i) => (i.id === id ? { ...i, status: "acknowledged" as const } : i)) } : p
      );
      return { prev };
    },
    onError: (err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(INCIDENTS_KEY, ctx.prev);
      setActionError(err instanceof Error ? err.message : "Action failed; rolled back.");
    },
    onSettled: () => qc.invalidateQueries({ queryKey: INCIDENTS_KEY }),
  });

  const resolve = useMutation({
    mutationFn: (id: number) => resolveIncident(id),
    onMutate: async (id: number) => {
      setActionError(null);
      await qc.cancelQueries({ queryKey: INCIDENTS_KEY });
      const prev = qc.getQueryData<{ items: Incident[] }>(INCIDENTS_KEY);
      qc.setQueryData<{ items: Incident[] }>(INCIDENTS_KEY, (p) =>
        p ? { items: p.items.map((i) => (i.id === id ? { ...i, status: "resolved" as const } : i)) } : p
      );
      return { prev };
    },
    onError: (err, _id, ctx) => {
      if (ctx?.prev) qc.setQueryData(INCIDENTS_KEY, ctx.prev);
      setActionError(err instanceof Error ? err.message : "Action failed; rolled back.");
    },
    onSettled: () => qc.invalidateQueries({ queryKey: INCIDENTS_KEY }),
  });

  return { ack, resolve, pending: ack.isPending || resolve.isPending };
}
