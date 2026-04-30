"use client";

import { useState, useEffect } from "react";
import MonthlyBreakdown, { type MonthRow, type MonthlyBreakdownScope } from "./MonthlyBreakdown";

interface MonthlyBreakdownSectionProps {
  scope: MonthlyBreakdownScope;
}

export default function MonthlyBreakdownSection({ scope }: MonthlyBreakdownSectionProps) {
  const [payload, setPayload] = useState<{ show: boolean; rows: MonthRow[] } | null>(null);

  useEffect(() => {
    async function fetch_() {
      try {
        const res = await fetch(`/api/public-record?scope=monthly&monthlyScope=${scope}`);
        const json = await res.json();
        if (!res.ok) throw new Error(json?.error || "Failed to load monthly breakdown");
        setPayload({ show: json.show === true, rows: (json.rows ?? []) as MonthRow[] });
      } catch (error) {
        console.error("Error fetching monthly breakdown:", error);
        setPayload({ show: false, rows: [] });
      }
    }
    fetch_();
  }, [scope]);

  if (payload?.show !== true || payload.rows.length === 0) return null;

  return (
    <section className="border-b border-slate-800/30 py-16 md:py-20">
      <div className="max-w-6xl mx-auto px-4 sm:px-6 lg:px-8">
        <MonthlyBreakdown scope={scope} rowsOverride={payload.rows} />
      </div>
    </section>
  );
}

