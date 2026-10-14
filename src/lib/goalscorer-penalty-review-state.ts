import "server-only";

import { promises as fs } from "fs";
import path from "path";
import { randomUUID } from "node:crypto";
import { readPenaltyEditorial, savePenaltyEditorial } from "@/lib/penalty-editorial-store";

export type PenaltyReviewResolution = "accepted" | "ignored" | "deferred" | "applied";

export type PenaltyReviewStateEntry = {
  status: PenaltyReviewResolution;
  updated_at: string;
};

type PenaltyReviewStatePayload = {
  schema_version: 1;
  items: Record<string, PenaltyReviewStateEntry>;
};

const STATE_PATH = path.join(process.cwd(), "data/goalscorer/penalty-duty-review-state.json");

function normalizeEntry(value: unknown): PenaltyReviewStateEntry | null {
  if (!value || typeof value !== "object") return null;
  const rawStatus =
    typeof (value as { status?: unknown }).status === "string"
      ? (value as { status: string }).status
      : "";
  const updatedAt =
    typeof (value as { updated_at?: unknown }).updated_at === "string"
      ? (value as { updated_at: string }).updated_at
      : "";

  // Preserve review decisions made before the four-state ticket lifecycle.
  const status =
    rawStatus === "dismissed"
      ? "ignored"
      : rawStatus === "done"
        ? "applied"
        : rawStatus;
  if (
    status !== "accepted" &&
    status !== "ignored" &&
    status !== "deferred" &&
    status !== "applied"
  ) {
    return null;
  }
  if (!updatedAt) return null;
  return {
    status: status as PenaltyReviewResolution,
    updated_at: updatedAt,
  };
}

async function readLocalPenaltyReviewState(): Promise<Record<string, PenaltyReviewStateEntry>> {
  try {
    const raw = await fs.readFile(STATE_PATH, "utf8");
    const parsed = JSON.parse(raw) as Partial<PenaltyReviewStatePayload>;
    const items = parsed.items && typeof parsed.items === "object" ? parsed.items : {};
    return Object.fromEntries(
      Object.entries(items).flatMap(([key, value]) => {
        const normalized = normalizeEntry(value);
        return normalized ? [[key, normalized]] : [];
      }),
    );
  } catch {
    return {};
  }
}

export async function readPenaltyReviewState(): Promise<Record<string, PenaltyReviewStateEntry>> {
  const [items, state] = await Promise.all([readLocalPenaltyReviewState(), readPenaltyEditorial()]);
  for (const [id, entry] of Object.entries(state.payload.tickets)) {
    if (entry.status === "active") delete items[id];
    else items[id] = {status: entry.status, updated_at: entry.updated_at};
  }
  return items;
}

export async function setPenaltyReviewResolution(
  id: string,
  status: PenaltyReviewResolution | "active",
): Promise<Record<string, PenaltyReviewStateEntry>> {
  const trimmedId = id.trim();
  if (!trimmedId) {
    throw new Error("Missing penalty review id");
  }

  const state = await readPenaltyEditorial();
  const at = new Date().toISOString();
  state.payload.tickets[trimmedId] = {status, updated_at: at};
  state.payload.audit.push({id: randomUUID(), at, action: `ticket_${status}`, ticket: trimmedId, club: "", before: null, after: null, reason: "Reviewed in Model Monitor"});
  await savePenaltyEditorial(state.revision, state.payload);
  return readPenaltyReviewState();
}
