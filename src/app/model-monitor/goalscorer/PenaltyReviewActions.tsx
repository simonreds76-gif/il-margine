"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

type Props = {
  rowId: string;
  resolvedStatus?: "dismissed" | "done";
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

export function PenaltyReviewActions({ rowId, resolvedStatus }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [statusText, setStatusText] = useState<string | null>(null);

  const handleClick = (status: "dismissed" | "done" | "active", successText: string) => {
    setError(null);
    setStatusText(null);
    startTransition(async () => {
      try {
        await updateResolution(rowId, status);
        setStatusText(successText);
        await new Promise((resolve) => setTimeout(resolve, 350));
        router.refresh();
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Update failed");
      }
    });
  };

  if (resolvedStatus) {
    return (
      <div className="mt-4 flex flex-wrap items-center gap-2">
        <button
          type="button"
          onClick={() => handleClick("active", "Restored")}
          disabled={isPending}
          className="inline-flex items-center rounded-full border border-cyan-500/30 bg-cyan-500/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-cyan-200 transition-colors hover:border-cyan-400/40 hover:text-cyan-100 disabled:cursor-not-allowed disabled:opacity-60"
        >
          Restore row
        </button>
        <span className="text-xs text-slate-500">
          {resolvedStatus === "done" ? "Marked as updated taker data." : "Marked as no action needed."}
        </span>
        {isPending ? <span className="text-xs text-cyan-200">Saving...</span> : null}
        {!isPending && statusText ? <span className="text-xs text-emerald-300">{statusText}</span> : null}
        {error ? <span className="text-xs text-rose-300">{error}</span> : null}
      </div>
    );
  }

  return (
    <div className="mt-4 flex flex-wrap items-center gap-2">
      <button
        type="button"
        onClick={() => handleClick("done", "Saved as updated")}
        disabled={isPending}
        className="inline-flex items-center rounded-full border border-emerald-500/30 bg-emerald-500/10 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-emerald-200 transition-colors hover:border-emerald-400/40 hover:text-emerald-100 disabled:cursor-not-allowed disabled:opacity-60"
      >
        Updated taker data
      </button>
      <button
        type="button"
        onClick={() => handleClick("dismissed", "Saved as no action")}
        disabled={isPending}
        className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-950/60 px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] text-slate-300 transition-colors hover:border-slate-500/80 hover:text-slate-100 disabled:cursor-not-allowed disabled:opacity-60"
      >
        No action needed
      </button>
      {isPending ? <span className="text-xs text-cyan-200">Saving...</span> : null}
      {!isPending && statusText ? <span className="text-xs text-emerald-300">{statusText}</span> : null}
      {error ? <span className="text-xs text-rose-300">{error}</span> : null}
    </div>
  );
}

