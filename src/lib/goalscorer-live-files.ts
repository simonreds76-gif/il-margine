import "server-only";

import { execFile } from "child_process";
import { promises as fs } from "fs";
import { promisify } from "util";

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

type HostedRawFile = {
  content: string;
  mtime: string | null;
};

const SNAPSHOT_TABLE = "goalscorer_live_snapshot";
const SNAPSHOT_KEY = process.env.GOALSCORER_LIVE_SNAPSHOT_KEY || "live_state";
const LOCAL_SNAPSHOT_FILE = "data/goalscorer/goalscorer-live-snapshot.json";
const PREFER_LOCAL = process.env.MONITOR_PREFER_LOCAL === "1";
const GITHUB_RAW_BASE =
  process.env.MONITOR_GITHUB_RAW_BASE ||
  "https://raw.githubusercontent.com/simonreds76-gif/il-margine/golden-with-speed-insights";
const GIT_REMOTE_REF = process.env.MONITOR_GIT_REMOTE_REF || "origin/golden-with-speed-insights";
const HOSTED_CACHE_TTL_MS = process.env.NODE_ENV === "development" ? 15 * 1000 : 5 * 60 * 1000;
const execFileAsync = promisify(execFile);

let snapshotCache: { expiresAt: number; payload: SnapshotPayload | null } | null = null;
let gitFetchPromise: Promise<void> | null = null;
let lastGitFetchAttemptAt = 0;
const rawFileCache = new Map<string, { expiresAt: number; value: HostedRawFile | null }>();

function parseCsvLine(line: string): string[] {
  const result: string[] = [];
  let current = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const char = line[i];
    if (char === '"') {
      if (inQuotes && line[i + 1] === '"') {
        current += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (char === "," && !inQuotes) {
      result.push(current);
      current = "";
      continue;
    }
    current += char;
  }
  result.push(current);
  return result;
}

function extractEmbeddedFreshness(relativePath: string, content: string | null | undefined): string | null {
  if (!content) return null;

  const jsonLike = relativePath.endsWith(".json");
  if (jsonLike) {
    try {
      const parsed = JSON.parse(content) as Record<string, unknown>;
      const candidates = [
        parsed.generated_at,
        parsed.updated_at,
        parsed.last_successful_finished_at,
        parsed.compared_at,
      ];
      for (const candidate of candidates) {
        if (typeof candidate === "string" && Number.isFinite(Date.parse(candidate))) {
          return candidate;
        }
      }
    } catch {
      // fall through
    }
  }

  if (relativePath.endsWith(".csv")) {
    const lines = content.split(/\r?\n/).filter(Boolean);
    if (lines.length >= 2) {
      const headers = parseCsvLine(lines[0]).map((header) => header.trim());
      const values = parseCsvLine(lines[1]);
      const timestampColumns = ["compared_at", "generated_at", "updated_at", "logged_at", "settled_at", "captured_at"];
      for (const column of timestampColumns) {
        const index = headers.indexOf(column);
        if (index >= 0) {
          const candidate = (values[index] ?? "").trim();
          if (candidate && Number.isFinite(Date.parse(candidate))) {
            return candidate;
          }
        }
      }
    }
  }

  return null;
}

function maybeRefreshGitRemoteInBackground(): void {
  if (process.env.NODE_ENV !== "development") return;
  if (gitFetchPromise) return;
  if (Date.now() - lastGitFetchAttemptAt < HOSTED_CACHE_TTL_MS) return;
  lastGitFetchAttemptAt = Date.now();
  gitFetchPromise = (async () => {
    try {
      await execFileAsync("git", ["fetch", "origin", "golden-with-speed-insights", "--quiet"], {
        cwd: process.cwd(),
        maxBuffer: 64 * 1024 * 1024,
      });
    } catch {
      // Fall back to the currently available remote-tracking ref.
    } finally {
      gitFetchPromise = null;
    }
  })();
}

async function loadHostedSnapshot(): Promise<SnapshotPayload | null> {
  if (snapshotCache && snapshotCache.expiresAt > Date.now()) {
    return snapshotCache.payload;
  }

  let payload: SnapshotPayload | null = null;

  if (process.env.NODE_ENV === "development") {
    try {
      maybeRefreshGitRemoteInBackground();
      const { stdout } = await execFileAsync("git", ["show", `${GIT_REMOTE_REF}:${LOCAL_SNAPSHOT_FILE}`], {
        cwd: process.cwd(),
        maxBuffer: 64 * 1024 * 1024,
      });
      const data = JSON.parse(stdout) as SnapshotPayload;
      if (data && typeof data === "object") payload = data;
    } catch {
      payload = null;
    }
  }

  if (!payload) {
    try {
      const supabase = getSupabaseAdmin();
      const { data, error } = await supabase
        .from(SNAPSHOT_TABLE)
        .select("payload")
        .eq("snapshot_key", SNAPSHOT_KEY)
        .maybeSingle();

      if (!error && data?.payload && typeof data.payload === "object") {
        payload = data.payload as SnapshotPayload;
      }
    } catch {
      // Fall through to other hosted snapshot sources.
    }
  }

  if (!payload && process.env.NODE_ENV !== "development") {
    try {
      const response = await fetch(`${GITHUB_RAW_BASE}/${LOCAL_SNAPSHOT_FILE}`, {
        cache: "no-store",
      });
      if (response.ok) {
        const data = (await response.json()) as SnapshotPayload;
        if (data && typeof data === "object") payload = data;
      }
    } catch {
      // Fall through to git fallback.
    }
  }

  snapshotCache = {
    expiresAt: Date.now() + HOSTED_CACHE_TTL_MS,
    payload,
  };
  return payload;
}

async function loadHostedRawFile(relativePath: string): Promise<HostedRawFile | null> {
  const cached = rawFileCache.get(relativePath);
  if (cached && cached.expiresAt > Date.now()) {
    return cached.value;
  }

  let value: HostedRawFile | null = null;

  if (process.env.NODE_ENV === "development") {
    try {
      maybeRefreshGitRemoteInBackground();
      const [contentResult, mtimeResult] = await Promise.all([
        execFileAsync("git", ["show", `${GIT_REMOTE_REF}:${relativePath}`], {
          cwd: process.cwd(),
          maxBuffer: 64 * 1024 * 1024,
        }),
        execFileAsync("git", ["log", "-1", "--format=%cI", GIT_REMOTE_REF, "--", relativePath], {
          cwd: process.cwd(),
          maxBuffer: 1024 * 1024,
        }),
      ]);
      const mtime = mtimeResult.stdout.trim();
      value = {
        content: contentResult.stdout,
        mtime: mtime || null,
      };
    } catch {
      value = null;
    }
  }

  if (!value && process.env.NODE_ENV !== "development") {
    try {
      const response = await fetch(`${GITHUB_RAW_BASE}/${relativePath}`, {
        cache: "no-store",
      });
      if (response.ok) {
        const content = await response.text();
        const lastModified = response.headers.get("last-modified");
        const parsedLastModified = lastModified ? Date.parse(lastModified) : Number.NaN;
        value = {
          content,
          mtime: Number.isFinite(parsedLastModified) ? new Date(parsedLastModified).toISOString() : null,
        };
      }
    } catch {
      value = null;
    }
  }

  if (!value) {
    const payload = await loadHostedSnapshot();
    const hostedEntry = getSnapshotFileEntry(payload, relativePath);
    if (typeof hostedEntry?.content === "string") {
      value = {
        content: hostedEntry.content,
        mtime: hostedEntry.mtime ?? payload?.generated_at ?? null,
      };
    }
  }

  rawFileCache.set(relativePath, {
    expiresAt: Date.now() + HOSTED_CACHE_TTL_MS,
    value,
  });
  return value;
}

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

export async function readGoalscorerLiveFile(relativePath: string): Promise<string | null> {
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
    const [hostedRaw, local, localMtime] = await Promise.all([loadHostedRawFile(relativePath), readLocal(), readLocalMtime()]);

    const payload = await loadHostedSnapshot();
    const hostedEntry = getSnapshotFileEntry(payload, relativePath);
    const hostedContent = hostedRaw?.content ?? (typeof hostedEntry?.content === "string" ? hostedEntry.content : null);
    const hostedFreshness = newerTimestamp(
      extractEmbeddedFreshness(relativePath, hostedContent),
      newerTimestamp(hostedEntry?.mtime ?? payload?.generated_at ?? null, hostedRaw?.mtime ?? null),
    );
    const localFreshness = newerTimestamp(extractEmbeddedFreshness(relativePath, local), localMtime);

    if (hostedContent && shouldPreferHosted(hostedFreshness, localFreshness)) {
      return hostedContent;
    }
    if (typeof local === "string") return local;
    if (hostedContent) return hostedContent;
    return null;
  }

  const local = await readLocal();
  if (typeof local === "string") return local;

  const hostedRaw = await loadHostedRawFile(relativePath);
  if (hostedRaw?.content) return hostedRaw.content;

  const hostedEntry = getSnapshotFileEntry(await loadHostedSnapshot(), relativePath);
  if (typeof hostedEntry?.content === "string") return hostedEntry.content;
  return null;
}

export async function readGoalscorerLiveJson<T>(relativePath: string): Promise<T | null> {
  const text = await readGoalscorerLiveFile(relativePath);
  if (!text) return null;
  try {
    return JSON.parse(text) as T;
  } catch {
    return null;
  }
}

/**
 * Read content ONLY from hosted sources (git remote ref, snapshot, GitHub raw).
 * Does NOT fall back to local disk. Use this when you always need the remote/hosted
 * version regardless of local freshness — e.g. to merge hosted current picks with
 * local settled history without letting the freshness comparison discard either side.
 */
export async function readGoalscorerHostedContent(relativePath: string): Promise<string | null> {
  if (process.env.NODE_ENV === "development") {
    try {
      maybeRefreshGitRemoteInBackground();
      const { stdout } = await execFileAsync("git", ["show", `${GIT_REMOTE_REF}:${relativePath}`], {
        cwd: process.cwd(),
        maxBuffer: 64 * 1024 * 1024,
      });
      if (stdout) return stdout;
    } catch {
      // not in remote ref — fall through
    }
  }

  const payload = await loadHostedSnapshot();
  const entry = getSnapshotFileEntry(payload, relativePath);
  if (typeof entry?.content === "string") return entry.content;

  if (process.env.NODE_ENV !== "development") {
    try {
      const response = await fetch(`${GITHUB_RAW_BASE}/${relativePath}`, { cache: "no-store" });
      if (response.ok) return await response.text();
    } catch {
      // fall through
    }
  }

  return null;
}

export async function readGoalscorerLiveMtime(relativePath: string): Promise<string | null> {
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
    const [hostedRaw, local, localMtime] = await Promise.all([
      loadHostedRawFile(relativePath),
      readGoalscorerLiveFile(relativePath),
      readLocalMtime(),
    ]);
    const payload = await loadHostedSnapshot();
    const hosted = newerTimestamp(
      extractEmbeddedFreshness(relativePath, hostedRaw?.content ?? getSnapshotFileEntry(payload, relativePath)?.content ?? null),
      getSnapshotFileEntry(payload, relativePath)?.mtime ?? payload?.generated_at ?? null,
    );
    const localFreshness = newerTimestamp(extractEmbeddedFreshness(relativePath, local), localMtime);
    if (shouldPreferHosted(hosted, localFreshness)) return hosted;
    if (typeof localMtime === "string") return localMtime;
    if (typeof hosted === "string") return hosted;
    return null;
  }

  const localMtime = await readLocalMtime();
  if (typeof localMtime === "string") return localMtime;

  return getSnapshotFileEntry(await loadHostedSnapshot(), relativePath)?.mtime ?? null;
}

export async function readGoalscorerLiveSnapshotGeneratedAt(): Promise<string | null> {
  const payload = await loadHostedSnapshot();
  const hostedGeneratedAt = typeof payload?.generated_at === "string" ? payload.generated_at : null;
  const localGeneratedAt = await readLocalSnapshotGeneratedAt();
  return newerTimestamp(hostedGeneratedAt, localGeneratedAt);
}
