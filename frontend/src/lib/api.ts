import type { Incident, IngestionStatus, VideoSourceItem, VideoStatus, VisionStatus } from "@/types";

export const API_BASE =
  process.env.NEXT_PUBLIC_API_URL ?? "http://localhost:8000";

async function request<T>(path: string, init?: RequestInit): Promise<T> {
  const res = await fetch(`${API_BASE}${path}`, {
    headers: { "Content-Type": "application/json" },
    ...init,
  });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status} ${path}: ${body.slice(0, 200)}`);
  }
  return res.json() as Promise<T>;
}

export function fetchIncidents(limit = 200): Promise<{ items: Incident[] }> {
  return request<{ items: Incident[] }>(
    `/api/incidents?limit=${encodeURIComponent(limit)}`
  );
}

export function fetchIncident(id: number): Promise<Incident> {
  return request<Incident>(`/api/incidents/${id}`);
}

export function ackIncident(
  id: number,
  actor = "operator"
): Promise<{ incident: Incident; changed: boolean }> {
  return request(`/api/incidents/${id}/acknowledge`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export function resolveIncident(
  id: number,
  actor = "operator"
): Promise<{ incident: Incident; changed: boolean }> {
  return request(`/api/incidents/${id}/resolve`, {
    method: "POST",
    body: JSON.stringify({ actor }),
  });
}

export function fetchVideoStatus(): Promise<VideoStatus> {
  return request<VideoStatus>("/api/video/status");
}

export function videoStart(): Promise<VideoStatus> {
  return request<VideoStatus>("/api/video/start", { method: "POST" });
}

export function videoStop(): Promise<VideoStatus> {
  return request<VideoStatus>("/api/video/stop", { method: "POST" });
}

export function fetchVideoSources(): Promise<{ items: VideoSourceItem[] }> {
  return request<{ items: VideoSourceItem[] }>("/api/video/sources");
}

export function selectVideoSource(source: string): Promise<VideoStatus> {
  return request<VideoStatus>("/api/video/source", {
    method: "POST",
    body: JSON.stringify({ source }),
  });
}

export async function uploadVideo(file: File): Promise<VideoSourceItem & { path: string }> {
  const form = new FormData();
  form.append("file", file);
  const res = await fetch(`${API_BASE}/api/video/upload`, { method: "POST", body: form });
  if (!res.ok) {
    const body = await res.text().catch(() => "");
    throw new Error(`API ${res.status} /api/video/upload: ${body.slice(0, 200)}`);
  }
  return res.json();
}

export function videoFileUrl(id: string): string {
  return `${API_BASE}/api/video/file/${encodeURIComponent(id)}`;
}

export function videoSnapshotUrl(annotated = true): string {
  return `${API_BASE}/api/video/snapshot.jpg?annotated=${annotated ? "true" : "false"}`;
}

export function videoStreamUrl(): string {
  return `${API_BASE}/api/video/stream.mjpeg`;
}

export function sendBrowserFrame(
  image_b64: string,
  site_id?: string,
  zone?: string
): Promise<{ emitted: boolean; reason?: string; motion_score?: number; error?: string }> {
  return request("/api/video/frames", {
    method: "POST",
    body: JSON.stringify({ image_b64, site_id, zone }),
  });
}

export function fetchIngestionStatus(): Promise<IngestionStatus> {
  return request<IngestionStatus>("/api/ingestion/status");
}

export function ingestionStart(): Promise<IngestionStatus> {
  return request<IngestionStatus>("/api/ingestion/start", { method: "POST" });
}

export function ingestionStop(): Promise<IngestionStatus> {
  return request<IngestionStatus>("/api/ingestion/stop", { method: "POST" });
}

export function fetchVisionStatus(): Promise<VisionStatus> {
  return request<VisionStatus>("/api/vision/status");
}
