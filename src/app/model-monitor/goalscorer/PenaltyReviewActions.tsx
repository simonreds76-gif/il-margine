"use client";

import { useRouter } from "next/navigation";
import { useState, useTransition } from "react";

export type PenaltyReviewStatus = "accepted" | "ignored" | "deferred" | "applied";

type Props = {
  rowId: string;
  status?: PenaltyReviewStatus;
  mode?: "event" | "source";
};

async function updateResolution(
  rowId: string,
  status: PenaltyReviewStatus | "active",
) {
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

type Action = {
  label: string;
  status: PenaltyReviewStatus | "active";
  successText: string;
  className: string;
};

const primaryClass =
  "border-emerald-500/30 bg-emerald-500/10 text-emerald-200 hover:border-emerald-400/40 hover:text-emerald-100";
const warningClass =
  "border-amber-500/30 bg-amber-500/10 text-amber-200 hover:border-amber-400/40 hover:text-amber-100";
const neutralClass =
  "border-slate-700/80 bg-slate-950/60 text-slate-300 hover:border-slate-500/80 hover:text-slate-100";
const restoreClass =
  "border-cyan-500/30 bg-cyan-500/10 text-cyan-200 hover:border-cyan-400/40 hover:text-cyan-100";

function actionsFor(status?: PenaltyReviewStatus): Action[] {
  if (!status) {
    return [
      {
        label: "Accept evidence",
        status: "accepted",
        successText: "Evidence accepted; hierarchy edit still required",
        className: primaryClass,
      },
      {
        label: "Defer",
        status: "deferred",
        successText: "Parked for more evidence",
        className: warningClass,
      },
      {
        label: "Done - keep order",
        status: "ignored",
        successText: "Reviewed and closed with the current order",
        className: neutralClass,
      },
    ];
  }
  if (status === "accepted") {
    return [
      {
        label: "Mark applied",
        status: "applied",
        successText: "Hierarchy and audit date validated",
        className: primaryClass,
      },
      {
        label: "Defer",
        status: "deferred",
        successText: "Parked for more evidence",
        className: warningClass,
      },
      {
        label: "Done - keep order",
        status: "ignored",
        successText: "Reviewed and closed with the current order",
        className: neutralClass,
      },
    ];
  }
  if (status === "deferred") {
    return [
      {
        label: "Accept evidence",
        status: "accepted",
        successText: "Evidence accepted; hierarchy edit still required",
        className: primaryClass,
      },
      {
        label: "Re-open",
        status: "active",
        successText: "Returned to active review",
        className: restoreClass,
      },
      {
        label: "Done - keep order",
        status: "ignored",
        successText: "Reviewed and closed with the current order",
        className: neutralClass,
      },
    ];
  }
  return [
    {
      label: "Restore ticket",
      status: "active",
      successText: "Returned to active review",
      className: restoreClass,
    },
  ];
}

function sourceActionsFor(status?: PenaltyReviewStatus): Action[] {
  if (status) {
    return [
      {
        label: "Restore ticket",
        status: "active",
        successText: "Returned to active review",
        className: restoreClass,
      },
    ];
  }
  return [
    {
      label: "Hierarchy updated",
      status: "applied",
      successText: "Hierarchy change validated",
      className: primaryClass,
    },
    {
      label: "Keep current order",
      status: "ignored",
      successText: "Closed with no public change",
      className: neutralClass,
    },
  ];
}

function statusDescription(status?: PenaltyReviewStatus, mode: "event" | "source" = "event"): string {
  if (mode === "source") {
    if (status === "ignored") return "Closed after review; the current public order is unchanged.";
    if (status === "applied") return "Closed after the reviewed hierarchy update passed validation.";
    return "Choose an outcome only after checking squad status and direct match evidence.";
  }
  if (status === "accepted") return "Evidence accepted. Edit the hierarchy, evidence log and audit date before marking applied.";
  if (status === "deferred") return "Parked until stronger evidence arrives.";
  if (status === "ignored") return "Reviewed and closed with the current public order unchanged.";
  if (status === "applied") return "Public hierarchy membership and update dates passed validation.";
  return "Review the event before changing any public hierarchy.";
}

export function PenaltyReviewActions({ rowId, status, mode = "event" }: Props) {
  const router = useRouter();
  const [isPending, startTransition] = useTransition();
  const [error, setError] = useState<string | null>(null);
  const [statusText, setStatusText] = useState<string | null>(null);

  const handleClick = (action: Action) => {
    setError(null);
    setStatusText(null);
    startTransition(async () => {
      try {
        await updateResolution(rowId, action.status);
        setStatusText(action.successText);
        await new Promise((resolve) => setTimeout(resolve, 350));
        router.refresh();
      } catch (nextError) {
        setError(nextError instanceof Error ? nextError.message : "Update failed");
      }
    });
  };

  return (
    <div className="mt-4">
      <div className="flex flex-wrap items-center gap-2">
        {(mode === "source" ? sourceActionsFor(status) : actionsFor(status)).map((action) => (
          <button
            key={action.status}
            type="button"
            onClick={() => handleClick(action)}
            disabled={isPending}
            className={`inline-flex items-center rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] transition-colors disabled:cursor-not-allowed disabled:opacity-60 ${action.className}`}
          >
            {action.label}
          </button>
        ))}
        {isPending ? <span className="text-xs text-cyan-200">Saving...</span> : null}
        {!isPending && statusText ? <span className="text-xs text-emerald-300">{statusText}</span> : null}
      </div>
      <p className="mt-2 text-xs text-slate-500">{statusDescription(status, mode)}</p>
      {error ? <p className="mt-2 text-xs font-medium text-rose-300">{error}</p> : null}
    </div>
  );
}
