import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
/** Service role used only for bookmaker_odds_snapshot so Pinnacle shows even if RLS blocks anon. */
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

export interface FairOddsRow {
  id: number;
  tournament: string;
  surface: string;
  player1_id: number;
  player2_id: number;
  player1_name: string;
  player2_name: string;
  p1_win_prob: number;
  p2_win_prob: number;
  odds1: number;
  odds2: number;
  p1_serve?: number;
  p1_return?: number;
  p1_total?: number;
  p2_serve?: number;
  p2_return?: number;
  p2_total?: number;
  expected_total_games?: number;
  ou_line_1?: number;
  ou_over_1?: number;
  ou_under_1?: number;
  ou_line_2?: number;
  ou_over_2?: number;
  ou_under_2?: number;
  ou_line_3?: number;
  ou_over_3?: number;
  ou_under_3?: number;
  pinnacle_odds1?: number;
  pinnacle_odds2?: number;
  pinnacle_margin?: number;
  pinnacle_ou_line?: number;
  pinnacle_ou_over?: number;
  pinnacle_ou_under?: number;
  spread_line?: number;
  spread_odds1?: number;
  spread_odds2?: number;
  handicap_edge_p1?: number;
  handicap_edge_p2?: number;
  value_p1?: number;
  value_p2?: number;
  confidence?: string;
  series_bucket?: string;
  policy_match?: boolean;
  spread_eligible?: boolean;
  shadow_match?: boolean;
  shadow_spread_eligible?: boolean;
  spread_shadow_eligible?: boolean;
  spread_shadow_reason?: string;
  blocked_reason?: string;
  recent_injured_p1?: boolean;
  recent_injured_p2?: boolean;
  recent_injured_any?: boolean;
  recent_injured_p1_mode?: string;
  recent_injured_p2_mode?: string;
}

type StrictPolicyMode = "base" | "overlay";
type OverlayMissingMode = "skip" | "allow";
type ShadowProfile = "off" | "volume_275" | "volume_200";

interface OverlayPolicySummary {
  enabled: boolean;
  policy_file: string;
  window: string;
  family: "seed" | "entry";
  min_n: number;
  min_roi_pct: number;
  missing_mode: OverlayMissingMode;
  keys_loaded: number;
  considered_matches: number;
  passed_matches: number;
  skipped_missing: number;
  skipped_min_n: number;
  skipped_min_roi: number;
}

interface InjuryOverlaySummary {
  enabled: boolean;
  csv_file: string;
  lookback_days: number;
  rows_loaded: number;
  rows_recent: number;
  flagged_matches: number;
  skipped_matches: number;
}

interface StrictPolicyPayload {
  mode: "strict" | "off";
  production_mode: StrictPolicyMode;
  min_value_pct: number;
  allowed_segments: string[];
  allowed_confidence: string[];
  exclusion_rules: string[];
  eligible_matches: number;
  excluded_matches: number;
  signaled_matches: number;
  overlay?: OverlayPolicySummary;
  injury_overlay?: InjuryOverlaySummary;
}

const API_TIMEOUT_MS = 15000;
const STRICT_POLICY_MODE = true;
const STRICT_POLICY_INTERNAL_MIN_VALUE_PCT = 5;
const STRICT_POLICY_PUBLIC_MIN_VALUE_PCT = 10;
const STRICT_POLICY_ALLOWED_SEGMENTS = new Set<string>(["Hard|Masters 1000"]);
const STRICT_POLICY_ALLOWED_CONFIDENCE = new Set<string>(["high"]);
const STRICT_POLICY_EXCLUDE_ATP500_HARD_SHORT_FAVORITES = true;
const STRICT_POLICY_SHORT_FAVORITE_MAX_ODDS = 1.8;
const STRICT_POLICY_SHORT_FAVORITE_CONFIDENCE = new Set<string>(["high"]);
// Skip matches where model favourite odds < 1.25. Model cannot price extreme mismatches — both sides unreliable.
const STRICT_POLICY_MISPRICE_FAV_ODDS_MIN = 1.25;
const STRICT_POLICY_PRODUCTION_MODE: StrictPolicyMode =
  (process.env.STRICT_POLICY_PRODUCTION_MODE ?? "base").trim().toLowerCase() === "overlay"
    ? "overlay"
    : "base";
const STRICT_OVERLAY_POLICY_FILE =
  process.env.STRICT_OVERLAY_POLICY_FILE ?? path.join("data", "backtest", "tournament-segment-roi.csv");
const STRICT_OVERLAY_WINDOW = process.env.STRICT_OVERLAY_WINDOW ?? "prior_editions";
const STRICT_OVERLAY_FAMILY: "seed" | "entry" =
  (process.env.STRICT_OVERLAY_FAMILY ?? "seed").trim().toLowerCase() === "entry" ? "entry" : "seed";
const STRICT_OVERLAY_MIN_N = parseNumberEnv("STRICT_OVERLAY_MIN_N", 50);
const STRICT_OVERLAY_MIN_ROI_PCT = parseNumberEnv("STRICT_OVERLAY_MIN_ROI_PCT", -5);
const STRICT_OVERLAY_MISSING_MODE: OverlayMissingMode =
  (process.env.STRICT_OVERLAY_MISSING_MODE ?? "skip").trim().toLowerCase() === "allow"
    ? "allow"
    : "skip";
const STRICT_INJURY_OVERLAY_ENABLED = parseBoolEnv("STRICT_INJURY_OVERLAY_ENABLED", false);
const STRICT_INJURY_LOOKBACK_DAYS = parseNumberEnv("STRICT_INJURY_LOOKBACK_DAYS", 14);
const INJURED_PLAYERS_CSV =
  process.env.INJURED_PLAYERS_CSV ?? path.join("data", "injured-players-tennisexplorer.csv");

const HANDICAP_MIN_EDGE_PCT = 20;
const STRICT_UNIT_GBP = parseNumberEnv("STRICT_UNIT_GBP", 100);
const SHADOW_POLICY_MODE = normalizeShadowProfile(process.env.STRICT_POLICY_VOLUME_MODE);
function computeStakeUnits(
  ourOdds1: number,
  ourOdds2: number,
  pinOdds1: number,
  pinOdds2: number,
  side: "P1" | "P2",
  valuePct: number
): { units: number; gbp: number } {
  // value_tiered: 5–10% → 0.5u, 10–15% → 1u, 15–20% → 1.5u, 20%+ → 2u
  const units =
    valuePct >= 20 ? 2 : valuePct >= 15 ? 1.5 : valuePct >= 10 ? 1 : valuePct >= 5 ? 0.5 : 0.5;
  return { units, gbp: units * STRICT_UNIT_GBP };
}

function parseNumberEnv(name: string, fallback: number): number {
  const parsed = Number(process.env[name]);
  return Number.isFinite(parsed) ? parsed : fallback;
}

function parseBoolEnv(name: string, fallback: boolean): boolean {
  const raw = process.env[name];
  if (raw == null) return fallback;
  return ["1", "true", "yes", "on"].includes(raw.trim().toLowerCase());
}

function buildStrictPolicyPayload(
  eligibleMatches: number,
  signaledMatches: number,
  excludedMatches: number,
  overlaySummary?: OverlayPolicySummary,
  injurySummary?: InjuryOverlaySummary
): StrictPolicyPayload {
  const exclusionRules: string[] = [];
  if (STRICT_POLICY_EXCLUDE_ATP500_HARD_SHORT_FAVORITES) {
    exclusionRules.push(
      `Exclude ATP500 Hard short favorites: confidence in [${Array.from(
        STRICT_POLICY_SHORT_FAVORITE_CONFIDENCE
      ).join(", ")}], model favorite odds < ${STRICT_POLICY_SHORT_FAVORITE_MAX_ODDS.toFixed(2)}`
    );
  }
  if (STRICT_INJURY_OVERLAY_ENABLED) {
    exclusionRules.push(
      `Exclude matches with recent injured-list flag: source=injured, lookback=${Math.max(
        0,
        Math.floor(STRICT_INJURY_LOOKBACK_DAYS)
      )}d`
    );
  }
  return {
    mode: STRICT_POLICY_MODE ? "strict" : "off",
    production_mode: STRICT_POLICY_PRODUCTION_MODE,
    min_value_pct: STRICT_POLICY_PUBLIC_MIN_VALUE_PCT,
    allowed_segments: Array.from(STRICT_POLICY_ALLOWED_SEGMENTS),
    allowed_confidence: Array.from(STRICT_POLICY_ALLOWED_CONFIDENCE),
    exclusion_rules: exclusionRules,
    eligible_matches: eligibleMatches,
    excluded_matches: excludedMatches,
    signaled_matches: signaledMatches,
    ...(overlaySummary ? { overlay: overlaySummary } : {}),
    ...(injurySummary ? { injury_overlay: injurySummary } : {}),
  };
}

function seriesBucketFromTour(tourName?: string, tourRank?: number | null): string {
  const u = (tourName ?? "").toUpperCase();
  if (
    ["AUSTRALIAN OPEN", "ROLAND GARROS", "WIMBLEDON", "US OPEN", "GRAND SLAM"].some((x) =>
      u.includes(x)
    )
  ) {
    return "Grand Slam";
  }
  if (u.includes("MASTERS CUP") || u.includes("ATP FINALS") || u.includes("TOUR FINALS")) {
    return "Masters Cup";
  }
  if (u.includes("MASTERS") || u.includes("1000")) return "Masters 1000";
  if (u.includes("ATP 500") || u.includes("500")) return "ATP500";
  if (u.includes("ATP 250") || u.includes("250")) return "ATP250";
  if (u.includes("CHALLENGER")) return "ATP250";

  const rankNum = tourRank != null ? Number(tourRank) : NaN;
  if (Number.isFinite(rankNum)) {
    if (rankNum === 1) return "Grand Slam";
    if (rankNum === 3) return "Masters 1000";
    if (rankNum === 2) return "ATP500";
  }
  return "ATP250";
}

function strictPolicyAllowsValue(surface: string, seriesBucket: string, confidence?: string): boolean {
  if (!STRICT_POLICY_MODE) return confidence !== "none";
  if (!STRICT_POLICY_ALLOWED_SEGMENTS.has(`${surface}|${seriesBucket}`)) return false;
  if (!confidence || !STRICT_POLICY_ALLOWED_CONFIDENCE.has(confidence)) return false;
  return true;
}

function strictPolicyExcludedByShortFavorite(
  surface: string,
  seriesBucket: string,
  confidence: string | undefined,
  p1WinProb: number,
  p2WinProb: number
): boolean {
  if (!STRICT_POLICY_MODE || !STRICT_POLICY_EXCLUDE_ATP500_HARD_SHORT_FAVORITES) return false;
  if (!(surface === "Hard" && seriesBucket === "ATP500")) return false;
  if (!confidence || !STRICT_POLICY_SHORT_FAVORITE_CONFIDENCE.has(confidence)) return false;
  const favProb = Math.max(Number(p1WinProb) || 0, Number(p2WinProb) || 0);
  if (!(favProb > 0 && favProb < 1)) return false;
  const favOdds = 1 / favProb;
  return favOdds < STRICT_POLICY_SHORT_FAVORITE_MAX_ODDS;
}

/** Volume_275 profile rules (shadow-test ~275 bets/year). Same exclusions as strict. */
const VOLUME_275_RULES: Array<{
  surface: string;
  series: string;
  confidence: Set<string>;
  min_value_pct: number;
}> = [
  { surface: "Hard", series: "Masters 1000", confidence: new Set(["high"]), min_value_pct: 15 },
  { surface: "Hard", series: "Masters 1000", confidence: new Set(["medium"]), min_value_pct: 30 },
  { surface: "Clay", series: "Masters 1000", confidence: new Set(["high"]), min_value_pct: 20 },
  { surface: "Hard", series: "Grand Slam", confidence: new Set(["high", "medium"]), min_value_pct: 5 },
  { surface: "Grass", series: "ATP500", confidence: new Set(["high", "medium"]), min_value_pct: 10 },
  { surface: "Hard", series: "ATP250", confidence: new Set(["high", "medium"]), min_value_pct: 20 },
];

const VOLUME_200_RULES = VOLUME_275_RULES.filter(
  (rule) => !(rule.surface === "Clay" && rule.series === "Masters 1000")
);

function normalizeShadowProfile(raw: string | undefined): ShadowProfile {
  const value = (raw ?? "volume_200").trim().toLowerCase();
  if (value === "off" || value === "volume_275" || value === "volume_200") return value;
  return "volume_200";
}

function shadowMinValueFor(surface: string, seriesBucket: string, confidence: string): number | null {
  const rules =
    SHADOW_POLICY_MODE === "volume_275"
      ? VOLUME_275_RULES
      : SHADOW_POLICY_MODE === "volume_200"
        ? VOLUME_200_RULES
        : [];
  let minVal: number | null = null;
  for (const rule of rules) {
    if (surface !== rule.surface || seriesBucket !== rule.series) continue;
    if (!rule.confidence.has(confidence)) continue;
    const v = rule.min_value_pct;
    if (minVal == null || v < minVal) minVal = v;
  }
  return minVal;
}

function shadowProfileLabel(profile: ShadowProfile): string {
  if (profile === "volume_200") return "volume_200";
  if (profile === "volume_275") return "volume_275";
  return "shadow";
}

function spreadShadowReasonFor(surface: string, seriesBucket: string, confidence?: string): string | null {
  const conf = (confidence ?? "").trim().toLowerCase();
  if (!(conf === "high" || conf === "medium")) return null;

  const inStrictMatchSegment =
    STRICT_POLICY_ALLOWED_SEGMENTS.has(`${surface}|${seriesBucket}`) &&
    STRICT_POLICY_ALLOWED_CONFIDENCE.has(conf);
  const isClay = surface === "Clay";
  if (isClay && !inStrictMatchSegment) return "clay_non_policy";
  if (isClay) return "clay";
  if (!inStrictMatchSegment) return "non_policy";
  return null;
}

function firstBlockedReason(params: {
  hasPositiveRawValue: boolean;
  anySignal: boolean;
  recentInjuredAny: boolean;
  pinnacleShortFavoriteExcluded: boolean;
  modelShortFavoriteExcluded: boolean;
  atp500HardShortFavoriteExcluded: boolean;
  shadowMinVal: number | null;
  rawValueP1?: number;
  rawValueP2?: number;
}): string | undefined {
  if (!params.hasPositiveRawValue || params.anySignal) return undefined;
  if (params.recentInjuredAny) return "Blocked: recent injury flag";
  if (params.pinnacleShortFavoriteExcluded) return "Blocked: Pinnacle fav <1.25";
  if (params.modelShortFavoriteExcluded) return "Blocked: model fav <1.25";
  if (params.atp500HardShortFavoriteExcluded) return "Blocked: ATP500 Hard short favorite filter";
  if (params.shadowMinVal == null) return `Blocked: not in ${shadowProfileLabel(SHADOW_POLICY_MODE)} segment`;
  const bestRawValue = Math.max(params.rawValueP1 ?? Number.NEGATIVE_INFINITY, params.rawValueP2 ?? Number.NEGATIVE_INFINITY);
  if (Number.isFinite(bestRawValue) && bestRawValue < params.shadowMinVal) {
    return `Blocked: below ${shadowProfileLabel(SHADOW_POLICY_MODE)} threshold`;
  }
  return "Blocked: filtered by policy";
}

type OverlayLookupValue = { n: number; roi_pct_shrunk: number };
type OverlayLookup = Map<string, OverlayLookupValue>;
type OverlayYearsByKeySide = Map<string, number[]>;
type OverlayLookupIndex = { lookup: OverlayLookup; yearsByKeySide: OverlayYearsByKeySide };

interface OverlayDecision {
  pass: boolean;
  reason: "ok" | "missing_allow" | "missing" | "min_n" | "min_roi";
  n?: number;
  roi_pct_shrunk?: number;
}

function tourKey(name?: string): string {
  const core = (name ?? "").trim().toLowerCase();
  if (!core) return "";
  return core
    .replace(/\b\d{4}\b/g, " ")
    .replace(/\b(challenger|qualifiers?|qualifying|qualification|atp|wta)\b/g, " ")
    .replace(/[^a-z0-9]+/g, " ")
    .trim()
    .replace(/\s+/g, " ");
}

function tourKeyCandidates(name?: string): string[] {
  const raw = (name ?? "").trim().toLowerCase();
  if (!raw) return [];
  const parts = raw
    .split(/\s*-\s*/)
    .map((x) => x.trim())
    .filter(Boolean);
  const cands = [tourKey(raw)];
  if (parts.length) {
    cands.push(tourKey(parts[0]));
    cands.push(tourKey(parts[parts.length - 1]));
  }
  if (parts.length >= 2) {
    cands.push(tourKey(`${parts[0]} ${parts[parts.length - 1]}`));
  }
  const out: string[] = [];
  const seen = new Set<string>();
  for (const c of cands) {
    if (!c || seen.has(c)) continue;
    seen.add(c);
    out.push(c);
  }
  return out;
}

function makeOverlayKey(seasonYear: number, tournamentKey: string, betSide: "fav" | "dog"): string {
  return `${seasonYear}|${tournamentKey}|${betSide}`;
}

function makeOverlayKeySide(tournamentKey: string, betSide: "fav" | "dog"): string {
  return `${tournamentKey}|${betSide}`;
}

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const c = line[i];
    if (c === '"') {
      if (inQuotes && i + 1 < line.length && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (c === "," && !inQuotes) {
      out.push(cur);
      cur = "";
      continue;
    }
    cur += c;
  }
  out.push(cur);
  return out.map((x) => x.trim());
}

interface InjuryIndex {
  csvPath: string;
  lookbackDays: number;
  rowsLoaded: number;
  rowsRecent: number;
  strongKeys: Set<string>;
  softCounts: Map<string, number>;
}

function stripAccents(text: string): string {
  return (text ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "");
}

function tokenizeIdentityName(text: string): string[] {
  const cleaned = stripAccents(text ?? "")
    .toLowerCase()
    .replace(/[-'.,]/g, " ")
    .replace(/[^a-z0-9 ]+/g, " ")
    .trim();
  return cleaned.split(/\s+/).filter(Boolean);
}

function tokenizeIdentitySlug(slug: string): string[] {
  const cleaned = stripAccents(slug ?? "")
    .toLowerCase()
    .replace(/[^a-z0-9_-]+/g, "-")
    .replace(/_/g, "-")
    .replace(/-+/g, "-")
    .replace(/^-+|-+$/g, "")
    .replace(/-(?:[0-9a-f]{5,}|\d{3,})$/g, "");
  if (!cleaned) return [];
  return cleaned.split("-").filter(Boolean);
}

function surnameVariants(tokens: string[]): string[] {
  const t = tokens.filter((x) => x && x.length >= 2);
  if (!t.length) return [];
  const out = new Set<string>();
  out.add(t[t.length - 1]);
  if (t.length >= 2) {
    out.add(`${t[t.length - 2]} ${t[t.length - 1]}`);
    out.add(`${t[t.length - 2]}${t[t.length - 1]}`);
  }
  out.add(t.join(" "));
  out.add(t.join(""));
  return Array.from(out).filter((x) => x.replace(/ /g, "").length >= 2);
}

function parseTeName(playerName: string): { surnameTokens: string[]; initial: string } {
  const tokens = tokenizeIdentityName(playerName);
  if (!tokens.length) return { surnameTokens: [], initial: "" };
  if (tokens.length >= 2 && tokens[tokens.length - 1].length === 1) {
    return { surnameTokens: tokens.slice(0, -1), initial: tokens[tokens.length - 1] };
  }
  if (tokens.length >= 2 && tokens[0].length === 1) {
    return { surnameTokens: tokens.slice(1), initial: tokens[0] };
  }
  if (tokens.length >= 2) {
    return { surnameTokens: tokens, initial: tokens[0][0] };
  }
  return { surnameTokens: tokens, initial: "" };
}

function parseOncourtName(playerName: string): { surnameTokens: string[]; initial: string } {
  const raw = playerName ?? "";
  if (raw.includes(",")) {
    const [left, right] = raw.split(",", 2);
    const surnameTokens = tokenizeIdentityName(left);
    const givenTokens = tokenizeIdentityName(right);
    const initial = givenTokens.length ? givenTokens[0][0] : surnameTokens.length ? surnameTokens[0][0] : "";
    return { surnameTokens: surnameTokens.length ? surnameTokens : tokenizeIdentityName(raw), initial };
  }
  const tokens = tokenizeIdentityName(raw);
  if (!tokens.length) return { surnameTokens: [], initial: "" };
  if (tokens.length >= 2 && tokens[tokens.length - 1].length === 1) {
    return { surnameTokens: tokens.slice(0, -1), initial: tokens[tokens.length - 1][0] };
  }
  if (tokens.length >= 2 && tokens[0].length === 1) {
    return { surnameTokens: tokens.slice(1), initial: tokens[0][0] };
  }
  if (tokens.length === 1) return { surnameTokens: tokens, initial: tokens[0][0] };
  return { surnameTokens: tokens.slice(1), initial: tokens[0][0] };
}

function makeStrongKeys(surnames: string[], initial: string): string[] {
  const i = (initial ?? "").trim().toLowerCase();
  if (!i) return [];
  return surnames.filter(Boolean).map((s) => `${s}|${i}`);
}

function buildTeKeys(playerName: string, playerSlug: string): { strong: Set<string>; soft: Set<string> } {
  const parsed = parseTeName(playerName);
  const soft = new Set<string>();
  for (const k of surnameVariants(parsed.surnameTokens)) soft.add(k);
  for (const k of surnameVariants(tokenizeIdentitySlug(playerSlug))) soft.add(k);
  const strong = new Set<string>(makeStrongKeys(Array.from(soft), parsed.initial));
  return { strong, soft };
}

function buildOncourtKeys(playerName: string): { strong: Set<string>; soft: Set<string> } {
  const parsed = parseOncourtName(playerName);
  const soft = new Set<string>(surnameVariants(parsed.surnameTokens));
  const strong = new Set<string>(makeStrongKeys(Array.from(soft), parsed.initial));
  return { strong, soft };
}

function parseIsoDateOnly(value: string): Date | null {
  const raw = (value ?? "").trim().slice(0, 10);
  if (!/^\d{4}-\d{2}-\d{2}$/.test(raw)) return null;
  const d = new Date(`${raw}T00:00:00Z`);
  return Number.isNaN(d.getTime()) ? null : d;
}

function loadInjuryIndex(todayIso: string): InjuryIndex {
  const csvPath = path.resolve(process.cwd(), INJURED_PLAYERS_CSV);
  const out: InjuryIndex = {
    csvPath,
    lookbackDays: Math.max(0, Math.floor(STRICT_INJURY_LOOKBACK_DAYS)),
    rowsLoaded: 0,
    rowsRecent: 0,
    strongKeys: new Set<string>(),
    softCounts: new Map<string, number>(),
  };
  if (!fs.existsSync(csvPath)) return out;

  let text = "";
  try {
    text = fs.readFileSync(csvPath, "utf8");
  } catch (e) {
    console.warn(`[fair-odds] Could not read injury CSV: ${csvPath}`, e);
    return out;
  }
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (lines.length < 2) return out;

  const header = parseCsvLine(lines[0]);
  const index = new Map<string, number>();
  header.forEach((h, i) => index.set(h, i));
  const required = ["date", "player_name", "player_slug", "source"];
  if (required.some((k) => !index.has(k))) return out;

  const todayDate = parseIsoDateOnly(todayIso);
  if (!todayDate) return out;

  const getCol = (cols: string[], name: string) => cols[index.get(name) ?? -1] ?? "";
  for (let i = 1; i < lines.length; i += 1) {
    const cols = parseCsvLine(lines[i]);
    out.rowsLoaded += 1;
    const source = getCol(cols, "source").trim().toLowerCase();
    if (source !== "injured") continue;
    const rowDate = parseIsoDateOnly(getCol(cols, "date"));
    if (!rowDate) continue;
    const diffDays = Math.floor((todayDate.getTime() - rowDate.getTime()) / 86400000);
    if (diffDays < 0 || diffDays > out.lookbackDays) continue;
    const keys = buildTeKeys(getCol(cols, "player_name"), getCol(cols, "player_slug"));
    if (!keys.strong.size && !keys.soft.size) continue;
    out.rowsRecent += 1;
    for (const k of keys.strong) out.strongKeys.add(k);
    for (const sk of keys.soft) {
      out.softCounts.set(sk, (out.softCounts.get(sk) ?? 0) + 1);
    }
  }
  return out;
}

function isRecentInjuredPlayer(playerName: string, injuryIndex: InjuryIndex): { matched: boolean; mode: string } {
  const keys = buildOncourtKeys(playerName);
  for (const k of keys.strong) {
    if (injuryIndex.strongKeys.has(k)) return { matched: true, mode: "strong" };
  }
  for (const sk of keys.soft) {
    if ((injuryIndex.softCounts.get(sk) ?? 0) === 1) return { matched: true, mode: "soft_unique" };
  }
  return { matched: false, mode: "none" };
}

function loadOverlayPolicyLookup(): OverlayLookupIndex {
  const out: OverlayLookup = new Map();
  const yearsByKeySide: OverlayYearsByKeySide = new Map();
  const absPath = path.resolve(process.cwd(), STRICT_OVERLAY_POLICY_FILE);
  if (!fs.existsSync(absPath)) return { lookup: out, yearsByKeySide };

  let text = "";
  try {
    text = fs.readFileSync(absPath, "utf8");
  } catch (e) {
    console.warn(`[fair-odds] Could not read overlay policy file: ${absPath}`, e);
    return { lookup: out, yearsByKeySide };
  }
  const lines = text.split(/\r?\n/).filter((l) => l.trim().length > 0);
  if (!lines.length) return { lookup: out, yearsByKeySide };

  const header = parseCsvLine(lines[0]).map((h) => h.trim());
  const index = new Map<string, number>();
  header.forEach((h, i) => index.set(h, i));
  const required = [
    "tournament_key",
    "window_type",
    "target_season_year",
    "bet_side",
    "segment_family",
    "n",
    "roi_pct_shrunk",
  ];
  if (required.some((k) => !index.has(k))) return { lookup: out, yearsByKeySide };

  const weighted = new Map<string, { wRoi: number; wN: number }>();
  for (let i = 1; i < lines.length; i += 1) {
    const cols = parseCsvLine(lines[i]);
    const get = (name: string) => cols[index.get(name) ?? -1] ?? "";
    if (get("window_type") !== STRICT_OVERLAY_WINDOW) continue;
    if (get("segment_family") !== STRICT_OVERLAY_FAMILY) continue;
    const betSide = get("bet_side");
    if (betSide !== "fav" && betSide !== "dog") continue;
    const seasonYear = Number.parseInt(get("target_season_year"), 10);
    if (!Number.isFinite(seasonYear)) continue;
    const tKey = get("tournament_key").trim();
    if (!tKey) continue;
    const n = Number(get("n"));
    const roi = Number(get("roi_pct_shrunk"));
    if (!(Number.isFinite(n) && Number.isFinite(roi)) || n <= 0) continue;

    const key = makeOverlayKey(seasonYear, tKey, betSide);
    const prev = weighted.get(key) ?? { wRoi: 0, wN: 0 };
    prev.wRoi += roi * n;
    prev.wN += n;
    weighted.set(key, prev);
    const ks = makeOverlayKeySide(tKey, betSide);
    const years = yearsByKeySide.get(ks) ?? [];
    if (!years.includes(seasonYear)) years.push(seasonYear);
    yearsByKeySide.set(ks, years);
  }

  for (const [k, v] of weighted.entries()) {
    if (v.wN <= 0) continue;
    out.set(k, { n: v.wN, roi_pct_shrunk: v.wRoi / v.wN });
  }
  for (const [k, years] of yearsByKeySide.entries()) {
    years.sort((a, b) => a - b);
    yearsByKeySide.set(k, years);
  }
  return { lookup: out, yearsByKeySide };
}

function evaluateOverlayGate(
  seasonYear: number,
  tournamentName: string,
  betSide: "fav" | "dog",
  overlayIndex: OverlayLookupIndex
): OverlayDecision {
  const { lookup: overlayLookup, yearsByKeySide } = overlayIndex;
  const candidates = tourKeyCandidates(tournamentName);
  let policy: OverlayLookupValue | undefined;

  // Exact season-year lookup.
  for (const tKey of candidates) {
    policy = overlayLookup.get(makeOverlayKey(seasonYear, tKey, betSide));
    if (policy) break;
  }
  // Fallback: latest available <= seasonYear, else latest available.
  if (!policy) {
    for (const tKey of candidates) {
      const years = yearsByKeySide.get(makeOverlayKeySide(tKey, betSide)) ?? [];
      if (!years.length) continue;
      const prior = years.filter((y) => y <= seasonYear);
      const resolvedYear = prior.length ? prior[prior.length - 1] : years[years.length - 1];
      policy = overlayLookup.get(makeOverlayKey(resolvedYear, tKey, betSide));
      if (policy) break;
    }
  }

  if (!policy) {
    if (STRICT_OVERLAY_MISSING_MODE === "allow") {
      return { pass: true, reason: "missing_allow" };
    }
    return { pass: false, reason: "missing" };
  }
  if (policy.n < STRICT_OVERLAY_MIN_N) {
    return { pass: false, reason: "min_n", n: policy.n, roi_pct_shrunk: policy.roi_pct_shrunk };
  }
  if (policy.roi_pct_shrunk < STRICT_OVERLAY_MIN_ROI_PCT) {
    return { pass: false, reason: "min_roi", n: policy.n, roi_pct_shrunk: policy.roi_pct_shrunk };
  }
  return { pass: true, reason: "ok", n: policy.n, roi_pct_shrunk: policy.roi_pct_shrunk };
}

async function run(): Promise<Response> {
  if (!url || !anonKey) {
    return NextResponse.json(
      { error: "Missing Supabase env (NEXT_PUBLIC_SUPABASE_URL, NEXT_PUBLIC_SUPABASE_ANON_KEY)" },
      { status: 500 }
    );
  }
  const supabase = createClient(url, anonKey);

  const FAIR_ODDS_LIMIT = 2000;

  const { data: oddsRows, error: oddsErr } = await supabase
    .from("daily_fair_odds")
    .select("id, tour_id, player1_id, player2_id, surface, p1_win_prob, p2_win_prob, odds1, odds2, expected_total_games, ou_line_1, ou_over_1, ou_under_1, ou_line_2, ou_over_2, ou_under_2, ou_line_3, ou_over_3, ou_under_3, confidence, spread_line, spread_odds1, spread_odds2, handicap_edge_p1, handicap_edge_p2")
    .order("tour_id")
    .order("draw")
    .order("round_id")
    .limit(FAIR_ODDS_LIMIT);

  if (oddsErr) {
    return NextResponse.json({ error: oddsErr.message }, { status: 500 });
  }
  if (!oddsRows?.length) {
    return NextResponse.json({
      matches: [],
      pinnacle_count: 0,
      pinnacle_matched_count: 0,
      policy: buildStrictPolicyPayload(0, 0, 0),
    });
  }

  const playerIds = new Set<number>();
  const tourIds = new Set<number>();
  for (const r of oddsRows) {
    if (r.player1_id != null) playerIds.add(r.player1_id);
    if (r.player2_id != null) playerIds.add(r.player2_id);
    if (r.tour_id != null) tourIds.add(r.tour_id);
  }

  const BATCH = 100;
  const playerIdArr = Array.from(playerIds);
  const tourIdArr = Array.from(tourIds);
  const playersChunks =
    playerIdArr.length > 0
      ? await Promise.all(
          Array.from({ length: Math.ceil(playerIdArr.length / BATCH) }, (_, i) =>
            supabase.from("oncourt_players").select("id, name").in("id", playerIdArr.slice(i * BATCH, (i + 1) * BATCH))
          )
        )
      : [];
  const toursChunks =
    tourIdArr.length > 0
      ? await Promise.all(
          Array.from({ length: Math.ceil(tourIdArr.length / BATCH) }, (_, i) =>
            supabase
              .from("oncourt_tours")
              .select("id, name, rank")
              .in("id", tourIdArr.slice(i * BATCH, (i + 1) * BATCH))
          )
        )
      : [];
  const statsChunks =
    playerIdArr.length > 0
      ? await Promise.all(
          Array.from({ length: Math.ceil(playerIdArr.length / BATCH) }, (_, i) =>
            supabase
              .from("player_surface_stats")
              .select("player_id, surface, hold_pct, return_pct")
              .in("player_id", playerIdArr.slice(i * BATCH, (i + 1) * BATCH))
          )
        )
      : [];

  const players = new Map<number, string>();
  for (const res of playersChunks) {
    for (const p of res.data ?? []) {
      players.set(p.id, p.name ?? `Player ${p.id}`);
    }
  }
  for (const id of playerIdArr) {
    if (!players.has(id)) players.set(id, `Player ${id}`);
  }
  type TourMeta = { name: string; rank: number | null };
  const tours = new Map<number, TourMeta>();
  for (const res of toursChunks) {
    for (const t of res.data ?? []) {
      const rankRaw = t.rank != null ? Number(t.rank) : NaN;
      tours.set(t.id, {
        name: t.name ?? "",
        rank: Number.isFinite(rankRaw) ? rankRaw : null,
      });
    }
  }
  const mainTourOddsRows = oddsRows;

  const normalizeSurfaceKey = (surface?: string | null): string => {
    const s = (surface ?? "").trim().toLowerCase();
    if (!s) return "n/a";
    if (s === "i.hard" || s === "ihard" || s === "indoor hard") return "i.hard";
    if (s === "hard") return "hard";
    if (s === "clay") return "clay";
    if (s === "grass") return "grass";
    if (s === "n/a" || s === "na") return "n/a";
    return s;
  };
  const surfaceCandidates = (surface?: string | null): string[] => {
    const s = normalizeSurfaceKey(surface);
    if (s === "i.hard") return ["i.hard", "hard", "n/a"];
    if (s === "hard") return ["hard", "i.hard", "n/a"];
    return [s, "n/a"];
  };
  const stats = new Map<string, { hold_pct: number; return_pct: number }>();
  for (const res of statsChunks) {
    for (const s of res.data ?? []) {
      const pid = s.player_id != null ? Number(s.player_id) : NaN;
      if (!Number.isFinite(pid)) continue;
      const key = `${pid}:${normalizeSurfaceKey(s.surface)}`;
      const hold = s.hold_pct != null ? Number(s.hold_pct) : 0;
      const ret = s.return_pct != null ? Number(s.return_pct) : 0;
      stats.set(key, { hold_pct: hold, return_pct: ret });
    }
  }
  const getSurfaceStats = (playerId?: number | null, surface?: string | null) => {
    if (playerId == null) return null;
    for (const surf of surfaceCandidates(surface)) {
      const row = stats.get(`${playerId}:${surf}`);
      if (row) return row;
    }
    return null;
  };

  // Use UTC date so it matches script: datetime.now(timezone.utc).date().isoformat()
  const now = new Date();
  const today = `${now.getUTCFullYear()}-${String(now.getUTCMonth() + 1).padStart(2, "0")}-${String(now.getUTCDate()).padStart(2, "0")}`;
  const seasonYear = Number.parseInt(today.slice(0, 4), 10);
  const injuryIndex = loadInjuryIndex(today);
  let injuryFlaggedCount = 0;
  let injurySkippedCount = 0;
  const overlayIndex: OverlayLookupIndex =
    STRICT_POLICY_MODE && STRICT_POLICY_PRODUCTION_MODE === "overlay"
      ? loadOverlayPolicyLookup()
      : { lookup: new Map(), yearsByKeySide: new Map() };
  let overlayConsideredCount = 0;
  let overlayPassedCount = 0;
  let overlaySkippedMissingCount = 0;
  let overlaySkippedMinNCount = 0;
  let overlaySkippedMinRoiCount = 0;
  let pinnacleRows: {
    player1_name: string;
    player2_name: string;
    odds1: number;
    odds2: number;
    ou_line?: number;
    ou_over?: number;
    ou_under?: number;
  }[] = [];
  const snapshotClient = url && serviceRoleKey ? createClient(url, serviceRoleKey) : supabase;

  // Try today first; if the scraper ran before midnight UTC (e.g. 23:55), fall back to yesterday.
  const yesterday = (() => {
    const d = new Date(now.getTime() - 86_400_000);
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
  })();

  const { data: snapshotData } = await snapshotClient
    .from("bookmaker_odds_snapshot")
    .select("player1_name, player2_name, odds1, odds2, ou_line, ou_over, ou_under, league, captured_at")
    .eq("bookmaker", "Pinnacle")
    .eq("capture_date", today)
    .order("captured_at", { ascending: false })
    .limit(2000);

  let rawSnapshot = snapshotData;

  if (!rawSnapshot?.length) {
    const { data: yesterdayData } = await snapshotClient
      .from("bookmaker_odds_snapshot")
      .select("player1_name, player2_name, odds1, odds2, ou_line, ou_over, ou_under, league, captured_at")
      .eq("bookmaker", "Pinnacle")
      .eq("capture_date", yesterday)
      .order("captured_at", { ascending: false })
      .limit(2000);
    rawSnapshot = yesterdayData;
  }

  if (rawSnapshot?.length) {
    pinnacleRows = rawSnapshot
      .filter((row: { league?: string }) => row.league === "ATP" || row.league === "Challenger")
      .map((row) => ({
      player1_name: (row.player1_name ?? "").trim(),
      player2_name: (row.player2_name ?? "").trim(),
      odds1: Number(row.odds1 ?? 0),
      odds2: Number(row.odds2 ?? 0),
      ou_line: row.ou_line != null ? Number(row.ou_line) : undefined,
      ou_over: row.ou_over != null ? Number(row.ou_over) : undefined,
      ou_under: row.ou_under != null ? Number(row.ou_under) : undefined,
    }));
  }

  /** Normalise for lookup: lowercase, strip accents, hyphens, apostrophes. */
  function norm(s: string): string {
    return (s ?? "")
      .toLowerCase()
      .normalize("NFD")
      .replace(/[\u0300-\u036f]/g, "")
      .replace(/-/g, "")
      .replace(/'/g, "")
      .trim();
  }
  function tokeniseName(name: string): string[] {
    const cleaned = (name ?? "")
      .replace(/\s*\([^)]*\)/g, " ")
      .replace(/\s*\[[^\]]*\]/g, " ")
      .replace(/,/g, " ")
      .replace(/-/g, " ")
      .replace(/'/g, " ")
      .trim();
    return cleaned
      .split(/\s+/)
      .map(norm)
      .filter(Boolean)
      .filter((t) => !/^[a-z]$/.test(t)); // drop initials
  }

  /** Multi-key surname set to match hyphen/compound variants safely. */
  function normaliseSurnameKeys(name: string): string[] {
    const t = tokeniseName(name);
    if (!t.length) return [];
    const out = new Set<string>();
    const n = t.length;
    out.add(t[n - 1]); // last token
    if (n >= 2) {
      out.add(t[n - 2]); // second-last token
      out.add(`${t[n - 2]} ${t[n - 1]}`); // last two tokens
      out.add(`${t[n - 2]}${t[n - 1]}`);  // compact last two (hyphen-like)
    }
    return Array.from(out);
  }

  function normaliseFirstWord(name: string): string {
    const t = tokeniseName(name);
    return t.length ? t[0] : "";
  }

  function normaliseFullName(name: string): string {
    return tokeniseName(name).join(" ");
  }

  type PinnacleRow = (typeof pinnacleRows)[0];
  const isDoublesPin = (p: PinnacleRow) =>
    (p.player1_name ?? "").includes("/") || (p.player2_name ?? "").includes("/") ||
    (p.player1_name ?? "").includes("&") || (p.player2_name ?? "").includes("&");

  function matchPinnacle(
    fairOddsRows: { id: number; player1_name: string; player2_name: string }[],
    pinRows: PinnacleRow[]
  ): {
    matched: Map<number, { pinnacle_odds1: number; pinnacle_odds2: number; pinnacle_margin: number; pinnacle_ou_line?: number; pinnacle_ou_over?: number; pinnacle_ou_under?: number }>;
    pinnacleOnly: PinnacleRow[];
  } {
    const matched = new Map<number, { pinnacle_odds1: number; pinnacle_odds2: number; pinnacle_margin: number; pinnacle_ou_line?: number; pinnacle_ou_over?: number; pinnacle_ou_under?: number }>();
    const matchedPinRows = new Set<PinnacleRow>();
    const pinLookup = new Map<string, Array<{ row: PinnacleRow; reversed: boolean }>>();

    const addLookup = (key: string, value: { row: PinnacleRow; reversed: boolean }) => {
      if (!key) return;
      const arr = pinLookup.get(key);
      if (arr) arr.push(value);
      else pinLookup.set(key, [value]);
    };

    const makePairKeys = (a: string, b: string): string[] => {
      const aKeys = normaliseSurnameKeys(a);
      const bKeys = normaliseSurnameKeys(b);
      const out = new Set<string>();
      for (const ka of aKeys) for (const kb of bKeys) out.add(`${ka}|${kb}`);
      return Array.from(out);
    };

    for (const pin of pinRows) {
      if (isDoublesPin(pin)) continue;
      for (const key of makePairKeys(pin.player1_name ?? "", pin.player2_name ?? "")) {
        addLookup(key, { row: pin, reversed: false });
      }
      for (const key of makePairKeys(pin.player2_name ?? "", pin.player1_name ?? "")) {
        addLookup(key, { row: pin, reversed: true });
      }
    }

    for (const fo of fairOddsRows) {
      const p1 = fo.player1_name ?? "";
      const p2 = fo.player2_name ?? "";
      const candidateMap = new Map<string, { row: PinnacleRow; reversed: boolean; score: number }>();
      const pairKeys = makePairKeys(p1, p2);
      for (const key of pairKeys) {
        for (const ent of pinLookup.get(key) ?? []) {
          const id = `${ent.row.player1_name}|${ent.row.player2_name}|${ent.reversed ? "R" : "N"}`;
          const prev = candidateMap.get(id);
          if (prev) prev.score += 1;
          else candidateMap.set(id, { row: ent.row, reversed: ent.reversed, score: 1 });
        }
      }
      if (!candidateMap.size) continue;

      const foP1First = normaliseFirstWord(p1);
      const foP2First = normaliseFirstWord(p2);
      const foP1Full = normaliseFullName(p1);
      const foP2Full = normaliseFullName(p2);

      for (const cand of candidateMap.values()) {
        const pinP1 = cand.reversed ? cand.row.player2_name : cand.row.player1_name;
        const pinP2 = cand.reversed ? cand.row.player1_name : cand.row.player2_name;
        if (foP1First && foP1First === normaliseFirstWord(pinP1)) cand.score += 2;
        if (foP2First && foP2First === normaliseFirstWord(pinP2)) cand.score += 2;
        if (foP1Full && foP1Full === normaliseFullName(pinP1)) cand.score += 4;
        if (foP2Full && foP2Full === normaliseFullName(pinP2)) cand.score += 4;
      }

      const ranked = Array.from(candidateMap.values())
        .filter((c) => !matchedPinRows.has(c.row))
        .sort((a, b) => b.score - a.score);
      if (!ranked.length) continue;
      if (ranked.length > 1 && ranked[0].score === ranked[1].score) continue; // keep unique-only behavior

      const best = ranked[0];
      const pin = best.row;
      matchedPinRows.add(pin);
      const margin =
        pin.odds1 > 0 && pin.odds2 > 0 ? 1 / pin.odds1 + 1 / pin.odds2 - 1 : 0;
      if (best.reversed) {
        matched.set(fo.id, {
          pinnacle_odds1: pin.odds2,
          pinnacle_odds2: pin.odds1,
          pinnacle_margin: margin,
          pinnacle_ou_line: pin.ou_line,
          pinnacle_ou_over: pin.ou_over,
          pinnacle_ou_under: pin.ou_under,
        });
      } else {
        matched.set(fo.id, {
          pinnacle_odds1: pin.odds1,
          pinnacle_odds2: pin.odds2,
          pinnacle_margin: margin,
          pinnacle_ou_line: pin.ou_line,
          pinnacle_ou_over: pin.ou_over,
          pinnacle_ou_under: pin.ou_under,
        });
      }
    }

    const singlesPin = pinRows.filter((p) => !isDoublesPin(p));
    const pinnacleOnly = singlesPin.filter((p) => !matchedPinRows.has(p));
    if (pinnacleOnly.length > 0) {
      console.log(
        `[fair-odds] Unmatched Pinnacle rows (e.g. Indian Wells not in OnCourt today):`,
        pinnacleOnly.map((p) => `${p.player1_name} vs ${p.player2_name}`)
      );
    }

    console.log(
      `[fair-odds] Pinnacle matching: ${matched.size}/${fairOddsRows.length} matched, ${pinRows.length} Pinnacle rows, ${pinnacleOnly.length} Pinnacle-only (no fair odds).`
    );
    return { matched, pinnacleOnly };
  }

  const isDoubles = (name: string) => (name ?? "").includes("/") || (name ?? "").includes("&");
  const fairOddsRowsForMatch = mainTourOddsRows
    .map((r) => ({
      id: r.id,
      player1_name: (r.player1_id != null ? players.get(r.player1_id) : null) ?? "",
      player2_name: (r.player2_id != null ? players.get(r.player2_id) : null) ?? "",
    }))
    .filter((r) => !isDoubles(r.player1_name) && !isDoubles(r.player2_name));
  const { matched: pinnacleMap } = matchPinnacle(fairOddsRowsForMatch, pinnacleRows);

  let strictPolicyEligibleCount = 0;
  let strictPolicyExcludedCount = 0;
  let strictPolicySignaledCount = 0;

  const matches: FairOddsRow[] = mainTourOddsRows.map((r) => {
    const p1Stats = getSurfaceStats(r.player1_id, r.surface);
    const p2Stats = getSurfaceStats(r.player2_id, r.surface);
    const p1Name = (r.player1_id != null ? players.get(r.player1_id) : null) ?? "";
    const p2Name = (r.player2_id != null ? players.get(r.player2_id) : null) ?? "";
    const tourMeta = r.tour_id != null ? tours.get(r.tour_id) : undefined;
    const tournamentName = tourMeta?.name ?? "";
    const seriesBucket = seriesBucketFromTour(tournamentName, tourMeta?.rank);
    const confidenceRaw = (r as { confidence?: string }).confidence;
    const confidence = confidenceRaw ? confidenceRaw.toLowerCase() : undefined;
    const p1WinProb = r.p1_win_prob != null ? Number(r.p1_win_prob) : 0;
    const p2WinProb = r.p2_win_prob != null ? Number(r.p2_win_prob) : 0;
    const p1Injury = isRecentInjuredPlayer(p1Name, injuryIndex);
    const p2Injury = isRecentInjuredPlayer(p2Name, injuryIndex);
    const recentInjuredAny = p1Injury.matched || p2Injury.matched;
    if (recentInjuredAny) injuryFlaggedCount += 1;
    const pinnacle = pinnacleRows.length ? pinnacleMap.get(r.id) ?? null : null;
    const ourOdds1 = r.odds1 != null ? Number(r.odds1) : 0;
    const ourOdds2 = r.odds2 != null ? Number(r.odds2) : 0;
    const rawValueP1 =
      pinnacle && ourOdds1 > 1 && pinnacle.pinnacle_odds1 > 1
        ? Math.round((pinnacle.pinnacle_odds1 / ourOdds1 - 1) * 10000) / 100
        : undefined;
    const rawValueP2 =
      pinnacle && ourOdds2 > 1 && pinnacle.pinnacle_odds2 > 1
        ? Math.round((pinnacle.pinnacle_odds2 / ourOdds2 - 1) * 10000) / 100
        : undefined;
    const policyBaseAllows = strictPolicyAllowsValue(r.surface ?? "", seriesBucket, confidence);
    const shortFavoriteExcluded = strictPolicyExcludedByShortFavorite(
      r.surface ?? "",
      seriesBucket,
      confidence,
      p1WinProb,
      p2WinProb
    );
    const modelFavOddsMispriceExcluded =
      STRICT_POLICY_MODE && Math.min(ourOdds1, ourOdds2) < STRICT_POLICY_MISPRICE_FAV_ODDS_MIN;
    const pinFavOddsMispriceExcluded =
      STRICT_POLICY_MODE &&
      pinnacle != null &&
      Math.min(pinnacle.pinnacle_odds1 ?? 0, pinnacle.pinnacle_odds2 ?? 0) < STRICT_POLICY_MISPRICE_FAV_ODDS_MIN;
    const injuryExcluded = STRICT_POLICY_MODE && STRICT_INJURY_OVERLAY_ENABLED && recentInjuredAny;
    const mispriceExcluded = modelFavOddsMispriceExcluded || pinFavOddsMispriceExcluded;
    if (
      policyBaseAllows &&
      (shortFavoriteExcluded || mispriceExcluded || injuryExcluded)
    )
      strictPolicyExcludedCount += 1;
    if (policyBaseAllows && injuryExcluded) injurySkippedCount += 1;
    const policyAllows =
      policyBaseAllows &&
      !shortFavoriteExcluded &&
      !mispriceExcluded &&
      !injuryExcluded;
    if (policyAllows) strictPolicyEligibleCount += 1;
    const strictCandidateValueP1 =
      policyAllows && rawValueP1 != null && rawValueP1 >= STRICT_POLICY_INTERNAL_MIN_VALUE_PCT ? rawValueP1 : undefined;
    const strictCandidateValueP2 =
      policyAllows && rawValueP2 != null && rawValueP2 >= STRICT_POLICY_INTERNAL_MIN_VALUE_PCT ? rawValueP2 : undefined;
    let strictValueP1 = strictCandidateValueP1;
    let strictValueP2 = strictCandidateValueP2;

    if (STRICT_POLICY_MODE && STRICT_POLICY_PRODUCTION_MODE === "overlay") {
      strictValueP1 = undefined;
      strictValueP2 = undefined;
      const candidateSide: "P1" | "P2" | undefined =
        strictCandidateValueP1 == null && strictCandidateValueP2 == null
          ? undefined
          : strictCandidateValueP2 == null ||
              (strictCandidateValueP1 ?? Number.NEGATIVE_INFINITY) >=
                (strictCandidateValueP2 ?? Number.NEGATIVE_INFINITY)
            ? "P1"
            : "P2";
      if (candidateSide && Number.isFinite(seasonYear)) {
        overlayConsideredCount += 1;
        const ourFavSide: "P1" | "P2" = ourOdds1 > 0 && ourOdds2 > 0 && ourOdds1 <= ourOdds2 ? "P1" : "P2";
        const betSide: "fav" | "dog" = candidateSide === ourFavSide ? "fav" : "dog";
        const decision = evaluateOverlayGate(seasonYear, tournamentName, betSide, overlayIndex);
        if (decision.pass) {
          overlayPassedCount += 1;
          if (candidateSide === "P1") strictValueP1 = strictCandidateValueP1;
          else strictValueP2 = strictCandidateValueP2;
        } else if (decision.reason === "missing") {
          overlaySkippedMissingCount += 1;
        } else if (decision.reason === "min_n") {
          overlaySkippedMinNCount += 1;
        } else if (decision.reason === "min_roi") {
          overlaySkippedMinRoiCount += 1;
        }
      }
    }
    const strictPublicValueP1 =
      strictValueP1 != null && strictValueP1 >= STRICT_POLICY_PUBLIC_MIN_VALUE_PCT ? strictValueP1 : undefined;
    const strictPublicValueP2 =
      strictValueP2 != null && strictValueP2 >= STRICT_POLICY_PUBLIC_MIN_VALUE_PCT ? strictValueP2 : undefined;
    const valueP1 = STRICT_POLICY_MODE ? strictPublicValueP1 : confidence === "none" ? undefined : rawValueP1;
    const valueP2 = STRICT_POLICY_MODE ? strictPublicValueP2 : confidence === "none" ? undefined : rawValueP2;
    const policyMatch = STRICT_POLICY_MODE ? valueP1 != null || valueP2 != null : false;
    const displayValueP1 = pinnacle && ourOdds1 > 1 && pinnacle.pinnacle_odds1 > 1 ? rawValueP1 : undefined;
    const displayValueP2 = pinnacle && ourOdds2 > 1 && pinnacle.pinnacle_odds2 > 1 ? rawValueP2 : undefined;
    if (policyMatch) strictPolicySignaledCount += 1;

    // Active shadow profile: same exclusions as strict, different segment/value rules (no overlay)
    const volumeMinVal = SHADOW_POLICY_MODE === "off" ? null : shadowMinValueFor(r.surface ?? "", seriesBucket, confidence ?? "");
    const volumeExcluded =
      shortFavoriteExcluded || mispriceExcluded || injuryExcluded;
    const volumeValueP1 =
      volumeMinVal != null &&
      !volumeExcluded &&
      rawValueP1 != null &&
      rawValueP1 >= volumeMinVal
        ? rawValueP1
        : undefined;
    const volumeValueP2 =
      volumeMinVal != null &&
      !volumeExcluded &&
      rawValueP2 != null &&
      rawValueP2 >= volumeMinVal
        ? rawValueP2
        : undefined;
    const shadowMatch = volumeValueP1 != null || volumeValueP2 != null;
    const shadowSpreadEligible =
      volumeMinVal != null &&
      !shortFavoriteExcluded &&
      !injuryExcluded;
    const spreadShadowReason = spreadShadowReasonFor(r.surface ?? "", seriesBucket, confidence ?? "");
    const spreadShadowEligible = spreadShadowReason != null && !shortFavoriteExcluded && !injuryExcluded;
    const strictSpreadWouldSignal =
      policyBaseAllows &&
      !shortFavoriteExcluded &&
      !recentInjuredAny &&
      ((r.handicap_edge_p1 != null && Number(r.handicap_edge_p1) >= 20) ||
        (r.handicap_edge_p2 != null && Number(r.handicap_edge_p2) >= 20));
    const shadowSpreadWouldSignal =
      shadowSpreadEligible &&
      ((r.handicap_edge_p1 != null && Number(r.handicap_edge_p1) >= 20) ||
        (r.handicap_edge_p2 != null && Number(r.handicap_edge_p2) >= 20));
    const spreadShadowWouldSignal =
      spreadShadowEligible &&
      ((r.handicap_edge_p1 != null && Number(r.handicap_edge_p1) >= HANDICAP_MIN_EDGE_PCT) ||
        (r.handicap_edge_p2 != null && Number(r.handicap_edge_p2) >= HANDICAP_MIN_EDGE_PCT));
    const hasPositiveRawValue = (rawValueP1 ?? Number.NEGATIVE_INFINITY) > 0 || (rawValueP2 ?? Number.NEGATIVE_INFINITY) > 0;
    const blockedReason = firstBlockedReason({
      hasPositiveRawValue,
      anySignal: policyMatch || strictSpreadWouldSignal || shadowMatch || shadowSpreadWouldSignal || spreadShadowWouldSignal,
      recentInjuredAny,
      pinnacleShortFavoriteExcluded: pinFavOddsMispriceExcluded,
      modelShortFavoriteExcluded: modelFavOddsMispriceExcluded,
      atp500HardShortFavoriteExcluded: shortFavoriteExcluded,
      shadowMinVal: volumeMinVal,
      rawValueP1,
      rawValueP2,
    });

    return {
      id: r.id,
      tournament: tournamentName,
      surface: r.surface ?? "",
      player1_id: r.player1_id ?? 0,
      player2_id: r.player2_id ?? 0,
      player1_name: p1Name,
      player2_name: p2Name,
      p1_win_prob: p1WinProb,
      p2_win_prob: p2WinProb,
      odds1: ourOdds1,
      odds2: ourOdds2,
      p1_serve: p1Stats ? Math.round(p1Stats.hold_pct * 1000) / 10 : undefined,
      p1_return: p1Stats ? Math.round(p1Stats.return_pct * 1000) / 10 : undefined,
      p1_total: p1Stats ? Math.round((p1Stats.hold_pct + p1Stats.return_pct) * 1000) / 10 : undefined,
      p2_serve: p2Stats ? Math.round(p2Stats.hold_pct * 1000) / 10 : undefined,
      p2_return: p2Stats ? Math.round(p2Stats.return_pct * 1000) / 10 : undefined,
      p2_total: p2Stats ? Math.round((p2Stats.hold_pct + p2Stats.return_pct) * 1000) / 10 : undefined,
      expected_total_games: r.expected_total_games != null ? Number(r.expected_total_games) : undefined,
      ou_line_1: r.ou_line_1 != null ? Number(r.ou_line_1) : undefined,
      ou_over_1: r.ou_over_1 != null ? Number(r.ou_over_1) : undefined,
      ou_under_1: r.ou_under_1 != null ? Number(r.ou_under_1) : undefined,
      ou_line_2: r.ou_line_2 != null ? Number(r.ou_line_2) : undefined,
      ou_over_2: r.ou_over_2 != null ? Number(r.ou_over_2) : undefined,
      ou_under_2: r.ou_under_2 != null ? Number(r.ou_under_2) : undefined,
      ou_line_3: r.ou_line_3 != null ? Number(r.ou_line_3) : undefined,
      ou_over_3: r.ou_over_3 != null ? Number(r.ou_over_3) : undefined,
      ou_under_3: r.ou_under_3 != null ? Number(r.ou_under_3) : undefined,
      pinnacle_odds1: pinnacle?.pinnacle_odds1,
      pinnacle_odds2: pinnacle?.pinnacle_odds2,
      pinnacle_margin: pinnacle?.pinnacle_margin,
      pinnacle_ou_line: pinnacle?.pinnacle_ou_line,
      pinnacle_ou_over: pinnacle?.pinnacle_ou_over,
      pinnacle_ou_under: pinnacle?.pinnacle_ou_under,
      spread_line: r.spread_line != null ? Number(r.spread_line) : undefined,
      spread_odds1: r.spread_odds1 != null ? Number(r.spread_odds1) : undefined,
      spread_odds2: r.spread_odds2 != null ? Number(r.spread_odds2) : undefined,
      handicap_edge_p1: r.handicap_edge_p1 != null ? Number(r.handicap_edge_p1) : undefined,
      handicap_edge_p2: r.handicap_edge_p2 != null ? Number(r.handicap_edge_p2) : undefined,
      value_p1: displayValueP1,
      value_p2: displayValueP2,
      confidence,
      series_bucket: seriesBucket,
      policy_match: policyMatch,
      spread_eligible: policyBaseAllows && !shortFavoriteExcluded && !recentInjuredAny,
      shadow_match: shadowMatch,
      shadow_spread_eligible: shadowSpreadEligible,
      spread_shadow_eligible: spreadShadowEligible,
      spread_shadow_reason: spreadShadowReason ?? undefined,
      blocked_reason: blockedReason,
      recent_injured_p1: p1Injury.matched,
      recent_injured_p2: p2Injury.matched,
      recent_injured_any: recentInjuredAny,
      recent_injured_p1_mode: p1Injury.mode,
      recent_injured_p2_mode: p2Injury.mode,
    };
  });

  const overlaySummary: OverlayPolicySummary | undefined =
    STRICT_POLICY_MODE && STRICT_POLICY_PRODUCTION_MODE === "overlay"
      ? {
          enabled: true,
          policy_file: path.resolve(process.cwd(), STRICT_OVERLAY_POLICY_FILE),
          window: STRICT_OVERLAY_WINDOW,
          family: STRICT_OVERLAY_FAMILY,
          min_n: STRICT_OVERLAY_MIN_N,
          min_roi_pct: STRICT_OVERLAY_MIN_ROI_PCT,
          missing_mode: STRICT_OVERLAY_MISSING_MODE,
          keys_loaded: overlayIndex.lookup.size,
          considered_matches: overlayConsideredCount,
          passed_matches: overlayPassedCount,
          skipped_missing: overlaySkippedMissingCount,
          skipped_min_n: overlaySkippedMinNCount,
          skipped_min_roi: overlaySkippedMinRoiCount,
        }
      : undefined;
  const injurySummary: InjuryOverlaySummary = {
    enabled: STRICT_INJURY_OVERLAY_ENABLED,
    csv_file: injuryIndex.csvPath,
    lookback_days: injuryIndex.lookbackDays,
    rows_loaded: injuryIndex.rowsLoaded,
    rows_recent: injuryIndex.rowsRecent,
    flagged_matches: injuryFlaggedCount,
    skipped_matches: injurySkippedCount,
  };

  const policy = buildStrictPolicyPayload(
    strictPolicyEligibleCount,
    strictPolicySignaledCount,
    strictPolicyExcludedCount,
    overlaySummary,
    injurySummary
  );

  const pinnacleHint =
    pinnacleRows.length === 0
      ? "No Pinnacle rows for today (UTC). Run: npm run daily-odds. Ensure .env.local has SUPABASE_SERVICE_ROLE_KEY so the API can read bookmaker_odds_snapshot."
      : pinnacleMap.size === 0
        ? "Pinnacle snapshot loaded but no matches linked (name mismatch?). Check server log for match counts."
        : undefined;

  function toSignal(m: (typeof matches)[0]) {
    const side = (m.value_p1 ?? -Infinity) >= (m.value_p2 ?? -Infinity) ? "P1" : "P2";
    const valuePct = side === "P1" ? m.value_p1 : m.value_p2;
    const pinnacleOdds = side === "P1" ? m.pinnacle_odds1 : m.pinnacle_odds2;
    const pin1 = m.pinnacle_odds1 ?? 0;
    const pin2 = m.pinnacle_odds2 ?? 0;
    const valuePctNum = valuePct ?? 0;
    const { units, gbp } =
      pin1 > 0 && pin2 > 0
        ? computeStakeUnits(m.odds1, m.odds2, pin1, pin2, side as "P1" | "P2", valuePctNum)
        : { units: 1, gbp: STRICT_UNIT_GBP };
    return {
      id: m.id,
      player1_name: m.player1_name,
      player2_name: m.player2_name,
      side,
      value_pct: valuePct ?? 0,
      pinnacle_odds: pinnacleOdds,
      stake_units: Math.round(units * 100) / 100,
      stake_gbp: Math.round(gbp * 100) / 100,
      bet_type: "match" as const,
      tournament: m.tournament,
      surface: m.surface,
    };
  }

  const matchSignalsStrict = matches.filter((m) => m.policy_match).map((m) => toSignal(m));

  function toSpreadSignal(
    m: (typeof matches)[0],
    side: "P1+" | "P2-",
    edgePct: number,
    pinOdds: number,
    spreadLine: number,
    extra?: { shadow_reason?: string }
  ) {
    return {
      id: m.id * 1000 + (side === "P1+" ? 1 : 2),
      player1_name: m.player1_name,
      player2_name: m.player2_name,
      side,
      value_pct: edgePct,
      pinnacle_odds: pinOdds,
      stake_units: 1,
      stake_gbp: STRICT_UNIT_GBP,
      bet_type: "spread" as const,
      spread_line: spreadLine,
      tournament: m.tournament,
      surface: m.surface,
      ...(extra?.shadow_reason ? { shadow_reason: extra.shadow_reason } : {}),
    };
  }

  const spreadSignalsStrict: Array<ReturnType<typeof toSpreadSignal>> = [];
  for (const m of matches) {
    const spreadOk =
      (m.policy_match || m.spread_eligible) &&
      !m.recent_injured_any &&
      m.spread_line != null &&
      m.spread_odds1 != null &&
      m.spread_odds2 != null &&
      m.handicap_edge_p1 != null &&
      m.handicap_edge_p2 != null;
    if (!spreadOk) continue;
    const sl = m.spread_line;
    const so1 = m.spread_odds1;
    const so2 = m.spread_odds2;
    const he1 = m.handicap_edge_p1;
    const he2 = m.handicap_edge_p2;
    if (sl == null || so1 == null || so2 == null || he1 == null || he2 == null) continue;
    if (he1 >= HANDICAP_MIN_EDGE_PCT) {
      spreadSignalsStrict.push(toSpreadSignal(m, "P1+", he1, so1, sl));
    }
    if (he2 >= HANDICAP_MIN_EDGE_PCT) {
      spreadSignalsStrict.push(toSpreadSignal(m, "P2-", he2, so2, sl));
    }
  }

  const signals_strict = [...matchSignalsStrict, ...spreadSignalsStrict];
  const matchSignalsVolume = matches.filter((m) => m.shadow_match).map((m) => toSignal(m));
  const spreadSignalsVolume: Array<ReturnType<typeof toSpreadSignal>> = [];
  for (const m of matches) {
    const spreadOk =
      (m.shadow_match || m.shadow_spread_eligible) &&
      !m.recent_injured_any &&
      m.spread_line != null &&
      m.spread_odds1 != null &&
      m.spread_odds2 != null &&
      m.handicap_edge_p1 != null &&
      m.handicap_edge_p2 != null;
    if (!spreadOk) continue;
    const sl = m.spread_line;
    const so1 = m.spread_odds1;
    const so2 = m.spread_odds2;
    const he1 = m.handicap_edge_p1;
    const he2 = m.handicap_edge_p2;
    if (sl == null || so1 == null || so2 == null || he1 == null || he2 == null) continue;
    if (he1 >= HANDICAP_MIN_EDGE_PCT) {
      spreadSignalsVolume.push(toSpreadSignal(m, "P1+", he1, so1, sl));
    }
    if (he2 >= HANDICAP_MIN_EDGE_PCT) {
      spreadSignalsVolume.push(toSpreadSignal(m, "P2-", he2, so2, sl));
    }
  }
  const signals_volume = [...matchSignalsVolume, ...spreadSignalsVolume];
  const spreadSignalsSpreadShadow: Array<ReturnType<typeof toSpreadSignal>> = [];
  for (const m of matches) {
    const spreadOk =
      m.spread_shadow_eligible &&
      !m.recent_injured_any &&
      m.spread_line != null &&
      m.spread_odds1 != null &&
      m.spread_odds2 != null &&
      m.handicap_edge_p1 != null &&
      m.handicap_edge_p2 != null;
    if (!spreadOk) continue;
    const sl = m.spread_line;
    const so1 = m.spread_odds1;
    const so2 = m.spread_odds2;
    const he1 = m.handicap_edge_p1;
    const he2 = m.handicap_edge_p2;
    if (sl == null || so1 == null || so2 == null || he1 == null || he2 == null) continue;
    if (he1 >= HANDICAP_MIN_EDGE_PCT) {
      spreadSignalsSpreadShadow.push(
        toSpreadSignal(m, "P1+", he1, so1, sl, { shadow_reason: m.spread_shadow_reason })
      );
    }
    if (he2 >= HANDICAP_MIN_EDGE_PCT) {
      spreadSignalsSpreadShadow.push(
        toSpreadSignal(m, "P2-", he2, so2, sl, { shadow_reason: m.spread_shadow_reason })
      );
    }
  }

  const matchesWithSpread = matches.filter(
    (m) =>
      m.spread_line != null &&
      m.spread_odds1 != null &&
      m.spread_odds2 != null &&
      m.handicap_edge_p1 != null &&
      m.handicap_edge_p2 != null
  );
  const spreadStrictEligible = matchesWithSpread.filter(
    (m) => (m.policy_match || m.spread_eligible) && !m.recent_injured_any
  );
  const spreadWithEdge20 = spreadStrictEligible.filter(
    (m) => (m.handicap_edge_p1 ?? 0) >= HANDICAP_MIN_EDGE_PCT || (m.handicap_edge_p2 ?? 0) >= HANDICAP_MIN_EDGE_PCT
  );
  const spreadHint =
    matchesWithSpread.length === 0
      ? "Spread data missing. Run: python scripts/compute-handicap-values.py (or full pipeline: python scripts/run-daily-odds.py)"
      : spreadSignalsStrict.length === 0
        ? `Spread: ${matchesWithSpread.length} matches have data, ${spreadStrictEligible.length} pass strict policy, ${spreadWithEdge20.length} have edge ≥20%.`
        : undefined;

  return NextResponse.json({
    matches,
    pinnacle_count: pinnacleRows.length,
    pinnacle_matched_count: pinnacleMap.size,
    policy,
    shadow_profile: SHADOW_POLICY_MODE,
    signals_strict,
    signals_volume,
    signals_spread_shadow: spreadSignalsSpreadShadow,
    ...(pinnacleHint ? { pinnacle_hint: pinnacleHint } : {}),
    ...(spreadHint ? { spread_hint: spreadHint } : {}),
  });
}

export async function GET() {
  const timeout = new Promise<Response>((resolve) =>
    setTimeout(
      () => resolve(NextResponse.json({ error: "Fair-odds API timed out (15s). Check Supabase or network." }, { status: 503 })),
      API_TIMEOUT_MS
    )
  );
  try {
    return await Promise.race([run(), timeout]);
  } catch (e) {
    return NextResponse.json(
      { error: e instanceof Error ? e.message : "Fair-odds API error" },
      { status: 500 }
    );
  }
}
