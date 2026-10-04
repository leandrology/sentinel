import { beforeEach, describe, expect, it, vi } from "vitest";
import { ackIncident, fetchIncidents, resolveIncident } from "@/lib/api";

function mockFetch(json: unknown, ok = true, status = 200) {
  return vi.fn().mockResolvedValue({ ok, status, json: async () => json, text: async () => "" });
}

beforeEach(() => {
  vi.stubGlobal("fetch", mockFetch({ items: [] }));
});

describe("api client", () => {
  it("fetches incidents and unwraps items", async () => {
    vi.stubGlobal("fetch", mockFetch({ items: [{ id: 1 }] }));
    await expect(fetchIncidents()).resolves.toEqual({ items: [{ id: 1 }] });
    const url = (fetch as ReturnType<typeof vi.fn>).mock.calls[0][0] as string;
    expect(url).toContain("/api/incidents?limit=200");
  });

  it("posts acknowledge with actor", async () => {
    const f = mockFetch({ incident: { id: 1 }, changed: true });
    vi.stubGlobal("fetch", f);
    await ackIncident(1, "op-1");
    const [url, init] = f.mock.calls[0];
    expect(url).toContain("/api/incidents/1/acknowledge");
    expect(JSON.parse((init as RequestInit).body as string)).toEqual({ actor: "op-1" });
  });

  it("throws on failed resolve with status", async () => {
    vi.stubGlobal(
      "fetch",
      vi.fn().mockResolvedValue({ ok: false, status: 409, text: async () => "conflict" })
    );
    await expect(resolveIncident(9)).rejects.toThrow("API 409");
  });
});
