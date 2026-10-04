"use client";

import { Suspense } from "react";
import IncidentsView from "@/components/IncidentsView";

export default function IncidentsPage() {
  return (
    <Suspense fallback={<p className="p-6 text-sm text-slate-400">Loading incidents…</p>}>
      <IncidentsView />
    </Suspense>
  );
}
