import type { Severity } from "@/types";

/** Severity is always icon + text, never color alone. */
export default function SeverityBadge({
  severity,
  size = "md",
}: {
  severity: Severity;
  size?: "sm" | "md";
}) {
  const config = {
    critical: { icon: "▲", label: "CRITICAL", cls: "border-red-500/70 bg-red-950/50 text-red-200" },
    warning: { icon: "◆", label: "WARNING", cls: "border-amber-500/60 bg-amber-950/30 text-amber-200" },
    info: { icon: "●", label: "INFO", cls: "border-slate-500/60 bg-slate-900 text-slate-300" },
  } as const;
  const c = config[severity];
  const sizing = size === "sm" ? "px-1 py-px text-[10px]" : "px-1.5 py-0.5 text-xs";
  return (
    <span
      className={`inline-flex shrink-0 items-center gap-1 rounded border font-semibold tracking-wide ${c.cls} ${sizing}`}
    >
      <span aria-hidden="true">{c.icon}</span> {c.label}
    </span>
  );
}

export function StatusPill({ status }: { status: string }) {
  const map: Record<string, string> = {
    open: "border-sky-500/50 bg-sky-950/40 text-sky-200",
    acknowledged: "border-violet-500/50 bg-violet-950/40 text-violet-200",
    resolved: "border-emerald-500/50 bg-emerald-950/30 text-emerald-200",
  };
  const cls = map[status] ?? "border-slate-600 bg-slate-900 text-slate-300";
  return (
    <span
      className={`inline-flex shrink-0 items-center rounded-full border px-2 py-px text-[11px] font-medium ${cls}`}
    >
      {status}
    </span>
  );
}
