import { describe, expect, it, vi, beforeEach, afterEach } from "vitest";
import { render, screen, fireEvent } from "@testing-library/react";
import VideoStudio from "@/components/VideoStudio";
import IngestionToggle from "@/components/IngestionToggle";
import Providers from "@/components/Providers";

function fakeFetch(url: string): Promise<Response> {
  const ok = (json: unknown) =>
    Promise.resolve({ ok: true, status: 200, json: async () => json, text: async () => "" } as Response);
  if (url.includes("/api/video/sources")) return ok({ items: [] });
  if (url.includes("/api/vision/status"))
    return ok({ provider: "mock", configured: "mock", enabled: true, analyzed: 0, failed: 0, last: null });
  if (url.includes("/api/video/status"))
    return ok({ running: false, source: "", frames_read: 0, detections: 0, last_error: null });
  if (url.includes("/api/ingestion/status"))
    return ok({ connected: false, enabled: false, queue_size: 0, queue_max: 500 });
  return ok({});
}

beforeEach(() => {
  vi.stubGlobal("fetch", (url: string) => fakeFetch(url));
});

afterEach(() => {
  vi.unstubAllGlobals();
});

describe("VideoStudio", () => {
  it("renders three source tabs and upload input", async () => {
    render(
      <Providers>
        <VideoStudio />
      </Providers>
    );
    expect(await screen.findByRole("tab", { name: "Uploaded file" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Server webcam" })).toBeInTheDocument();
    expect(screen.getByRole("tab", { name: "Browser webcam" })).toBeInTheDocument();
    expect(screen.getByLabelText("Upload video file")).toBeInTheDocument();
  });

  it("switches to browser webcam tab with enable button", async () => {
    render(
      <Providers>
        <VideoStudio />
      </Providers>
    );
    fireEvent.click(await screen.findByRole("tab", { name: "Browser webcam" }));
    expect(await screen.findByText("Enable webcam")).toBeInTheDocument();
  });

  it("shows vision provider badge", async () => {
    render(
      <Providers>
        <VideoStudio />
      </Providers>
    );
    expect(await screen.findByText("VISION: MOCK")).toBeInTheDocument();
  });
});

describe("IngestionToggle", () => {
  it("renders opted-out state with opt-out/resume controls", async () => {
    render(
      <Providers>
        <IngestionToggle />
      </Providers>
    );
    expect(await screen.findByText("○ OPTED OUT")).toBeInTheDocument();
    expect(screen.getByRole("button", { name: "Opt out" })).toBeDisabled();
    expect(screen.getByRole("button", { name: "Resume" })).toBeInTheDocument();
  });
});
