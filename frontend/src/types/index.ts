export type Severity = "info" | "warning" | "critical";
export type IncidentStatus = "open" | "acknowledged" | "resolved";

/** Mirrors backend serialize_detail. Only real processed incidents, never mocks. */
export interface Incident {
  id: number;
  event_id: string;
  site_id: string;
  zone: string;
  type: string;
  source: "sensor" | "camera";
  confidence: number;
  timestamp: string;
  snapshot_url: string | null;
  metadata: Record<string, unknown>;
  severity: Severity;
  threat_assessment: string;
  summary: string;
  recommended_action: string;
  certainty: number;
  provider: string;
  model: string;
  fallback: boolean;
  triage_status: string;
  status: IncidentStatus;
  acknowledged_by: string | null;
  acknowledged_at: string | null;
  resolved_by: string | null;
  resolved_at: string | null;
  escalated: boolean;
  created_at: string;
  updated_at: string;
}

export interface VideoStatus {
  running: boolean;
  source: string;
  frames_read: number;
  detections: number;
  last_error: string | null;
  vision_provider?: string;
  vision_analyzed?: number;
  vision_failed?: number;
  preview_fps?: number | null;
  sample_fps?: number | null;
  source_fps?: number | null;
  preview_seq?: number | null;
  skipped?: number | null;
  loops?: number | null;
  last_vision?: {
    label: string;
    severity_hint: string;
    description: string;
    certainty: number;
    provider: string;
    model: string;
  } | null;
}

export interface VideoSourceItem {
  id: string;
  filename: string;
  path: string;
  size_bytes: number;
}

export interface VisionStatus {
  provider: string;
  configured: string;
  enabled: boolean;
  analyzed: number;
  failed: number;
  last: VideoStatus["last_vision"];
}

export interface IngestionStatus {
  connected: boolean;
  enabled?: boolean;
  reconnects?: number;
  last_error?: string | null;
  queue_size: number;
  queue_max: number;
  workers?: number;
  enqueued?: number;
  processed?: number;
  dropped?: number;
}
