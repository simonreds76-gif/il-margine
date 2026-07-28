import "server-only";

import { promises as fs } from "fs";
import path from "path";

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

export async function readPenaltyReviewState(): Promise<Record<string, PenaltyReviewStateEntry>> {
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

async function writePenaltyReviewState(items: Record<string, PenaltyReviewStateEntry>): Promise<void> {
  const payload: PenaltyReviewStatePayload = {
    schema_version: 1,
    items,
  };
  await fs.mkdir(path.dirname(STATE_PATH), { recursive: true });
  await fs.writeFile(STATE_PATH, `${JSON.stringify(payload, null, 2)}\n`, "utf8");
}

export async function setPenaltyReviewResolution(
  id: string,
  status: PenaltyReviewResolution | "active",
): Promise<Record<string, PenaltyReviewStateEntry>> {
  const trimmedId = id.trim();
  if (!trimmedId) {
    throw new Error("Missing penalty review id");
  }

  const current = await readPenaltyReviewState();
  if (status === "active") {
    delete current[trimmedId];
  } else {
    current[trimmedId] = {
      status,
      updated_at: new Date().toISOString(),
    };
  }
  await writePenaltyReviewState(current);
  return current;
}
