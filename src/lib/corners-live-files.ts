import "server-only";

import { promises as fs } from "fs";
import { cache } from "react";

import { tryGetKnownProjectFilePath } from "@/lib/project-file-paths";
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
const SNAPSHOT_KEY = process.env.CORNERS_LIVE_SNAPSHOT_KEY || "corners_state";
const RUNNING_ON_VERCEL = process.env.VERCEL === "1" || Boolean(process.env.VERCEL_ENV);
const LOCAL_SNAPSHOT_FILE = "data/corners-ou/corners-live-snapshot.json";

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

function newerTimestamp(left: string | null, right: string | null): string | null {
  const leftMs = left ? Date.parse(left) : Number.NaN;
  const rightMs = right ? Date.parse(right) : Number.NaN;
  const leftValid = Number.isFinite(leftMs);
  const rightValid = Number.isFinite(rightMs);
  if (leftValid && rightValid) return leftMs >= rightMs ? left : right;
  if (leftValid) return left;
  if (rightValid) return right;
  return right ?? left ?? null;
}

async function readLocalSnapshotGeneratedAt(): Promise<string | null> {
  try {
    const fullPath = tryGetKnownProjectFilePath(LOCAL_SNAPSHOT_FILE);
    if (!fullPath) return null;
    const stat = await fs.stat(fullPath);
    return stat.mtime.toISOString();
  } catch {
    return null;
  }
}

export async function readCornersLiveFile(relativePath: string): Promise<string | null> {
  const readLocal = async (): Promise<string | null> => {
    try {
      const fullPath = tryGetKnownProjectFilePath(relativePath);
      if (!fullPath) return null;
      return await fs.readFile(fullPath, "utf8");
    } catch {
      return null;
    }
  };

  if (!RUNNING_ON_VERCEL) {
    const local = await readLocal();
    if (typeof local === "string") return local;
  }

  const hosted = getSnapshotFileEntry(await loadHostedSnapshot(), relativePath)?.content;
  if (typeof hosted === "string") return hosted;

  if (RUNNING_ON_VERCEL) {
    return await readLocal();
  }

  return null;
}

export async function readCornersLiveJson<T>(relativePath: string): Promise<T | null> {
  const text = await readCornersLiveFile(relativePath);
  if (!text) return null;
  try {
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}

export async function readCornersLiveMtime(relativePath: string): Promise<string | null> {
  const readLocalMtime = async (): Promise<string | null> => {
    try {
      const fullPath = tryGetKnownProjectFilePath(relativePath);
      if (!fullPath) return null;
      const stat = await fs.stat(fullPath);
      return stat.mtime.toISOString();
    } catch {
      return null;
    }
  };

  if (!RUNNING_ON_VERCEL) {
    const localMtime = await readLocalMtime();
    if (typeof localMtime === "string") return localMtime;
  }

  const hosted = getSnapshotFileEntry(await loadHostedSnapshot(), relativePath)?.mtime;
  if (typeof hosted === "string") return hosted;

  if (RUNNING_ON_VERCEL) {
    return await readLocalMtime();
  }

  return null;
}

export async function readCornersLiveSnapshotGeneratedAt(): Promise<string | null> {
  const payload = await loadHostedSnapshot();
  const hostedGeneratedAt = typeof payload?.generated_at === "string" ? payload.generated_at : null;
  const localGeneratedAt = await readLocalSnapshotGeneratedAt();
  return newerTimestamp(hostedGeneratedAt, localGeneratedAt);
}
