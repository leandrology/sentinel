import { afterEach, beforeEach, describe, expect, it, vi } from "vitest";
import { fireEvent, render, screen, waitFor, within } from "@testing-library/react";
import Dashboard from "@/components/Dashboard";
import Providers from "@/components/Providers";
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

const mk = (over: Partial<Incident> & { id: number }): Incident => ({
  event_id: `e${over.id}`,
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
  summary: `summary ${over.id}`,
  recommended_action: "review it",
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
  ...over,
});

let items: Incident[];
let failNext: string | null;

function fakeFetch(url: string, init?: RequestInit): Promise<Response> {
  const method = init?.method ?? "GET";
  const ok = (json: unknown) =>
    Promise.resolve({ ok: true, status: 200, json: async () => json, text: async () => "" } as Response);
  if (url.includes("/api/video/")) {
    return ok({ running: false, source: "", frames_read: 0, detections: 0, last_error: null });
  }
  if (url.includes("/api/incidents?")) return ok({ items });
  const m = url.match(/\/api\/incidents\/(\d+)\/(acknowledge|resolve)/);
  if (m && method === "POST") {
    const id = Number(m[1]);
    if (failNext === m[2]) {
      failNext = null;
      return Promise.resolve({ ok: false, status: 409, text: async () => "conflict" } as Response);
    }
    const to = m[2] === "acknowledge" ? "acknowledged" : "resolved";
    items = items.map((i) => (i.id === id ? { ...i, status: to } : i));
    return ok({ incident: items.find((i) => i.id === id), changed: true });
  }
  return Promise.resolve({ ok: false, status: 404, text: async () => "?" } as Response);
}

beforeEach(() => {
  MockEventSource.instances = [];
  vi.stubGlobal("EventSource", MockEventSource);
  items = [
    mk({ id: 1, severity: "critical", type: "fire_alarm", summary: "Fire alarm in lobby" }),
    mk({ id: 2, severity: "info", type: "motion_detected", site_id: "site-101" }),
  ];
  failNext = null;
  vi.stubGlobal("fetch", (url: string, init?: RequestInit) => fakeFetch(url, init));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

function openStream() {
  MockEventSource.instances[0].onopen?.();
}

describe("Dashboard", () => {
  it("renders critical alerts with text labels and sorts feed by severity", async () => {
    render(
      <Providers>
        <Dashboard />
      </Providers>
    );
    openStream();
    const panel = await screen.findByLabelText("Critical alerts");
    expect(within(panel).getByText("CRITICAL")).toBeInTheDocument();
    expect(within(panel).getByText(/fire_alarm/)).toBeInTheDocument();
    const feed = await screen.findByLabelText("Incident feed");
    const buttons = within(feed).getAllByRole("button");
    expect(buttons[0]).toHaveAccessibleName(/critical fire_alarm/);
  });

  it("shows SSE incidents without refresh and without duplicates", async () => {
    render(
      <Providers>
        <Dashboard />
      </Providers>
    );
    openStream();
    await screen.findByLabelText("Incident feed");
    MockEventSource.instances[0].emit("incident", mk({ id: 3, type: "door_forced" }));
    MockEventSource.instances[0].emit("incident", mk({ id: 3, type: "door_forced" }));
    await waitFor(() => {
      expect(screen.getAllByText("door_forced — site-100 / lobby")).toHaveLength(1);
    });
  });

  it("acknowledges with optimistic update and persists", async () => {
    render(
      <Providers>
        <Dashboard />
      </Providers>
    );
    openStream();
    const feed = await screen.findByLabelText("Incident feed");
    fireEvent.click(within(feed).getByRole("button", { name: /critical fire_alarm/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Acknowledge" }));
    await waitFor(() => {
      expect(screen.getByLabelText("Incident details")).toHaveTextContent("acknowledged");
    });
    expect(items.find((i) => i.id === 1)?.status).toBe("acknowledged");
  });

  it("rolls back and shows an error when acknowledge fails", async () => {
    failNext = "acknowledge";
    render(
      <Providers>
        <Dashboard />
      </Providers>
    );
    openStream();
    const feed = await screen.findByLabelText("Incident feed");
    fireEvent.click(within(feed).getByRole("button", { name: /critical fire_alarm/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Acknowledge" }));
    await waitFor(() => {
      expect(screen.getByRole("alert")).toHaveTextContent(/409/);
    });
    expect(items.find((i) => i.id === 1)?.status).toBe("open");
  });

  it("resolves an incident", async () => {
    render(
      <Providers>
        <Dashboard />
      </Providers>
    );
    openStream();
    const feed = await screen.findByLabelText("Incident feed");
    fireEvent.click(within(feed).getByRole("button", { name: /critical fire_alarm/ }));
    fireEvent.click(await screen.findByRole("button", { name: "Resolve" }));
    // Resolve requires confirmation (destructive action guard).
    fireEvent.click(await screen.findByRole("button", { name: "Confirm resolve" }));
    await waitFor(() => {
      expect(screen.getByLabelText("Incident details")).toHaveTextContent("resolved");
    });
  });

  it("filters by site and shows empty state", async () => {
    render(
      <Providers>
        <Dashboard />
      </Providers>
    );
    openStream();
    await screen.findByLabelText("Incident feed");
    fireEvent.change(screen.getByLabelText("Site"), { target: { value: "site-106" } });
    expect(await screen.findByText("No incidents match these filters.")).toBeInTheDocument();
  });

  it("shows reconnecting status on stream errors", async () => {
    render(
      <Providers>
        <Dashboard />
      </Providers>
    );
    await screen.findByLabelText("Incident feed");
    MockEventSource.instances[0].onerror?.();
    expect(await screen.findByText("Reconnecting…")).toBeInTheDocument();
  });

  it("shows error state with retry when loading fails", async () => {
    vi.stubGlobal(
      "fetch",
      () => Promise.resolve({ ok: false, status: 500, text: async () => "down" }) as Promise<Response>
    );
    render(
      <Providers>
        <Dashboard />
      </Providers>
    );
    expect(await screen.findByText("Failed to load incidents.", {}, { timeout: 10000 }))
      .toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Retry" })).toBeInTheDocument();
  });
});
