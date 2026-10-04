import type { Incident } from "@/types";

export function sortIncidents(a: Incident, b: Incident): number {
  const rank = { critical: 0, warning: 1, info: 2 } as const;
  if (rank[a.severity] !== rank[b.severity]) return rank[a.severity] - rank[b.severity];
  return b.timestamp.localeCompare(a.timestamp);
}

/** Merge an SSE incident into a list: upsert by id, no duplicates. */
export function mergeIncident(list: Incident[], incoming: Incident): Incident[] {
  const idx = list.findIndex((i) => i.id === incoming.id);
  if (idx >= 0) {
    const next = [...list];
    next[idx] = incoming;
    return next;
  }
  return [incoming, ...list];
}
