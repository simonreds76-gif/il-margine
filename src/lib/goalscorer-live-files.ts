import "server-only";

import { promises as fs } from "fs";
import path from "path";
import { cache } from "react";

import { getSupabaseAdmin } from "@/lib/supabase-server";

type SnapshotFileEntry =
  | string
  | {
      content?: string;
      mtime?: string;
    };

type SnapshotPayload = {
  generated_at?: string;
  files?: Record<string, SnapshotFileEntry>;
};

const SNAPSHOT_TABLE = "goalscorer_live_snapshot";
const SNAPSHOT_KEY = process.env.GOALSCORER_LIVE_SNAPSHOT_KEY || "live_state";

const loadHostedSnapshot = cache(async (): Promise<SnapshotPayload | null> => {
  try {
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from(SNAPSHOT_TABLE)
      .select("payload")
      .eq("snapshot_key", SNAPSHOT_KEY)
      .maybeSingle();

    if (error || !data?.payload || typeof data.payload !== "object") return null;
    return data.payload as SnapshotPayload;
  } catch {
    return null;
  }
});

function getSnapshotFileEntry(payload: SnapshotPayload | null, relativePath: string): { content?: string; mtime?: string } | null {
  const rawEntry = payload?.files?.[relativePath];
  if (!rawEntry) return null;
  if (typeof rawEntry === "string") return { content: rawEntry };
  return {
    content: typeof rawEntry.content === "string" ? rawEntry.content : undefined,
    mtime: typeof rawEntry.mtime === "string" ? rawEntry.mtime : undefined,
  };
}

export async function readGoalscorerLiveFile(relativePath: string): Promise<string | null> {
  const hosted = getSnapshotFileEntry(await loadHostedSnapshot(), relativePath)?.content;
  if (typeof hosted === "string") return hosted;

  try {
    return await fs.readFile(path.join(process.cwd(), relativePath), "utf8");
  } catch {
    return null;
  }
}

export async function readGoalscorerLiveMtime(relativePath: string): Promise<string | null> {
  const hosted = getSnapshotFileEntry(await loadHostedSnapshot(), relativePath)?.mtime;
  if (typeof hosted === "string") return hosted;

  try {
    const stat = await fs.stat(path.join(process.cwd(), relativePath));
    return stat.mtime.toISOString();
  } catch {
    return null;
  }
}

export async function readGoalscorerLiveSnapshotGeneratedAt(): Promise<string | null> {
  const payload = await loadHostedSnapshot();
  return typeof payload?.generated_at === "string" ? payload.generated_at : null;
}
