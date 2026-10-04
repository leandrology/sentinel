"use client";

function pageNumbers(page: number, totalPages: number): Array<number | "…"> {
  if (totalPages <= 7) return Array.from({ length: totalPages }, (_, k) => k + 1);
  const window = new Set<number>([1, 2, page - 1, page, page + 1, totalPages - 1, totalPages]);
  const sorted = Array.from(window).filter((p) => p >= 1 && p <= totalPages).sort((a, b) => a - b);
  const out: Array<number | "…"> = [];
  for (let k = 0; k < sorted.length; k++) {
    out.push(sorted[k]);
    if (k < sorted.length - 1 && sorted[k + 1] - sorted[k] > 1) out.push("…");
  }
  return out;
}

const btnCls =
  "rounded border border-slate-700 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:bg-slate-800 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500 disabled:cursor-not-allowed disabled:opacity-40";

export default function Pagination({
  page,
  totalPages,
  totalItems,
  pageSize,
  onChange,
  label,
}: {
  page: number;
  totalPages: number;
  totalItems: number;
  pageSize: number;
  onChange: (page: number) => void;
  label: string;
}) {
  if (totalItems === 0 || totalPages <= 1) return null;
  const start = (page - 1) * pageSize + 1;
  const end = Math.min(page * pageSize, totalItems);
  return (
    <nav
      aria-label={label}
      className="flex flex-wrap items-center gap-x-3 gap-y-2 border-t border-slate-800 px-4 py-3"
    >
      <p aria-live="polite" className="text-xs text-slate-500">
        Showing <span className="font-semibold text-slate-300">{start}–{end}</span> of{" "}
        <span className="font-semibold text-slate-300">{totalItems}</span>
      </p>
      <div className="ml-auto flex flex-wrap items-center gap-1">
        <button
          onClick={() => onChange(page - 1)}
          disabled={page <= 1}
          aria-label="Previous page"
          className={btnCls}
        >
          ← Prev
        </button>
        {pageNumbers(page, totalPages).map((p, k) =>
          p === "…" ? (
            <span key={`gap-${k}`} aria-hidden="true" className="px-1 text-xs text-slate-600">
              …
            </span>
          ) : (
            <button
              key={p}
              onClick={() => onChange(p)}
              aria-label={`Page ${p}`}
              aria-current={p === page ? "page" : undefined}
              className={[
                btnCls,
                p === page ? "border-sky-500/60 bg-sky-950/40 text-sky-100" : "",
              ].join(" ")}
            >
              {p}
            </button>
          )
        )}
        <button
          onClick={() => onChange(page + 1)}
          disabled={page >= totalPages}
          aria-label="Next page"
          className={btnCls}
        >
          Next →
        </button>
      </div>
    </nav>
  );
}
