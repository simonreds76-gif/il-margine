import { createClient } from "@supabase/supabase-js";
import { NextResponse } from "next/server";
import fs from "node:fs";
import path from "node:path";
import {
  getKnownProjectFilePath,
  resolveConfiguredProjectFilePath,
} from "@/lib/project-file-paths";

export const dynamic = "force-dynamic";
export const revalidate = 0;

const url = process.env.NEXT_PUBLIC_SUPABASE_URL;
const anonKey = process.env.NEXT_PUBLIC_SUPABASE_ANON_KEY;
/** Service role used only for bookmaker_odds_snapshot so Pinnacle shows even if RLS blocks anon. */
const serviceRoleKey = process.env.SUPABASE_SERVICE_ROLE_KEY;

/** Pinnacle snapshot: only ATP + Challenger singles; cap must exceed busy days (many events) or rows past the limit never load (e.g. Naples Challenger). */
const PINNACLE_SNAPSHOT_SELECT =
  "player1_name, player2_name, odds1, odds2, ou_line, ou_over, ou_under, league, captured_at";
const PINNACLE_SNAPSHOT_ROW_CAP = 12000;
const LOCAL_PINNACLE_HISTORY_DIR = path.join(process.cwd(), "data", "pinnacle-history");

export interface FairOddsRow {
  id: number;
  tournament: string;
  surface: string;
  league?: "ATP" | "Challenger";
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
  p_a?: number;
  p_b?: number;
  handicap_point_prob_source?: "stored_p_a_p_b" | "fallback_divergent_gap" | "fallback_missing";
  handicap_reverse_solve?: boolean;
  handicap_point_prob_gap?: number;
  value_p1?: number;
  value_p2?: number;
  strict_signal_value_p1?: number;
  strict_signal_value_p2?: number;
  shadow_profile_value_p1?: number;
  shadow_profile_value_p2?: number;
  shadow_value_p1?: number;
  shadow_value_p2?: number;
  confidence?: string;
  series_bucket?: string;
  policy_match?: boolean;
  spread_eligible?: boolean;
  shadow_profile_match?: boolean;
  shadow_overlap_match?: boolean;
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
  tournament_speed_signal?: number;
  fast_clay_flag?: boolean;
  fast_clay_selected_side?: "P1" | "P2";
  fast_clay_archetype?: "both" | "serve_led" | "return_led" | "contrarian";
  fast_clay_return_led_flag?: boolean;
  row_signals?: ShadowSignalSummary[];
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
// Skip matches where model favourite odds < 1.25. Model cannot price extreme mismatches - both sides unreliable.
const STRICT_POLICY_MISPRICE_FAV_ODDS_MIN = 1.25;
// Proxy for the bad strict tail we found in backtesting: heavy-favourite Masters hard
// matches where dog ML strict signals underperform. We keep this narrow and leave the
// broader Masters calibration untouched.
const STRICT_POLICY_HEAVY_FAV_DOG_GUARD_MIN_FAV_PROB = 0.74;
const STRICT_POLICY_PRODUCTION_MODE: StrictPolicyMode =
  (process.env.STRICT_POLICY_PRODUCTION_MODE ?? "base").trim().toLowerCase() === "overlay"
    ? "overlay"
    : "base";
const STRICT_OVERLAY_POLICY_FILE = resolveConfiguredProjectFilePath(
  process.env.STRICT_OVERLAY_POLICY_FILE,
  "data/backtest/tournament-segment-roi.csv",
);
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
const INJURED_PLAYERS_CSV = resolveConfiguredProjectFilePath(
  process.env.INJURED_PLAYERS_CSV,
  "data/injured-players-tennisexplorer.csv",
);

const HANDICAP_MIN_EDGE_PCT = 20;
const STRICT_UNIT_GBP = parseNumberEnv("STRICT_UNIT_GBP", 100);
const SHADOW_POLICY_MODE = normalizeShadowProfile(process.env.STRICT_POLICY_VOLUME_MODE);
const SURFACE_LEAGUE_AVG: Record<string, number> = {
  hard: 0.64,
  clay: 0.62,
  grass: 0.67,
  "i.hard": 0.64,
  "n/a": 0.64,
};
const MIN_TOUR_MATCHES_FOR_SHIFT = 30;
const MIN_VENUE_SPW_MATCHES = 50;
const POINT_PROB_MATCH_PROB_GAP_MAX = 0.12;
const SPEED_RATIO_CLAMP: [number, number] = [0.92, 1.08];
const TOURNAMENT_SPEED_VENUE_COMPONENT_WEIGHT = 0.75;
const TOURNAMENT_SPEED_SHIFT_COMPONENT_WEIGHT = 0.25;
const TOURNAMENT_SPEED_VENUE_FULL_MATCHES = 150;
const TOURNAMENT_SPEED_SHIFT_FULL_MATCHES = 90;
const TOURNAMENT_SPEED_SHIFT_SIGNAL_SCALE = 2.0;
const FAST_CLAY_SPEED_THRESHOLD = 0.1;
const CLAY_2026_SIGNAL_CSV = getKnownProjectFilePath("data/backtest/strict-signals-claycal-live.csv");
const SPREAD_SHADOW_SIGNAL_CSV = getKnownProjectFilePath("data/backtest/strict-signals-spreadshadow-live.csv");
const FAIR_ODDS_CLAY_2026_ENABLED = parseBoolEnv("FAIR_ODDS_CLAY_2026_ENABLED", false);
type MatchSide = "P1" | "P2";
type FastClayArchetype = "both" | "serve_led" | "return_led" | "contrarian";
type ShadowSignalKind = "clay_2026" | "spread_shadow";

interface ShadowSignalSummary {
  id: number;
  kind: ShadowSignalKind;
  player1_id?: number;
  player2_id?: number;
  player1_name: string;
  player2_name: string;
  side: string;
  value_pct: number;
  pinnacle_odds?: number;
  stake_units?: number;
  stake_gbp?: number;
  bet_type: "match" | "spread";
  spread_line?: number;
  tournament: string;
  surface: string;
  league?: "ATP" | "Challenger";
  shadow_reason?: string;
  tournament_speed_signal?: number;
  clay_speed_tier?: "fast" | "normal";
  raw_value_p1?: number;
  raw_value_p2?: number;
  clay_2026_raw_value_same_side?: number;
  clay_2026_value_p1?: number;
  clay_2026_value_p2?: number;
  clay_2026_raw_odds1?: number;
  clay_2026_raw_odds2?: number;
  clay_2026_calibrated_odds1?: number;
  clay_2026_calibrated_odds2?: number;
  clay_2026_selected_prob?: number;
  handicap_point_prob_source?: "stored_p_a_p_b" | "fallback_divergent_gap" | "fallback_missing";
}

interface SignalAttachmentDiagnostics {
  loaded: number;
  attached: number;
  unmatched: number;
}

function computeStakeUnits(): { units: number; gbp: number } {
  return { units: 1, gbp: STRICT_UNIT_GBP };
}

function signalMatchKey(player1Id: number, player2Id: number): string {
  return `${player1Id}|${player2Id}`;
}

function normaliseSignalName(name: string): string {
  return (name ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[-'.,]/g, " ")
    .replace(/\s+/g, " ")
    .trim();
}

function signalNameKey(player1Name: string, player2Name: string): string {
  return `name|${normaliseSignalName(player1Name)}|${normaliseSignalName(player2Name)}`;
}

function spreadConflictDirection(signal: ShadowSignalSummary): MatchSide | null {
  if (signal.kind !== "spread_shadow" || signal.bet_type !== "spread" || signal.spread_line == null) return null;
  if (Math.abs(signal.spread_line) > 1.0) return null;
  if (signal.side === "P1+") return "P1";
  if (signal.side === "P2-") return "P2";
  return null;
}

function suppressConflictingClaySignals(
  claySignals: ShadowSignalSummary[],
  spreadSignals: ShadowSignalSummary[],
): ShadowSignalSummary[] {
  const spreadDirectionsByKey = new Map<string, Set<MatchSide>>();

  for (const signal of spreadSignals) {
    const direction = spreadConflictDirection(signal);
    if (!direction) continue;
    if (signal.player1_id != null && signal.player2_id != null) {
      const key = signalMatchKey(signal.player1_id, signal.player2_id);
      if (!spreadDirectionsByKey.has(key)) spreadDirectionsByKey.set(key, new Set<MatchSide>());
      spreadDirectionsByKey.get(key)!.add(direction);
    }
    if (signal.player1_name && signal.player2_name) {
      const key = signalNameKey(signal.player1_name, signal.player2_name);
      if (!spreadDirectionsByKey.has(key)) spreadDirectionsByKey.set(key, new Set<MatchSide>());
      spreadDirectionsByKey.get(key)!.add(direction);
    }
  }

  return claySignals.filter((signal) => {
    const clayDirection = signal.side === "P1" ? "P1" : signal.side === "P2" ? "P2" : null;
    if (!clayDirection) return true;
    const lookupKeys: string[] = [];
    if (signal.player1_id != null && signal.player2_id != null) {
      lookupKeys.push(signalMatchKey(signal.player1_id, signal.player2_id));
    }
    if (signal.player1_name && signal.player2_name) {
      lookupKeys.push(signalNameKey(signal.player1_name, signal.player2_name));
    }

    const directions = new Set<MatchSide>();
    for (const key of lookupKeys) {
      for (const direction of spreadDirectionsByKey.get(key) ?? []) directions.add(direction);
    }
    if (directions.size === 0) return true;
    if (directions.has(clayDirection)) return true;
    return false;
  });
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

function clamp(value: number, lo: number, hi: number): number {
  return Math.max(lo, Math.min(hi, value));
}

function parsePointProb(value: unknown): number | undefined {
  const parsed = Number(value);
  if (!Number.isFinite(parsed)) return undefined;
  if (!(parsed > 0 && parsed < 1)) return undefined;
  return parsed;
}

function probGame(pointProb: number): number {
  if (pointProb <= 0 || pointProb >= 1) return clamp(pointProb, 0, 1);
  const deuceProb = (pointProb * pointProb) / (1 - 2 * pointProb * (1 - pointProb));
  return (
    pointProb ** 4 +
    4 * pointProb ** 4 * (1 - pointProb) +
    10 * pointProb ** 4 * (1 - pointProb) ** 2 +
    20 * pointProb ** 3 * (1 - pointProb) ** 3 * deuceProb
  );
}

function tbServerIsA(totalPoints: number): boolean {
  return totalPoints % 4 === 0 || totalPoints % 4 === 3;
}

function probTiebreak(pA: number, pB: number, aServesFirst = true): number {
  const pointA = clamp(pA, 0.01, 0.99);
  const pointB = clamp(pB, 0.01, 0.99);
  const maxPts = 30;
  const dp: number[][] = Array.from({ length: maxPts + 1 }, () => Array(maxPts + 1).fill(0));

  const pWinPoint = (total: number) => {
    const serverA = aServesFirst ? tbServerIsA(total) : !tbServerIsA(total);
    return serverA ? pointA : 1 - pointB;
  };

  for (let a = maxPts; a >= 0; a -= 1) {
    for (let b = maxPts; b >= 0; b -= 1) {
      if (a >= 7 && a - b >= 2) {
        dp[a][b] = 1;
      } else if (b >= 7 && b - a >= 2) {
        dp[a][b] = 0;
      } else if (a + b >= 12 && a === b && a > 6) {
        const total = a + b;
        const p = pWinPoint(total);
        const pNextA = pWinPoint(total + 1);
        const pNextB = pWinPoint(total + 2);
        const denom = 1 - (p * (1 - pNextA) + (1 - p) * (1 - pNextB));
        dp[a][b] = Math.abs(denom) >= 1e-9 ? (p * pNextA) / denom : 0.5;
      } else {
        const total = a + b;
        const p = pWinPoint(total);
        const nextA = a + 1 <= maxPts ? dp[a + 1][b] : 0.5;
        const nextB = b + 1 <= maxPts ? dp[a][b + 1] : 0.5;
        dp[a][b] = p * nextA + (1 - p) * nextB;
      }
    }
  }

  return dp[0][0];
}

function probSet(pA: number, pB: number, aServesFirst = true): number {
  const pointA = clamp(pA, 0.01, 0.99);
  const pointB = clamp(pB, 0.01, 0.99);
  const cache = new Map<string, number>();

  const solve = (a: number, b: number, aServes: boolean): number => {
    const key = `${a}:${b}:${aServes ? 1 : 0}`;
    const hit = cache.get(key);
    if (hit != null) return hit;
    let out = 0;
    if (a >= 6 && a - b >= 2) {
      out = 1;
    } else if (b >= 6 && b - a >= 2) {
      out = 0;
    } else if (a === 6 && b === 6) {
      out = probTiebreak(pointA, pointB, aServes);
    } else {
      const pGameA = probGame(pointA);
      const pGameB = probGame(pointB);
      const pWinGame = aServes ? pGameA : 1 - pGameB;
      out = pWinGame * solve(a + 1, b, !aServes) + (1 - pWinGame) * solve(a, b + 1, !aServes);
    }
    cache.set(key, out);
    return out;
  };

  return solve(0, 0, aServesFirst);
}

function probMatchBestOf3(pA: number, pB: number): number {
  const s1 = probSet(pA, pB, true);
  const s2 = probSet(pA, pB, false);
  return s1 * s2 + s1 * (1 - s2) * s1 + (1 - s1) * s2 * s1;
}

function sampleScale(matchCount: number | null | undefined, fullMatches: number): number {
  if (!Number.isFinite(matchCount as number)) return 0;
  if (fullMatches <= 0) return 1;
  return clamp(Number(matchCount) / fullMatches, 0, 1);
}

function computeTournamentSpeedSignal(params: {
  leagueAvg: number;
  venueEntry?: { venue_avg_spw: number; match_count: number };
  shiftEntry?: { shift_from_surface: number; match_count: number };
}): number {
  const { leagueAvg, venueEntry, shiftEntry } = params;
  if (!(leagueAvg > 0)) return 0;

  const parts: Array<{ signal: number; weight: number }> = [];
  const speedRatioSpan = Math.max(
    SPEED_RATIO_CLAMP[1] - 1,
    1 - SPEED_RATIO_CLAMP[0],
    1e-6
  );

  if (venueEntry && Number.isFinite(venueEntry.venue_avg_spw) && venueEntry.venue_avg_spw > 0) {
    const ratio = clamp(venueEntry.venue_avg_spw / leagueAvg, SPEED_RATIO_CLAMP[0], SPEED_RATIO_CLAMP[1]);
    const signal = clamp((ratio - 1) / speedRatioSpan, -1, 1);
    const weight =
      TOURNAMENT_SPEED_VENUE_COMPONENT_WEIGHT *
      sampleScale(venueEntry.match_count, TOURNAMENT_SPEED_VENUE_FULL_MATCHES);
    if (weight > 0) parts.push({ signal, weight });
  }

  if (shiftEntry && Number.isFinite(shiftEntry.shift_from_surface)) {
    const signal = clamp(shiftEntry.shift_from_surface / TOURNAMENT_SPEED_SHIFT_SIGNAL_SCALE, -1, 1);
    const weight =
      TOURNAMENT_SPEED_SHIFT_COMPONENT_WEIGHT *
      sampleScale(shiftEntry.match_count, TOURNAMENT_SPEED_SHIFT_FULL_MATCHES);
    if (weight > 0) parts.push({ signal, weight });
  }

  if (!parts.length) return 0;
  const totalWeight = parts.reduce((sum, part) => sum + part.weight, 0);
  if (!(totalWeight > 0)) return 0;
  return clamp(
    parts.reduce((sum, part) => sum + part.signal * part.weight, 0) / totalWeight,
    -1,
    1
  );
}

function pickSideByValues(p1?: number, p2?: number): MatchSide | undefined {
  const v1 = Number.isFinite(p1 as number) ? Number(p1) : Number.NEGATIVE_INFINITY;
  const v2 = Number.isFinite(p2 as number) ? Number(p2) : Number.NEGATIVE_INFINITY;
  if (!(v1 > Number.NEGATIVE_INFINITY) && !(v2 > Number.NEGATIVE_INFINITY)) return undefined;
  return v1 >= v2 ? "P1" : "P2";
}

function classifySelectedArchetype(
  side: MatchSide | undefined,
  p1Stats: { hold_pct: number; return_pct: number } | null,
  p2Stats: { hold_pct: number; return_pct: number } | null
): FastClayArchetype | undefined {
  if (!side || !p1Stats || !p2Stats) return undefined;
  const serveAdv =
    side === "P1" ? p1Stats.hold_pct - p2Stats.hold_pct : p2Stats.hold_pct - p1Stats.hold_pct;
  const returnAdv =
    side === "P1" ? p1Stats.return_pct - p2Stats.return_pct : p2Stats.return_pct - p1Stats.return_pct;
  if (serveAdv > 0 && returnAdv > 0) return "both";
  if (serveAdv > 0 && returnAdv <= 0) return "serve_led";
  if (returnAdv > 0 && serveAdv <= 0) return "return_led";
  return "contrarian";
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
  exclusionRules.push(
    `Exclude strict underdog MLs in Hard Masters 1000 when calibrated favourite win probability >= ${(
      STRICT_POLICY_HEAVY_FAV_DOG_GUARD_MIN_FAV_PROB * 100
    ).toFixed(0)}%`
  );
  exclusionRules.push("Suppress strict dog MLs when the same match also shows a favourite handicap signal");
  exclusionRules.push("Suppress displayed ML value when the opposite side also has a handicap edge");
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

function strictPolicyExcludedByHeavyFavoriteDog(
  surface: string,
  seriesBucket: string,
  favoriteProb: number,
  side: "P1" | "P2",
  favoriteSide: "P1" | "P2"
): boolean {
  if (!STRICT_POLICY_MODE) return false;
  if (!(surface === "Hard" && seriesBucket === "Masters 1000")) return false;
  if (side === favoriteSide) return false;
  return favoriteProb >= STRICT_POLICY_HEAVY_FAV_DOG_GUARD_MIN_FAV_PROB;
}

function strictPolicyConflictWithFavoriteSpread(
  favoriteSide: "P1" | "P2",
  spreadLine: number | null | undefined,
  handicapEdgeP1: number | null | undefined,
  handicapEdgeP2: number | null | undefined
): boolean {
  if (spreadLine == null || handicapEdgeP1 == null || handicapEdgeP2 == null) return false;
  if (favoriteSide === "P1") return spreadLine < 0 && handicapEdgeP1 >= HANDICAP_MIN_EDGE_PCT;
  return spreadLine > 0 && handicapEdgeP2 >= HANDICAP_MIN_EDGE_PCT;
}

function oppositeSideHandicapConflict(
  side: "P1" | "P2",
  handicapEdgeP1: number | null | undefined,
  handicapEdgeP2: number | null | undefined
): boolean {
  if (side === "P1") return handicapEdgeP2 != null && handicapEdgeP2 >= HANDICAP_MIN_EDGE_PCT;
  return handicapEdgeP1 != null && handicapEdgeP1 >= HANDICAP_MIN_EDGE_PCT;
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
const HOUSTON_SHADOW_MIN_VALUE_PCT = 20;
const HOUSTON_SHADOW_CONFIDENCE = new Set(["high", "medium"]);
const VALIDATED_FAST_CLAY_TOUR_KEYS = new Set(["houston", "madrid"]);

function normalizeShadowProfile(raw: string | undefined): ShadowProfile {
  const value = (raw ?? "volume_200").trim().toLowerCase();
  if (value === "off" || value === "volume_275" || value === "volume_200") return value;
  return "volume_200";
}

function isHoustonClayShadowException(surface: string, tournamentName?: string): boolean {
  if (surface !== "Clay") return false;
  return tourKeyCandidates(tournamentName).includes("houston");
}

function isValidatedFastClayVenue(surface: string, tournamentName?: string): boolean {
  if (surface !== "Clay") return false;
  return tourKeyCandidates(tournamentName).some((key) => VALIDATED_FAST_CLAY_TOUR_KEYS.has(key));
}

function shadowMinValueFor(
  surface: string,
  seriesBucket: string,
  confidence: string,
  tournamentName?: string
): number | null {
  const rules =
    SHADOW_POLICY_MODE === "volume_275"
      ? VOLUME_275_RULES
      : SHADOW_POLICY_MODE === "volume_200"
        ? VOLUME_200_RULES
        : [];
  let minVal: number | null = null;
  if (
    SHADOW_POLICY_MODE !== "off" &&
    isHoustonClayShadowException(surface, tournamentName) &&
    HOUSTON_SHADOW_CONFIDENCE.has(confidence)
  ) {
    minVal = HOUSTON_SHADOW_MIN_VALUE_PCT;
  }
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

function spreadShadowReasonFor(
  surface: string,
  seriesBucket: string,
  confidence?: string,
  tournamentName?: string
): string | null {
  const conf = (confidence ?? "").trim().toLowerCase();
  if (!(conf === "high" || conf === "medium")) return null;
  if (isHoustonClayShadowException(surface, tournamentName)) return null;

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
  recentInjuredAny: boolean;
  pinnacleShortFavoriteExcluded: boolean;
  modelShortFavoriteExcluded: boolean;
  atp500HardShortFavoriteExcluded: boolean;
  heavyFavoriteDogExcluded: boolean;
  favoriteSpreadConflictExcluded: boolean;
  oppositeSideHandicapConflictExcluded: boolean;
  shadowMinVal: number | null;
  rawValueP1?: number;
  rawValueP2?: number;
}): string | undefined {
  if (!params.hasPositiveRawValue) return undefined;
  if (params.recentInjuredAny) return "Blocked: recent injury flag";
  if (params.pinnacleShortFavoriteExcluded) return "Blocked: Pinnacle fav <1.25";
  if (params.modelShortFavoriteExcluded) return "Blocked: model fav <1.25";
  if (params.atp500HardShortFavoriteExcluded) return "Blocked: ATP500 Hard short favorite filter";
  if (params.heavyFavoriteDogExcluded) return "Blocked: Masters hard heavy-favorite dog ML guard";
  if (params.favoriteSpreadConflictExcluded) return "Blocked: same-match favourite handicap conflict";
  if (params.oppositeSideHandicapConflictExcluded) return "Blocked: same-match mixed-side ML/handicap conflict";
  if (params.shadowMinVal == null) return `ML only: not in ${shadowProfileLabel(SHADOW_POLICY_MODE)} segment`;
  const bestRawValue = Math.max(params.rawValueP1 ?? Number.NEGATIVE_INFINITY, params.rawValueP2 ?? Number.NEGATIVE_INFINITY);
  if (Number.isFinite(bestRawValue) && bestRawValue < params.shadowMinVal) {
    return `ML only: below ${shadowProfileLabel(SHADOW_POLICY_MODE)} threshold`;
  }
  return "Blocked: filtered by policy";
}

function mlDisplayGuardReason(params: {
  confidence?: string;
  rawValueP1?: number;
  rawValueP2?: number;
  suppressDisplayValueP1: boolean;
  suppressDisplayValueP2: boolean;
  pinnacleShortFavoriteExcluded: boolean;
  modelShortFavoriteExcluded: boolean;
  heavyFavoriteDogExcluded: boolean;
  favoriteSpreadConflictExcluded: boolean;
  oppositeSideHandicapConflictExcluded: boolean;
}): string | undefined {
  const positiveSuppressedP1 = params.suppressDisplayValueP1 && (params.rawValueP1 ?? Number.NEGATIVE_INFINITY) > 0;
  const positiveSuppressedP2 = params.suppressDisplayValueP2 && (params.rawValueP2 ?? Number.NEGATIVE_INFINITY) > 0;
  if (!positiveSuppressedP1 && !positiveSuppressedP2) return undefined;
  if (params.pinnacleShortFavoriteExcluded || params.modelShortFavoriteExcluded) {
    return "ML value hidden: favourite <1.25";
  }
  if (params.heavyFavoriteDogExcluded) {
    return "ML value hidden: heavy-favourite dog guard";
  }
  if (params.favoriteSpreadConflictExcluded) {
    return "ML value hidden: same-match handicap conflict";
  }
  if (params.oppositeSideHandicapConflictExcluded) {
    return "ML value hidden: opposite-side handicap signal";
  }
  if (params.confidence === "none") {
    return "ML value hidden: low-confidence row";
  }
  return "ML value hidden by guard";
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

function parseCsvNumber(value: string | undefined): number | undefined {
  if (value == null) return undefined;
  const trimmed = value.trim();
  if (!trimmed) return undefined;
  const parsed = Number(trimmed);
  return Number.isFinite(parsed) ? parsed : undefined;
}

function parseCsvLeague(value: string | undefined): "ATP" | "Challenger" | undefined {
  const normalized = (value ?? "").trim();
  if (normalized === "ATP" || normalized === "Challenger") return normalized;
  return undefined;
}

interface PinnacleSourceRow {
  player1_name: string;
  player2_name: string;
  odds1: number;
  odds2: number;
  ou_line?: number;
  ou_over?: number;
  ou_under?: number;
  league?: "ATP" | "Challenger";
  captured_at?: string;
}

function normalizePinnaclePairKey(player1Name: string, player2Name: string, league?: "ATP" | "Challenger"): string {
  return `${league ?? ""}|${normaliseSignalName(player1Name)}|${normaliseSignalName(player2Name)}`;
}

function sortByCapturedAtDesc<T extends { captured_at?: string }>(rows: T[]): T[] {
  return [...rows].sort((a, b) => {
    const aTime = a.captured_at ? Date.parse(a.captured_at) : 0;
    const bTime = b.captured_at ? Date.parse(b.captured_at) : 0;
    return bTime - aTime;
  });
}

function dedupeLatestPinnacleRows(rows: PinnacleSourceRow[]): PinnacleSourceRow[] {
  const deduped = new Map<string, PinnacleSourceRow>();
  for (const row of sortByCapturedAtDesc(rows)) {
    const key = normalizePinnaclePairKey(row.player1_name, row.player2_name, row.league);
    if (!key || deduped.has(key)) continue;
    deduped.set(key, row);
  }
  return Array.from(deduped.values());
}

function loadRecentLocalPinnacleHistory(activeDates: string[]): PinnacleSourceRow[] {
  if (!fs.existsSync(LOCAL_PINNACLE_HISTORY_DIR)) return [];
  const dateTokens = new Set(activeDates.map((value) => value.replace(/-/g, "")));
  const latestByPair = new Map<string, PinnacleSourceRow>();

  let fileNames: string[] = [];
  try {
    fileNames = fs
      .readdirSync(LOCAL_PINNACLE_HISTORY_DIR)
      .filter((name) => name.startsWith("pinnacle-history-") && name.endsWith(".csv"))
      .filter((name) => {
        const token = name.slice("pinnacle-history-".length, "pinnacle-history-".length + 8);
        return dateTokens.has(token);
      })
      .sort()
      .reverse();
  } catch (error) {
    console.warn("[fair-odds] Could not read local Pinnacle history directory", error);
    return [];
  }

  for (const fileName of fileNames) {
    const filePath = path.join(LOCAL_PINNACLE_HISTORY_DIR, fileName);
    let text = "";
    try {
      text = fs.readFileSync(filePath, "utf8");
    } catch (error) {
      console.warn(`[fair-odds] Could not read local Pinnacle history file: ${filePath}`, error);
      continue;
    }
    const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
    if (lines.length < 2) continue;
    const header = parseCsvLine(lines[0]);
    const index = new Map<string, number>();
    header.forEach((h, i) => index.set(h, i));
    const required = ["capture_date", "captured_at", "bookmaker", "league", "player1_name", "player2_name", "odds1", "odds2"];
    if (required.some((name) => !index.has(name))) continue;
    const get = (cols: string[], name: string) => cols[index.get(name) ?? -1] ?? "";

    for (let i = 1; i < lines.length; i += 1) {
      const cols = parseCsvLine(lines[i]);
      const captureDate = get(cols, "capture_date").trim();
      if (!dateTokens.has(captureDate.replace(/-/g, ""))) continue;
      if (get(cols, "bookmaker").trim() !== "Pinnacle") continue;
      const league = parseCsvLeague(get(cols, "league"));
      if (!league) continue;
      const player1Name = get(cols, "player1_name").trim();
      const player2Name = get(cols, "player2_name").trim();
      if (!player1Name || !player2Name) continue;
      const odds1 = parseCsvNumber(get(cols, "odds1"));
      const odds2 = parseCsvNumber(get(cols, "odds2"));
      if (odds1 == null || odds2 == null) continue;

      const row: PinnacleSourceRow = {
        player1_name: player1Name,
        player2_name: player2Name,
        odds1,
        odds2,
        ou_line: parseCsvNumber(get(cols, "ou_line")),
        ou_over: parseCsvNumber(get(cols, "ou_over")),
        ou_under: parseCsvNumber(get(cols, "ou_under")),
        league,
        captured_at: get(cols, "captured_at").trim() || undefined,
      };
      const key = normalizePinnaclePairKey(row.player1_name, row.player2_name, row.league);
      if (!key || latestByPair.has(key)) continue;
      latestByPair.set(key, row);
    }
  }

  return Array.from(latestByPair.values());
}

function loadActiveShadowSignals(csvPath: string, kind: ShadowSignalKind, activeDate?: string): ShadowSignalSummary[] {
  if (!fs.existsSync(csvPath)) return [];

  let text = "";
  try {
    text = fs.readFileSync(csvPath, "utf8");
  } catch (e) {
    console.warn(`[fair-odds] Could not read shadow signal CSV: ${csvPath}`, e);
    return [];
  }

  const lines = text.split(/\r?\n/).filter((line) => line.trim().length > 0);
  if (lines.length < 2) return [];

  const header = parseCsvLine(lines[0]);
  const index = new Map<string, number>();
  header.forEach((h, i) => index.set(h, i));
  const required = ["player1", "player2", "side", "value_pct", "bet_type"];
  if (required.some((k) => !index.has(k))) return [];
  const hasSettlementStatus = index.has("settlement_status");

  const get = (cols: string[], name: string) => cols[index.get(name) ?? -1] ?? "";
  const latestBySignalKey = new Map<string, ShadowSignalSummary & { settlement_status: string }>();
  const parsedRows: Array<{ cols: string[]; rowDate: string }> = [];
  const availableDates = new Set<string>();

  for (let i = 1; i < lines.length; i += 1) {
    const cols = parseCsvLine(lines[i]);
    const rowDate = get(cols, "date").trim();
    if (rowDate) availableDates.add(rowDate);
    parsedRows.push({ cols, rowDate });
  }

  const effectiveDate =
    activeDate && availableDates.has(activeDate)
      ? activeDate
      : Array.from(availableDates).sort().at(-1);

  for (let i = 0; i < parsedRows.length; i += 1) {
    const { cols, rowDate } = parsedRows[i];
    if (effectiveDate && rowDate && rowDate !== effectiveDate) continue;
    const player1Id = parseCsvNumber(get(cols, "player1_id"));
    const player2Id = parseCsvNumber(get(cols, "player2_id"));
    const player1Name = get(cols, "player1");
    const player2Name = get(cols, "player2");
    if (!player1Name || !player2Name) continue;
    const side = get(cols, "side");
    const betType = (get(cols, "bet_type") || "match").trim().toLowerCase() === "spread" ? "spread" : "match";
    const spreadLine = parseCsvNumber(get(cols, "spread_line"));
    const signalIdentity =
      player1Id != null && player2Id != null
        ? `${player1Id}|${player2Id}`
        : signalNameKey(player1Name, player2Name);
    // Keep only the latest active signal per live market lane.
    // The CSV append flow can legitimately record an earlier side and a later side
    // for the same match on the same day; the fair-odds page should show the latest
    // current lane, not both stale and current sides together.
    const signalKey =
      kind === "spread_shadow"
        ? `${kind}|${signalIdentity}|${betType}|${spreadLine ?? ""}`
        : `${kind}|${signalIdentity}|${betType}`;

    latestBySignalKey.set(signalKey, {
      id: i + 1,
      kind,
      player1_id: player1Id,
      player2_id: player2Id,
      player1_name: player1Name,
      player2_name: player2Name,
      side,
      value_pct: parseCsvNumber(get(cols, "value_pct")) ?? 0,
      pinnacle_odds: parseCsvNumber(get(cols, "spread_odds")) ?? parseCsvNumber(get(cols, side === "P1" || side === "P1+" ? "pin_odds1" : "pin_odds2")),
      stake_units: parseCsvNumber(get(cols, "stake_units")),
      stake_gbp: parseCsvNumber(get(cols, "stake_gbp")),
      bet_type: betType,
      spread_line: spreadLine,
      tournament: get(cols, "series"),
      surface: get(cols, "surface"),
      league: parseCsvLeague(get(cols, "league")),
      shadow_reason: get(cols, "shadow_reason") || undefined,
      tournament_speed_signal: parseCsvNumber(get(cols, "tournament_speed_signal")),
      clay_speed_tier:
        (get(cols, "clay_speed_tier") || "") === "fast"
          ? "fast"
          : (get(cols, "clay_speed_tier") || "") === "normal"
            ? "normal"
            : undefined,
      raw_value_p1: parseCsvNumber(get(cols, "raw_value_p1")) ?? parseCsvNumber(get(cols, "value_p1")),
      raw_value_p2: parseCsvNumber(get(cols, "raw_value_p2")) ?? parseCsvNumber(get(cols, "value_p2")),
      clay_2026_raw_value_same_side: parseCsvNumber(get(cols, "raw_value_same_side")),
      clay_2026_value_p1: parseCsvNumber(get(cols, "value_p1")),
      clay_2026_value_p2: parseCsvNumber(get(cols, "value_p2")),
      clay_2026_raw_odds1: parseCsvNumber(get(cols, "raw_odds1_shadow")),
      clay_2026_raw_odds2: parseCsvNumber(get(cols, "raw_odds2_shadow")),
      clay_2026_calibrated_odds1: parseCsvNumber(get(cols, "calibrated_odds1")),
      clay_2026_calibrated_odds2: parseCsvNumber(get(cols, "calibrated_odds2")),
      clay_2026_selected_prob: parseCsvNumber(get(cols, "calibrated_selected_prob")),
      handicap_point_prob_source:
        (get(cols, "handicap_point_prob_source") as FairOddsRow["handicap_point_prob_source"]) || undefined,
      settlement_status: hasSettlementStatus ? get(cols, "settlement_status").trim().toLowerCase() : "open",
    });
  }

  return Array.from(latestBySignalKey.values())
    .filter((row) => row.settlement_status !== "settled")
    .map((row) => {
      const { settlement_status, ...rest } = row;
      void settlement_status;
      return rest;
    });
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
  const csvPath = INJURED_PLAYERS_CSV;
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
  const absPath = STRICT_OVERLAY_POLICY_FILE;
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

  /** Must cover all singles rows from daily_fair_odds after full oncourt_today pagination (was 2000; dropped high tour_id). */
  const FAIR_ODDS_LIMIT = 5000;

  const { data: oddsRows, error: oddsErr } = await supabase
    .from("daily_fair_odds")
    .select("id, tour_id, player1_id, player2_id, surface, p1_win_prob, p2_win_prob, odds1, odds2, p_a, p_b, expected_total_games, ou_line_1, ou_over_1, ou_under_1, ou_line_2, ou_over_2, ou_under_2, ou_line_3, ou_over_3, ou_under_3, confidence, spread_line, spread_odds1, spread_odds2, handicap_edge_p1, handicap_edge_p2")
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

  const { data: oncourtTodayRows, error: oncourtTodayErr } = await supabase
    .from("oncourt_today")
    .select("tour_id, player1_id, player2_id")
    .limit(FAIR_ODDS_LIMIT);
  if (oncourtTodayErr) {
    console.warn("[fair-odds] Could not load oncourt_today for Pinnacle-only current-gap filtering", oncourtTodayErr.message);
  }
  const currentOncourtRows = oncourtTodayRows ?? [];

  const playerIds = new Set<number>();
  const tourIds = new Set<number>();
  for (const r of oddsRows) {
    if (r.player1_id != null) playerIds.add(r.player1_id);
    if (r.player2_id != null) playerIds.add(r.player2_id);
    if (r.tour_id != null) tourIds.add(r.tour_id);
  }
  for (const r of currentOncourtRows) {
    if (r.player1_id != null) playerIds.add(Number(r.player1_id));
    if (r.player2_id != null) playerIds.add(Number(r.player2_id));
    if (r.tour_id != null) tourIds.add(Number(r.tour_id));
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
  const tourShiftChunks =
    tourIdArr.length > 0
      ? await Promise.all(
          Array.from({ length: Math.ceil(tourIdArr.length / BATCH) }, (_, i) =>
            supabase
              .from("tournament_game_averages")
              .select("tour_id, surface, shift_from_surface, match_count")
              .in("tour_id", tourIdArr.slice(i * BATCH, (i + 1) * BATCH))
          )
        )
      : [];
  const serveProfileChunks =
    tourIdArr.length > 0
      ? await Promise.all(
          Array.from({ length: Math.ceil(tourIdArr.length / BATCH) }, (_, i) =>
            supabase
              .from("tournament_serve_profile")
              .select("tour_id, surface, venue_avg_spw, match_count")
              .in("tour_id", tourIdArr.slice(i * BATCH, (i + 1) * BATCH))
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
  const tourShiftLookup = new Map<string, { shift_from_surface: number; match_count: number }>();
  for (const res of tourShiftChunks) {
    for (const row of res.data ?? []) {
      const tid = row.tour_id != null ? Number(row.tour_id) : NaN;
      const shift = row.shift_from_surface != null ? Number(row.shift_from_surface) : NaN;
      const matchCount = row.match_count != null ? Number(row.match_count) : 0;
      if (!Number.isFinite(tid) || !Number.isFinite(shift) || matchCount < MIN_TOUR_MATCHES_FOR_SHIFT) continue;
      tourShiftLookup.set(`${tid}:${normalizeSurfaceKey(row.surface)}`, {
        shift_from_surface: shift,
        match_count: matchCount,
      });
    }
  }
  const serveProfileLookup = new Map<string, { venue_avg_spw: number; match_count: number }>();
  for (const res of serveProfileChunks) {
    for (const row of res.data ?? []) {
      const tid = row.tour_id != null ? Number(row.tour_id) : NaN;
      const venueAvgSpw = row.venue_avg_spw != null ? Number(row.venue_avg_spw) : NaN;
      const matchCount = row.match_count != null ? Number(row.match_count) : 0;
      if (!Number.isFinite(tid) || !Number.isFinite(venueAvgSpw) || matchCount < MIN_VENUE_SPW_MATCHES) continue;
      serveProfileLookup.set(`${tid}:${normalizeSurfaceKey(row.surface)}`, {
        venue_avg_spw: venueAvgSpw,
        match_count: matchCount,
      });
    }
  }
  const stats = new Map<string, { hold_pct: number; return_pct: number }>();
  for (const res of statsChunks) {
    for (const s of res.data ?? []) {
      const pid = s.player_id != null ? Number(s.player_id) : NaN;
      if (!Number.isFinite(pid)) continue;
      const key = `${pid}:${normalizeSurfaceKey(s.surface)}`;
      const hold = s.hold_pct != null ? Number(s.hold_pct) : NaN;
      const ret = s.return_pct != null ? Number(s.return_pct) : NaN;
      if (!Number.isFinite(hold) || !Number.isFinite(ret)) continue;
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
  const getTournamentLookup = <T,>(lookup: Map<string, T>, tourId?: number | null, surface?: string | null): T | undefined => {
    if (tourId == null) return undefined;
    for (const surf of surfaceCandidates(surface)) {
      const row = lookup.get(`${tourId}:${surf}`);
      if (row) return row;
    }
    return undefined;
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
  let pinnacleRows: PinnacleSourceRow[] = [];
  const snapshotClient = url && serviceRoleKey ? createClient(url, serviceRoleKey) : supabase;

  // Try today first; if the scraper ran before midnight UTC (e.g. 23:55), fall back to yesterday.
  const yesterday = (() => {
    const d = new Date(now.getTime() - 86_400_000);
    return `${d.getUTCFullYear()}-${String(d.getUTCMonth() + 1).padStart(2, "0")}-${String(d.getUTCDate()).padStart(2, "0")}`;
  })();

  const [todaySnapshotRes, yesterdaySnapshotRes] = await Promise.all([
    snapshotClient
      .from("bookmaker_odds_snapshot")
      .select(PINNACLE_SNAPSHOT_SELECT)
      .eq("bookmaker", "Pinnacle")
      .eq("capture_date", today)
      .or("league.eq.ATP,league.eq.Challenger")
      .order("captured_at", { ascending: false })
      .limit(PINNACLE_SNAPSHOT_ROW_CAP),
    snapshotClient
      .from("bookmaker_odds_snapshot")
      .select(PINNACLE_SNAPSHOT_SELECT)
      .eq("bookmaker", "Pinnacle")
      .eq("capture_date", yesterday)
      .or("league.eq.ATP,league.eq.Challenger")
      .order("captured_at", { ascending: false })
      .limit(PINNACLE_SNAPSHOT_ROW_CAP),
  ]);

  const snapshotRows: PinnacleSourceRow[] = [...(todaySnapshotRes.data ?? []), ...(yesterdaySnapshotRes.data ?? [])]
    .filter((row: { league?: string }) => row.league === "ATP" || row.league === "Challenger")
    .map((row): PinnacleSourceRow => ({
      player1_name: (row.player1_name ?? "").trim(),
      player2_name: (row.player2_name ?? "").trim(),
      odds1: Number(row.odds1 ?? 0),
      odds2: Number(row.odds2 ?? 0),
      ou_line: row.ou_line != null ? Number(row.ou_line) : undefined,
      ou_over: row.ou_over != null ? Number(row.ou_over) : undefined,
      ou_under: row.ou_under != null ? Number(row.ou_under) : undefined,
      league: row.league === "Challenger" ? "Challenger" : "ATP",
      captured_at: typeof row.captured_at === "string" ? row.captured_at : undefined,
    }))
    .filter((row) => row.player1_name && row.player2_name && row.odds1 > 0 && row.odds2 > 0);

  const localHistoryRows = loadRecentLocalPinnacleHistory([today, yesterday]);
  pinnacleRows = dedupeLatestPinnacleRows([...snapshotRows, ...localHistoryRows]);

  if (localHistoryRows.length > 0) {
    console.log(
      `[fair-odds] Local Pinnacle history supplement: ${localHistoryRows.length} recent rows across ${today} / ${yesterday}.`
    );
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

  function inferLeagueFromTournament(tournamentName: string, pinnacleLeague?: string): "ATP" | "Challenger" {
    if (pinnacleLeague === "ATP" || pinnacleLeague === "Challenger") return pinnacleLeague;
    return (tournamentName ?? "").toUpperCase().includes("CHALLENGER") ? "Challenger" : "ATP";
  }

  const currentOncourtPairKeys = new Set<string>();
  for (const row of currentOncourtRows) {
    const p1Id = row.player1_id != null ? Number(row.player1_id) : NaN;
    const p2Id = row.player2_id != null ? Number(row.player2_id) : NaN;
    const tourId = row.tour_id != null ? Number(row.tour_id) : NaN;
    if (!Number.isFinite(p1Id) || !Number.isFinite(p2Id)) continue;
    const p1Name = players.get(p1Id);
    const p2Name = players.get(p2Id);
    if (!p1Name || !p2Name) continue;
    const tourMeta = Number.isFinite(tourId) ? tours.get(tourId) : undefined;
    const league = inferLeagueFromTournament(tourMeta?.name ?? "");
    currentOncourtPairKeys.add(normalizePinnaclePairKey(p1Name, p2Name, league));
    currentOncourtPairKeys.add(normalizePinnaclePairKey(p2Name, p1Name, league));
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
    matched: Map<
      number,
      {
        pinnacle_odds1: number;
        pinnacle_odds2: number;
        pinnacle_margin: number;
        pinnacle_ou_line?: number;
        pinnacle_ou_over?: number;
        pinnacle_ou_under?: number;
        pinnacle_league?: "ATP" | "Challenger";
      }
    >;
    pinnacleOnly: PinnacleRow[];
  } {
    const matched = new Map<
      number,
      {
        pinnacle_odds1: number;
        pinnacle_odds2: number;
        pinnacle_margin: number;
        pinnacle_ou_line?: number;
        pinnacle_ou_over?: number;
        pinnacle_ou_under?: number;
        pinnacle_league?: "ATP" | "Challenger";
      }
    >();
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
      // When tied, prefer first (avoids skipping matches that would otherwise match)
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
          pinnacle_league: pin.league,
        });
      } else {
        matched.set(fo.id, {
          pinnacle_odds1: pin.odds1,
          pinnacle_odds2: pin.odds2,
          pinnacle_margin: margin,
          pinnacle_ou_line: pin.ou_line,
          pinnacle_ou_over: pin.ou_over,
          pinnacle_ou_under: pin.ou_under,
          pinnacle_league: pin.league,
        });
      }
    }

    const singlesPin = pinRows.filter((p) => !isDoublesPin(p));
    const currentOpponentsByPlayer = new Map<string, Set<string>>();
    const addCurrentOpponent = (playerName: string, opponentName: string) => {
      const playerKey = normaliseFullName(playerName ?? "");
      const opponentKey = normaliseFullName(opponentName ?? "");
      if (!playerKey || !opponentKey) return;
      const existing = currentOpponentsByPlayer.get(playerKey) ?? new Set<string>();
      existing.add(opponentKey);
      currentOpponentsByPlayer.set(playerKey, existing);
    };
    for (const fo of fairOddsRows) {
      addCurrentOpponent(fo.player1_name ?? "", fo.player2_name ?? "");
      addCurrentOpponent(fo.player2_name ?? "", fo.player1_name ?? "");
    }
    const isStaleAlternativePairing = (row: PinnacleRow) => {
      const p1Key = normaliseFullName(row.player1_name ?? "");
      const p2Key = normaliseFullName(row.player2_name ?? "");
      if (!p1Key || !p2Key) return false;
      const p1Opponents = currentOpponentsByPlayer.get(p1Key);
      if (p1Opponents && !p1Opponents.has(p2Key)) return true;
      const p2Opponents = currentOpponentsByPlayer.get(p2Key);
      if (p2Opponents && !p2Opponents.has(p1Key)) return true;
      return false;
    };
    const isInCurrentOncourtSchedule = (row: PinnacleRow) => {
      if (currentOncourtPairKeys.size === 0) return true;
      const directKey = normalizePinnaclePairKey(row.player1_name ?? "", row.player2_name ?? "", row.league);
      const reverseKey = normalizePinnaclePairKey(row.player2_name ?? "", row.player1_name ?? "", row.league);
      return currentOncourtPairKeys.has(directKey) || currentOncourtPairKeys.has(reverseKey);
    };
    const rawPinnacleOnly = singlesPin.filter((p) => !matchedPinRows.has(p));
    const staleAlternativePairings = rawPinnacleOnly.filter(isStaleAlternativePairing);
    const notInCurrentSchedule = rawPinnacleOnly.filter((p) => !isStaleAlternativePairing(p) && !isInCurrentOncourtSchedule(p));
    const pinnacleOnly = rawPinnacleOnly.filter((p) => !isStaleAlternativePairing(p) && isInCurrentOncourtSchedule(p));
    if (staleAlternativePairings.length > 0) {
      console.log(
        `[fair-odds] Suppressed stale Pinnacle-only rows that conflict with current fair-odds pairings:`,
        staleAlternativePairings.map((p) => `${p.player1_name} vs ${p.player2_name}`)
      );
    }
    if (notInCurrentSchedule.length > 0) {
      console.log(
        `[fair-odds] Suppressed Pinnacle-only rows not present in current oncourt_today schedule:`,
        notInCurrentSchedule.map((p) => `${p.player1_name} vs ${p.player2_name}`)
      );
    }
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
  const { matched: pinnacleMap, pinnacleOnly } = matchPinnacle(fairOddsRowsForMatch, pinnacleRows);

  let strictPolicyEligibleCount = 0;
  let strictPolicyExcludedCount = 0;
  let strictPolicySignaledCount = 0;

  const rawMatches: FairOddsRow[] = mainTourOddsRows.map((r) => {
    const p1Stats = getSurfaceStats(r.player1_id, r.surface);
    const p2Stats = getSurfaceStats(r.player2_id, r.surface);
    const p1Name = (r.player1_id != null ? players.get(r.player1_id) : null) ?? "";
    const p2Name = (r.player2_id != null ? players.get(r.player2_id) : null) ?? "";
    const surfaceKey = normalizeSurfaceKey(r.surface);
    const tourMeta = r.tour_id != null ? tours.get(r.tour_id) : undefined;
    const tournamentName = tourMeta?.name ?? "";
    const pinnacle = pinnacleRows.length ? pinnacleMap.get(r.id) ?? null : null;
    const league = inferLeagueFromTournament(tournamentName, pinnacle?.pinnacle_league);
    const seriesBucket = seriesBucketFromTour(tournamentName, tourMeta?.rank);
    const tournamentSpeedSignal =
      surfaceKey === "clay"
        ? computeTournamentSpeedSignal({
            leagueAvg: SURFACE_LEAGUE_AVG[surfaceKey] ?? SURFACE_LEAGUE_AVG["n/a"],
            venueEntry: getTournamentLookup(serveProfileLookup, r.tour_id, r.surface),
            shiftEntry: getTournamentLookup(tourShiftLookup, r.tour_id, r.surface),
          })
        : 0;
    const fastClayFlag =
      surfaceKey === "clay" &&
      tournamentSpeedSignal >= FAST_CLAY_SPEED_THRESHOLD &&
      isValidatedFastClayVenue(r.surface ?? "", tournamentName);
    const confidenceRaw = (r as { confidence?: string }).confidence;
    const confidence = confidenceRaw ? confidenceRaw.toLowerCase() : undefined;
    const p1WinProb = r.p1_win_prob != null ? Number(r.p1_win_prob) : 0;
    const p2WinProb = r.p2_win_prob != null ? Number(r.p2_win_prob) : 0;
    const storedPA = parsePointProb((r as { p_a?: number | string | null }).p_a);
    const storedPB = parsePointProb((r as { p_b?: number | string | null }).p_b);
    const storedMatchProb =
      storedPA != null && storedPB != null ? probMatchBestOf3(storedPA, storedPB) : undefined;
    const handicapPointProbGap =
      storedMatchProb != null ? storedMatchProb - p1WinProb : undefined;
    const handicapPointProbSource: FairOddsRow["handicap_point_prob_source"] =
      storedMatchProb == null || handicapPointProbGap == null
        ? "fallback_missing"
        : Math.abs(handicapPointProbGap) <= POINT_PROB_MATCH_PROB_GAP_MAX
          ? "stored_p_a_p_b"
          : "fallback_divergent_gap";
    const modelFavoriteProb = Math.max(p1WinProb, p2WinProb);
    const modelFavoriteSide: "P1" | "P2" = p1WinProb >= p2WinProb ? "P1" : "P2";
    const hasCurrentSpreadData =
      pinnacle != null &&
      r.spread_line != null &&
      r.spread_odds1 != null &&
      r.spread_odds2 != null &&
      r.handicap_edge_p1 != null &&
      r.handicap_edge_p2 != null;
    const spreadLine = hasCurrentSpreadData ? Number(r.spread_line) : undefined;
    const handicapEdgeP1 = hasCurrentSpreadData ? Number(r.handicap_edge_p1) : undefined;
    const handicapEdgeP2 = hasCurrentSpreadData ? Number(r.handicap_edge_p2) : undefined;
    const p1Injury = isRecentInjuredPlayer(p1Name, injuryIndex);
    const p2Injury = isRecentInjuredPlayer(p2Name, injuryIndex);
    const recentInjuredAny = p1Injury.matched || p2Injury.matched;
    if (recentInjuredAny) injuryFlaggedCount += 1;
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
    const strictCandidateValueP1Base =
      policyAllows && rawValueP1 != null && rawValueP1 >= STRICT_POLICY_INTERNAL_MIN_VALUE_PCT ? rawValueP1 : undefined;
    const strictCandidateValueP2Base =
      policyAllows && rawValueP2 != null && rawValueP2 >= STRICT_POLICY_INTERNAL_MIN_VALUE_PCT ? rawValueP2 : undefined;
    const strictHeavyFavoriteDogExcludedP1 =
      strictCandidateValueP1Base != null &&
      strictPolicyExcludedByHeavyFavoriteDog(
        r.surface ?? "",
        seriesBucket,
        modelFavoriteProb,
        "P1",
        modelFavoriteSide
      );
    const strictHeavyFavoriteDogExcludedP2 =
      strictCandidateValueP2Base != null &&
      strictPolicyExcludedByHeavyFavoriteDog(
        r.surface ?? "",
        seriesBucket,
        modelFavoriteProb,
        "P2",
        modelFavoriteSide
      );
    const strictFavoriteSpreadConflict =
      policyBaseAllows &&
      !shortFavoriteExcluded &&
      !recentInjuredAny &&
      strictPolicyConflictWithFavoriteSpread(
        modelFavoriteSide,
        spreadLine,
        handicapEdgeP1,
        handicapEdgeP2
      );
    const strictFavoriteSpreadConflictP1 =
      strictCandidateValueP1Base != null && modelFavoriteSide !== "P1" && strictFavoriteSpreadConflict;
    const strictFavoriteSpreadConflictP2 =
      strictCandidateValueP2Base != null && modelFavoriteSide !== "P2" && strictFavoriteSpreadConflict;
    const strictOppositeHandicapConflictP1 =
      strictCandidateValueP1Base != null &&
      oppositeSideHandicapConflict("P1", handicapEdgeP1, handicapEdgeP2);
    const strictOppositeHandicapConflictP2 =
      strictCandidateValueP2Base != null &&
      oppositeSideHandicapConflict("P2", handicapEdgeP1, handicapEdgeP2);
    if (
      policyBaseAllows &&
      !shortFavoriteExcluded &&
      !mispriceExcluded &&
      !injuryExcluded &&
      (
        strictHeavyFavoriteDogExcludedP1 ||
        strictHeavyFavoriteDogExcludedP2 ||
        strictFavoriteSpreadConflictP1 ||
        strictFavoriteSpreadConflictP2 ||
        strictOppositeHandicapConflictP1 ||
        strictOppositeHandicapConflictP2
      )
    ) {
      strictPolicyExcludedCount += 1;
    }
    const strictCandidateValueP1 =
      strictHeavyFavoriteDogExcludedP1 ||
      strictFavoriteSpreadConflictP1 ||
      strictOppositeHandicapConflictP1
        ? undefined
        : strictCandidateValueP1Base;
    const strictCandidateValueP2 =
      strictHeavyFavoriteDogExcludedP2 ||
      strictFavoriteSpreadConflictP2 ||
      strictOppositeHandicapConflictP2
        ? undefined
        : strictCandidateValueP2Base;
    const strictShadowCandidate = strictCandidateValueP1 != null || strictCandidateValueP2 != null;
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
    // Always surface the raw ML value in the fair-odds table when both our fair
    // odds and Pinnacle odds are present. Policy / signal routing still applies
    // separately; this only affects what the user can inspect on the board.
    const suppressDisplayValueP1 =
      confidence === "none" ||
      mispriceExcluded ||
      strictHeavyFavoriteDogExcludedP1 ||
      strictFavoriteSpreadConflictP1 ||
      strictOppositeHandicapConflictP1;
    const suppressDisplayValueP2 =
      confidence === "none" ||
      mispriceExcluded ||
      strictHeavyFavoriteDogExcludedP2 ||
      strictFavoriteSpreadConflictP2 ||
      strictOppositeHandicapConflictP2;
    const displayValueP1 =
      pinnacle && ourOdds1 > 1 && pinnacle.pinnacle_odds1 > 1
        ? rawValueP1
        : undefined;
    const displayValueP2 =
      pinnacle && ourOdds2 > 1 && pinnacle.pinnacle_odds2 > 1
        ? rawValueP2
        : undefined;
    if (policyMatch) strictPolicySignaledCount += 1;

    // Active shadow profile: same exclusions as strict, different segment/value rules (no overlay)
    const volumeMinVal =
      SHADOW_POLICY_MODE === "off"
        ? null
        : shadowMinValueFor(r.surface ?? "", seriesBucket, confidence ?? "", tournamentName);
    const volumeExcluded =
      shortFavoriteExcluded || mispriceExcluded || injuryExcluded;
    const volumeProfileValueP1 =
      volumeMinVal != null &&
      !volumeExcluded &&
      !strictOppositeHandicapConflictP1 &&
      rawValueP1 != null &&
      rawValueP1 >= volumeMinVal
        ? rawValueP1
        : undefined;
    const volumeProfileValueP2 =
      volumeMinVal != null &&
      !volumeExcluded &&
      !strictOppositeHandicapConflictP2 &&
      rawValueP2 != null &&
      rawValueP2 >= volumeMinVal
        ? rawValueP2
        : undefined;
    const shadowProfileMatch = volumeProfileValueP1 != null || volumeProfileValueP2 != null;
    const shadowOverlapMatch = shadowProfileMatch && strictShadowCandidate;
    const volumeValueP1 = !strictShadowCandidate ? volumeProfileValueP1 : undefined;
    const volumeValueP2 = !strictShadowCandidate ? volumeProfileValueP2 : undefined;
    const shadowMatch = volumeValueP1 != null || volumeValueP2 != null;
    const fastClaySelectedSide =
      policyMatch
        ? pickSideByValues(strictPublicValueP1, strictPublicValueP2)
        : shadowMatch
          ? pickSideByValues(volumeValueP1, volumeValueP2)
          : pickSideByValues(displayValueP1, displayValueP2);
    const fastClayArchetype = fastClayFlag
      ? classifySelectedArchetype(fastClaySelectedSide, p1Stats, p2Stats)
      : undefined;
    const fastClayReturnLedFlag = fastClayFlag && fastClayArchetype === "return_led";
    const shadowSpreadEligible =
      volumeMinVal != null &&
      !policyBaseAllows &&
      !shortFavoriteExcluded &&
      !injuryExcluded;
    const spreadShadowReason = spreadShadowReasonFor(r.surface ?? "", seriesBucket, confidence ?? "", tournamentName);
    const spreadShadowEligible = spreadShadowReason != null && !shortFavoriteExcluded && !injuryExcluded;
    const hasPositiveRawValue = (rawValueP1 ?? Number.NEGATIVE_INFINITY) > 0 || (rawValueP2 ?? Number.NEGATIVE_INFINITY) > 0;
    const displayGuardReason = mlDisplayGuardReason({
      confidence,
      rawValueP1,
      rawValueP2,
      suppressDisplayValueP1,
      suppressDisplayValueP2,
      pinnacleShortFavoriteExcluded: pinFavOddsMispriceExcluded,
      modelShortFavoriteExcluded: modelFavOddsMispriceExcluded,
      heavyFavoriteDogExcluded: strictHeavyFavoriteDogExcludedP1 || strictHeavyFavoriteDogExcludedP2,
      favoriteSpreadConflictExcluded: strictFavoriteSpreadConflictP1 || strictFavoriteSpreadConflictP2,
      oppositeSideHandicapConflictExcluded:
        strictOppositeHandicapConflictP1 || strictOppositeHandicapConflictP2,
    });
    const blockedReason = displayGuardReason ?? firstBlockedReason({
      hasPositiveRawValue,
      recentInjuredAny,
      pinnacleShortFavoriteExcluded: pinFavOddsMispriceExcluded,
      modelShortFavoriteExcluded: modelFavOddsMispriceExcluded,
      atp500HardShortFavoriteExcluded: shortFavoriteExcluded,
      heavyFavoriteDogExcluded: strictHeavyFavoriteDogExcludedP1 || strictHeavyFavoriteDogExcludedP2,
      favoriteSpreadConflictExcluded: strictFavoriteSpreadConflictP1 || strictFavoriteSpreadConflictP2,
      oppositeSideHandicapConflictExcluded:
        strictOppositeHandicapConflictP1 || strictOppositeHandicapConflictP2,
      shadowMinVal: volumeMinVal,
      rawValueP1,
      rawValueP2,
    });

    return {
      id: r.id,
      tournament: tournamentName,
      surface: r.surface ?? "",
      league,
      player1_id: r.player1_id ?? 0,
      player2_id: r.player2_id ?? 0,
      player1_name: p1Name,
      player2_name: p2Name,
      p1_win_prob: p1WinProb,
      p2_win_prob: p2WinProb,
      odds1: ourOdds1,
      odds2: ourOdds2,
      p_a: storedPA,
      p_b: storedPB,
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
      spread_line: spreadLine,
      spread_odds1: hasCurrentSpreadData ? Number(r.spread_odds1) : undefined,
      spread_odds2: hasCurrentSpreadData ? Number(r.spread_odds2) : undefined,
      handicap_edge_p1: handicapEdgeP1,
      handicap_edge_p2: handicapEdgeP2,
      handicap_point_prob_source: handicapPointProbSource,
      handicap_reverse_solve: handicapPointProbSource !== "stored_p_a_p_b",
      handicap_point_prob_gap: handicapPointProbGap,
      value_p1: displayValueP1,
      value_p2: displayValueP2,
      strict_signal_value_p1: strictPublicValueP1,
      strict_signal_value_p2: strictPublicValueP2,
      shadow_profile_value_p1: volumeProfileValueP1,
      shadow_profile_value_p2: volumeProfileValueP2,
      shadow_value_p1: volumeValueP1,
      shadow_value_p2: volumeValueP2,
      confidence,
      series_bucket: seriesBucket,
      policy_match: policyMatch,
      spread_eligible: policyBaseAllows && !shortFavoriteExcluded && !recentInjuredAny,
      shadow_profile_match: shadowProfileMatch,
      shadow_overlap_match: shadowOverlapMatch,
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
      tournament_speed_signal:
        fastClayFlag || Math.abs(tournamentSpeedSignal) >= FAST_CLAY_SPEED_THRESHOLD
          ? Math.round(tournamentSpeedSignal * 1000) / 1000
          : undefined,
      fast_clay_flag: fastClayFlag,
      fast_clay_selected_side: fastClaySelectedSide,
      fast_clay_archetype: fastClayArchetype,
      fast_clay_return_led_flag: fastClayReturnLedFlag,
    };
  });

  const clay2026SignalsCsv = FAIR_ODDS_CLAY_2026_ENABLED
    ? loadActiveShadowSignals(CLAY_2026_SIGNAL_CSV, "clay_2026", today)
    : [];
  const spreadShadowSignalsCsv = loadActiveShadowSignals(SPREAD_SHADOW_SIGNAL_CSV, "spread_shadow", today);
  const effectiveClay2026SignalsCsv = suppressConflictingClaySignals(clay2026SignalsCsv, spreadShadowSignalsCsv);
  const rowSignalsByMatch = new Map<string, ShadowSignalSummary[]>();
  const addSignalToRowKey = (key: string, signal: ShadowSignalSummary) => {
    const existing = rowSignalsByMatch.get(key);
    if (existing) existing.push(signal);
    else rowSignalsByMatch.set(key, [signal]);
  };
  const signalLookupKeys = (signal: ShadowSignalSummary): string[] => {
    const keys: string[] = [];
    if (signal.player1_id != null && signal.player2_id != null) {
      keys.push(signalMatchKey(signal.player1_id, signal.player2_id));
    }
    if (signal.player1_name && signal.player2_name) {
      keys.push(signalNameKey(signal.player1_name, signal.player2_name));
    }
    return Array.from(new Set(keys));
  };
  for (const signal of [...effectiveClay2026SignalsCsv, ...spreadShadowSignalsCsv]) {
    for (const key of signalLookupKeys(signal)) addSignalToRowKey(key, signal);
  }
  for (const signals of rowSignalsByMatch.values()) {
    signals.sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "clay_2026" ? -1 : 1;
      if (a.bet_type !== b.bet_type) return a.bet_type === "match" ? -1 : 1;
      return a.side.localeCompare(b.side);
    });
  }

  const matches: FairOddsRow[] = rawMatches.map((m) => {
    let rowSignals = Array.from(
      new Map(
        [signalMatchKey(m.player1_id, m.player2_id), signalNameKey(m.player1_name, m.player2_name)]
          .flatMap((key) => (rowSignalsByMatch.get(key) ?? []).map((signal) => [`${signal.kind}|${signal.id}`, signal] as const))
      ).values()
    ).sort((a, b) => {
      if (a.kind !== b.kind) return a.kind === "clay_2026" ? -1 : 1;
      if (a.bet_type !== b.bet_type) return a.bet_type === "match" ? -1 : 1;
      return a.side.localeCompare(b.side);
    });

    let claySignal = rowSignals.find((signal) => signal.kind === "clay_2026" && signal.bet_type === "match");
    let spreadSignal = rowSignals.find((signal) => signal.kind === "spread_shadow" && signal.bet_type === "spread");
    const spreadDirection = spreadSignal ? spreadConflictDirection(spreadSignal) : null;
    const clayDirection = claySignal?.side === "P2" ? "P2" : claySignal?.side === "P1" ? "P1" : null;

    if (claySignal && spreadSignal && clayDirection && spreadDirection && clayDirection !== spreadDirection) {
      const claySignalId = claySignal.id;
      rowSignals = rowSignals.filter((signal) => !(signal.kind === "clay_2026" && signal.id === claySignalId));
      claySignal = undefined;
      spreadSignal = rowSignals.find((signal) => signal.kind === "spread_shadow" && signal.bet_type === "spread");
    }

    return {
      ...m,
      league: claySignal?.league ?? spreadSignal?.league ?? m.league,
      tournament_speed_signal: m.tournament_speed_signal,
      spread_shadow_eligible: rowSignals.some((signal) => signal.kind === "spread_shadow" && signal.bet_type === "spread"),
      spread_shadow_reason: spreadSignal?.shadow_reason ?? m.spread_shadow_reason,
      row_signals: rowSignals,
    };
  });

  const attachedByKind: Record<ShadowSignalKind, Set<number>> = {
    clay_2026: new Set<number>(),
    spread_shadow: new Set<number>(),
  };
  let matchesWithRowSignals = 0;
  for (const match of matches) {
    const rowSignals = match.row_signals ?? [];
    if (rowSignals.length) matchesWithRowSignals += 1;
    for (const signal of rowSignals) attachedByKind[signal.kind].add(signal.id);
  }
  const signal_attachment: Record<ShadowSignalKind, SignalAttachmentDiagnostics> = {
    clay_2026: {
      loaded: effectiveClay2026SignalsCsv.length,
      attached: attachedByKind.clay_2026.size,
      unmatched: Math.max(0, effectiveClay2026SignalsCsv.length - attachedByKind.clay_2026.size),
    },
    spread_shadow: {
      loaded: spreadShadowSignalsCsv.length,
      attached: attachedByKind.spread_shadow.size,
      unmatched: Math.max(0, spreadShadowSignalsCsv.length - attachedByKind.spread_shadow.size),
    },
  };
  const unmatchedSignals = {
    clay_2026: effectiveClay2026SignalsCsv.filter((signal) => !attachedByKind.clay_2026.has(signal.id)),
    spread_shadow: spreadShadowSignalsCsv.filter((signal) => !attachedByKind.spread_shadow.has(signal.id)),
  };
  if (unmatchedSignals.clay_2026.length) {
    console.warn(
      "[fair-odds] Unmatched Clay 2026 signals:",
      unmatchedSignals.clay_2026.map((signal) => `${signal.id}: ${signal.player1_name} vs ${signal.player2_name} | ${signal.side}`)
    );
  }
  if (!FAIR_ODDS_CLAY_2026_ENABLED) {
    console.warn("[fair-odds] Clay 2026 lane disabled on live fair-odds route.");
  }
  if (unmatchedSignals.spread_shadow.length) {
    console.warn(
      "[fair-odds] Unmatched spread-shadow signals:",
      unmatchedSignals.spread_shadow.map(
        (signal) =>
          `${signal.id}: ${signal.player1_name} vs ${signal.player2_name} | ${signal.side}${signal.spread_line != null ? ` ${signal.spread_line}` : ""}`
      )
    );
  }

  const overlaySummary: OverlayPolicySummary | undefined =
    STRICT_POLICY_MODE && STRICT_POLICY_PRODUCTION_MODE === "overlay"
      ? {
          enabled: true,
          policy_file: STRICT_OVERLAY_POLICY_FILE,
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

  function toSignal(
    m: (typeof matches)[0],
    opts?: {
      valueKeyP1?: "strict_signal_value_p1" | "shadow_profile_value_p1" | "shadow_value_p1";
      valueKeyP2?: "strict_signal_value_p2" | "shadow_profile_value_p2" | "shadow_value_p2";
    }
  ) {
    const valueKeyP1 = opts?.valueKeyP1 ?? "strict_signal_value_p1";
    const valueKeyP2 = opts?.valueKeyP2 ?? "strict_signal_value_p2";
    const side = ((m[valueKeyP1] ?? -Infinity) as number) >= ((m[valueKeyP2] ?? -Infinity) as number) ? "P1" : "P2";
    const valuePct = side === "P1" ? (m[valueKeyP1] as number | undefined) : (m[valueKeyP2] as number | undefined);
    const pinnacleOdds = side === "P1" ? m.pinnacle_odds1 : m.pinnacle_odds2;
    const pin1 = m.pinnacle_odds1 ?? 0;
    const pin2 = m.pinnacle_odds2 ?? 0;
    const { units, gbp } =
      pin1 > 0 && pin2 > 0
        ? computeStakeUnits()
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
      league: m.league,
      tournament_speed_signal: m.tournament_speed_signal,
      raw_value_p1: m.value_p1,
      raw_value_p2: m.value_p2,
    };
  }

  const matchSignalsStrict = matches.filter((m) => m.policy_match).map((m) => toSignal(m));

  function toSpreadSignal(
    m: (typeof matches)[0],
    side: "P1+" | "P2-",
    edgePct: number,
    pinOdds: number,
    spreadLine: number,
    extra?: {
      shadow_reason?: string;
      handicap_point_prob_source?: FairOddsRow["handicap_point_prob_source"];
    }
  ) {
    return {
      id: m.id * 1000 + (side === "P1+" ? 1 : 2),
      player1_name: m.player1_name,
      player2_name: m.player2_name,
      side,
      value_pct: edgePct,
      pinnacle_odds: pinOdds,
      stake_units: 2,
      stake_gbp: STRICT_UNIT_GBP * 2,
      bet_type: "spread" as const,
      spread_line: spreadLine,
      tournament: m.tournament,
      surface: m.surface,
      league: m.league,
      ...(extra?.handicap_point_prob_source
        ? { handicap_point_prob_source: extra.handicap_point_prob_source }
        : {}),
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
      spreadSignalsStrict.push(
        toSpreadSignal(m, "P1+", he1, so1, sl, {
          handicap_point_prob_source: m.handicap_point_prob_source,
        })
      );
    }
    if (he2 >= HANDICAP_MIN_EDGE_PCT) {
      spreadSignalsStrict.push(
        toSpreadSignal(m, "P2-", he2, so2, sl, {
          handicap_point_prob_source: m.handicap_point_prob_source,
        })
      );
    }
  }

  const signals_strict = [...matchSignalsStrict, ...spreadSignalsStrict];
  const matchSignalsVolumeProfile = matches
    .filter((m) => m.shadow_profile_match)
    .map((m) =>
      toSignal(m, {
        valueKeyP1: "shadow_profile_value_p1",
        valueKeyP2: "shadow_profile_value_p2",
      })
    );
  const matchSignalsVolumeOverlap = matches
    .filter((m) => m.shadow_overlap_match)
    .map((m) =>
      toSignal(m, {
        valueKeyP1: "shadow_profile_value_p1",
        valueKeyP2: "shadow_profile_value_p2",
      })
    );
  const matchSignalsVolume = matches
    .filter((m) => m.shadow_match)
    .map((m) =>
      toSignal(m, {
        valueKeyP1: "shadow_value_p1",
        valueKeyP2: "shadow_value_p2",
      })
    );
  const matchSignalsVolumeAdditional = [...matchSignalsVolume];
  const spreadSignalsVolumeProfile: Array<ReturnType<typeof toSpreadSignal>> = [];
  const spreadSignalsVolumeOverlap: Array<ReturnType<typeof toSpreadSignal>> = [];
  const spreadSignalsVolume: Array<ReturnType<typeof toSpreadSignal>> = [];
  for (const m of matches) {
    const spreadProfileOk =
      m.shadow_profile_match &&
      !m.recent_injured_any &&
      m.spread_line != null &&
      m.spread_odds1 != null &&
      m.spread_odds2 != null &&
      m.handicap_edge_p1 != null &&
      m.handicap_edge_p2 != null;
    if (spreadProfileOk) {
      const sl = m.spread_line;
      const so1 = m.spread_odds1;
      const so2 = m.spread_odds2;
      const he1 = m.handicap_edge_p1;
      const he2 = m.handicap_edge_p2;
      if (sl != null && so1 != null && so2 != null && he1 != null && he2 != null) {
        if (he1 >= HANDICAP_MIN_EDGE_PCT) {
          spreadSignalsVolumeProfile.push(
            toSpreadSignal(m, "P1+", he1, so1, sl, {
              handicap_point_prob_source: m.handicap_point_prob_source,
            })
          );
          if (m.shadow_overlap_match)
            spreadSignalsVolumeOverlap.push(
              toSpreadSignal(m, "P1+", he1, so1, sl, {
                handicap_point_prob_source: m.handicap_point_prob_source,
              })
            );
        }
        if (he2 >= HANDICAP_MIN_EDGE_PCT) {
          spreadSignalsVolumeProfile.push(
            toSpreadSignal(m, "P2-", he2, so2, sl, {
              handicap_point_prob_source: m.handicap_point_prob_source,
            })
          );
          if (m.shadow_overlap_match)
            spreadSignalsVolumeOverlap.push(
              toSpreadSignal(m, "P2-", he2, so2, sl, {
                handicap_point_prob_source: m.handicap_point_prob_source,
              })
            );
        }
      }
    }

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
      spreadSignalsVolume.push(
        toSpreadSignal(m, "P1+", he1, so1, sl, {
          handicap_point_prob_source: m.handicap_point_prob_source,
        })
      );
    }
    if (he2 >= HANDICAP_MIN_EDGE_PCT) {
      spreadSignalsVolume.push(
        toSpreadSignal(m, "P2-", he2, so2, sl, {
          handicap_point_prob_source: m.handicap_point_prob_source,
        })
      );
    }
  }
  const signals_volume = [...matchSignalsVolume, ...spreadSignalsVolume];
  const signals_volume_profile = [...matchSignalsVolumeProfile, ...spreadSignalsVolumeProfile];
  const signals_volume_overlap = [...matchSignalsVolumeOverlap, ...spreadSignalsVolumeOverlap];
  const signals_volume_additional = [...matchSignalsVolumeAdditional, ...spreadSignalsVolume];
  const signals_clay_2026 = effectiveClay2026SignalsCsv;
  const spreadSignalsSpreadShadow = spreadShadowSignalsCsv;

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
        ? `Spread: ${matchesWithSpread.length} matches have data, ${spreadStrictEligible.length} pass strict policy, ${spreadWithEdge20.length} have edge >=20%.`
        : undefined;

  const pinnacle_only = pinnacleOnly.map((p) => ({
    player1_name: p.player1_name,
    player2_name: p.player2_name,
    odds1: p.odds1,
    odds2: p.odds2,
    ou_line: p.ou_line,
    ou_over: p.ou_over,
    ou_under: p.ou_under,
  }));

  return NextResponse.json({
    matches,
    matches_with_row_signals: matchesWithRowSignals,
    pinnacle_count: pinnacleRows.length,
    pinnacle_matched_count: pinnacleMap.size,
    pinnacle_only,
    policy,
    shadow_profile: SHADOW_POLICY_MODE,
    signals_strict,
    signals_volume_profile,
    signals_volume_overlap,
    signals_volume_additional,
    signals_volume,
    signals_clay_2026,
    signals_spread_shadow: spreadSignalsSpreadShadow,
    signal_attachment,
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
