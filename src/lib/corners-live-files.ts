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

export type CornersLiveSourceStatus = {
  source: "hosted" | "local" | "missing";
  reason:
    | "hosted_newer"
    | "local_newer"
    | "hosted_only"
    | "local_only"
    | "no_data";
  hostedSnapshotAvailable: boolean;
  localSnapshotAvailable: boolean;
  hostedGeneratedAt: string | null;
  localSnapshotGeneratedAt: string | null;
  hostedFileMtime: string | null;
  localFileMtime: string | null;
};

const SNAPSHOT_TABLE = "goalscorer_live_snapshot";
const SNAPSHOT_KEY = process.env.CORNERS_LIVE_SNAPSHOT_KEY || "corners_state";
const LOCAL_SNAPSHOT_FILE = "data/corners-ou/corners-live-snapshot.json";
const PREFER_LOCAL =
  process.env.MONITOR_PREFER_LOCAL === "1" || process.env.NODE_ENV !== "production";
const GITHUB_RAW_BASE =
  process.env.MONITOR_GITHUB_RAW_BASE ||
  "https://raw.githubusercontent.com/simonreds76-gif/il-margine/golden-with-speed-insights";

function snapshotFreshness(payload: SnapshotPayload | null): number {
  const stamp = payload?.generated_at ? Date.parse(payload.generated_at) : Number.NaN;
  return Number.isFinite(stamp) ? stamp : Number.NEGATIVE_INFINITY;
}

function chooseFreshestSnapshot(candidates: Array<SnapshotPayload | null>): SnapshotPayload | null {
  let best: SnapshotPayload | null = null;
  let bestFreshness = Number.NEGATIVE_INFINITY;
  for (const candidate of candidates) {
    if (!candidate) continue;
    const freshness = snapshotFreshness(candidate);
    if (!best || freshness >= bestFreshness) {
      best = candidate;
      bestFreshness = freshness;
    }
  }
  return best;
}

async function readSupabaseSnapshot(): Promise<SnapshotPayload | null> {
  try {
    const supabase = getSupabaseAdmin();
    const { data, error } = await supabase
      .from(SNAPSHOT_TABLE)
      .select("payload")
      .eq("snapshot_key", SNAPSHOT_KEY)
      .maybeSingle();

    if (!error && data?.payload && typeof data.payload === "object") {
      return data.payload as SnapshotPayload;
    }
  } catch {
    // Fall through.
  }
  return null;
}

async function readGithubSnapshot(): Promise<SnapshotPayload | null> {
  try {
    const response = await fetch(`${GITHUB_RAW_BASE}/${LOCAL_SNAPSHOT_FILE}`, {
      cache: "no-store",
    });
    if (!response.ok) return null;
    const data = (await response.json()) as SnapshotPayload;
    if (!data || typeof data !== "object") return null;
    return data;
  } catch {
    return null;
  }
}

const loadHostedSnapshot = cache(async (): Promise<SnapshotPayload | null> => {
  const [supabaseSnapshot, githubSnapshot] = await Promise.all([
    readSupabaseSnapshot(),
    readGithubSnapshot(),
  ]);
  return chooseFreshestSnapshot([supabaseSnapshot, githubSnapshot]);
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

function shouldPreferHosted(hostedMtime: string | null, localMtime: string | null): boolean {
  const hostedMs = hostedMtime ? Date.parse(hostedMtime) : Number.NaN;
  const localMs = localMtime ? Date.parse(localMtime) : Number.NaN;
  const hostedValid = Number.isFinite(hostedMs);
  const localValid = Number.isFinite(localMs);
  if (hostedValid && localValid) return hostedMs >= localMs;
  if (hostedValid) return true;
  return false;
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

  if (!PREFER_LOCAL) {
    const payload = await loadHostedSnapshot();
    const hostedEntry = getSnapshotFileEntry(payload, relativePath);
    const localMtime = await readLocalMtime();
    if (typeof hostedEntry?.content === "string" && shouldPreferHosted(hostedEntry.mtime ?? payload?.generated_at ?? null, localMtime)) {
      return hostedEntry.content;
    }
  }

  const local = await readLocal();
  if (typeof local === "string") return local;

  if (PREFER_LOCAL) {
    const hosted = getSnapshotFileEntry(await loadHostedSnapshot(), relativePath)?.content;
    if (typeof hosted === "string") return hosted;
  } else {
    const hosted = getSnapshotFileEntry(await loadHostedSnapshot(), relativePath)?.content;
    if (typeof hosted === "string") return hosted;
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

  if (!PREFER_LOCAL) {
    const payload = await loadHostedSnapshot();
    const hosted = getSnapshotFileEntry(payload, relativePath)?.mtime ?? payload?.generated_at ?? null;
    const localMtime = await readLocalMtime();
    if (shouldPreferHosted(hosted, localMtime)) return hosted;
    if (typeof localMtime === "string") return localMtime;
    if (typeof hosted === "string") return hosted;
    return null;
  }

  const localMtime = await readLocalMtime();
  if (typeof localMtime === "string") return localMtime;

  if (PREFER_LOCAL) {
    const hosted = getSnapshotFileEntry(await loadHostedSnapshot(), relativePath)?.mtime;
    if (typeof hosted === "string") return hosted;
  }

  return null;
}

export async function readCornersLiveSnapshotGeneratedAt(): Promise<string | null> {
  const payload = await loadHostedSnapshot();
  const hostedGeneratedAt = typeof payload?.generated_at === "string" ? payload.generated_at : null;
  const localGeneratedAt = await readLocalSnapshotGeneratedAt();
  return newerTimestamp(hostedGeneratedAt, localGeneratedAt);
}

export async function inspectCornersLiveSource(relativePath: string): Promise<CornersLiveSourceStatus> {
  const payload = await loadHostedSnapshot();
  const hostedGeneratedAt = typeof payload?.generated_at === "string" ? payload.generated_at : null;
  const hostedEntry = getSnapshotFileEntry(payload, relativePath);
  const hostedFileMtime = hostedEntry?.mtime ?? hostedGeneratedAt ?? null;
  const localSnapshotGeneratedAt = await readLocalSnapshotGeneratedAt();

  let localFileMtime: string | null = null;
  try {
    const fullPath = tryGetKnownProjectFilePath(relativePath);
    if (fullPath) {
      const stat = await fs.stat(fullPath);
      localFileMtime = stat.mtime.toISOString();
    }
  } catch {
    localFileMtime = null;
  }

  if (shouldPreferHosted(hostedFileMtime, localFileMtime)) {
    return {
      source: "hosted",
      reason: localFileMtime ? "hosted_newer" : "hosted_only",
      hostedSnapshotAvailable: Boolean(payload),
      localSnapshotAvailable: Boolean(localSnapshotGeneratedAt),
      hostedGeneratedAt,
      localSnapshotGeneratedAt,
      hostedFileMtime,
      localFileMtime,
    };
  }

  if (localFileMtime) {
    return {
      source: "local",
      reason: hostedFileMtime ? "local_newer" : "local_only",
      hostedSnapshotAvailable: Boolean(payload),
      localSnapshotAvailable: Boolean(localSnapshotGeneratedAt),
      hostedGeneratedAt,
      localSnapshotGeneratedAt,
      hostedFileMtime,
      localFileMtime,
    };
  }

  return {
    source: "missing",
    reason: "no_data",
    hostedSnapshotAvailable: Boolean(payload),
    localSnapshotAvailable: Boolean(localSnapshotGeneratedAt),
    hostedGeneratedAt,
    localSnapshotGeneratedAt,
    hostedFileMtime,
    localFileMtime,
  };
}
