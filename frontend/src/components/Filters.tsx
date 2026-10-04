"use client";

export const SITES = ["site-100", "site-101", "site-102", "site-103", "site-104", "site-105", "site-106"];
export const ZONES = ["north-perimeter", "lobby", "loading-dock", "roof", "server-room"];
export const SEVERITIES = ["critical", "warning", "info"] as const;
export const STATUSES = ["open", "acknowledged", "resolved"] as const;

const inputCls =
  "rounded border border-slate-700 bg-slate-900 px-2 py-1.5 text-sm text-slate-100 transition-colors hover:border-slate-600 focus:border-sky-500 focus:outline-none focus:ring-2 focus:ring-sky-500/40";

function Select({
  id,
  label,
  value,
  onChange,
  options,
}: {
  id: string;
  label: string;
  value: string;
  onChange: (v: string) => void;
  options: readonly string[];
}) {
  return (
    <span className="flex items-center gap-1.5">
      <label htmlFor={id} className="text-xs font-medium uppercase tracking-wide text-slate-400">
        {label}
      </label>
      <select id={id} value={value} onChange={(e) => onChange(e.target.value)} className={`${inputCls} min-w-[7rem]`}>
        <option value="">All</option>
        {options.map((o) => (
          <option key={o} value={o}>
            {o}
          </option>
        ))}
      </select>
    </span>
  );
}

export default function Filters({
  site,
  zone,
  status,
  severity = "",
  search = "",
  onSite,
  onZone,
  onStatus,
  onSeverity,
  onSearch,
  onClear,
  shown = null,
  total = null,
}: {
  site: string;
  zone: string;
  status: string;
  severity?: string;
  search?: string;
  onSite: (v: string) => void;
  onZone: (v: string) => void;
  onStatus: (v: string) => void;
  onSeverity?: (v: string) => void;
  onSearch?: (v: string) => void;
  onClear?: () => void;
  shown?: number | null;
  total?: number | null;
}) {
  const hasActive = Boolean(site || zone || status || severity || search);
  return (
    <div className="space-y-2">
      <div className="flex flex-wrap items-center gap-x-4 gap-y-2" role="group" aria-label="Site and zone filters">
        <Select id="filter-site" label="Site" value={site} onChange={onSite} options={SITES} />
        <Select id="filter-zone" label="Zone" value={zone} onChange={onZone} options={ZONES} />
        <Select id="filter-status" label="Status" value={status} onChange={onStatus} options={STATUSES} />
        {onSeverity && (
          <Select id="filter-severity" label="Severity" value={severity} onChange={onSeverity} options={SEVERITIES} />
        )}
        {onSearch && (
          <span className="flex min-w-[10rem] flex-1 items-center gap-1.5 sm:max-w-[16rem]">
            <label htmlFor="filter-search" className="text-xs font-medium uppercase tracking-wide text-slate-400">
              Search
            </label>
            <input
              id="filter-search"
              type="search"
              value={search}
              onChange={(e) => onSearch(e.target.value)}
              placeholder="type, site, zone…"
              className={`${inputCls} w-full placeholder:text-slate-600`}
            />
          </span>
        )}
        {onClear && hasActive && (
          <button
            onClick={onClear}
            className="rounded border border-slate-700 px-2.5 py-1.5 text-xs font-medium text-slate-300 transition-colors hover:border-slate-500 hover:bg-slate-800 hover:text-slate-100 focus:outline-none focus-visible:ring-2 focus-visible:ring-sky-500"
          >
            Reset filters
          </button>
        )}
      </div>
      {(shown !== null || hasActive) && (
        <p aria-live="polite" className="text-xs text-slate-500">
          {shown !== null && total !== null ? (
            <>Showing <span className="font-semibold text-slate-300">{shown}</span> of <span className="font-semibold text-slate-300">{total}</span> events{hasActive ? " — filters active" : ""}</>
          ) : hasActive ? (
            "Filters active"
          ) : (
            "No filters — showing everything"
          )}
        </p>
      )}
    </div>
  );
}
