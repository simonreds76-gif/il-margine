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

export type TeamShotsLiveSourceStatus = {
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
const SNAPSHOT_KEY = process.env.TEAM_SHOTS_LIVE_SNAPSHOT_KEY || "team_shots_state";
const LOCAL_SNAPSHOT_FILE = "data/team-shots/team-shots-live-snapshot.json";
// The scheduled jobs publish the canonical monitor bundle to hosted snapshots.
// Local files are allowed only as an explicit debugging override; otherwise
// localhost can silently lag behind the latest automated refresh.
const PREFER_LOCAL = process.env.NODE_ENV === "development" || process.env.MONITOR_PREFER_LOCAL === "1";
const INCLUDE_HOSTED_METADATA_IN_LOCAL_DEV = process.env.MONITOR_COMPARE_HOSTED === "1";
const TEAM_SHOTS_SHADOW_FILES = [
  "data/team-shots/shadow/team-shots-shadow-signals.csv",
  "data/team-shots/shadow/team-shots-shadow-performance.txt",
] as const;
const TEAM_SHOTS_MARKET_FILES = [
  "data/football-form/research-lane-state.json",
  "data/football-form/research-lane-state.md",
  "data/football-form/team-shots-active-allowed-leagues.json",
  "data/football-form/team-shots-last90-diagnostic.json",
  "data/football-form/team-shots-last90-diagnostic.md",
  "data/football-form/team-shots-v3-ema20-allowed-leagues.json",
  "data/football-form/team-shots-v3-ema20-promotion-check.json",
  "data/football-form/team-shots-v3-ema20-promotion-check.md",
  "data/football-form/team-shots-v3-ema20-published-picks.csv",
  "data/football-form/team-shots-v3-ema20-clv-monitor.csv",
  "data/football-form/team-shots-v3-ema20-clv-monitor.md",
  "data/football-form/football-count-market-coverage.json",
  "data/football-form/football-count-market-coverage.md",
  "data/football-form/football-foul-market-probe.json",
  "data/football-form/football-foul-market-probe.md",
  "data/football-form/fouls-empirical-baseline.json",
  "data/football-form/fouls-empirical-baseline.md",
  "data/football-form/team-fouls-v1-fold-report.json",
  "data/football-form/team-fouls-v1-fold-report.md",
  "data/football-form/team-fouls-f2-fold-report.json",
  "data/football-form/team-fouls-f2-fold-report.md",
  "data/football-form/team-fouls-definition-agreement.json",
  "data/football-form/team-fouls-definition-agreement.md",
  "data/football-form/team-fouls-fotmob-agreement.json",
  "data/football-form/team-fouls-fotmob-agreement.md",
  "data/football-form/weekly-research-report.json",
  "data/football-form/weekly-research-report.md",
  "data/goalkeeper-saves/gk-saves-capture-status.json",
  "data/goalkeeper-saves/gk-saves-v1-candidates.csv",
  "data/goalkeeper-saves/gk-saves-v1-provisional.csv",
  "data/goalkeeper-saves/gk-saves-v1-settlement-status.json",
  "data/goalkeeper-saves/gk-saves-v1-shadow-report.json",
  "data/goalkeeper-saves/gk-saves-v1-shadow-signals.csv",
  "data/team-shots/team-shots-comparison.csv",
  "data/team-shots/team-shots-comparison.txt",
  "data/team-shots/team-shots-odds-history.csv",
  "data/team-shots/team-shots-upcoming.csv",
  "data/team-shots/team-shots-monitor-summary.json",
  "data/team-shots/team-shots-scrape-last-run.json",
] as const;
const GITHUB_RAW_BASE =
  process.env.MONITOR_GITHUB_RAW_BASE ||
  "https://raw.githubusercontent.com/simonreds76-gif/il-margine/golden-with-speed-insights";

type TeamShotsBundleDecision = {
  source: "hosted" | "local" | "missing";
  reason: TeamShotsLiveSourceStatus["reason"];
  payload: SnapshotPayload | null;
  hostedGeneratedAt: string | null;
  localSnapshotGeneratedAt: string | null;
  hostedBundleFreshness: string | null;
  localBundleFreshness: string | null;
};

function stripUtf8Bom(text: string): string {
  return text.charCodeAt(0) === 0xfeff ? text.slice(1) : text;
}

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

async function readLocalFile(relativePath: string): Promise<string | null> {
  try {
    const fullPath = tryGetKnownProjectFilePath(relativePath);
    if (!fullPath) return null;
    return await fs.readFile(fullPath, "utf8");
  } catch {
    return null;
  }
}

async function readLocalFileMtime(relativePath: string): Promise<string | null> {
  try {
    const fullPath = tryGetKnownProjectFilePath(relativePath);
    if (!fullPath) return null;
    const stat = await fs.stat(fullPath);
    return stat.mtime.toISOString();
  } catch {
    return null;
  }
}

function latestHostedBundleFreshness(payload: SnapshotPayload | null, bundleFiles: readonly string[]): string | null {
  let freshest = typeof payload?.generated_at === "string" ? payload.generated_at : null;
  for (const path of bundleFiles) {
    const entry = getSnapshotFileEntry(payload, path);
    freshest = newerTimestamp(freshest, entry?.mtime ?? null);
  }
  return freshest;
}

async function latestLocalBundleFreshnessFor(bundleFiles: readonly string[]): Promise<string | null> {
  let freshest: string | null = null;
  for (const path of bundleFiles) {
    freshest = newerTimestamp(freshest, await readLocalFileMtime(path));
  }
  return freshest;
}

const resolveTeamShotsBundleDecision = cache(async (bundleKey: string): Promise<TeamShotsBundleDecision> => {
  const bundleFiles = bundleKey === "shadow" ? TEAM_SHOTS_SHADOW_FILES : TEAM_SHOTS_MARKET_FILES;
  const [payload, localSnapshotGeneratedAt, localBundleFreshness] = await Promise.all([
    loadHostedSnapshot(),
    readLocalSnapshotGeneratedAt(),
    latestLocalBundleFreshnessFor(bundleFiles),
  ]);

  const hostedGeneratedAt = typeof payload?.generated_at === "string" ? payload.generated_at : null;
  const hostedBundleFreshness = latestHostedBundleFreshness(payload, bundleFiles);

  // For market-facing team-shots files, default to the hosted snapshot unless
  // the user explicitly opts into local-only debugging. Local mtimes can be
  // newer because of follow-up status writes while still missing the last
  // scheduled hosted scrape bundle that the monitor should reflect.
  if (bundleKey === "market" && !PREFER_LOCAL) {
    if (hostedBundleFreshness) {
      return {
        source: "hosted",
        reason: localBundleFreshness ? "hosted_newer" : "hosted_only",
        payload,
        hostedGeneratedAt,
        localSnapshotGeneratedAt,
        hostedBundleFreshness,
        localBundleFreshness,
      };
    }
    if (localBundleFreshness) {
      return {
        source: "local",
        reason: "local_only",
        payload,
        hostedGeneratedAt,
        localSnapshotGeneratedAt,
        hostedBundleFreshness,
        localBundleFreshness,
      };
    }
    return {
      source: "missing",
      reason: "no_data",
      payload,
      hostedGeneratedAt,
      localSnapshotGeneratedAt,
      hostedBundleFreshness,
      localBundleFreshness,
    };
  }

  if (PREFER_LOCAL && !INCLUDE_HOSTED_METADATA_IN_LOCAL_DEV) {
    if (localBundleFreshness || localSnapshotGeneratedAt) {
      return {
        source: "local",
        reason: "local_only",
        payload,
        hostedGeneratedAt,
        localSnapshotGeneratedAt,
        hostedBundleFreshness,
        localBundleFreshness,
      };
    }
    if (hostedBundleFreshness) {
      return {
        source: "hosted",
        reason: "hosted_only",
        payload,
        hostedGeneratedAt,
        localSnapshotGeneratedAt,
        hostedBundleFreshness,
        localBundleFreshness,
      };
    }
    return {
      source: "missing",
      reason: "no_data",
      payload,
      hostedGeneratedAt,
      localSnapshotGeneratedAt,
      hostedBundleFreshness,
      localBundleFreshness,
    };
  }

  if (shouldPreferHosted(hostedBundleFreshness, localBundleFreshness)) {
    return {
      source: "hosted",
      reason: localBundleFreshness ? "hosted_newer" : "hosted_only",
      payload,
      hostedGeneratedAt,
      localSnapshotGeneratedAt,
      hostedBundleFreshness,
      localBundleFreshness,
    };
  }

  if (localBundleFreshness) {
    return {
      source: "local",
      reason: hostedBundleFreshness ? "local_newer" : "local_only",
      payload,
      hostedGeneratedAt,
      localSnapshotGeneratedAt,
      hostedBundleFreshness,
      localBundleFreshness,
    };
  }

  return {
    source: "missing",
    reason: "no_data",
    payload,
    hostedGeneratedAt,
    localSnapshotGeneratedAt,
    hostedBundleFreshness,
    localBundleFreshness,
  };
});

export async function readTeamShotsLiveFile(relativePath: string): Promise<string | null> {
  const bundleKey = relativePath.startsWith("data/team-shots/shadow/") ? "shadow" : "market";
  const decision = await resolveTeamShotsBundleDecision(bundleKey);
  const hosted = getSnapshotFileEntry(decision.payload, relativePath)?.content;

  if (decision.source === "local") {
    const local = await readLocalFile(relativePath);
    if (typeof local === "string") return local;
    if (typeof hosted === "string") return hosted;
    return null;
  }

  if (decision.source === "hosted") {
    if (typeof hosted === "string") return hosted;
    const local = await readLocalFile(relativePath);
    if (typeof local === "string") return local;
    return null;
  }

  const local = await readLocalFile(relativePath);
  if (typeof local === "string") return local;
  if (typeof hosted === "string") return hosted;

  return null;
}

export async function readTeamShotsLiveJson<T>(relativePath: string): Promise<T | null> {
  const text = await readTeamShotsLiveFile(relativePath);
  if (!text) return null;
  try {
    return JSON.parse(stripUtf8Bom(text)) as T;
  } catch {
    return null;
  }
}

export async function readTeamShotsLiveMtime(relativePath: string): Promise<string | null> {
  const bundleKey = relativePath.startsWith("data/team-shots/shadow/") ? "shadow" : "market";
  const decision = await resolveTeamShotsBundleDecision(bundleKey);
  const localMtime = await readLocalFileMtime(relativePath);
  const hostedMtime =
    getSnapshotFileEntry(decision.payload, relativePath)?.mtime ?? decision.hostedGeneratedAt;

  if (decision.source === "local") return localMtime ?? hostedMtime ?? null;
  if (decision.source === "hosted") return hostedMtime ?? localMtime ?? null;
  return localMtime ?? hostedMtime ?? null;
}

export async function readTeamShotsLiveSnapshotGeneratedAt(): Promise<string | null> {
  const [marketDecision, shadowDecision] = await Promise.all([
    resolveTeamShotsBundleDecision("market"),
    resolveTeamShotsBundleDecision("shadow"),
  ]);
  return newerTimestamp(
    newerTimestamp(
      marketDecision.source === "hosted"
        ? marketDecision.hostedBundleFreshness ?? marketDecision.hostedGeneratedAt
        : marketDecision.localBundleFreshness ?? marketDecision.localSnapshotGeneratedAt,
      shadowDecision.source === "hosted"
        ? shadowDecision.hostedBundleFreshness ?? shadowDecision.hostedGeneratedAt
        : shadowDecision.localBundleFreshness ?? shadowDecision.localSnapshotGeneratedAt,
    ),
    newerTimestamp(marketDecision.localSnapshotGeneratedAt, shadowDecision.localSnapshotGeneratedAt),
  );
}

export async function inspectTeamShotsLiveSource(relativePath: string): Promise<TeamShotsLiveSourceStatus> {
  const bundleKey = relativePath.startsWith("data/team-shots/shadow/") ? "shadow" : "market";
  const decision = await resolveTeamShotsBundleDecision(bundleKey);
  const localFileMtime = await readLocalFileMtime(relativePath);
  const hostedFileMtime =
    getSnapshotFileEntry(decision.payload, relativePath)?.mtime ?? decision.hostedGeneratedAt;

  return {
    source: decision.source,
    reason: decision.reason,
    hostedSnapshotAvailable: Boolean(decision.payload),
    localSnapshotAvailable: Boolean(decision.localSnapshotGeneratedAt ?? decision.localBundleFreshness),
    hostedGeneratedAt: decision.hostedGeneratedAt,
    localSnapshotGeneratedAt: decision.localSnapshotGeneratedAt ?? decision.localBundleFreshness,
    hostedFileMtime,
    localFileMtime,
  };
}
