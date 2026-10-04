"use client";

import { useCallback, useEffect, useRef, useState } from "react";
import { useMutation, useQuery, useQueryClient } from "@tanstack/react-query";
import VideoPanel from "@/components/VideoPanel";
import {
  fetchVideoSources,
  fetchVideoStatus,
  fetchVisionStatus,
  selectVideoSource,
  sendBrowserFrame,
  uploadVideo,
  videoFileUrl,
  videoStart,
  videoStop,
  videoStreamUrl,
} from "@/lib/api";

type Tab = "file" | "server" | "browser";

export default function VideoStudio() {
  const qc = useQueryClient();
  const [tab, setTab] = useState<Tab>("file");
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [uploadedId, setUploadedId] = useState<string | null>(null);
  const [previewUrl, setPreviewUrl] = useState<string | null>(null);
  const [serverCam, setServerCam] = useState("0");
  const [actionError, setActionError] = useState<string | null>(null);

  const status = useQuery({ queryKey: ["video"], queryFn: fetchVideoStatus, refetchInterval: 10000 });
  const sources = useQuery({ queryKey: ["video-sources"], queryFn: fetchVideoSources, refetchInterval: 15000 });
  const vision = useQuery({ queryKey: ["vision"], queryFn: fetchVisionStatus, refetchInterval: 15000 });

  const upload = useMutation({
    mutationFn: uploadVideo,
    onSuccess: (saved) => {
      setUploadedId(saved.id);
      setPreviewUrl(videoFileUrl(saved.id));
      setUploadError(null);
      qc.invalidateQueries({ queryKey: ["video-sources"] });
    },
    onError: (e: Error) => setUploadError(e.message),
  });

  const select = useMutation({
    mutationFn: selectVideoSource,
    onSuccess: () => {
      setActionError(null);
      qc.invalidateQueries({ queryKey: ["video"] });
    },
    onError: (e: Error) => setActionError(e.message),
  });

  const onFile = useCallback(
    (f: File | undefined) => {
      if (!f) return;
      setUploadError(null);
      // Instant local preview while uploading.
      const local = URL.createObjectURL(f);
      setPreviewUrl(local);
      upload.mutate(f);
    },
    [upload]
  );

  const useUploadedAsLive = useCallback(() => {
    if (!uploadedId) return;
    select.mutate(uploadedId);
  }, [uploadedId, select]);

  return (
    <section aria-label="Video studio" className="rounded-md border border-slate-800 bg-slate-900/30 p-4">
      <div className="flex items-center gap-2">
        <h3 className="text-sm font-semibold text-slate-200">Video studio — simulated live feed</h3>
        {vision.data && (
          <span
            title={`Vision provider: ${vision.data.provider} (analyzed ${vision.data.analyzed}, failed ${vision.data.failed})`}
            className="ml-auto rounded border border-sky-500/50 bg-sky-950/30 px-1.5 py-px text-[10px] font-bold tracking-wide text-sky-200"
          >
            VISION: {vision.data.provider.toUpperCase()}
          </span>
        )}
      </div>
      <div role="tablist" aria-label="Video source tabs" className="mt-2 flex gap-1 text-xs">
        {(
          [
            ["file", "Uploaded file"],
            ["server", "Server webcam"],
            ["browser", "Browser webcam"],
          ] as Array<[Tab, string]>
        ).map(([id, label]) => (
          <button
            key={id}
            role="tab"
            aria-selected={tab === id}
            onClick={() => setTab(id)}
            className={`rounded border px-2.5 py-1.5 font-medium transition-colors focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 ${
              tab === id
                ? "border-sky-500/60 bg-sky-950/40 text-sky-100"
                : "border-slate-700 text-slate-400 hover:bg-slate-800"
            }`}
          >
            {label}
          </button>
        ))}
      </div>

      {tab === "file" && (
        <div role="tabpanel" className="mt-3 space-y-2">
          <label className="block text-[13px] text-slate-300">
            <span className="mb-1 block font-medium">Downloaded video → simulated live camera</span>
            <input
              type="file"
              accept="video/mp4,video/webm,video/*"
              aria-label="Upload video file"
              onChange={(e) => onFile(e.target.files?.[0])}
              className="block w-full cursor-pointer rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-xs text-slate-300 file:mr-2 file:rounded file:border-0 file:bg-slate-700 file:px-2 file:py-1 file:text-xs file:text-slate-100"
            />
          </label>
          {upload.isPending && (
            <p role="status" className="text-xs text-slate-400">Uploading…</p>
          )}
          {uploadError && (
            <p role="alert" className="text-xs text-red-300">{uploadError}</p>
          )}
          {previewUrl && (
            <div>
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
                Raw preview (what you uploaded)
              </p>
              {/* key forces reload when a new file is chosen */}
              <video key={previewUrl} src={previewUrl} controls playsInline preload="metadata" className="w-full rounded border border-slate-800 bg-black" />
            </div>
          )}
          <div className="flex flex-wrap gap-2">
            <button
              onClick={useUploadedAsLive}
              disabled={!uploadedId || select.isPending}
              title={uploadedId ? "Loop this file as the live camera feed" : "Upload a file first"}
              className="rounded border border-emerald-600 px-3 py-1.5 text-sm text-emerald-100 transition-colors hover:bg-emerald-950/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:cursor-not-allowed disabled:opacity-40"
            >
              {select.isPending ? "Starting…" : "Use as live feed (loop)"}
            </button>
          </div>
          {(sources.data?.items?.length ?? 0) > 0 && (
            <div>
              <p className="mb-1 text-[11px] font-medium uppercase tracking-wide text-slate-500">
                Previous uploads
              </p>
              <ul className="space-y-1">
                {(sources.data?.items ?? []).slice(0, 5).map((s) => (
                  <li key={s.id} className="flex items-center gap-2 text-xs text-slate-300">
                    <span className="min-w-0 flex-1 truncate font-mono">{s.filename}</span>
                    <span className="tabular-nums text-slate-500">{Math.round(s.size_bytes / 1024)} KB</span>
                    <button
                      onClick={() => {
                        setUploadedId(s.id);
                        setPreviewUrl(videoFileUrl(s.id));
                        select.mutate(s.id);
                      }}
                      className="rounded border border-slate-600 px-2 py-0.5 text-xs hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
                    >
                      Loop
                    </button>
                  </li>
                ))}
              </ul>
            </div>
          )}
          {actionError && (
            <p role="alert" className="text-xs text-red-300">{actionError}</p>
          )}
          <ProcessedPreview />
        </div>
      )}

      {tab === "server" && (
        <div role="tabpanel" className="mt-3 space-y-2">
          <p className="text-[13px] text-slate-400">
            Server webcam (<code className="rounded bg-slate-800 px-1 font-mono text-[11px]">VIDEO_SOURCE=0</code> on
            the backend host). Not available inside Docker — run the backend locally for this tab.
          </p>
          <label className="flex items-center gap-2 text-[13px] text-slate-300">
            <span>Device / path</span>
            <input
              value={serverCam}
              onChange={(e) => setServerCam(e.target.value)}
              aria-label="Server camera source"
              placeholder="0"
              className="w-32 rounded border border-slate-700 bg-slate-900 px-2 py-1 font-mono text-xs"
            />
            <button
              onClick={() => select.mutate(serverCam.trim() || "0")}
              disabled={select.isPending}
              className="rounded border border-slate-600 px-3 py-1.5 text-sm hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:opacity-40"
            >
              {select.isPending ? "Connecting…" : "Connect"}
            </button>
          </label>
          <ProcessedPreview />
        </div>
      )}

      {tab === "browser" && <BrowserWebcam />}

      <div className="mt-3 border-t border-slate-800 pt-3">
        <VideoPanel />
        <VisionNote />
      </div>
    </section>
  );
}

function ProcessedPreview() {
  const [show, setShow] = useState(false);
  const status = useQuery({ queryKey: ["video"], queryFn: fetchVideoStatus, refetchInterval: 10000 });
  const running = !!status.data?.running;
  return (
    <div>
      <div className="flex items-center gap-2">
        <p className="text-[11px] font-medium uppercase tracking-wide text-slate-500">
          Processed feed (motion boxes, server-side)
        </p>
        <button
          onClick={() => setShow((v) => !v)}
          aria-expanded={show}
          className="rounded border border-slate-700 px-2 py-0.5 text-[11px] text-slate-300 hover:bg-slate-800"
        >
          {show ? "Hide" : "Show"}
        </button>
      </div>
      {show &&
        (running ? (
          // MJPEG multipart stream rendered as an image. Key busts cache on toggle.
          <img
            key="mjpeg"
            src={videoStreamUrl()}
            alt="Processed live feed with motion boxes"
            className="mt-1 w-full rounded border border-emerald-900/60 bg-black"
          />
        ) : (
          <p className="mt-1 text-xs text-slate-500">
            Start the feed to see annotated frames. Motion-gated vision calls run only on motion.
          </p>
        ))}
      {status.data?.last_vision && (
        <p className="mt-1 rounded border border-sky-900/60 bg-sky-950/20 px-2 py-1 text-xs text-sky-200">
          Vision ({status.data.last_vision.provider}): {status.data.last_vision.label} ·{" "}
          {status.data.last_vision.severity_hint} · {status.data.last_vision.description}
        </p>
      )}
    </div>
  );
}

function VisionNote() {
  const vision = useQuery({ queryKey: ["vision"], queryFn: fetchVisionStatus, refetchInterval: 15000 });
  if (!vision.data) return null;
  return (
    <p className="mt-2 text-[11px] leading-relaxed text-slate-500">
      Vision LLM: <span className="font-mono text-slate-300">{vision.data.provider}</span> · analyzed{" "}
      {vision.data.analyzed} · failed {vision.data.failed}. Motion is the gate; vision only enriches
      severity — safety clamp still applies.
    </p>
  );
}

function BrowserWebcam() {
  const videoRef = useRef<HTMLVideoElement | null>(null);
  const [active, setActive] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [sending, setSending] = useState(false);
  const [lastResult, setLastResult] = useState<string | null>(null);
  const streamRef = useRef<MediaStream | null>(null);

  const startCam = useCallback(async () => {
    setError(null);
    try {
      const stream = await navigator.mediaDevices.getUserMedia({ video: true, audio: false });
      streamRef.current = stream;
      if (videoRef.current) {
        videoRef.current.srcObject = stream;
        await videoRef.current.play().catch(() => undefined);
      }
      setActive(true);
    } catch {
      setError("Camera blocked — allow webcam access in the browser, then retry.");
    }
  }, []);

  const stopCam = useCallback(() => {
    streamRef.current?.getTracks().forEach((t) => t.stop());
    streamRef.current = null;
    if (videoRef.current) videoRef.current.srcObject = null;
    setActive(false);
  }, []);

  useEffect(() => () => stopCam(), [stopCam]);

  const sendFrame = useCallback(async () => {
    const video = videoRef.current;
    if (!video || !active || sending) return;
    try {
      const canvas = document.createElement("canvas");
      const w = Math.min(640, video.videoWidth || 640);
      const h = Math.round((w * (video.videoHeight || 480)) / (video.videoWidth || 640));
      canvas.width = w;
      canvas.height = h;
      const ctx = canvas.getContext("2d");
      if (!ctx) return;
      ctx.drawImage(video, 0, 0, w, h);
      const dataUrl = canvas.toDataURL("image/jpeg", 0.8);
      setSending(true);
      const res = await sendBrowserFrame(dataUrl);
      setLastResult(res.emitted ? `Sent → event created (motion ${res.motion_score ?? ""})` : `No event (${res.reason ?? "no motion"})`);
    } catch (e) {
      setLastResult(e instanceof Error ? e.message : "Send failed");
    } finally {
      setSending(false);
    }
  }, [active, sending]);

  return (
    <div role="tabpanel" className="mt-3 space-y-2">
      <p className="text-[13px] text-slate-400">
        Laptop / browser camera preview. Frames are sent to the backend only when you press Send
        (throttled server-side by motion + cooldown).
      </p>
      <video ref={videoRef} muted playsInline aria-label="Browser webcam preview" className="w-full rounded border border-slate-800 bg-black" />
      {error && (
        <p role="alert" className="text-xs text-red-300">{error}</p>
      )}
      <div className="flex gap-2">
        {!active ? (
          <button
            onClick={startCam}
            className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            Enable webcam
          </button>
        ) : (
          <>
            <button
              onClick={stopCam}
              className="rounded border border-slate-600 px-3 py-1.5 text-sm text-slate-200 hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
            >
              Stop
            </button>
            <button
              onClick={sendFrame}
              disabled={sending}
              className="rounded border border-emerald-600 px-3 py-1.5 text-sm text-emerald-100 hover:bg-emerald-950/50 focus:outline-none focus-visible:ring-2 focus-visible:ring-emerald-500 disabled:opacity-40"
            >
              {sending ? "Sending…" : "Send frame for analysis"}
            </button>
          </>
        )}
      </div>
      {lastResult && (
        <p aria-live="polite" className="text-xs text-slate-400">{lastResult}</p>
      )}
    </div>
  );
}

export { videoStart, videoStop };
