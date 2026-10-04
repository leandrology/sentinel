import { describe, expect, it } from "vitest";
import { mergeIncident, sortIncidents } from "@/lib/sort";
import type { Incident } from "@/types";

const mk = (severity: Incident["severity"], timestamp: string, id = 1): Incident => ({
  id,
  event_id: `e${id}`,
  site_id: "site-100",
  zone: "lobby",
  type: "motion_detected",
  source: "sensor",
  confidence: 0.7,
  timestamp,
  snapshot_url: null,
  metadata: {},
  severity,
  threat_assessment: "uncertain",
  summary: "test",
  recommended_action: "review",
  certainty: 0.5,
  provider: "mock",
  model: "mock-v1",
  fallback: false,
  triage_status: "triaged",
  status: "open",
  acknowledged_by: null,
  acknowledged_at: null,
  resolved_by: null,
  resolved_at: null,
  escalated: false,
  created_at: timestamp,
  updated_at: timestamp,
});

describe("sortIncidents", () => {
  it("orders critical before warning before info, newest first", () => {
    const input = [
      mk("info", "2026-10-01T12:02:00Z", 1),
      mk("critical", "2026-10-01T12:00:00Z", 2),
      mk("warning", "2026-10-01T12:05:00Z", 3),
      mk("critical", "2026-10-01T12:03:00Z", 4),
    ];
    expect([...input].sort(sortIncidents).map((i) => i.id)).toEqual([4, 2, 3, 1]);
  });
});

describe("mergeIncident", () => {
  it("appends new incidents without duplicating existing ids", () => {
    const list = [mk("info", "2026-10-01T12:00:00Z", 1)];
    const grown = mergeIncident(list, mk("critical", "2026-10-01T12:01:00Z", 2));
    expect(grown.map((i) => i.id)).toEqual([2, 1]);
    const updated = mergeIncident(grown, { ...mk("info", "2026-10-01T12:00:00Z", 1), status: "resolved" as const });
    expect(updated).toHaveLength(2);
    expect(updated.find((i) => i.id === 1)?.status).toBe("resolved");
  });
});
