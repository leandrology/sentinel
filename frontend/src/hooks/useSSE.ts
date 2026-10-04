"use client";

import { useEffect, useRef, useState } from "react";
import type { Incident } from "@/types";
import { API_BASE } from "@/lib/api";

export type StreamStatus = "connecting" | "connected" | "reconnecting" | "error";

/**
 * Subscribes to /api/events/stream via EventSource.
 * The browser re-sends Last-Event-ID on reconnect automatically; the
 * dashboard additionally dedupes by id and reloads REST history.
 */
export function useSSE(
  onIncident: (incident: Incident) => void,
  onSignal?: (kind: string, payload: unknown) => void
): {
  status: StreamStatus;
  reconnects: number;
} {
  const [status, setStatus] = useState<StreamStatus>("connecting");
  const [reconnects, setReconnects] = useState(0);
  const callback = useRef(onIncident);
  callback.current = onIncident;
  const signal = useRef(onSignal);
  signal.current = onSignal;

  useEffect(() => {
    let source: EventSource | null = null;
    let errors = 0;
    let cancelled = false;

    const connect = () => {
      source = new EventSource(`${API_BASE}/api/events/stream`);
      setStatus((s) => (s === "connected" ? s : "connecting"));
      source.addEventListener("incident", (ev) => {
        if (cancelled) return;
        errors = 0;
        try {
          callback.current(JSON.parse((ev as MessageEvent).data) as Incident);
        } catch {
          // Malformed frame: ignore, keep the stream alive.
        }
      });
      source.addEventListener("escalation", (ev) => {
        if (cancelled || !signal.current) return;
        try {
          signal.current("escalation", JSON.parse((ev as MessageEvent).data));
        } catch {
          // Malformed frame: ignore.
        }
      });
      source.onerror = () => {
        if (cancelled) return;
        errors += 1;
        setReconnects((n) => n + 1);
        setStatus(errors > 5 ? "error" : "reconnecting");
      };
      source.onopen = () => {
        if (cancelled) return;
        errors = 0;
        setStatus("connected");
      };
    };

    connect();
    return () => {
      cancelled = true;
      source?.close();
    };
  }, []);

  return { status, reconnects };
}
