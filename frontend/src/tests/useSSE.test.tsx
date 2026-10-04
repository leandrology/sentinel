import { afterEach, describe, expect, it, vi } from "vitest";
import { act, renderHook, waitFor } from "@testing-library/react";
import { useSSE } from "@/hooks/useSSE";
import type { Incident } from "@/types";

class MockEventSource {
  static instances: MockEventSource[] = [];
  listeners: Record<string, Array<(ev: { data: string }) => void>> = {};
  onopen: (() => void) | null = null;
  onerror: (() => void) | null = null;
  constructor(public url: string) {
    MockEventSource.instances.push(this);
  }
  addEventListener(type: string, fn: (ev: { data: string }) => void) {
    (this.listeners[type] ??= []).push(fn);
  }
  removeEventListener() {}
  close() {}
  emit(type: string, data: unknown) {
    for (const fn of this.listeners[type] ?? []) fn({ data: JSON.stringify(data) });
  }
}

function install() {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
}

afterEach(() => {
  vi.unstubAllGlobals();
});

const incident = (id: number): Incident => ({
  id,
  event_id: `e${id}`,
  site_id: "site-100",
  zone: "lobby",
  type: "motion_detected",
  source: "sensor",
  confidence: 0.7,
  timestamp: "2026-10-01T12:00:00Z",
  snapshot_url: null,
  metadata: {},
  severity: "info",
  threat_assessment: "uncertain",
  summary: "s",
  recommended_action: "a",
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
  created_at: "2026-10-01T12:00:00Z",
  updated_at: "2026-10-01T12:00:00Z",
});

describe("useSSE", () => {
  it("connects to the stream and delivers incidents", async () => {
    install();
    const seen: Incident[] = [];
    const { result } = renderHook(() => useSSE((i) => seen.push(i)));
    expect(MockEventSource.instances).toHaveLength(1);
    expect(MockEventSource.instances[0].url).toContain("/api/events/stream");

    act(() => MockEventSource.instances[0].onopen?.());
    expect(result.current.status).toBe("connected");

    act(() => MockEventSource.instances[0].emit("incident", incident(7)));
    await waitFor(() => expect(seen.map((i) => i.id)).toEqual([7]));
  });

  it("ignores malformed frames without dropping the stream", async () => {
    install();
    const seen: Incident[] = [];
    renderHook(() => useSSE((i) => seen.push(i)));
    act(() => MockEventSource.instances[0].onopen?.());
    act(() => {
      for (const fn of MockEventSource.instances[0].listeners["incident"] ?? [])
        fn({ data: "not-json{{{" });
    });
    await new Promise((r) => setTimeout(r, 20));
    expect(seen).toEqual([]);
  });

  it("reports reconnecting and counts errors", () => {
    install();
    const { result } = renderHook(() => useSSE(() => {}));
    act(() => MockEventSource.instances[0].onerror?.());
    act(() => MockEventSource.instances[0].onerror?.());
    expect(result.current.status).toBe("reconnecting");
    expect(result.current.reconnects).toBe(2);
  });

  it("forwards escalation signals without touching the incident list", () => {
    install();
    const seen: Incident[] = [];
    const signals: Array<{ kind: string; payload: unknown }> = [];
    renderHook(() => useSSE((i) => seen.push(i), (k, p) => signals.push({ kind: k, payload: p })));
    act(() => MockEventSource.instances[0].onopen?.());
    act(() => MockEventSource.instances[0].emit("escalation", { key: "k" }));
    expect(seen).toEqual([]);
    expect(signals).toEqual([{ kind: "escalation", payload: { key: "k" } }]);
  });
});
