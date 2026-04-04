"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

type Props = {
  rowId: string;
};

async function updateResolution(rowId: string, status: "dismissed" | "done" | "active") {
  const response = await fetch("/api/model-monitor/goalscorer/penalty-watchlist", {
    method: "POST",
    headers: {
      "Content-Type": "application/json",
    },
    body: JSON.stringify({ id: rowId, status }),
  });

  if (!response.ok) {
    const payload = (await response.json().catch(() => null)) as { error?: string } | null;
    throw new Error(payload?.error || "Failed to update penalty review row");
  }
}

export function PenaltyReviewActions({ rowId }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);

  const handleClick = (status: "dismissed" | "done") => {
    setError(null);
    startTransition(async () => {
      try {
        await updateResolution(rowId, status);
        router.refresh();
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Update failed");
      }
    });
  };

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => handleClick("done")}
        disabled={isPending}
        className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-200 transition-colors hover:border-emerald-400/40 hover:text-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
      >
        Mark done
      </button>
      <button
        type="button"
        onClick={() => handleClick("dismissed")}
        disabled={isPending}
        className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-950/60 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-slate-300 transition-colors hover:border-slate-500/80 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
      >
        Dismiss
      </button>
      {error ? <span className="text-xs text-rose-300">{error}</span> : null}
    </div>
  );
}
