import { cache } from "react";
import { notFound } from "next/navigation";
import {
  readTeamShotsLiveFile as readFile,
  readTeamShotsLiveJson as readJson,
  readTeamShotsLiveMtime as readKnownFileMtime,
  readTeamShotsLiveSnapshotGeneratedAt,
  inspectTeamShotsLiveSource,
} from "@/lib/team-shots-live-files";
import {
  MODEL_MONITOR_ENABLED,
  LeagueLabel,
  MatchLabel,
  MonitorNav,
  HeroCard,
  SectionCard,
  StatCard,
  StatusPill,
  TeamLabel,
  EmptyState,
} from "../shared";
import FootballVnextShadowPanel, { type FootballVnextGate } from "@/components/model-monitor/FootballVnextShadowPanel";

export const dynamic = "force-dynamic";



type CsvRow = Record<string, string>;
type FootballCountsGatePayload = { team_shots_v4?: FootballVnextGate; corners_v3?: FootballVnextGate };
type CountMarketCoverageItem = {
  status?: string;
  events?: number;
  paired_price_events?: number;
  pairing_unknown_events?: number;
  raw_market_names?: string[];
};
type CountMarketCoveragePayload = {
  generated_at?: string;
  categories?: Record<string, CountMarketCoverageItem>;
};
type TeamFoulsM1Payload = {
  generated_at?: string;
  usable_rows?: number;
  status?: string;
  market_gate?: string;
};
type TeamFoulsFoldPayload = {
  generated_at?: string;
  sample_matches?: number;
  decision?: {
    status?: string;
    count_gate_pass?: boolean;
    signals_authorized?: boolean;
    gates?: Record<string, boolean>;
    mae_checks?: Array<{ season?: string; improvement_pct?: number }>;
    hierarchical_nb_wins?: number;
    hierarchical_nb_cells?: number;
    fold_checks?: Array<{
      season?: string;
      mae_improvement_pct?: number;
      opening_strength_pass?: boolean;
      f1_distribution_pass?: boolean;
      reliability_pass?: boolean;
    }>;
  };
};
type TeamFoulsAgreementPayload = {
  generated_at?: string;
  status?: string;
  settlement_source_authorized?: boolean;
  api_football?: {
    comparable_team_values?: number;
    within_one_pct?: number;
  };
  fotmob?: {
    comparable_team_values?: number;
    within_one_pct?: number;
  };
};
type FootballFoulMarketProbePayload = {
  generated_at?: string;
  status?: string;
  events_probed?: number;
  decision?: string;
  labels?: {
    paired_foul_lines?: Array<{
      event_id?: string;
      bookmaker?: string;
      market_name?: string;
      line?: number;
    }>;
  };
};
type GoalkeeperSavesShadowReport = {
  generated_at?: string;
  status?: string;
  count_model?: string;
  selection_rule?: string;
  current?: {
    priced_lines?: number;
    eligible_lines?: number;
    blocked_lines?: number;
    signals_added?: number;
  };
  evidence?: {
    signals?: number;
    pending?: number;
    settled?: number;
    pnl_units?: number;
    roi?: number | null;
    clv_matched?: number;
    true_close_coverage?: number | null;
    clv?: number | null;
  };
  promotion?: {
    status?: string;
    settled_required?: number;
    true_close_coverage_required?: number;
    mean_true_close_clv_required?: number;
  };
};
type GoalkeeperSavesCaptureStatus = {
  generated_at?: string;
  status?: string;
  requests_used?: number;
  request_budget?: number;
  events_selected?: number;
  events_with_lines?: number;
  rows_observed?: number;
  capture_mode?: string;
};
type TeamShotsLiveLine = {
  bookmaker: string;
  line: number;
  lineLabel: string;
  overOdds?: number;
  underOdds?: number;
  overCapturedAt?: string;
  underCapturedAt?: string;
};

type CalibrationPayload = {
  lines?: Record<string, { a: number; b: number }>;
};

type TeamLineMetrics = {
  fairOver: number;
  fairUnder: number;
  overEdge: number | null;
  underEdge: number | null;
};

type TeamPropsStatus = {

  state?: string;

  updated_at?: string;

  last_started_at?: string;

  last_finished_at?: string | null;

  last_successful_finished_at?: string;

  current_step?: string;

  message?: string;

  warnings?: string[];

  critical_failures?: string[];

  last_exit_code?: number;

};

type TeamShotsScrapeStatus = {
  run_at?: string;
  leagues?: string[];
  events_found?: number;
  rows_scraped?: number;
  provider_errors?: string[];
  sources_used?: string[];
  run_url?: string;
  success?: boolean;
  error?: string;
};

type ResearchLane = {
  market?: string;
  model?: string;
  state?: string;
  allowed_leagues?: string[];
  canonical_only_allowed?: boolean;
  clv_monitor?: string;
  last_segment_gate_run?: string;
  next_action?: string;
  notes?: string;
};

type ResearchLaneState = {
  generated_at?: string;
  lanes?: ResearchLane[];
};

type AllowedLeagueConfig = {
  allowed_leagues?: string[];
  blocked_leagues?: string[];
  canonical_only_allowed?: boolean;
  generated_at?: string;
  model?: string;
  rules?: string[];
};

type TeamShotsV3PromotionCheck = {
  generated_at?: string;
  ready_leagues?: string[];
  blocked_leagues?: string[];
  research_lane_ready_all_leagues?: boolean;
  canonical_only?: {
    hard_block?: boolean;
    n?: number;
    reason?: string;
  };
  league_results?: Array<{
    league?: string;
    common?: {
      n?: number;
      current_mae?: number;
      canonical_mae?: number;
      improvement_pct?: number;
    };
    last_90_common?: {
      n?: number;
      current_mae?: number;
      canonical_mae?: number;
      improvement_pct?: number;
      count_ok?: boolean;
      brier_ok?: boolean;
      log_loss_ok?: boolean;
    };
  }>;
};

type PredictionsSummary = {
  prediction_count?: number;
  recent_predictions?: CsvRow[];
};

const CURRENT_POLICY = "venue-consensus-v2";
const LEGACY_POLICY = "legacy";

function policyVersion(row: CsvRow): string {
  const raw = (row.policy_version ?? "").trim();
  return raw || LEGACY_POLICY;
}

function policyLabel(version: string): string {
  return version === CURRENT_POLICY ? "Current policy" : "Legacy";
}



function parseCsv(text: string): CsvRow[] {

  const lines = text.split("\n").filter((l) => l.trim());

  if (lines.length < 2) return [];

  const headers = lines[0].split(",").map((h) => h.trim());

  return lines.slice(1).map((line) => {

    const values = line.split(",").map((v) => v.trim());

    const row: CsvRow = {};

    headers.forEach((h, i) => {

      row[h] = values[i] ?? "";

    });

    return row;

  });

}



const parseCsvCached = cache((text: string) => parseCsv(text));

function pf(val: string | undefined, fallback = 0): number {

  const n = parseFloat(val ?? "");

  return isNaN(n) ? fallback : n;

}

function maybeFloat(val: string | undefined): number | null {
  const n = parseFloat(val ?? "");
  return Number.isFinite(n) ? n : null;
}

function fairOddsFromProbability(probability: number | null): number | null {
  if (probability === null || !Number.isFinite(probability) || probability <= 0) return null;
  return 1 / probability;
}

function evEdgePct(probability: number | null, odds: number | null): number | null {
  if (
    probability === null ||
    !Number.isFinite(probability) ||
    probability <= 0 ||
    odds === null ||
    !Number.isFinite(odds) ||
    odds <= 0
  ) {
    return null;
  }
  return (probability * odds - 1) * 100;
}

function formatMaybeFixed(val: string | undefined, digits = 2, placeholder = "--"): string {
  const n = maybeFloat(val);
  return n === null ? placeholder : n.toFixed(digits);
}



const LEAGUE_ORDER = [

  "epl",

  "la-liga",

  "serie-a",

  "bundesliga",

] as const;

const TEAM_ALIASES: Record<string, string> = {
  liverpool: "liverpool",
  "liverpool fc": "liverpool",
  fulham: "fulham",
  "fulham fc": "fulham",
  "real sociedad san sebastian": "sociedad",
  "real sociedad de futbol": "sociedad",
  "real sociedad": "sociedad",
  sociedad: "sociedad",
  "deportivo alaves": "alaves",
  "deportivo alaves sad": "alaves",
  "alav s": "alaves",
  alaves: "alaves",
  "elche cf": "elche",
  elche: "elche",
  "valencia cf": "valencia",
  valencia: "valencia",
  "fc barcelona": "barcelona",
  barcelona: "barcelona",
  espanyol: "espanyol",
  "espanyol barcelona": "espanyol",
  "atletico madrid": "atletico madrid",
  "atletico de madrid": "atletico madrid",
  "atletico de madrid sad": "atletico madrid",
  "atletico madrid sad": "atletico madrid",
  "manchester united": "manchester united",
  "manchester united fc": "manchester united",
  "man utd": "manchester united",
  "aston villa fc": "aston villa",
  "leeds united fc": "leeds united",
  "ca osasuna": "osasuna",
  osasuna: "osasuna",
  "real betis": "real betis",
  "fc st pauli": "st pauli",
  "1 fc heidenheim": "heidenheim",
  "1 fc koln": "fc koln",
  "1 fc cologne": "fc koln",
  "real betis balompie": "real betis",
  "real betis seville": "real betis",
  "rc celta de vigo": "celta vigo",
  "celta de vigo": "celta vigo",
  "real oviedo": "oviedo",
  oviedo: "oviedo",
  "athletic club bilbao": "athletic club",
  "athletic bilbao": "athletic club",
  "athletic club": "athletic club",
  "villarreal cf": "villarreal",
  villarreal: "villarreal",
  "afc bournemouth": "bournemouth",
  "brighton and hove albion": "brighton",
  "brighton hove albion": "brighton",
  "cagliari calcio": "cagliari",
  "us cremonese": "cremonese",
  "udinese calcio": "udinese",
  "juventus turin": "juventus",
  "genoa cfc": "genoa",
  "sassuolo calcio": "sassuolo",
  "parma calcio": "parma",
  "ssc napoli": "napoli",
  "como 1907": "como",
  "inter milano": "inter milan",
  "us lecce": "lecce",
  "lazio rome": "lazio",
  "acf fiorentina": "fiorentina",
  "tottenham hotspur": "tottenham",
  "wolverhampton wanderers": "wolves",
  "west ham united": "west ham",
  "newcastle united": "newcastle",
  "nottingham forest": "nottingham forest",
  "sunderland afc": "sunderland",
};

function leagueTitle(id: string): string {

  const map: Record<string, string> = {

    epl: "Premier League",

    "la-liga": "La Liga",

    "serie-a": "Serie A",

    bundesliga: "Bundesliga",

    "ligue-1": "Ligue 1",

  };

  return map[id] ?? id;

}

function competitionToLeagueId(value: string | undefined): string | null {
  const raw = (value ?? "").trim().toLowerCase();
  if (!raw) return null;
  if (raw === "premier league" || raw === "epl") return "epl";
  if (raw === "serie a" || raw === "serie-a") return "serie-a";
  if (raw === "bundesliga") return "bundesliga";
  if (raw === "la liga" || raw === "laliga" || raw === "la-liga") return "la-liga";
  if (raw === "ligue 1" || raw === "ligue-1") return "ligue-1";
  return null;
}



function formatKickoffUtc(iso: string | undefined): string {
  if (!iso?.trim()) return "-";
  const d = new Date(iso);
  if (Number.isNaN(d.getTime())) return iso;
  return `${new Intl.DateTimeFormat("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
    timeZone: "UTC",
  }).format(d)} UTC`;
}



function sortLeagueKeys(keys: string[]): string[] {

  return [...keys].sort((a, b) => {

    const ia = LEAGUE_ORDER.indexOf(a as (typeof LEAGUE_ORDER)[number]);

    const ib = LEAGUE_ORDER.indexOf(b as (typeof LEAGUE_ORDER)[number]);

    if (ia === -1 && ib === -1) return a.localeCompare(b);

    if (ia === -1) return 1;

    if (ib === -1) return -1;

    return ia - ib;

  });

}



function groupUpcomingByLeague(rows: CsvRow[]): Map<string, CsvRow[]> {

  const map = new Map<string, CsvRow[]>();

  for (const row of rows) {

    const lg = (row.league ?? "").trim() || "other";
    if (lg === "ligue-1") continue;

    if (!map.has(lg)) map.set(lg, []);

    map.get(lg)!.push(row);

  }

  for (const list of map.values()) {

    list.sort((a, b) =>

      (a.kickoff_iso ?? "").localeCompare(b.kickoff_iso ?? ""),

    );

  }

  return map;

}

function comparisonKey(
  homeTeam: string | undefined,
  awayTeam: string | undefined,
  team: string | undefined,
  line: string | undefined,
): string {
  return [
    (homeTeam ?? "").trim().toLowerCase(),
    (awayTeam ?? "").trim().toLowerCase(),
    (team ?? "").trim().toLowerCase(),
    (line ?? "").trim(),
  ].join("|");
}

function normalizeTeamName(value: string | undefined): string {
  const cleaned = (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .filter((token) => !["fc", "afc", "sc", "cf", "ac", "club", "ca", "rc"].includes(token))
    .join(" ");
  return TEAM_ALIASES[cleaned] ?? cleaned;
}

function matchKey(
  date: string | undefined,
  homeTeam: string | undefined,
  awayTeam: string | undefined,
): string {
  return [
    (date ?? "").trim(),
    normalizeTeamName(homeTeam),
    normalizeTeamName(awayTeam),
  ].join("|");
}

function comparisonSignalKey(
  date: string | undefined,
  homeTeam: string | undefined,
  awayTeam: string | undefined,
  team: string | undefined,
  bookmaker: string | undefined,
  line: string | undefined,
  side: string | undefined,
): string {
  return [
    matchKey(date, homeTeam, awayTeam),
    normalizeTeamName(team),
    (bookmaker ?? "").trim().toLowerCase(),
    (line ?? "").trim(),
    (side ?? "").trim().toLowerCase(),
  ].join("|");
}

function sigmoid(value: number): number {
  if (value >= 0) return 1 / (1 + Math.exp(-value));
  const expValue = Math.exp(value);
  return expValue / (1 + expValue);
}

function poissonPmf(k: number, lam: number): number {
  if (lam <= 0) return k === 0 ? 1 : 0;
  return Math.exp(-lam) * (lam ** k) / factorial(k);
}

function factorial(n: number): number {
  let out = 1;
  for (let i = 2; i <= n; i += 1) out *= i;
  return out;
}

function poissonCdf(k: number, lam: number): number {
  let total = 0;
  for (let i = 0; i <= k; i += 1) total += poissonPmf(i, lam);
  return total;
}

function poissonProbOver(line: number, lam: number): number {
  return 1 - poissonCdf(Math.trunc(line), lam);
}

function formatSignedPercent(edge: number | null): string {
  if (edge === null || Number.isNaN(edge)) return "-";
  return `${edge >= 0 ? "+" : ""}${edge.toFixed(1)}%`;
}

function calibratedOverProbability(
  row: CsvRow,
  side: "home" | "away",
  line: number,
  calibration: CalibrationPayload | null,
): number | null {
  const key = `${side}_p_over_${line.toFixed(1)}`;
  let raw = pf(row[key], Number.NaN);
  if (Number.isNaN(raw) || raw <= 0 || raw >= 1) {
    const lam =
      pf(row[`${side}_lambda_venue`], Number.NaN) ||
      pf(row[`${side}_lambda`], Number.NaN);
    if (Number.isNaN(lam) || lam <= 0) return null;
    raw = poissonProbOver(line, lam);
  }
  const params = calibration?.lines?.[line.toFixed(1)];
  if (!params) return raw;
  const logit = Math.log(raw / (1 - raw));
  return sigmoid(params.a * logit + params.b);
}

function computeLineMetrics(
  row: CsvRow,
  side: "home" | "away",
  line: TeamShotsLiveLine,
  calibration: CalibrationPayload | null,
): TeamLineMetrics | null {
  const pOver = calibratedOverProbability(row, side, line.line, calibration);
  if (pOver === null) return null;
  const pUnder = 1 - pOver;
  const fairOver = pOver > 0 ? 1 / pOver : 0;
  const fairUnder = pUnder > 0 ? 1 / pUnder : 0;
  return {
    fairOver,
    fairUnder,
    overEdge: line.overOdds ? (pOver * line.overOdds - 1) * 100 : null,
    underEdge: line.underOdds ? (pUnder * line.underOdds - 1) * 100 : null,
  };
}

function qualifiesForShadow(
  sideEdge: number | null,
  sideOdds?: number,
): boolean {
  if (sideEdge === null || sideOdds === undefined) return false;
  return sideEdge >= 5 && sideOdds >= 1.5 && sideOdds <= 5.0;
}

function shadowFixtureKey(row: CsvRow): string {
  return [
    (row.date ?? "").slice(0, 10),
    (row.league ?? "").trim().toLowerCase(),
    (row.home_team ?? "").trim().toLowerCase(),
    (row.away_team ?? "").trim().toLowerCase(),
  ].join("|");
}

function dedupeBestShadowFixtureRows(rows: CsvRow[]): CsvRow[] {
  const bestByFixture = new Map<string, CsvRow>();

  for (const row of rows) {
    const key = shadowFixtureKey(row);
    const existing = bestByFixture.get(key);
    const edge = pf(row.edge, Number.NaN);
    const odds = pf(row.book_odds, Number.NaN);

    if (!existing) {
      bestByFixture.set(key, row);
      continue;
    }

    const existingEdge = pf(existing.edge, Number.NaN);
    const existingOdds = pf(existing.book_odds, Number.NaN);
    if (
      edge > existingEdge ||
      (edge === existingEdge && odds > existingOdds)
    ) {
      bestByFixture.set(key, row);
    }
  }

  return rows.filter((row) => bestByFixture.get(shadowFixtureKey(row)) === row);
}

function shadowStakeUnits(edgeDecimal: number): string {
  if (edgeDecimal >= 0.16) return "2.0u";
  if (edgeDecimal >= 0.12) return "1.5u";
  if (edgeDecimal >= 0.08) return "1.0u";
  return "0.5u";
}

function bestLineSummary(
  lines: TeamShotsLiveLine[],
  row: CsvRow,
  side: "home" | "away",
  calibration: CalibrationPayload | null,
  shadowOnly = false,
): string {
  let best:
    | { bookmaker: string; lineLabel: string; side: "O" | "U"; odds: number; edge: number }
    | undefined;

  for (const line of lines) {
    const metrics = computeLineMetrics(row, side, line, calibration);
    if (!metrics) continue;
    if (line.overOdds) {
      const edge = metrics.overEdge ?? Number.NaN;
      if (shadowOnly && !qualifiesForShadow(metrics.overEdge, line.overOdds)) continue;
      if (!best || edge > best.edge) {
        best = {
          bookmaker: line.bookmaker,
          lineLabel: line.lineLabel,
          side: "O",
          odds: line.overOdds,
          edge,
        };
      }
    }
    if (line.underOdds) {
      const edge = metrics.underEdge ?? Number.NaN;
      if (shadowOnly && !qualifiesForShadow(metrics.underEdge, line.underOdds)) continue;
      if (!best || edge > best.edge) {
        best = {
          bookmaker: line.bookmaker,
          lineLabel: line.lineLabel,
          side: "U",
          odds: line.underOdds,
          edge,
        };
      }
    }
  }

  if (!best) return shadowOnly ? "No shadow-qualified line" : "No live team-shots line";
  return `${best.bookmaker} ${best.lineLabel} ${best.side} ${best.odds.toFixed(2)} (${formatSignedPercent(best.edge)})`;
}

function bestSummarySide(
  entry:
    | {
        metrics: TeamLineMetrics;
      }
    | undefined,
): "O" | "U" | "-" {
  if (!entry) return "-";
  return entry.metrics.overEdge !== null && entry.metrics.overEdge === Math.max(entry.metrics.overEdge ?? -999, entry.metrics.underEdge ?? -999)
    ? "O"
    : "U";
}

type ConsensusState = "aligned" | "divergent" | "conflict";

function consensusStateForRow(row: CsvRow, side: "home" | "away"): ConsensusState {
  const raw = (row[`${side}_consensus`] ?? "").trim().toLowerCase();
  if (raw === "divergent" || raw === "conflict") return raw;

  const venue = pf(row[`${side}_lambda_venue`], Number.NaN);
  const recent = pf(row[`${side}_lambda_recent`], Number.NaN);
  if (Number.isNaN(venue) || !(venue > 0) || Number.isNaN(recent)) return "aligned";
  const divergence = Math.abs(recent - venue) / venue;
  if (divergence <= 0.15) return "aligned";
  if (divergence <= 0.3) return "divergent";
  return "conflict";
}

function divergenceForRow(row: CsvRow, side: "home" | "away"): number {
  const raw = maybeFloat(row[`${side}_divergence`]);
  if (raw !== null) return raw;
  const venue = pf(row[`${side}_lambda_venue`], Number.NaN);
  const recent = pf(row[`${side}_lambda_recent`], Number.NaN);
  if (Number.isNaN(venue) || !(venue > 0) || Number.isNaN(recent)) return 0;
  return Math.abs(recent - venue) / venue;
}

function pctDelta(from: number | null, to: number | null): number | null {
  if (from === null || to === null || Math.abs(from) < 1e-6) return null;
  return ((to - from) / from) * 100;
}

function formatPctDelta(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "--";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function finiteNumber(value: unknown): number | null {
  return typeof value === "number" && Number.isFinite(value) ? value : null;
}

function formatDiagnosticMetric(value: unknown, digits = 4): string {
  const parsed = finiteNumber(value);
  return parsed === null ? "--" : parsed.toFixed(digits);
}

function formatModelName(model?: string | null): string {
  if (!model) return "-";
  if (model === "canonical_form_v3_ema20_nb") return "V3 EMA20";
  if (model === "canonical_form_v2_pooled_opp_nb") return "V2 pooled";
  if (model === "canonical_form_v1_market_nb") return "V1 market";
  return model.replace(/^canonical_form_/, "").replace(/_/g, " ");
}

function formatLeagueList(leagues?: string[] | null): string {
  const items = (leagues ?? []).filter(Boolean);
  if (items.length === 0) return "-";
  return items.map((league) => leagueTitle(league)).join(", ");
}

function parseClvMonitorSummary(report?: string | null): {
  picks: string;
  settled: string;
  avgClv: string;
} {
  const text = report ?? "";
  const pickMatch = text.match(/- Picks:\s*([0-9]+)/i);
  const settledMatch = text.match(/- Settled:\s*([0-9]+)/i);
  const avgMatch = text.match(/- Average published-to-close CLV:\s*([^\n]+)/i);
  return {
    picks: pickMatch?.[1] ?? "-",
    settled: settledMatch?.[1] ?? "-",
    avgClv: avgMatch?.[1]?.trim() ?? "-",
  };
}

type ResearchBetSummary = {
  total: number;
  settled: number;
  pending: number;
  won: number;
  lost: number;
  pushed: number;
  pnl: number;
  roi: number | null;
  winRate: number | null;
};

function researchRowIsGuarded(row: CsvRow): boolean {
  const blockedReason = (row.blocked_reason ?? "").trim();
  const guarded = (row.confidence_guard_applied ?? "").trim().toLowerCase() === "true";
  return Boolean(blockedReason || guarded);
}

function researchRowIsActive(row: CsvRow): boolean {
  return !researchRowIsGuarded(row);
}

function researchResult(row: CsvRow): string {
  return (row.result ?? "").trim().toLowerCase();
}

function isSettledResearchRow(row: CsvRow): boolean {
  return ["won", "lost", "push"].includes(researchResult(row));
}

function researchBetSummary(rows: CsvRow[]): ResearchBetSummary {
  const activeRows = rows.filter(researchRowIsActive);
  const settledRows = activeRows.filter(isSettledResearchRow);
  const won = settledRows.filter((row) => researchResult(row) === "won").length;
  const lost = settledRows.filter((row) => researchResult(row) === "lost").length;
  const pushed = settledRows.filter((row) => researchResult(row) === "push").length;
  const pnl = settledRows.reduce((sum, row) => sum + pf(row.pnl_units, 0), 0);
  const graded = won + lost;

  return {
    total: activeRows.length,
    settled: settledRows.length,
    pending: activeRows.filter((row) => {
      const result = researchResult(row);
      return !result || result === "pending";
    }).length,
    won,
    lost,
    pushed,
    pnl,
    roi: settledRows.length > 0 ? (pnl / settledRows.length) * 100 : null,
    winRate: graded > 0 ? (won / graded) * 100 : null,
  };
}

function researchAvgPublishedClvPct(rows: CsvRow[]): { avg: number | null; n: number } {
  const settledRows = rows.filter(researchRowIsActive).filter(isSettledResearchRow);
  const values = settledRows
    .map((row) => maybeFloat(row.published_to_close_clv))
    .filter((value): value is number => value !== null);
  if (values.length === 0) return { avg: null, n: 0 };
  return { avg: (values.reduce((sum, value) => sum + value, 0) / values.length) * 100, n: values.length };
}

function formatUnits(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}u`;
}

function researchRowSortKey(row: CsvRow): string {
  return row.settled_at ?? row.kickoff_utc ?? row.published_at_utc ?? row.match_date ?? "";
}

function findResearchLane(state: ResearchLaneState | null, market: string, model: string): ResearchLane | null {
  return state?.lanes?.find((lane) => lane.market === market && lane.model === model) ?? null;
}

function consensusTone(consensus: ConsensusState): string {
  if (consensus === "conflict") return "bg-rose-500/10 text-rose-300 border-rose-500/20";
  if (consensus === "divergent") return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
}

function signalBadge(
  edge: number | null,
  side: "over" | "under",
  consensus: ConsensusState,
): { label: string; tone: string } | null {
  if (edge === null || Number.isNaN(edge) || edge < 5) return null;
  if (edge >= 12) {
    if (consensus === "conflict") {
      return { label: "FLAGGED", tone: "bg-rose-500/10 text-rose-300 border-rose-500/20" };
    }
    if (consensus === "divergent") {
      return { label: "SIGNAL ?", tone: "bg-amber-500/10 text-amber-300 border-amber-500/20" };
    }
    if (side === "under") {
      return { label: "UNDER ?", tone: "bg-cyan-500/10 text-cyan-300 border-cyan-500/20" };
    }
    return { label: "SIGNAL", tone: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" };
  }
  return { label: "WATCH", tone: "bg-slate-700/30 text-slate-300 border-slate-600/30" };
}

function effectiveStake(edgeDecimal: number, consensus: ConsensusState): number {
  const stake = shadowStakeUnits(edgeDecimal);
  const numericStake = pf(stake.replace("u", ""), 0);
  if (consensus !== "conflict") return numericStake;
  if (edgeDecimal < 0.08) return 0;
  if (numericStake >= 2) return 1.5;
  if (numericStake >= 1.5) return 1.0;
  if (numericStake >= 1.0) return 0.5;
  return 0.5;
}

function LambdaTrustPanel({
  leagueKey,
  row,
}: {
  leagueKey: string;
  row: CsvRow;
}) {
  const teamConfigs: Array<{ side: "home" | "away"; team: string }> = [
    { side: "home", team: row.home_team ?? "" },
    { side: "away", team: row.away_team ?? "" },
  ];

  return (
    <div className="mb-3 rounded-2xl border border-slate-800 bg-slate-950/40 p-4">
      <div className="mb-3 flex items-center justify-between gap-2">
        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-slate-500">
          Lambda Trust Panel
        </div>
        <div className="text-[11px] text-slate-500">
          venue fair drives scanner | recent is confidence only
        </div>
      </div>
      <div className="grid gap-3 lg:grid-cols-2">
        {teamConfigs.map(({ side, team }) => {
          const base = maybeFloat(row[`${side}_lambda`]);
          const venue = maybeFloat(row[`${side}_lambda_venue`]);
          const recent = maybeFloat(row[`${side}_lambda_recent`]);
          const consensus = consensusStateForRow(row, side);
          const divergence = divergenceForRow(row, side);
          const baseToVenue = pctDelta(base, venue);
          const venueToRecent = pctDelta(venue, recent);
          const hotCold =
            venueToRecent !== null && venueToRecent > 15
              ? { label: "HOT", tone: "text-emerald-300" }
              : venueToRecent !== null && venueToRecent < -15
                ? { label: "COLD", tone: "text-rose-300" }
                : null;

          return (
            <div key={`${side}-${team}`} className="rounded-xl border border-slate-800/70 bg-slate-900/50 p-3">
              <div className="mb-2 flex items-center justify-between gap-2">
                <TeamLabel
                  league={leagueKey}
                  team={team}
                  iconSize={18}
                  teamClassName="text-sm font-medium text-slate-100"
                />
                <StatusPill label={consensus.toUpperCase()} tone={consensusTone(consensus)} />
              </div>
              <div className="grid gap-2 sm:grid-cols-3">
                <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Base</div>
                  <div className="mt-1 font-mono text-sm text-slate-100">
                    {base !== null ? base.toFixed(2) : "--"}
                  </div>
                </div>
                <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Venue</div>
                  <div className="mt-1 font-mono text-sm text-slate-100">
                    {venue !== null ? venue.toFixed(2) : "--"}
                  </div>
                  <div className={`mt-1 text-[11px] ${baseToVenue !== null && Math.abs(baseToVenue) > 10 ? "text-amber-300" : "text-slate-500"}`}>
                    {formatPctDelta(baseToVenue)} vs base
                  </div>
                </div>
                <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-3 py-2">
                  <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Recent</div>
                  <div className="mt-1 font-mono text-sm text-slate-100">
                    {recent !== null ? recent.toFixed(2) : "--"}
                  </div>
                  <div className={`mt-1 text-[11px] ${hotCold ? hotCold.tone : "text-slate-500"}`}>
                    {formatPctDelta(venueToRecent)} vs venue{hotCold ? ` | ${hotCold.label}` : ""}
                  </div>
                </div>
              </div>
              <div className="mt-2 flex flex-wrap items-center gap-2 text-[11px] text-slate-400">
                <span>divergence {(divergence * 100).toFixed(1)}%</span>
                {recent !== null && venue !== null && Math.abs(recent - venue) < 0.01 ? (
                  <span className="text-slate-500">recent fallback / limited signal</span>
                ) : null}
              </div>
            </div>
          );
        })}
      </div>
    </div>
  );
}



function formatDateTime(value?: string | null): string {
  if (!value) return "missing";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-GB", {
    day: "2-digit",
    month: "2-digit",
    year: "numeric",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  });
}



function formatRelativeAgeShort(value?: string | null, referenceNowMs?: number): string {

  if (!value) return "n/a";

  const stamp = Date.parse(value);

  if (Number.isNaN(stamp)) return "n/a";

  const anchorMs =
    typeof referenceNowMs === "number" && Number.isFinite(referenceNowMs)
      ? referenceNowMs
      : stamp;

  const diffMs = anchorMs - stamp;

  if (diffMs < 0) return "just now";

  const diffMinutes = Math.round(diffMs / 60000);

  if (diffMinutes < 60) return `${diffMinutes}m ago`;

  const diffHours = Math.round(diffMinutes / 60);

  if (diffHours < 24) return `${diffHours}h ago`;

  return ">1d";

}

function formatSourceReason(
  reason: "hosted_newer" | "local_newer" | "hosted_only" | "local_only" | "no_data",
): string {
  switch (reason) {
    case "hosted_newer":
      return "hosted newer";
    case "local_newer":
      return "local newer";
    case "hosted_only":
      return "hosted only";
    case "local_only":
      return "local only";
    default:
      return "no data";
  }
}

function sourceTone(source: "hosted" | "local" | "missing"): "default" | "green" | "red" | "amber" {
  if (source === "hosted") return "green";
  if (source === "local") return "amber";
  if (source === "missing") return "red";
  return "default";
}

function parseIsoMillis(iso?: string | null): number | null {
  if (!iso) return null;
  const millis = Date.parse(iso);
  return Number.isFinite(millis) ? millis : null;
}

function monitorStaleHours(): number {
  const raw = process.env.MONITOR_STALE_HOURS ?? process.env.TEAM_PROPS_MONITOR_STALE_HOURS;
  const parsed = Number.parseFloat(raw ?? "");
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 18;
}

function currentServerRenderMillis(): number {
  return Date.now();
}

function scrapeTone(
  status: TeamShotsScrapeStatus | null,
  ageMinutes: number | null,
): "default" | "green" | "red" | "amber" {
  if (!status) return "red";
  if (status.success === false) return "red";
  if (ageMinutes === null) return "default";
  if (ageMinutes <= 120) return "green";
  if (ageMinutes <= 360) return "amber";
  return "red";
}



// Tone helper: converts "green"/"red"/"amber" to CSS class strings for StatCard.
function statTone(t?: "default" | "green" | "red" | "amber"): string | undefined {
  if (!t || t === "default") return undefined;
  const map: Record<string, string> = {
    green: "text-emerald-300",
    red: "text-rose-300",
    amber: "text-amber-300",
  };
  return map[t];
}

export default async function TeamShotsMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) {

    notFound();

  }



  const [

    calibrationTxt,
    calibrationParams,

    backtestReportTxt,

    backtestCsv,

    shadowSignalsCsv,

    shadowPerformanceTxt,

    predictionsSummary,

    researchLaneState,

    teamShotsV3AllowedConfig,

    teamShotsV3PromotionCheck,

    teamShotsV3ClvCsv,

    teamShotsV3ClvReport,

    comparisonCsv,

    comparisonTxt,

    oddsArchiveCsv,

    upcomingCsv,

    pipelineStatus,

    predictionsMtime,

    comparisonMtime,

    upcomingMtime,

    snapshotGeneratedAt,

    comparisonSource,

    scrapeStatus,

    teamShotsV4ClvCsv,

    vnextCandidatesCsv,

    vnextGate,

    countMarketCoverage,

    teamFoulsM1,

    teamFoulsF1,

    teamFoulsF2,

    teamFoulsM2,

    footballFoulMarketProbe,

    goalkeeperSavesReport,

    goalkeeperSavesCapture,

    goalkeeperSavesCandidatesCsv,

  ] = await Promise.all([

    readFile("data/team-shots/team-shots-calibration.txt"),
    readJson<CalibrationPayload>("data/team-shots/team-shots-calibration-params.json"),

    readFile("data/team-shots/team-shots-backtest-report.txt"),

    readFile("data/team-shots/team-shots-backtest-results.csv"),

    readFile("data/team-shots/shadow/team-shots-shadow-signals.csv"),

    readFile("data/team-shots/shadow/team-shots-shadow-performance.txt"),

    readJson<PredictionsSummary>("data/team-shots/team-shots-monitor-summary.json"),

    readJson<ResearchLaneState>("data/football-form/research-lane-state.json"),

    readJson<AllowedLeagueConfig>("data/football-form/team-shots-v3-ema20-allowed-leagues.json"),

    readJson<TeamShotsV3PromotionCheck>("data/football-form/team-shots-v3-ema20-promotion-check.json"),

    readFile("data/football-form/team-shots-v3-ema20-clv-monitor.csv"),

    readFile("data/football-form/team-shots-v3-ema20-clv-monitor.md"),

    readFile("data/team-shots/team-shots-comparison.csv"),

    readFile("data/team-shots/team-shots-comparison.txt"),

    readFile("data/team-shots/team-shots-odds-history.csv"),

    readFile("data/team-shots/team-shots-upcoming.csv"),

    readJson<TeamPropsStatus>("data/shortlist/team-props-status.json"),

    readKnownFileMtime("data/team-shots/team-shots-predictions.csv"),

    readKnownFileMtime("data/team-shots/team-shots-comparison.csv"),

    readKnownFileMtime("data/team-shots/team-shots-upcoming.csv"),

    readTeamShotsLiveSnapshotGeneratedAt(),

    inspectTeamShotsLiveSource("data/team-shots/team-shots-comparison.csv"),

    readJson<TeamShotsScrapeStatus>("data/team-shots/team-shots-scrape-last-run.json"),

    readFile("data/football-form/team-shots-v4-shadow-clv.csv"),

    readFile("data/football-form/football-counts-vnext-candidates.csv"),

    readJson<FootballCountsGatePayload>("data/football-form/football-counts-vnext-gate.json"),

    readJson<CountMarketCoveragePayload>("data/football-form/football-count-market-coverage.json"),

    readJson<TeamFoulsM1Payload>("data/football-form/fouls-empirical-baseline.json"),

    readJson<TeamFoulsFoldPayload>("data/football-form/team-fouls-v1-fold-report.json"),

    readJson<TeamFoulsFoldPayload>("data/football-form/team-fouls-f2-fold-report.json"),

    readJson<TeamFoulsAgreementPayload>("data/football-form/team-fouls-definition-agreement.json"),

    readJson<FootballFoulMarketProbePayload>("data/football-form/football-foul-market-probe.json"),

    readJson<GoalkeeperSavesShadowReport>("data/goalkeeper-saves/gk-saves-v1-shadow-report.json"),

    readJson<GoalkeeperSavesCaptureStatus>("data/goalkeeper-saves/gk-saves-capture-status.json"),

    readFile("data/goalkeeper-saves/gk-saves-v1-candidates.csv"),

  ]);



  const shadowSignals = shadowSignalsCsv ? parseCsvCached(shadowSignalsCsv) : [];
  const comparisonRows = (comparisonCsv ? parseCsvCached(comparisonCsv) : []).filter(
    (row) => (row.league ?? "").trim() !== "ligue-1",
  );

  const backtestRows = backtestCsv ? parseCsvCached(backtestCsv) : [];
  const hasBacktestArtifacts = Boolean(backtestCsv?.trim() || backtestReportTxt?.trim());

  const predictionsCsv =
    predictionsSummary ? null : await readFile("data/team-shots/team-shots-predictions.csv");
  const predictions = predictionsCsv ? parseCsvCached(predictionsCsv) : [];
  const predictionCount =
    typeof predictionsSummary?.prediction_count === "number"
      ? predictionsSummary.prediction_count
      : predictions.length;

  const oddsArchiveRaw = oddsArchiveCsv ? parseCsvCached(oddsArchiveCsv) : [];

  const oddsArchive = oddsArchiveRaw.filter(

    (r) =>

      (r.market || "").toUpperCase() === "TEAM_SHOTS" ||

      ((r.team || "").trim() !== "" && !(r.player || "").trim()),

  );



  const settledShadow = shadowSignals.filter(

    (r) => r.result === "won" || r.result === "lost" || r.result === "push",

  );

  const pendingShadow = shadowSignals.filter((r) => r.result === "pending");

  const currentSettledShadow = settledShadow.filter((r) => policyVersion(r) === CURRENT_POLICY);
  const currentPendingShadow = pendingShadow.filter((r) => policyVersion(r) === CURRENT_POLICY);

  const activeSettledShadow = currentSettledShadow;
  const activePendingShadow = currentPendingShadow;

  const shadowPnl = activeSettledShadow.reduce((s, r) => s + pf(r.pnl), 0);

  const shadowPnlStaked = activeSettledShadow.reduce((s, r) => s + pf(r.pnl_staked), 0);

  const shadowStakedTotal = activeSettledShadow.reduce((s, r) => s + pf(r.stake_units || "1"), 0);

  const shadowWins = activeSettledShadow.filter((r) => r.result === "won").length;

  const shadowRoi =

    activeSettledShadow.length > 0 ? (shadowPnl / activeSettledShadow.length) * 100 : 0;

  const shadowRoiStaked =

    shadowStakedTotal > 0 ? (shadowPnlStaked / shadowStakedTotal) * 100 : 0;

  const clvSettled = activeSettledShadow.filter((r) => r.clv && r.clv.trim() !== "");
  const avgClv = clvSettled.length > 0
    ? clvSettled.reduce((s, r) => s + pf(r.clv), 0) / clvSettled.length * 100
    : null;



  const backtestPnl = backtestRows.reduce((s, r) => s + pf(r.pnl), 0);

  const backtestWins = backtestRows.filter(

    (r) => r.won === "True" || r.won === "true",

  ).length;

  const backtestRoi =

    backtestRows.length > 0 ? (backtestPnl / backtestRows.length) * 100 : 0;



  const recentPredictions = Array.isArray(predictionsSummary?.recent_predictions)
    ? predictionsSummary.recent_predictions
    : predictions.slice(-100).reverse();

  const currentShadowLive = dedupeBestShadowFixtureRows([...comparisonRows]
    .filter((row) => {
      const edge = pf(row.edge, Number.NaN);
      const odds = pf(row.book_odds, Number.NaN);
      return (
        !Number.isNaN(edge) &&
        edge >= 0.05 &&
        !Number.isNaN(odds) &&
        odds >= 1.5 &&
        odds <= 5.0
      );
    })
    .sort((a, b) => {
      const dateCmp = (a.date ?? "").localeCompare(b.date ?? "");
      if (dateCmp !== 0) return dateCmp;
      return pf(b.edge) - pf(a.edge);
    }));



  const upcomingRows = (upcomingCsv ? parseCsvCached(upcomingCsv) : []).filter(
    (row) => (row.league ?? "").trim() !== "ligue-1",
  );
  const upcomingModelByMatchTeam = new Map<string, { row: CsvRow; side: "home" | "away" }>();
  for (const row of upcomingRows) {
    const date = (row.kickoff_iso ?? "").slice(0, 10);
    upcomingModelByMatchTeam.set(
      `${matchKey(date, row.home_team, row.away_team)}|${normalizeTeamName(row.home_team)}`,
      { row, side: "home" },
    );
    upcomingModelByMatchTeam.set(
      `${matchKey(date, row.home_team, row.away_team)}|${normalizeTeamName(row.away_team)}`,
      { row, side: "away" },
    );
  }
  const comparisonRowBySignal = new Map<string, CsvRow>();
  for (const row of comparisonRows) {
    comparisonRowBySignal.set(
      comparisonSignalKey(
        row.date,
        row.home_team,
        row.away_team,
        row.team,
        row.bookmaker,
        row.line,
        row.side,
      ),
      row,
    );
  }
  const liveOddsByMatchTeam = new Map<string, Map<string, TeamShotsLiveLine>>();
  for (const row of oddsArchive) {
    const date = (row.match_date ?? row.kickoff_at ?? "").slice(0, 10);
    const lineNumber = pf(row.line, Number.NaN);
    if (!date || Number.isNaN(lineNumber)) continue;
    const teamKey = `${matchKey(date, row.home_team, row.away_team)}|${normalizeTeamName(row.team)}`;
    if (!liveOddsByMatchTeam.has(teamKey)) {
      liveOddsByMatchTeam.set(teamKey, new Map<string, TeamShotsLiveLine>());
    }
    const lineKey = `${(row.bookmaker ?? "").trim()}|${(row.line ?? "").trim()}`;
    const teamLines = liveOddsByMatchTeam.get(teamKey)!;
    const existing =
      teamLines.get(lineKey) ??
      {
        bookmaker: row.bookmaker ?? "-",
        line: lineNumber,
        lineLabel: row.line ?? "",
      };
    if ((row.side ?? "").trim().toLowerCase() === "over") {
      if (!existing.overCapturedAt || (row.captured_at ?? "") >= existing.overCapturedAt) {
        existing.overOdds = pf(row.odds_decimal);
        existing.overCapturedAt = row.captured_at ?? "";
      }
    }
    if ((row.side ?? "").trim().toLowerCase() === "under") {
      if (!existing.underCapturedAt || (row.captured_at ?? "") >= existing.underCapturedAt) {
        existing.underOdds = pf(row.odds_decimal);
        existing.underCapturedAt = row.captured_at ?? "";
      }
    }
    teamLines.set(lineKey, existing);
  }

function LiveLineTable({
  leagueKey,
  teamName,
  row,
  side,
  lines,
  calibration,
}: {
  leagueKey: string;
  teamName: string;
  row: CsvRow;
  side: "home" | "away";
  lines: TeamShotsLiveLine[];
  calibration: CalibrationPayload | null;
}) {
  if (lines.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-500">
        No live bookmaker lines yet.
      </div>
    );
  }
  const lambdaBase = maybeFloat(row[`${side}_lambda`]);
  const lambdaVenue = maybeFloat(row[`${side}_lambda_venue`]) ?? lambdaBase;
  const lambdaRecent = maybeFloat(row[`${side}_lambda_recent`]) ?? lambdaVenue;
  const consensus = consensusStateForRow(row, side);
  const divergence = divergenceForRow(row, side);
  if (!(lambdaVenue !== null && lambdaVenue > 0)) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-500">
        No model estimate for this team yet.
      </div>
    );
  }

  const evaluatedLines = lines
    .map((line) => {
      const metrics = computeLineMetrics(row, side, line, calibration);
      if (!metrics) return null;
      const overShadow = qualifiesForShadow(metrics.overEdge, line.overOdds);
      const underShadow = qualifiesForShadow(metrics.underEdge, line.underOdds);
      const bestEdge = Math.max(metrics.overEdge ?? -999, metrics.underEdge ?? -999);
      const positiveCount = [metrics.overEdge, metrics.underEdge].filter(
        (edge) => edge !== null && edge > 0,
      ).length;
      return {
        line,
        metrics,
        overShadow,
        underShadow,
        shadow: overShadow || underShadow,
        bestEdge,
        positiveCount,
      };
    })
    .filter((entry): entry is NonNullable<typeof entry> => Boolean(entry))
    .sort((a, b) => {
      if (a.shadow !== b.shadow) return a.shadow ? -1 : 1;
      if (a.positiveCount !== b.positiveCount) return b.positiveCount - a.positiveCount;
      if (a.bestEdge !== b.bestEdge) return b.bestEdge - a.bestEdge;
      return a.line.line - b.line.line || a.line.bookmaker.localeCompare(b.line.bookmaker);
    });

  const focusLines = evaluatedLines.filter((entry) => entry.shadow || entry.bestEdge > 0);
  const primaryLines = (focusLines.length > 0 ? focusLines : evaluatedLines).slice(0, 4);
  const extraLines = evaluatedLines.slice(primaryLines.length);
  const bestLive = primaryLines[0];
  const bestShadow = evaluatedLines.find((entry) => entry.shadow);
  const bestShadowMatchesLive =
    Boolean(bestLive && bestShadow) &&
    bestLive!.line.bookmaker === bestShadow!.line.bookmaker &&
    bestLive!.line.lineLabel === bestShadow!.line.lineLabel &&
    (bestLive!.metrics.overEdge !== null && bestLive!.metrics.overEdge === bestLive!.bestEdge ? "O" : "U") ===
      (bestShadow!.metrics.overEdge !== null && bestShadow!.metrics.overEdge === bestShadow!.bestEdge ? "O" : "U");
  const bestLiveText = bestLive
    ? `${bestLive.line.bookmaker} ${bestLive.line.lineLabel} ${
        bestLive.metrics.overEdge !== null && bestLive.metrics.overEdge === bestLive.bestEdge ? "O" : "U"
      } ${formatSignedPercent(bestLive.bestEdge)}`
    : "-";
  const bestShadowText = bestShadow
    ? bestShadowMatchesLive
      ? "same as live"
      : `${bestShadow.line.bookmaker} ${bestShadow.line.lineLabel} ${
          bestShadow.metrics.overEdge !== null && bestShadow.metrics.overEdge === bestShadow.bestEdge ? "O" : "U"
        } ${formatSignedPercent(bestShadow.bestEdge)}`
    : "none";

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-950/40">
      <div className="border-b border-slate-800 px-4 py-3">
        <TeamLabel
          league={leagueKey}
          team={teamName}
          iconSize={20}
          teamClassName="text-sm font-medium text-slate-100"
        />
        <div className="mt-1 flex flex-wrap items-center gap-2">
          <div className="text-xs text-slate-500">
            base {lambdaBase !== null ? lambdaBase.toFixed(2) : "--"} | venue {lambdaVenue.toFixed(2)} | recent {lambdaRecent !== null ? lambdaRecent.toFixed(2) : "--"}
          </div>
          <StatusPill label={consensus.toUpperCase()} tone={consensusTone(consensus)} />
          <div className="text-[11px] text-slate-500">divergence {(divergence * 100).toFixed(1)}%</div>
        </div>
        <div className="mt-2 grid gap-2 text-[11px] sm:grid-cols-2">
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 px-2 py-1.5 text-slate-300">
            Best live:{" "}
            <span
              className={`font-mono ${
                bestLive && bestLive.bestEdge >= 0 ? "text-emerald-300" : "text-rose-300"
              }`}
            >
              {bestLiveText}
            </span>
          </div>
          <div className="rounded-lg border border-slate-800 bg-slate-900/60 px-2 py-1.5 text-slate-300">
            Best shadow:{" "}
            <span
              className={`font-mono ${
                bestShadow ? (bestShadow.bestEdge >= 0 ? "text-emerald-300" : "text-rose-300") : "text-slate-500"
              }`}
            >
              {bestShadowText}
            </span>
          </div>
        </div>
      </div>
      <table className="w-full text-left text-xs">
        <thead>
          <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
            <th className="py-2 pl-4 pr-3">Book</th>
            <th className="py-2 pr-3 font-mono">Line</th>
            <th className="py-2 pr-3 font-mono">Fair O/U</th>
            <th className="py-2 pr-3 font-mono">Book O/U</th>
            <th className="py-2 pr-4 font-mono">Value O/U</th>
            <th className="py-2 pr-4">Signal O/U</th>
          </tr>
        </thead>
        <tbody>
          {primaryLines.map(({ line, metrics, overShadow, underShadow }, i) => {
            const overBadge = signalBadge(metrics.overEdge, "over", consensus);
            const underBadge = signalBadge(metrics.underEdge, "under", consensus);
            return (
              <tr key={`${line.bookmaker}-${line.lineLabel}-${i}`} className="border-b border-slate-800/40">
                <td className="py-2 pl-4 pr-3 text-slate-300">{line.bookmaker}</td>
                <td className="py-2 pr-3 font-mono tabular-nums text-slate-100">{line.lineLabel}</td>
                <td className="py-2 pr-3 font-mono tabular-nums text-slate-400">
                  {metrics.fairOver.toFixed(2)} / {metrics.fairUnder.toFixed(2)}
                </td>
                <td className="py-2 pr-3 font-mono tabular-nums text-slate-100">
                  {line.overOdds ? line.overOdds.toFixed(2) : "-"} / {line.underOdds ? line.underOdds.toFixed(2) : "-"}
                </td>
                <td className="py-2 pr-4 font-mono tabular-nums">
                  <span className={metrics.overEdge !== null && metrics.overEdge >= 0 ? "text-emerald-300" : "text-slate-500"}>
                    {formatSignedPercent(metrics.overEdge)}
                  </span>
                  <span className="text-slate-600"> / </span>
                  <span className={metrics.underEdge !== null && metrics.underEdge >= 0 ? "text-emerald-300" : "text-slate-500"}>
                    {formatSignedPercent(metrics.underEdge)}
                  </span>
                </td>
                <td className="py-2 pr-4">
                  <div className="flex flex-wrap items-center gap-1">
                    {overBadge ? (
                      <StatusPill label={overBadge.label} tone={overBadge.tone} />
                    ) : overShadow ? (
                      <StatusPill label="WATCH" tone="bg-slate-700/30 text-slate-300 border-slate-600/30" />
                    ) : (
                      <span className="text-[10px] text-slate-600">-</span>
                    )}
                    <span className="text-slate-600">/</span>
                    {underBadge ? (
                      <StatusPill label={underBadge.label} tone={underBadge.tone} />
                    ) : underShadow ? (
                      <StatusPill label="WATCH" tone="bg-slate-700/30 text-slate-300 border-slate-600/30" />
                    ) : (
                      <span className="text-[10px] text-slate-600">-</span>
                    )}
                  </div>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
      {extraLines.length > 0 ? (
        <details className="border-t border-slate-800">
          <summary className="cursor-pointer px-4 py-2 text-xs text-slate-400 hover:text-slate-200">
            Show all lines ({evaluatedLines.length})
          </summary>
          <table className="w-full text-left text-xs">
            <tbody>
              {extraLines.map(({ line, metrics, overShadow, underShadow }, i) => (
                <tr key={`extra-${line.bookmaker}-${line.lineLabel}-${i}`} className="border-t border-slate-800/40">
                  <td className="py-2 pl-4 pr-3 text-slate-300">{line.bookmaker}</td>
                  <td className="py-2 pr-3 font-mono tabular-nums text-slate-100">{line.lineLabel}</td>
                  <td className="py-2 pr-3 font-mono tabular-nums text-slate-400">
                    {metrics.fairOver.toFixed(2)} / {metrics.fairUnder.toFixed(2)}
                  </td>
                  <td className="py-2 pr-3 font-mono tabular-nums text-slate-100">
                    {line.overOdds ? line.overOdds.toFixed(2) : "-"} / {line.underOdds ? line.underOdds.toFixed(2) : "-"}
                  </td>
                  <td className="py-2 pr-4 font-mono tabular-nums">
                    <span className={metrics.overEdge !== null && metrics.overEdge >= 0 ? "text-emerald-300" : "text-slate-500"}>
                      {formatSignedPercent(metrics.overEdge)}
                    </span>
                    <span className="text-slate-600"> / </span>
                    <span className={metrics.underEdge !== null && metrics.underEdge >= 0 ? "text-emerald-300" : "text-slate-500"}>
                      {formatSignedPercent(metrics.underEdge)}
                    </span>
                  </td>
                  <td className="py-2 pr-4">
                    <div className="flex flex-wrap items-center gap-1">
                      {signalBadge(metrics.overEdge, "over", consensus) ? (
                        <StatusPill label={signalBadge(metrics.overEdge, "over", consensus)!.label} tone={signalBadge(metrics.overEdge, "over", consensus)!.tone} />
                      ) : overShadow ? (
                        <StatusPill label="WATCH" tone="bg-slate-700/30 text-slate-300 border-slate-600/30" />
                      ) : (
                        <span className="text-[10px] text-slate-600">-</span>
                      )}
                      <span className="text-slate-600">/</span>
                      {signalBadge(metrics.underEdge, "under", consensus) ? (
                        <StatusPill label={signalBadge(metrics.underEdge, "under", consensus)!.label} tone={signalBadge(metrics.underEdge, "under", consensus)!.tone} />
                      ) : underShadow ? (
                        <StatusPill label="WATCH" tone="bg-slate-700/30 text-slate-300 border-slate-600/30" />
                      ) : (
                        <span className="text-[10px] text-slate-600">-</span>
                      )}
                    </div>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        </details>
      ) : null}
    </div>
  );
}

  const upcomingByLeague = groupUpcomingByLeague(upcomingRows);

  const upcomingLeagueKeys = sortLeagueKeys([...upcomingByLeague.keys()]);

  const schedulerHeartbeatAt =
    comparisonMtime ??
    upcomingMtime ??
    predictionsMtime ??
    pipelineStatus?.last_successful_finished_at ??
    pipelineStatus?.updated_at ??
    null;

  const freshnessAnchorAt =
    snapshotGeneratedAt ??
    schedulerHeartbeatAt ??
    comparisonMtime ??
    upcomingMtime ??
    predictionsMtime ??
    null;
  const freshnessAnchorMillis = parseIsoMillis(freshnessAnchorAt);
  const scrapeRunAt = scrapeStatus?.run_at ?? null;
  const scrapeRunMillis = parseIsoMillis(scrapeRunAt);
  const scrapeDisplayAt = scrapeRunAt ?? freshnessAnchorAt;
  const scrapeAgeMinutes =
    scrapeRunMillis === null || freshnessAnchorMillis === null
      ? null
      : Math.max(0, Math.round((freshnessAnchorMillis - scrapeRunMillis) / 60000));
  const renderReferenceMillis =
    freshnessAnchorMillis ??
    scrapeRunMillis ??
    parseIsoMillis(pipelineStatus?.updated_at ?? null) ??
    0;
  const scrapeAgeLabel = scrapeDisplayAt
    ? formatRelativeAgeShort(scrapeDisplayAt, renderReferenceMillis)
    : "-";
  const scrapeErrors = scrapeStatus?.provider_errors?.length ?? 0;
  const scrapeDetailParts: string[] = [];
  if (typeof scrapeStatus?.rows_scraped === "number") {
    scrapeDetailParts.push(`${scrapeStatus.rows_scraped} rows`);
  }
  if (typeof scrapeStatus?.events_found === "number") {
    scrapeDetailParts.push(`${scrapeStatus.events_found} events`);
  }
  if (scrapeErrors > 0) {
    scrapeDetailParts.push(`${scrapeErrors} errors`);
  }
  const scrapeDetail =
    scrapeDetailParts.length > 0
      ? scrapeDetailParts.join(" | ")
      : scrapeStatus
        ? undefined
        : "pipeline fallback";
  const scrapeToneValue = scrapeStatus ? scrapeTone(scrapeStatus, scrapeAgeMinutes) : "amber";
  const pipelineStatusAt =
    pipelineStatus?.last_successful_finished_at ??
    pipelineStatus?.updated_at ??
    null;
  const pipelineStatusMillis = parseIsoMillis(pipelineStatusAt);
  const hostedPipelineAt =
    snapshotGeneratedAt ??
    scrapeRunAt ??
    comparisonMtime ??
    upcomingMtime ??
    predictionsMtime ??
    null;
  const hostedPipelineMillis = parseIsoMillis(hostedPipelineAt);
  const pipelineStatusIsStale =
    pipelineStatusMillis !== null &&
    hostedPipelineMillis !== null &&
    pipelineStatusMillis + 5 * 60 * 1000 < hostedPipelineMillis;
  const pipelineStateValue =
    pipelineStatusIsStale
      ? scrapeStatus?.success === false
        ? "failed"
        : hostedPipelineAt
          ? "idle"
          : (pipelineStatus?.state ?? "unknown")
      : (pipelineStatus?.state ?? (scrapeStatus?.success === false ? "failed" : hostedPipelineAt ? "idle" : "unknown"));
  const pipelineTone =
    pipelineStateValue === "failed"
      ? "red"
      : pipelineStatusIsStale
        ? scrapeErrors > 0
          ? "amber"
          : "green"
        : pipelineStatus?.warnings?.length
          ? "amber"
          : "green";
  const pipelineStateDetail = pipelineStatusIsStale
    ? scrapeStatus
      ? "hosted team-shots status"
      : "hosted snapshot fallback"
    : (pipelineStatus?.current_step || undefined);
  const pipelineMessage = pipelineStatusIsStale
    ? `Using hosted team-shots status from ${formatDateTime(hostedPipelineAt)} because team-props status is older.`
    : (pipelineStatus?.message ?? null);
  const staleHours = monitorStaleHours();
  const realNowMillis = currentServerRenderMillis();
  const hostedSnapshotAt = comparisonSource?.hostedGeneratedAt ?? null;
  const hostedSnapshotMillis = parseIsoMillis(hostedSnapshotAt);
  const hostedSnapshotAgeHours =
    hostedSnapshotMillis === null ? null : Math.max(0, (realNowMillis - hostedSnapshotMillis) / (60 * 60 * 1000));
  const hostedSnapshotIsStale =
    !comparisonSource?.hostedSnapshotAvailable ||
    hostedSnapshotMillis === null ||
    hostedSnapshotAgeHours === null ||
    hostedSnapshotAgeHours > staleHours ||
    comparisonSource.source !== "hosted";

  const coverageReferenceMillis = renderReferenceMillis;
  const coverageWindowEndMillis = coverageReferenceMillis + 48 * 60 * 60 * 1000;
  const upcomingCoverageByLeague = new Map<string, Map<string, string>>();
  for (const row of upcomingRows) {
    const leagueKey = (row.league ?? "").trim();
    const kickoffIso = row.kickoff_iso ?? "";
    const kickoffMillis = parseIsoMillis(kickoffIso);
    if (!leagueKey || kickoffMillis === null) continue;
    if (kickoffMillis < coverageReferenceMillis || kickoffMillis > coverageWindowEndMillis) continue;
    if (!upcomingCoverageByLeague.has(leagueKey)) {
      upcomingCoverageByLeague.set(leagueKey, new Map<string, string>());
    }
    const key = matchKey(kickoffIso.slice(0, 10), row.home_team, row.away_team);
    upcomingCoverageByLeague.get(leagueKey)!.set(
      key,
      `${row.home_team ?? "?"} v ${row.away_team ?? "?"}`,
    );
  }
  const latestCaptureAtByLeague = new Map<string, number>();
  const latestCaptureIsoByLeague = new Map<string, string>();
  const latestCapturedMatchesByLeague = new Map<string, Map<string, string>>();
  for (const row of oddsArchive) {
    const leagueKey =
      competitionToLeagueId(row.competition) ??
      competitionToLeagueId(row.league) ??
      ((row.league ?? "").trim() || null);
    const capturedAt = row.captured_at ?? "";
    const capturedMillis = parseIsoMillis(capturedAt);
    const matchDate = (row.match_date ?? row.kickoff_at ?? "").slice(0, 10);
    if (!leagueKey || capturedMillis === null || !matchDate) continue;
    const existingMillis = latestCaptureAtByLeague.get(leagueKey) ?? Number.NEGATIVE_INFINITY;
    if (capturedMillis > existingMillis) {
      latestCaptureAtByLeague.set(leagueKey, capturedMillis);
      latestCaptureIsoByLeague.set(leagueKey, capturedAt);
      latestCapturedMatchesByLeague.set(leagueKey, new Map<string, string>());
    }
    if ((latestCaptureAtByLeague.get(leagueKey) ?? Number.NEGATIVE_INFINITY) !== capturedMillis) continue;
    const key = matchKey(matchDate, row.home_team, row.away_team);
    latestCapturedMatchesByLeague.get(leagueKey)!.set(
      key,
      `${row.home_team ?? "?"} v ${row.away_team ?? "?"}`,
    );
  }
  const coverageIssues = [...upcomingCoverageByLeague.entries()]
    .map(([leagueKey, expectedMatches]) => {
      const capturedMatches = latestCapturedMatchesByLeague.get(leagueKey) ?? new Map<string, string>();
      const missingMatches = [...expectedMatches.entries()]
        .filter(([key]) => !capturedMatches.has(key))
        .map(([, label]) => label);
      return {
        leagueKey,
        expectedCount: expectedMatches.size,
        capturedCount: capturedMatches.size,
        missingMatches,
        capturedAt: latestCaptureIsoByLeague.get(leagueKey) ?? null,
      };
    })
    .filter((issue) => issue.expectedCount > 0 && issue.capturedCount < issue.expectedCount)
    .sort((a, b) => a.leagueKey.localeCompare(b.leagueKey));
  const hasPartialScrape = Boolean(scrapeStatus?.success) && scrapeErrors > 0;

  // Use a stable snapshot-based day boundary so server/client render the same split.
  const asOfIso = (
    snapshotGeneratedAt ??
    comparisonMtime ??
    upcomingMtime ??
    predictionsMtime ??
    pipelineStatus?.updated_at ??
    scrapeRunAt ??
    "1970-01-01T00:00:00Z"
  ).slice(0, 10);

  // Shadow signal count per league -- counts upcoming signals only (fixture card auto-open logic).
  const shadowCountByLeague = new Map<string, number>();
  for (const row of currentShadowLive) {
    const d = (row.date ?? "").slice(0, 10);
    if (d > asOfIso) {
      const lg = (row.league ?? "").trim() || "other";
      shadowCountByLeague.set(lg, (shadowCountByLeague.get(lg) ?? 0) + 1);
    }
  }

  type PendingShadowRow = {
    date: string;
    league: string;
    home_team: string;
    away_team: string;
    team: string;
    bookmaker: string;
    line: string;
    side: string;
    book_odds: string;
    stake_units: string;
    logged_at: string;
    model_fair_odds: string;
    edge: string;
    entryEdgePct: number | null;
    currentFairOdds: number | null;
    currentEdgePct: number | null;
    repricedFairOdds: number | null;
    repricedEdgePct: number | null;
    pendingState: "upcoming" | "awaiting result";
    currentOdds: number | null;
    delta: number | null;
    currentLine: string | null;
    currentBookmaker: string | null;
    exactLineAvailable: boolean;
    lineMoved: boolean;
  };

  const buildPendingShadowRows = (rows: CsvRow[]): PendingShadowRow[] =>
    rows
    .map((row): PendingShadowRow => {
      const matchDate = (row.date ?? "").slice(0, 10);
      const teamKey = `${matchKey(matchDate, row.home_team, row.away_team)}|${normalizeTeamName(row.team)}`;
      const currentTeamLines = liveOddsByMatchTeam.get(teamKey);
      const lineKey = `${(row.bookmaker ?? "").trim()}|${(row.line ?? "").trim()}`;
      const exactLine = currentTeamLines?.get(lineKey) ?? null;
      const sameBookLines = [...(currentTeamLines?.values() ?? [])].filter(
        (line) => line.bookmaker === (row.bookmaker ?? "").trim(),
      );
      const activeLine =
        exactLine ??
        sameBookLines
          .slice()
          .sort((a, b) => Math.abs(a.line - pf(row.line, 0)) - Math.abs(b.line - pf(row.line, 0)))[0];
      const currentOdds =
        activeLine
          ? (row.side === "over" ? activeLine.overOdds : activeLine.underOdds) ?? null
          : null;
      const loggedOdds = pf(row.book_odds, Number.NaN);
      const loggedModelProb = maybeFloat(row.model_prob);
      const delta =
        exactLine && currentOdds !== null && !Number.isNaN(loggedOdds) ? currentOdds - loggedOdds : null;
      const currentModel = upcomingModelByMatchTeam.get(teamKey);
      const currentMetrics =
        activeLine && currentModel
          ? computeLineMetrics(currentModel.row, currentModel.side, activeLine, calibrationParams)
          : null;
      const activeComparison = activeLine
        ? comparisonRowBySignal.get(
            comparisonSignalKey(
              row.date,
              row.home_team,
              row.away_team,
              row.team,
              row.bookmaker,
              activeLine.lineLabel,
              row.side,
            ),
          )
        : null;
      let currentFairOdds: number | null = null;
      let currentEdgePct: number | null = null;
      let repricedFairOdds =
        currentMetrics
          ? row.side === "over"
            ? currentMetrics.fairOver
            : currentMetrics.fairUnder
          : null;
      let repricedEdgePct =
        currentMetrics
          ? row.side === "over"
            ? currentMetrics.overEdge
            : currentMetrics.underEdge
          : null;
      if (activeComparison) {
        const fair = pf(activeComparison.model_fair_odds, Number.NaN);
        const edge = pf(activeComparison.edge, Number.NaN);
        currentFairOdds = Number.isNaN(fair) ? null : fair;
        currentEdgePct = Number.isNaN(edge) ? null : edge * 100;
      } else if (repricedFairOdds !== null || repricedEdgePct !== null) {
        currentFairOdds = repricedFairOdds;
        currentEdgePct = repricedEdgePct;
      } else if (exactLine) {
        currentFairOdds = fairOddsFromProbability(loggedModelProb);
        currentEdgePct = evEdgePct(loggedModelProb, currentOdds);
      }
      if (repricedFairOdds === null || repricedEdgePct === null) {
        const currentComparison = comparisonRowBySignal.get(
          comparisonSignalKey(
            row.date,
            row.home_team,
            row.away_team,
            row.team,
            row.bookmaker,
            row.line,
            row.side,
          ),
        );
        if (currentComparison) {
          const fair = pf(currentComparison.model_fair_odds, Number.NaN);
          const edge = pf(currentComparison.edge, Number.NaN);
          repricedFairOdds = Number.isNaN(fair) ? null : fair;
          repricedEdgePct = Number.isNaN(edge) ? null : edge * 100;
        }
      }
      const storedEdge = maybeFloat(row.edge);
      const entryEdgePct =
        evEdgePct(loggedModelProb, Number.isNaN(loggedOdds) ? null : loggedOdds) ??
        (storedEdge !== null ? storedEdge * 100 : null);
      return {
        date: row.date ?? "",
        league: row.league ?? "",
        home_team: row.home_team ?? "",
        away_team: row.away_team ?? "",
        team: row.team ?? "",
        bookmaker: row.bookmaker ?? "",
        line: row.line ?? "",
        side: row.side ?? "",
        book_odds: row.book_odds ?? "",
        stake_units: row.stake_units ?? "",
        logged_at: row.logged_at ?? "",
        model_fair_odds: row.model_fair_odds ?? "",
        edge: row.edge ?? "",
        entryEdgePct,
        currentFairOdds,
        currentEdgePct,
        repricedFairOdds,
        repricedEdgePct,
        pendingState: matchDate > asOfIso ? "upcoming" : "awaiting result",
        currentOdds,
        delta,
        currentLine: activeLine ? activeLine.lineLabel : null,
        currentBookmaker: activeLine ? activeLine.bookmaker : null,
        exactLineAvailable: Boolean(exactLine),
        lineMoved: Boolean(activeLine && !exactLine),
      };
    })
    .sort((a, b) => {
      const dateCmp = (a.date ?? "").localeCompare(b.date ?? "");
      if (dateCmp !== 0) return dateCmp;
      const edgeCmp = pf(b.edge) - pf(a.edge);
      if (Math.abs(edgeCmp) > 1e-9) return edgeCmp;
      return `${a.home_team} ${a.away_team} ${a.team}`.localeCompare(
        `${b.home_team} ${b.away_team} ${b.team}`,
      );
    });

  const pendingShadowRows = buildPendingShadowRows(activePendingShadow);

  const pendingUpcomingCount = pendingShadowRows.filter((row) => row.pendingState === "upcoming").length;
  const pendingAwaitingCount = pendingShadowRows.length - pendingUpcomingCount;
  const pendingRowsByDate = new Map<string, typeof pendingShadowRows>();
  for (const row of pendingShadowRows) {
    const key = (row.date ?? "").slice(0, 10) || "unknown";
    if (!pendingRowsByDate.has(key)) pendingRowsByDate.set(key, []);
    pendingRowsByDate.get(key)!.push(row);
  }
  const pendingDateKeys = [...pendingRowsByDate.keys()].sort();
  const defaultOpenPendingDate =
    pendingDateKeys.find((date) => date >= asOfIso) ?? pendingDateKeys[pendingDateKeys.length - 1] ?? null;

  const recentSettledShadow = [...activeSettledShadow]
    .sort((a, b) =>
      (b.settled_at ?? b.date ?? "").localeCompare(a.settled_at ?? a.date ?? ""),
    )
    .slice(0, 15);

  const teamShotsV3Lane = findResearchLane(researchLaneState, "team_shots", "canonical_form_v3_ema20_nb");
  const teamShotsV3AllowedLeagues =
    teamShotsV3AllowedConfig?.allowed_leagues ??
    teamShotsV3Lane?.allowed_leagues ??
    teamShotsV3PromotionCheck?.ready_leagues ??
    [];
  const teamShotsV3BlockedLeagues =
    teamShotsV3AllowedConfig?.blocked_leagues ?? teamShotsV3PromotionCheck?.blocked_leagues ?? [];
  const teamShotsV3Clv = parseClvMonitorSummary(teamShotsV3ClvReport);
  const teamShotsV4ClvRows = teamShotsV4ClvCsv ? parseCsvCached(teamShotsV4ClvCsv) : [];
  const vnextCandidateRows = vnextCandidatesCsv ? parseCsvCached(vnextCandidatesCsv) : [];
  const goalkeeperCandidateRows = goalkeeperSavesCandidatesCsv ? parseCsvCached(goalkeeperSavesCandidatesCsv) : [];
  const goalkeeperTopRows = goalkeeperCandidateRows
    .filter((row) => row.strongest_for_fixture === "yes")
    .sort((a, b) => (maybeFloat(b.edge) ?? -999) - (maybeFloat(a.edge) ?? -999))
    .slice(0, 8);
  const goalkeeperCurrent = goalkeeperSavesReport?.current;
  const goalkeeperEvidence = goalkeeperSavesReport?.evidence;
  const teamShotsV3ClvRows = teamShotsV3ClvCsv ? parseCsvCached(teamShotsV3ClvCsv) : [];
  const teamShotsV3Summary = researchBetSummary(teamShotsV3ClvRows);
  const teamShotsV3SideRows = (["over", "under"] as const).map((side) => {
    const rows = teamShotsV3ClvRows.filter((row) => (row.side ?? "").trim().toLowerCase() === side);
    return {
      side,
      label: side === "over" ? "Overs" : "Unders",
      summary: researchBetSummary(rows),
      clv: researchAvgPublishedClvPct(rows),
    };
  });
  const teamShotsV3SettledPicks = teamShotsV3ClvRows.filter((row) =>
    researchRowIsActive(row) && isSettledResearchRow(row),
  );
  const teamShotsV3RecentSettledPicks = [...teamShotsV3SettledPicks]
    .sort((a, b) => researchRowSortKey(b).localeCompare(researchRowSortKey(a)))
    .slice(0, 8);
  const teamShotsV3GuardBlockedPicks = teamShotsV3ClvRows.filter(researchRowIsGuarded);
  const teamShotsV3PendingPicks = teamShotsV3ClvRows
    .filter((row) => {
      const result = researchResult(row);
      return (!result || result === "pending") && researchRowIsActive(row);
    })
    .sort((a, b) => (a.kickoff_utc ?? a.match_date ?? "").localeCompare(b.kickoff_utc ?? b.match_date ?? ""));
  const teamShotsV3LeagueRows = [...(teamShotsV3PromotionCheck?.league_results ?? [])].sort((a, b) =>
    (a.league ?? "").localeCompare(b.league ?? ""),
  );

  return (
    <div className="min-h-screen bg-[#0a0f19] px-4 py-10 text-slate-200 sm:px-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">

        <MonitorNav current="team-shots" />

        {/* Hero */}
        <HeroCard title="Team Total Shots Monitor" eyebrow="Team Shots Model">
          <span className="text-slate-300">Shadow signals | calibrated Poisson | Platt-scaled over/under.</span>
          <span className="mx-2 text-slate-700">|</span>
          <span className="text-slate-500">
            Snapshot {snapshotGeneratedAt ? formatDateTime(snapshotGeneratedAt) : "-"}
          </span>
        </HeroCard>

        {hostedSnapshotIsStale ? (
          <section className="rounded-2xl border border-rose-500/35 bg-rose-950/35 p-4 text-sm text-rose-100">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-300">
              Stale hosted team-shots data
            </div>
            <p className="mt-2">
              Do not trust an empty or quiet board until this clears. The canonical hosted `team_shots_state` snapshot is{" "}
              {hostedSnapshotAt ? `${formatRelativeAgeShort(hostedSnapshotAt, realNowMillis)} old` : "missing"}; threshold is {staleHours.toFixed(0)}h.
            </p>
            <p className="mt-1 text-xs text-rose-200/80">
              Source: {comparisonSource?.source ?? "missing"} | hosted generated {hostedSnapshotAt ? formatDateTime(hostedSnapshotAt) : "missing"} | local fallback{" "}
              {comparisonSource?.localSnapshotGeneratedAt ? formatDateTime(comparisonSource.localSnapshotGeneratedAt) : "missing"}.
            </p>
          </section>
        ) : null}

        <FootballVnextShadowPanel
          title="Team Shots v4 Prospective Lane"
          model="team_shots_v4"
          rows={teamShotsV4ClvRows}
          candidates={vnextCandidateRows}
          gate={vnextGate?.team_shots_v4 ?? null}
        />

        <SectionCard
          id="goalkeeper-saves"
          collapsible
          title="Goalkeeper Saves v1 Prospective Lane"
          subtitle="Bet365 O/U prices, confirmed starting goalkeepers, named-player settlement, and true-close evidence. Research shadow only."
        >
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-6">
            <StatCard
              label="Price capture"
              value={(goalkeeperSavesCapture?.status ?? "NOT RUN").replaceAll("_", " ")}
              tone={statTone(goalkeeperSavesCapture?.status === "CAPTURED" ? "green" : "amber")}
              detail={goalkeeperSavesCapture?.generated_at ? formatDateTime(goalkeeperSavesCapture.generated_at) : "Awaiting first scheduled capture"}
            />
            <StatCard label="Priced lines" value={`${goalkeeperCurrent?.priced_lines ?? 0}`} detail={`${goalkeeperCurrent?.eligible_lines ?? 0} eligible`} />
            <StatCard label="Signals" value={`${goalkeeperEvidence?.signals ?? 0}`} detail={`${goalkeeperEvidence?.pending ?? 0} pending`} />
            <StatCard
              label="Settled / P&L"
              value={`${goalkeeperEvidence?.settled ?? 0} / ${formatUnits(goalkeeperEvidence?.pnl_units ?? 0)}`}
              detail={`ROI ${formatSignedPercent(goalkeeperEvidence?.roi == null ? null : goalkeeperEvidence.roi * 100)}`}
            />
            <StatCard
              label="True-close CLV"
              value={formatSignedPercent(goalkeeperEvidence?.clv == null ? null : goalkeeperEvidence.clv * 100)}
              detail={`${goalkeeperEvidence?.clv_matched ?? 0}/${goalkeeperEvidence?.settled ?? 0} matched`}
            />
            <StatCard
              label="Promotion"
              value={(goalkeeperSavesReport?.promotion?.status ?? "BLOCKED").replaceAll("_", " ")}
              tone={statTone("red")}
              detail={`Need ${goalkeeperSavesReport?.promotion?.settled_required ?? 150} settled`}
            />
          </div>

          <div className="mt-4 flex flex-wrap items-center gap-2">
            <StatusPill
              label={(goalkeeperSavesReport?.status ?? "NO CURRENT LINES").replaceAll("_", " ")}
              tone="border-amber-500/20 bg-amber-500/10 text-amber-300"
            />
            <span className="text-xs text-slate-500">
              {goalkeeperSavesReport?.selection_rule ?? "One strongest O/U side per fixture; edge >=8%; confirmed starter only."}
            </span>
          </div>

          {goalkeeperTopRows.length ? (
            <div className="mt-4 overflow-x-auto rounded-2xl border border-slate-800 bg-slate-950/45">
              <table className="min-w-full text-left text-xs">
                <thead className="border-b border-slate-800 text-[10px] uppercase tracking-[0.14em] text-slate-500">
                  <tr>
                    <th className="px-4 py-3">Fixture</th>
                    <th className="px-4 py-3">Goalkeeper</th>
                    <th className="px-4 py-3">Book line</th>
                    <th className="px-4 py-3">Model</th>
                    <th className="px-4 py-3">Edge</th>
                    <th className="px-4 py-3">Gate</th>
                  </tr>
                </thead>
                <tbody className="divide-y divide-slate-800/70">
                  {goalkeeperTopRows.map((row) => {
                    const edge = maybeFloat(row.edge);
                    return (
                      <tr key={`${row.event_id}|${row.goalkeeper}|${row.line}`}>
                        <td className="px-4 py-3">
                          <MatchLabel league={row.league} homeTeam={row.home_team} awayTeam={row.away_team} />
                          <div className="mt-1 text-[11px] text-slate-600">{row.kickoff_at ? formatDateTime(row.kickoff_at) : row.match_date}</div>
                        </td>
                        <td className="px-4 py-3 font-semibold text-slate-200">{row.goalkeeper || "-"}</td>
                        <td className="px-4 py-3 tabular-nums text-slate-300">{(row.side || "over").replace(/^./, (letter) => letter.toUpperCase())} {row.line} @ {formatMaybeFixed(row.odds_decimal)}</td>
                        <td className="px-4 py-3 tabular-nums text-slate-300">{formatMaybeFixed(row.model_mean)} saves</td>
                        <td className={`px-4 py-3 font-semibold tabular-nums ${edge !== null && edge >= 0 ? "text-emerald-300" : "text-slate-400"}`}>
                          {formatSignedPercent(edge === null ? null : edge * 100)}
                        </td>
                        <td className="px-4 py-3">
                          <StatusPill
                            label={(row.candidate_status || "blocked").replaceAll("_", " ")}
                            tone={row.candidate_status === "eligible_shadow" ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300" : "border-slate-700 bg-slate-900 text-slate-400"}
                          />
                          {row.blockers ? <div className="mt-1 max-w-xs text-[10px] text-slate-600">{row.blockers.replaceAll("|", " / ")}</div> : null}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          ) : (
            <p className="mt-4 rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-sm text-slate-400">
              No current Bet365 goalkeeper-save candidates. The scheduled capture will populate this board when the market is listed.
            </p>
          )}
        </SectionCard>

        <SectionCard
          id="team-fouls"
          collapsible
          title="Team Fouls Research Gate"
          subtitle="Count validation only. No foul bet is authorized until prices, source agreement, and prospective CLV all pass."
        >
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <StatCard
              label="M1 empirical base"
              value={teamFoulsM1?.usable_rows ? `${teamFoulsM1.usable_rows.toLocaleString()} matches` : "Missing"}
              tone={statTone(teamFoulsM1?.usable_rows ? "green" : "red")}
              detail={teamFoulsM1?.status?.replaceAll("_", " ")}
            />
            <StatCard
              label="F1 count gate"
              value={teamFoulsF1?.decision?.count_gate_pass ? "PASS" : "FAIL"}
              tone={statTone(teamFoulsF1?.decision?.count_gate_pass ? "green" : "red")}
              detail={`${teamFoulsF1?.sample_matches?.toLocaleString() ?? 0} tested matches`}
            />
            <StatCard
              label="F2 Poisson gate"
              value={teamFoulsF2?.decision?.count_gate_pass ? "PASS" : "FAIL"}
              tone={statTone(teamFoulsF2?.decision?.count_gate_pass ? "green" : "red")}
              detail={`${teamFoulsF2?.sample_matches?.toLocaleString() ?? 0} tested matches`}
            />
            <StatCard
              label="M2 source agreement"
              value={(teamFoulsM2?.status ?? "NOT RUN").replaceAll("_", " ")}
              tone={statTone(teamFoulsM2?.settlement_source_authorized ? "green" : "amber")}
              detail={`API ${teamFoulsM2?.api_football?.comparable_team_values ?? 0} | FotMob ${teamFoulsM2?.fotmob?.comparable_team_values ?? 0} team values`}
            />
            <StatCard
              label="Market / signals"
              value={(footballFoulMarketProbe?.status ?? "NOT PROBED").replaceAll("_", " ")}
              tone={statTone(footballFoulMarketProbe?.status === "PAIRED_FOUL_PRICES_RETURNED" ? "green" : "red")}
              detail={
                footballFoulMarketProbe?.generated_at
                  ? `${footballFoulMarketProbe.events_probed ?? 0} events | ${formatDateTime(footballFoulMarketProbe.generated_at)}`
                  : "Run the bounded GitHub feed probe"
              }
            />
          </div>

          <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/45 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill
                label={teamFoulsF1?.decision?.status?.replaceAll("_", " ") ?? "F1 NOT RUN"}
                tone={
                  teamFoulsF1?.decision?.count_gate_pass
                    ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                    : "border-rose-500/20 bg-rose-500/10 text-rose-300"
                }
              />
              {(teamFoulsF1?.decision?.mae_checks ?? []).map((check) => (
                <span key={check.season} className="rounded-full border border-emerald-500/20 bg-emerald-500/10 px-2.5 py-1 text-[11px] font-semibold text-emerald-300">
                  {check.season}: MAE {typeof check.improvement_pct === "number" ? `${check.improvement_pct.toFixed(1)}% better` : "-"}
                </span>
              ))}
            </div>
            <p className="mt-3 text-sm leading-6 text-slate-300">
              The causal mean model cleared the 5% accuracy target in both holdouts. The registered full model still failed because referee and cards did not add enough, hierarchical NB beat both controls in only {teamFoulsF1?.decision?.hierarchical_nb_wins ?? 0}/{teamFoulsF1?.decision?.hierarchical_nb_cells ?? 0} league-fold cells, and calibration narrowly missed one fold.
            </p>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(teamFoulsF1?.decision?.gates ?? {}).map(([gate, passed]) => (
                <span
                  key={gate}
                  className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                    passed
                      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                      : "border-rose-500/20 bg-rose-500/10 text-rose-300"
                  }`}
                >
                  {passed ? "Pass" : "Fail"} {gate.replaceAll("_", " ")}
                </span>
              ))}
            </div>
            <p className="mt-3 text-xs text-slate-500">
              F1 remains the richer control. F2 retained only team form, opponent fouls drawn and opening-market strength with Poisson tails. Its mean stayed strong, but it did not beat F1 distribution scores and the market-strength increment failed one locked fold.
            </p>
          </div>

          <div className="mt-4 rounded-2xl border border-slate-800 bg-slate-950/45 p-4">
            <div className="flex flex-wrap items-center gap-2">
              <StatusPill
                label={teamFoulsF2?.decision?.status?.replaceAll("_", " ") ?? "F2 NOT RUN"}
                tone={
                  teamFoulsF2?.decision?.count_gate_pass
                    ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                    : "border-rose-500/20 bg-rose-500/10 text-rose-300"
                }
              />
              {(teamFoulsF2?.decision?.fold_checks ?? []).map((check) => (
                <span key={check.season} className="rounded-full border border-sky-500/20 bg-sky-500/10 px-2.5 py-1 text-[11px] font-semibold text-sky-200">
                  {check.season}: MAE {typeof check.mae_improvement_pct === "number" ? `${check.mae_improvement_pct.toFixed(1)}% better` : "-"}
                </span>
              ))}
            </div>
            <div className="mt-3 flex flex-wrap gap-2">
              {Object.entries(teamFoulsF2?.decision?.gates ?? {}).map(([gate, passed]) => (
                <span
                  key={gate}
                  className={`rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.12em] ${
                    passed
                      ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                      : "border-rose-500/20 bg-rose-500/10 text-rose-300"
                  }`}
                >
                  {passed ? "Pass" : "Fail"} {gate.replaceAll("_", " ")}
                </span>
              ))}
            </div>
          </div>

          <p className="mt-4 text-xs leading-5 text-slate-500">
            Latest price-feed decision: {footballFoulMarketProbe?.decision ?? "No bounded Bet365 foul-market probe has been recorded yet."}
          </p>
        </SectionCard>

        <SectionCard
          collapsible
          title="Next Count-Market Coverage"
          subtitle="Observed through the configured Bet365 feed; this is a price-availability gate, not a betting signal."
        >
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            {[
              ["Team fouls", "team_fouls_total"],
              ["Match fouls", "match_fouls_total"],
              ["Team cards", "team_cards_total"],
              ["Match cards", "match_cards_total"],
            ].map(([label, category]) => {
              const item = countMarketCoverage?.categories?.[category];
              const status = item?.status ?? "NOT_AUDITED";
              const tone =
                status === "PAIRED_PRICES_OBSERVED"
                  ? "border-emerald-500/20 bg-emerald-500/10 text-emerald-300"
                  : status === "MARKET_NAME_ONLY"
                    ? "border-amber-500/20 bg-amber-500/10 text-amber-300"
                    : "border-slate-600/40 bg-slate-700/40 text-slate-400";
              return (
                <div key={category} className="rounded-2xl border border-slate-800 bg-slate-950/45 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="text-sm font-semibold text-white">{label}</div>
                      <div className="mt-1 text-xs text-slate-500">
                        {item?.events ?? 0} events | {item?.paired_price_events ?? 0} paired O/U
                      </div>
                    </div>
                    <StatusPill label={status.replaceAll("_", " ")} tone={tone} />
                  </div>
                  <p className="mt-3 text-xs leading-5 text-slate-400">
                    {(item?.raw_market_names ?? []).join(", ") || "No matching market returned by the feed."}
                  </p>
                </div>
              );
            })}
          </div>
          <p className="mt-3 text-xs text-slate-500">
            Team Fouls remains blocked until paired prices are observed and bookmaker settlement definitions match the result source.
            {countMarketCoverage?.generated_at ? ` Last audit ${formatDateTime(countMarketCoverage.generated_at)}.` : ""}
          </p>
        </SectionCard>

        {/* Pipeline health */}
        <SectionCard collapsible title="Pipeline Health" subtitle={pipelineStateValue}>
          <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-6">
            <StatCard
              label="Pipeline state"
              value={pipelineStateValue}
              tone={statTone(pipelineTone)}
              detail={pipelineStateDetail}
            />
            <StatCard
              label="Last heartbeat"
              value={schedulerHeartbeatAt ? formatRelativeAgeShort(schedulerHeartbeatAt, renderReferenceMillis) : "-"}
            />
            <StatCard
              label="Data source"
              value={comparisonSource?.source ?? "-"}
              tone={statTone(sourceTone(comparisonSource?.source ?? "missing"))}
              detail={comparisonSource ? formatSourceReason(comparisonSource.reason) : undefined}
            />
            <StatCard label="Predictions" value={predictionsMtime ? formatRelativeAgeShort(predictionsMtime, renderReferenceMillis) : "-"} />
            <StatCard label="Comparison"  value={comparisonMtime  ? formatRelativeAgeShort(comparisonMtime, renderReferenceMillis)  : "-"} />
            <StatCard label="Upcoming"    value={upcomingMtime    ? formatRelativeAgeShort(upcomingMtime, renderReferenceMillis)    : "-"} />
            <StatCard
              label="Last scrape"
              value={scrapeAgeLabel}
              tone={statTone(scrapeToneValue)}
              detail={scrapeDetail}
            />
          </div>
          {pipelineMessage ? (
            <p className="mt-3 rounded-lg border border-slate-700/50 bg-slate-900/50 px-3 py-2 text-xs text-slate-400">
              {pipelineMessage}
            </p>
          ) : null}
          {scrapeStatus?.success === false ? (
            <p className="mt-3 rounded-lg border border-rose-500/20 bg-rose-500/8 px-3 py-2 text-xs text-rose-300">
              Team shots scrape failed{scrapeStatus.error ? `: ${scrapeStatus.error}` : "."}
            </p>
          ) : null}
          {hasPartialScrape ? (
            <p className="mt-3 rounded-lg border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-xs text-amber-300">
              Latest scrape was partial. Primary feed degraded and bookmaker fallback was used
              {scrapeErrors > 0 ? ` (${scrapeErrors} provider issue${scrapeErrors === 1 ? "" : "s"})` : ""}.
            </p>
          ) : null}
          {coverageIssues.length > 0 ? (
            <div className="mt-3 space-y-1">
              {coverageIssues.map((issue) => (
                <p key={issue.leagueKey} className="rounded-lg border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-xs text-amber-300">
                  Latest {leagueTitle(issue.leagueKey)} capture covers {issue.capturedCount} of {issue.expectedCount} upcoming matches in the next 48h.
                  {issue.missingMatches.length > 0 ? ` Missing: ${issue.missingMatches.slice(0, 3).join(" | ")}${issue.missingMatches.length > 3 ? ` (+${issue.missingMatches.length - 3} more)` : ""}.` : ""}
                  {issue.capturedAt ? ` Capture: ${formatDateTime(issue.capturedAt)}.` : ""}
                </p>
              ))}
            </div>
          ) : null}
          {!pipelineStatusIsStale && (pipelineStatus?.warnings?.length ?? 0) > 0 ? (
            <div className="mt-3 space-y-1">
              {pipelineStatus!.warnings!.map((w, i) => (
                <p key={i} className="rounded-lg border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-xs text-amber-300">
                  {w}
                </p>
              ))}
            </div>
          ) : null}
          {(pipelineStatus?.critical_failures?.length ?? 0) > 0 ? (
            <div className="mt-3 space-y-1">
              {pipelineStatus!.critical_failures!.map((f, i) => (
                <p key={i} className="rounded-lg border border-rose-500/20 bg-rose-500/8 px-3 py-2 text-xs text-rose-300">
                  {f}
                </p>
              ))}
            </div>
          ) : null}
          {scrapeStatus?.run_url ? (
            <p className="mt-3 text-xs text-slate-500">
              Run: <a className="text-sky-300 hover:text-sky-200" href={scrapeStatus.run_url} target="_blank" rel="noreferrer">open logs</a>
            </p>
          ) : null}
        </SectionCard>

        {/* -- KPI strip -- */}
        <section className="grid gap-2.5 sm:grid-cols-3 xl:grid-cols-5">
          <StatCard
            label="Current policy"
            value={String(activeSettledShadow.length + activePendingShadow.length)}
            detail={`${activeSettledShadow.length} settled | ${activePendingShadow.length} pending`}
          />
          <StatCard
            label="Flat P/L (1u)"
            value={`${shadowPnl >= 0 ? "+" : ""}${shadowPnl.toFixed(2)}u`}
            tone={shadowPnl >= 0 ? "text-emerald-300" : "text-rose-300"}
          />
          <StatCard
            label="Flat ROI (1u)"
            value={`${shadowRoi >= 0 ? "+" : ""}${shadowRoi.toFixed(1)}%`}
            tone={shadowRoi >= 0 ? "text-emerald-300" : "text-rose-300"}
            detail={`${shadowWins}/${activeSettledShadow.length} wins`}
          />
          <StatCard
            label="Staked P/L"
            value={`${shadowPnlStaked >= 0 ? "+" : ""}${shadowPnlStaked.toFixed(2)}u`}
            tone={shadowPnlStaked >= 0 ? "text-emerald-300" : "text-rose-300"}
          />
          <StatCard
            label="Current Avg CLV"
            value={avgClv !== null ? `${avgClv >= 0 ? "+" : ""}${avgClv.toFixed(1)}%` : "-"}
            tone={avgClv !== null ? (avgClv >= 0 ? "text-emerald-300" : "text-rose-300") : undefined}
          />
        </section>

        <SectionCard
          collapsible
          defaultOpen
          title="Legacy Team Shots V3 Control"
          subtitle="Frozen comparison lane | canonical_form_v3_ema20_nb | retained so v4 can be judged against its predecessor"
        >
          {teamShotsV3PromotionCheck || teamShotsV3Lane ? (
            <>
              <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-6">
                <StatCard
                  label="Research state"
                  value={teamShotsV3Lane?.state ?? (teamShotsV3PromotionCheck?.research_lane_ready_all_leagues ? "research_all_leagues" : "unknown")}
                  tone={statTone(teamShotsV3PromotionCheck?.research_lane_ready_all_leagues ? "green" : "amber")}
                  detail={formatModelName(teamShotsV3Lane?.model ?? teamShotsV3AllowedConfig?.model ?? "canonical_form_v3_ema20_nb")}
                />
                <StatCard
                  label="Allowed leagues"
                  value={`${teamShotsV3AllowedLeagues.length}/5`}
                  tone={statTone(teamShotsV3AllowedLeagues.length === 5 ? "green" : "amber")}
                  detail={formatLeagueList(teamShotsV3AllowedLeagues)}
                />
                <StatCard
                  label="Canonical-only"
                  value={teamShotsV3PromotionCheck?.canonical_only?.hard_block || teamShotsV3AllowedConfig?.canonical_only_allowed === false ? "blocked" : "allowed"}
                  tone={statTone(teamShotsV3PromotionCheck?.canonical_only?.hard_block || teamShotsV3AllowedConfig?.canonical_only_allowed === false ? "amber" : "green")}
                  detail={teamShotsV3PromotionCheck?.canonical_only?.n !== undefined ? `${teamShotsV3PromotionCheck.canonical_only.n.toLocaleString("en-GB")} rows not published` : "guard active"}
                />
                <StatCard
                  label="Open V3 picks"
                  value={String(teamShotsV3PendingPicks.length)}
                  tone={statTone(teamShotsV3PendingPicks.length > 0 ? "green" : "default")}
                  detail={`${teamShotsV3Summary.settled} settled | ${teamShotsV3Summary.total} active`}
                />
                <StatCard
                  label="W / L"
                  value={`${teamShotsV3Summary.won}W / ${teamShotsV3Summary.lost}L`}
                  tone={statTone(teamShotsV3Summary.won >= teamShotsV3Summary.lost ? "green" : "red")}
                  detail={`${teamShotsV3Summary.pushed} push | ${teamShotsV3Summary.pending} open`}
                />
                <StatCard
                  label="P&L flat"
                  value={formatUnits(teamShotsV3Summary.pnl)}
                  tone={statTone(teamShotsV3Summary.pnl > 0 ? "green" : teamShotsV3Summary.pnl < 0 ? "red" : "default")}
                  detail="1u per published pick"
                />
                <StatCard
                  label="ROI flat"
                  value={teamShotsV3Summary.roi !== null ? formatSignedPercent(teamShotsV3Summary.roi) : "-"}
                  tone={statTone(
                    teamShotsV3Summary.roi === null
                      ? "default"
                      : teamShotsV3Summary.roi > 0
                        ? "green"
                        : teamShotsV3Summary.roi < 0
                          ? "red"
                          : "default",
                  )}
                  detail={teamShotsV3Summary.winRate !== null ? `${teamShotsV3Summary.winRate.toFixed(0)}% win rate` : undefined}
                />
                <StatCard
                  label="Avg CLV"
                  value={teamShotsV3Clv.avgClv}
                  tone={teamShotsV3Clv.avgClv.startsWith("+") ? "text-emerald-300" : teamShotsV3Clv.avgClv.startsWith("-") ? "text-rose-300" : undefined}
                  detail={teamShotsV3GuardBlockedPicks.length > 0 ? `${teamShotsV3GuardBlockedPicks.length} guard-blocked` : undefined}
                />
                <StatCard
                  label="Last gate"
                  value={teamShotsV3Lane?.last_segment_gate_run ? formatRelativeAgeShort(teamShotsV3Lane.last_segment_gate_run, renderReferenceMillis) : "-"}
                  detail={teamShotsV3Lane?.last_segment_gate_run ? formatDateTime(teamShotsV3Lane.last_segment_gate_run) : undefined}
                />
              </div>

              <div className="mt-3 grid gap-2.5 md:grid-cols-2">
                {teamShotsV3SideRows.map(({ side, label, summary, clv }) => (
                  <div
                    key={side}
                    className={`rounded-xl border px-3 py-3 ${
                      side === "over"
                        ? "border-emerald-500/20 bg-emerald-500/8"
                        : "border-sky-500/20 bg-sky-500/8"
                    }`}
                  >
                    <div className="flex items-center justify-between gap-2">
                      <div>
                        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                          Side split
                        </div>
                        <div className="mt-1 text-sm font-semibold text-slate-100">{label}</div>
                      </div>
                      <StatusPill
                        label={side.toUpperCase()}
                        tone={side === "over"
                          ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                          : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                      />
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-4">
                      <div>
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Settled</div>
                        <div className="mt-0.5 font-mono text-slate-200">{summary.settled}/{summary.total}</div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">W-L-P</div>
                        <div className="mt-0.5 font-mono text-slate-200">{summary.won}-{summary.lost}-{summary.pushed}</div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">ROI</div>
                        <div className={`mt-0.5 font-mono ${summary.roi !== null && summary.roi >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {summary.roi !== null ? formatSignedPercent(summary.roi) : "-"}
                        </div>
                      </div>
                      <div>
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">CLV</div>
                        <div className={`mt-0.5 font-mono ${clv.avg !== null && clv.avg >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {clv.avg !== null ? `${formatSignedPercent(clv.avg)} (${clv.n})` : "-"}
                        </div>
                      </div>
                    </div>
                    <div className={`mt-2 text-xs ${summary.pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                      {formatUnits(summary.pnl)} flat P&L | {summary.pending} open
                    </div>
                  </div>
                ))}
              </div>

              <div className="mt-3 rounded-xl border border-emerald-500/20 bg-emerald-500/8 px-3 py-2 text-xs text-emerald-100">
                V3 EMA20 is the only active team-shots model shown here. Superseded v1/v2 diagnostics are retired from the monitor; canonical-only fixtures remain blocked.
                {teamShotsV3Lane?.next_action ? ` Next action: ${teamShotsV3Lane.next_action}` : ""}
              </div>

              {teamShotsV3LeagueRows.length > 0 ? (
                <div className="mt-3 overflow-x-auto rounded-xl border border-slate-800/60 bg-slate-950/30">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                        <th className="py-2.5 pl-4 pr-3">League</th>
                        <th className="py-2.5 pr-3 font-mono">N</th>
                        <th className="py-2.5 pr-3 font-mono">Current MAE</th>
                        <th className="py-2.5 pr-3 font-mono">V3 MAE</th>
                        <th className="py-2.5 pr-3 font-mono">Improve</th>
                        <th className="py-2.5 pr-4">Gate</th>
                      </tr>
                    </thead>
                    <tbody>
                      {teamShotsV3LeagueRows.map((row) => {
                        const last90 = row.last_90_common;
                        const passes = Boolean(last90?.count_ok && last90?.brier_ok && last90?.log_loss_ok);
                        const improvement = finiteNumber(last90?.improvement_pct);
                        return (
                          <tr key={row.league ?? "unknown"} className="border-b border-slate-800/40">
                            <td className="py-2 pl-4 pr-3 text-slate-200">{leagueTitle(row.league ?? "")}</td>
                            <td className="py-2 pr-3 font-mono tabular-nums text-slate-400">{last90?.n ?? "-"}</td>
                            <td className="py-2 pr-3 font-mono tabular-nums text-slate-300">{formatDiagnosticMetric(last90?.current_mae)}</td>
                            <td className="py-2 pr-3 font-mono tabular-nums text-emerald-300">{formatDiagnosticMetric(last90?.canonical_mae)}</td>
                            <td className="py-2 pr-3 font-mono tabular-nums text-emerald-300">
                              {improvement === null ? "-" : `+${(improvement * 100).toFixed(1)}%`}
                            </td>
                            <td className="py-2 pr-4">
                              <StatusPill
                                label={passes ? "PASS" : "HOLD"}
                                tone={passes
                                  ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                                  : "bg-rose-500/10 text-rose-300 border-rose-500/20"}
                              />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}

              {teamShotsV3BlockedLeagues.length > 0 ? (
                <p className="mt-3 text-xs text-amber-200">
                  Blocked leagues: {formatLeagueList(teamShotsV3BlockedLeagues)}
                </p>
              ) : null}

              {teamShotsV3RecentSettledPicks.length > 0 ? (
                <div className="mt-3 overflow-x-auto rounded-xl border border-slate-800/60 bg-slate-950/30">
                  <div className="border-b border-slate-800 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                    Recent Team Shots V3 EMA20 Settled
                  </div>
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                        <th className="py-2.5 pl-4 pr-3">Result</th>
                        <th className="py-2.5 pr-3">Match</th>
                        <th className="py-2.5 pr-3">Team / pick</th>
                        <th className="py-2.5 pr-3 font-mono">Actual</th>
                        <th className="py-2.5 pr-3 font-mono">P&L</th>
                        <th className="py-2.5 pr-4">Settled</th>
                      </tr>
                    </thead>
                    <tbody>
                      {teamShotsV3RecentSettledPicks.map((row, index) => {
                        const result = researchResult(row);
                        const pnl = pf(row.pnl_units, 0);
                        return (
                          <tr key={`${row.pick_id || row.match_id || index}-settled`} className="border-b border-slate-800/40">
                            <td className="py-2 pl-4 pr-3">
                              <StatusPill
                                label={result.toUpperCase()}
                                tone={result === "won"
                                  ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                                  : result === "lost"
                                    ? "bg-rose-500/10 text-rose-300 border-rose-500/20"
                                    : "bg-slate-700/30 text-slate-300 border-slate-600/30"}
                              />
                            </td>
                            <td className="py-2 pr-3">
                              <MatchLabel
                                league={row.league}
                                homeTeam={row.home_team}
                                awayTeam={row.away_team}
                                iconSize={16}
                                textClassName="text-xs text-slate-200"
                              />
                            </td>
                            <td className="py-2 pr-3 text-slate-300">
                              {row.team || "-"} {row.line || "-"} {(row.side ?? "").toUpperCase()}
                            </td>
                            <td className="py-2 pr-3 font-mono tabular-nums text-slate-300">{row.actual_team_shots || "-"}</td>
                            <td className={`py-2 pr-3 font-mono tabular-nums ${pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                              {formatUnits(pnl)}
                            </td>
                            <td className="py-2 pr-4 text-slate-500">{row.settled_at ? formatDateTime(row.settled_at) : "-"}</td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}
            </>
          ) : (
            <EmptyState message="Team-shots V3 EMA20 research state is missing from the snapshot. Rebuild the team-shots snapshot." />
          )}
        </SectionCard>

        <SectionCard
          collapsible
          defaultOpen
          title={`Team Shots V3 EMA20 Pending Picks - ${teamShotsV3PendingPicks.length}`}
          subtitle="Research-only published picks waiting for result/close. Canonical-only blocked rows are excluded."
        >
          {teamShotsV3PendingPicks.length > 0 ? (
            <div className="grid gap-3 xl:grid-cols-2">
              {teamShotsV3PendingPicks.map((row, index) => {
                const publicationOdds = maybeFloat(row.book_price_at_publication);
                const modelFair = maybeFloat(row.model_fair_odds);
                const modelProb = maybeFloat(row.model_implied_prob);
                const edgePct =
                  publicationOdds !== null && modelProb !== null
                    ? evEdgePct(modelProb, publicationOdds)
                    : null;
                return (
                  <div key={`${row.pick_id || row.match_id || index}`} className="rounded-2xl border border-emerald-500/20 bg-emerald-500/8 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">
                          Team Shots V3 EMA20 open
                        </div>
                        <div className="mt-1">
                          <MatchLabel
                            league={row.league}
                            homeTeam={row.home_team}
                            awayTeam={row.away_team}
                            iconSize={18}
                            textClassName="text-sm font-medium text-slate-100"
                          />
                        </div>
                        <div className="mt-1 flex flex-wrap items-center gap-2 text-[11px] text-slate-500">
                          <TeamLabel
                            league={row.league}
                            team={row.team}
                            iconSize={14}
                            teamClassName="text-[11px] text-slate-400"
                          />
                          <span>{row.kickoff_utc ? formatDateTime(row.kickoff_utc) : row.match_date || "-"}</span>
                        </div>
                      </div>
                      <StatusPill
                        label={`${row.line || "-"} ${(row.side ?? "").toUpperCase()}`}
                        tone={row.side === "over"
                          ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                          : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                      />
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Book</div>
                        <div className="mt-0.5 text-slate-300">{row.bookmaker || "-"}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Entry odds</div>
                        <div className="mt-0.5 font-mono text-slate-200">{publicationOdds !== null ? publicationOdds.toFixed(2) : "-"}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Model fair</div>
                        <div className="mt-0.5 font-mono text-slate-200">{modelFair !== null ? modelFair.toFixed(2) : "-"}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Entry edge</div>
                        <div className={`mt-0.5 font-mono ${edgePct !== null && edgePct >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {edgePct !== null ? formatSignedPercent(edgePct) : "-"}
                        </div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Published</div>
                        <div className="mt-0.5 text-slate-300">{row.published_at_utc ? formatDateTime(row.published_at_utc) : "-"}</div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          ) : (
            <EmptyState message="No Team Shots V3 EMA20 pending research picks right now. The board will fill automatically once the V3 publisher writes open rows into the CLV monitor." />
          )}
        </SectionCard>

        {/* Recent settled shadow bets */}
        {recentSettledShadow.length > 0 ? (
          <SectionCard
            collapsible
            title={`Current policy settled bets - ${activeSettledShadow.length} total`}
            subtitle={`Last ${recentSettledShadow.length} results`}
          >
            {/* Mobile cards */}
            <div className="space-y-2 lg:hidden">
              {recentSettledShadow.map((r, i) => {
                const rowTone =
                  r.result === "won" ? "bg-emerald-950/25" :
                  r.result === "lost" ? "bg-rose-950/25" : "";
                const pnlVal = pf(r.pnl);
                const edgeRaw = pf(r.edge, Number.NaN);
                const clvRaw = r.clv && r.clv.trim() ? pf(r.clv, Number.NaN) : Number.NaN;
                return (
                  <div key={i} className={`rounded-xl border border-slate-800/60 px-3 py-3 ${rowTone}`}>
                    <div className="flex items-start justify-between gap-2">
                      <div className="min-w-0">
                        <TeamLabel
                          league={r.league}
                          team={r.team}
                          iconSize={18}
                          teamClassName="truncate text-sm font-medium text-white"
                        />
                        <div className="mt-1">
                          <MatchLabel
                            league={r.league}
                            homeTeam={r.home_team}
                            awayTeam={r.away_team}
                            iconSize={16}
                            separator="v"
                            textClassName="text-[11px] text-slate-500"
                          />
                        </div>
                        <div className="text-[11px] text-slate-600">{(r.date ?? "").slice(0, 10)}</div>
                        <div className="text-[11px] text-slate-500">
                          {r.side === "over" ? "Over" : "Under"} {r.line || "-"}
                        </div>
                        {r.settled_at ? (
                          <div className="text-[11px] text-slate-500">Settled {formatDateTime(r.settled_at)}</div>
                        ) : null}
                      </div>
                      <div className="flex flex-col items-end gap-1">
                        <StatusPill
                          label={r.side === "over" ? "Over" : "Under"}
                          tone={r.side === "over"
                            ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                            : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                        />
                        <StatusPill
                          label={r.result ?? "-"}
                          tone={r.result === "won"
                            ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                            : r.result === "lost"
                            ? "bg-rose-500/10 text-rose-300 border-rose-500/20"
                            : "bg-slate-700/40 text-slate-400 border-slate-600/40"}
                        />
                      </div>
                    </div>
                    <div className="mt-2 grid grid-cols-2 gap-1 sm:grid-cols-5">
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Entry</div>
                        <div className="mt-0.5 font-mono text-xs text-slate-200">{r.book_odds || "-"}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Fair</div>
                        <div className="mt-0.5 font-mono text-xs text-slate-200">{r.model_fair_odds || "-"}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Edge</div>
                        <div className={`mt-0.5 font-mono text-xs ${!Number.isNaN(edgeRaw) && edgeRaw >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {!Number.isNaN(edgeRaw) ? formatSignedPercent(edgeRaw * 100) : "-"}
                        </div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">P&L</div>
                        <div className={`mt-0.5 font-mono text-xs ${pnlVal >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {`${pnlVal >= 0 ? "+" : ""}${pnlVal.toFixed(2)}u`}
                        </div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Stake</div>
                        <div className="mt-0.5 font-mono text-xs text-amber-200">
                          {`${pf(r.stake_units || "1", 1).toFixed(1)}u`}
                        </div>
                      </div>
                    </div>
                    {!Number.isNaN(clvRaw) ? (
                      <div className="mt-1.5 text-[11px] text-slate-500">
                        CLV{" "}
                        <span className={clvRaw >= 0 ? "text-emerald-400" : "text-rose-400"}>
                          {formatSignedPercent(clvRaw * 100)}
                        </span>
                      </div>
                    ) : null}
                  </div>
                );
              })}
            </div>
            {/* Desktop table */}
            <div className="hidden overflow-x-auto rounded-xl border border-slate-800/60 bg-slate-950/30 lg:block">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                    <th className="py-2.5 pl-4 pr-3">Date</th>
                    <th className="py-2.5 pr-3">Team / Match</th>
                    <th className="py-2.5 pr-3">Line</th>
                    <th className="py-2.5 pr-3">Side</th>
                    <th className="py-2.5 pr-3">Result</th>
                    <th className="py-2.5 pr-3 font-mono">Entry</th>
                    <th className="py-2.5 pr-3 font-mono">Fair</th>
                    <th className="py-2.5 pr-3 font-mono">Edge</th>
                    <th className="py-2.5 pr-3 font-mono">Stake</th>
                    <th className="py-2.5 pr-3 font-mono">P&L</th>
                    <th className="py-2.5 pr-4 font-mono">CLV</th>
                  </tr>
                </thead>
                <tbody>
                  {recentSettledShadow.map((r, i) => {
                    const rowTone =
                      r.result === "won" ? "bg-emerald-950/25" :
                      r.result === "lost" ? "bg-rose-950/25" : "";
                    const pnlVal = pf(r.pnl);
                    const edgeRaw = pf(r.edge, Number.NaN);
                    const clvRaw = r.clv && r.clv.trim() ? pf(r.clv, Number.NaN) : Number.NaN;
                    return (
                      <tr key={i} className={`border-b border-slate-800/40 ${rowTone}`}>
                        <td className="py-2 pl-4 pr-3 tabular-nums text-slate-400">{(r.date ?? "").slice(0, 10)}</td>
                        <td className="py-2 pr-3">
                          <TeamLabel
                            league={r.league}
                            team={r.team}
                            iconSize={18}
                            teamClassName="font-medium text-slate-200"
                          />
                          <div className="mt-1">
                            <MatchLabel
                              league={r.league}
                              homeTeam={r.home_team}
                              awayTeam={r.away_team}
                              iconSize={16}
                              separator="v"
                              textClassName="text-[11px] text-slate-500"
                            />
                          </div>
                          {r.settled_at ? (
                            <div className="text-[11px] text-slate-600">Settled {formatDateTime(r.settled_at)}</div>
                          ) : null}
                        </td>
                        <td className="py-2 pr-3">
                          <div className="font-mono tabular-nums text-slate-200">{r.line || "-"}</div>
                        </td>
                        <td className="py-2 pr-3">
                          <StatusPill
                            label={r.side === "over" ? "Over" : "Under"}
                            tone={r.side === "over"
                              ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                              : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                          />
                        </td>
                        <td className="py-2 pr-3">
                          <StatusPill
                            label={r.result ?? "-"}
                            tone={r.result === "won"
                              ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                              : r.result === "lost"
                              ? "bg-rose-500/10 text-rose-300 border-rose-500/20"
                              : "bg-slate-700/40 text-slate-400 border-slate-600/40"}
                          />
                        </td>
                        <td className="py-2 pr-3 font-mono tabular-nums text-slate-200">{r.book_odds || "-"}</td>
                        <td className="py-2 pr-3 font-mono tabular-nums text-slate-400">{r.model_fair_odds || "-"}</td>
                        <td className={`py-2 pr-3 font-mono tabular-nums ${!Number.isNaN(edgeRaw) && edgeRaw >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {!Number.isNaN(edgeRaw) ? formatSignedPercent(edgeRaw * 100) : "-"}
                        </td>
                        <td className="py-2 pr-3 font-mono tabular-nums text-amber-200">
                          {`${pf(r.stake_units || "1", 1).toFixed(1)}u`}
                        </td>
                        <td className={`py-2 pr-3 font-mono tabular-nums ${pnlVal >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {`${pnlVal >= 0 ? "+" : ""}${pnlVal.toFixed(2)}u`}
                        </td>
                        <td className={`py-2 pr-4 font-mono tabular-nums ${!Number.isNaN(clvRaw) ? (clvRaw >= 0 ? "text-emerald-300" : "text-rose-300") : "text-slate-500"}`}>
                          {!Number.isNaN(clvRaw) ? formatSignedPercent(clvRaw * 100) : "-"}
                        </td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </SectionCard>
        ) : null}

        {/* Pending shadow bets */}
        {pendingShadowRows.length > 0 ? (
          <SectionCard
            collapsible
            title={`Current policy pending bets - ${pendingShadowRows.length} total`}
            subtitle={`${pendingUpcomingCount} upcoming | ${pendingAwaitingCount} awaiting result`}
          >
            <div className="space-y-2">
              {pendingDateKeys.map((dateKey) => {
                const rows = pendingRowsByDate.get(dateKey) ?? [];
                return (
                  <details key={dateKey} open={dateKey === defaultOpenPendingDate} className="group">
                    <summary className="flex cursor-pointer select-none list-none items-center justify-between rounded-lg border border-slate-800/60 bg-slate-900/40 px-3 py-2 text-xs text-slate-400 hover:text-slate-200 marker:hidden">
                      <span className="font-medium">{dateKey}</span>
                      <span className="text-slate-600">{rows.length} bet{rows.length !== 1 ? "s" : ""}</span>
                    </summary>
                    <div className="mt-1 space-y-1.5">
                      {rows.map((row, j) => {
                        const edgePct = row.entryEdgePct;
                        const curEdge = row.exactLineAvailable ? row.currentEdgePct : null;
                        const deltaOdds = row.delta;
                        return (
                          <div key={j} className="rounded-xl border border-slate-800/60 bg-slate-950/40 px-3 py-3">
                            <div className="flex items-start justify-between gap-2">
                              <div className="min-w-0">
                                <TeamLabel
                                  league={row.league}
                                  team={row.team}
                                  iconSize={18}
                                  teamClassName="truncate text-sm font-medium text-white"
                                />
                                <div className="mt-1">
                                  <MatchLabel
                                    league={row.league}
                                    homeTeam={row.home_team}
                                    awayTeam={row.away_team}
                                    iconSize={16}
                                    separator="v"
                                    textClassName="text-[11px] text-slate-500"
                                  />
                                </div>
                              </div>
                              <div className="flex flex-col items-end gap-1">
                                <StatusPill
                                  label={row.side === "over" ? "Over" : "Under"}
                                  tone={row.side === "over"
                                    ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                                    : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                                />
                                <StatusPill
                                  label={row.pendingState}
                                  tone={row.pendingState === "upcoming"
                                    ? "bg-amber-500/10 text-amber-300 border-amber-500/20"
                                    : "bg-cyan-500/10 text-cyan-300 border-cyan-500/20"}
                                />
                              </div>
                            </div>
                            <div className="mt-2 grid grid-cols-2 gap-1 sm:grid-cols-4 xl:grid-cols-8">
                              <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Book</div>
                                <div className="mt-0.5 text-xs text-slate-300">
                                  {row.bookmaker} {row.line} {row.side === "over" ? "O" : "U"}
                                </div>
                              </div>
                              <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Entry odds</div>
                                <div className="mt-0.5 font-mono text-xs text-slate-200">{row.book_odds || "-"}</div>
                              </div>
                              <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Entry edge</div>
                                <div className={`mt-0.5 font-mono text-xs ${edgePct !== null && edgePct >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                                  {edgePct !== null ? formatSignedPercent(edgePct) : "-"}
                                </div>
                              </div>
                              <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Now market</div>
                                <div className="mt-0.5 text-xs text-slate-300">
                                  {row.currentLine && row.currentBookmaker
                                    ? `${row.currentBookmaker} ${row.currentLine} ${row.side === "over" ? "O" : "U"}`
                                    : "-"}
                                </div>
                                <div className={`mt-1 text-[10px] ${row.lineMoved ? "text-amber-400" : "text-slate-500"}`}>
                                  {row.lineMoved ? "moved line" : row.exactLineAvailable ? "tracked line" : "not quoted"}
                                </div>
                              </div>
                              <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Now odds</div>
                                <div className="mt-0.5 font-mono text-xs text-slate-200">
                                  {row.currentOdds !== null ? row.currentOdds.toFixed(2) : "-"}
                                  {row.exactLineAvailable && deltaOdds !== null ? (
                                    <span className={`ml-1 ${deltaOdds > 0 ? "text-emerald-300" : deltaOdds < 0 ? "text-rose-300" : "text-slate-500"}`}>
                                      ({deltaOdds > 0 ? "+" : deltaOdds < 0 ? "-" : ""}{Math.abs(deltaOdds).toFixed(2)})
                                    </span>
                                  ) : null}
                                </div>
                              </div>
                              <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Now fair</div>
                                <div className="mt-0.5 font-mono text-xs text-slate-200">
                                  {row.currentFairOdds !== null ? row.currentFairOdds.toFixed(2) : "-"}
                                </div>
                                {row.currentFairOdds !== null ? (
                                  <div className={`mt-1 text-[10px] ${row.lineMoved ? "text-amber-400" : "text-slate-500"}`}>
                                    {row.lineMoved ? "adjacent line fair" : "tracked line fair"}
                                  </div>
                                ) : null}
                              </div>
                              <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Now edge</div>
                                <div className={`mt-0.5 font-mono text-xs ${curEdge !== null && curEdge >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                                  {curEdge !== null ? formatSignedPercent(curEdge) : "-"}
                                </div>
                                {row.lineMoved ? (
                                  <div className="mt-1 text-[10px] text-amber-400">
                                    suppressed for moved line
                                  </div>
                                ) : null}
                              </div>
                              <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Stake</div>
                                <div className="mt-0.5 font-mono text-xs text-amber-200">
                                  {`${pf(row.stake_units || "1", 1).toFixed(1)}u`}
                                </div>
                              </div>
                            </div>
                            {row.lineMoved ? (
                              <p className="mt-1.5 text-[11px] text-amber-400">
                                Tracked line {row.line} {row.side === "over" ? "O" : "U"} disappeared. Latest quoted market: {row.currentBookmaker} {row.currentLine} {row.side === "over" ? "O" : "U"}{row.currentOdds !== null ? ` @ ${row.currentOdds.toFixed(2)}` : ""}
                              </p>
                            ) : (!row.exactLineAvailable && !row.currentLine) ? (
                              <p className="mt-1.5 text-[11px] text-rose-400">
                                Tracked line {row.line} {row.side === "over" ? "O" : "U"} is no longer quoted and no nearby same-book line is currently available.
                              </p>
                            ) : null}
                          </div>
                        );
                      })}
                    </div>
                  </details>
                );
              })}
            </div>
          </SectionCard>
        ) : null}

        {/* -- No upcoming warning -- */}
        {upcomingLeagueKeys.length === 0 && predictionCount === 0 ? (
          <SectionCard title="Upcoming Fixtures">
            <EmptyState message="No upcoming fixture data yet." />
          </SectionCard>
        ) : null}

        {/* -- Upcoming by league (with live line tables) -- */}
        {upcomingLeagueKeys.map((leagueKey) => {
          const rows = upcomingByLeague.get(leagueKey) ?? [];
          const shadowCount = shadowCountByLeague.get(leagueKey) ?? 0;
          return (
            <SectionCard
              key={leagueKey}
              collapsible
              defaultOpen={shadowCount > 0}
              title={<LeagueLabel league={leagueKey} label={leagueTitle(leagueKey)} className="text-[15px] font-semibold text-slate-100" iconSize={16} />}
              subtitle={`${rows.length} fixture${rows.length !== 1 ? "s" : ""}${shadowCount > 0 ? ` | ${shadowCount} shadow signal${shadowCount !== 1 ? "s" : ""}` : ""}`}
            >
              <div className="space-y-4">
                {rows.map((row, rowIdx) => {
                  const date = (row.kickoff_iso ?? "").slice(0, 10);
                  const homeKey = `${matchKey(date, row.home_team, row.away_team)}|${normalizeTeamName(row.home_team)}`;
                  const awayKey = `${matchKey(date, row.home_team, row.away_team)}|${normalizeTeamName(row.away_team)}`;
                  const homeLines = [...(liveOddsByMatchTeam.get(homeKey)?.values() ?? [])];
                  const awayLines = [...(liveOddsByMatchTeam.get(awayKey)?.values() ?? [])];
                  const bestHome = bestLineSummary(homeLines, row, "home", calibrationParams, true);
                  const bestAway = bestLineSummary(awayLines, row, "away", calibrationParams, true);
                  const hasShadow =
                    bestHome !== "No shadow-qualified line" || bestAway !== "No shadow-qualified line";
                  return (
                    <div key={rowIdx} className="rounded-2xl border border-slate-800 bg-slate-900/30 p-4">
                      <div className="mb-3 flex flex-wrap items-center justify-between gap-2">
                        <div>
                          <LeagueLabel
                            league={leagueKey}
                            label={leagueTitle(leagueKey)}
                            className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600"
                            iconSize={14}
                          />
                          <div className="mt-0.5">
                            <MatchLabel
                              league={leagueKey}
                              homeTeam={row.home_team}
                              awayTeam={row.away_team}
                              iconSize={18}
                              separator="v"
                              textClassName="text-sm font-medium text-white"
                            />
                          </div>
                          <div className="text-[11px] text-slate-500">{formatKickoffUtc(row.kickoff_iso)}</div>
                        </div>
                      {hasShadow ? (
                          <StatusPill
                            label="shadow signal"
                            tone="bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                          />
                        ) : null}
                      </div>
                      <LambdaTrustPanel leagueKey={leagueKey} row={row} />
                      <div className="grid gap-3 sm:grid-cols-2">
                        <LiveLineTable
                          leagueKey={leagueKey}
                          teamName={row.home_team}
                          row={row}
                          side="home"
                          lines={homeLines}
                          calibration={calibrationParams}
                        />
                        <LiveLineTable
                          leagueKey={leagueKey}
                          teamName={row.away_team}
                          row={row}
                          side="away"
                          lines={awayLines}
                          calibration={calibrationParams}
                        />
                      </div>
                    </div>
                  );
                })}
              </div>
            </SectionCard>
          );
        })}

        {/* -- Book odds archive -- */}
        {oddsArchive.length > 0 ? (
          <SectionCard
            collapsible
            defaultOpen={false}
            title="Book Odds Archive"
            subtitle={`${oddsArchive.length} rows`}
          >
            <div className="overflow-x-auto rounded-xl border border-slate-800/60 bg-slate-950/30">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                    <th className="py-2.5 pl-4 pr-3">Date</th>
                    <th className="py-2.5 pr-3">Match</th>
                    <th className="py-2.5 pr-3">Team</th>
                    <th className="py-2.5 pr-3">Bookmaker</th>
                    <th className="py-2.5 pr-3 font-mono">Line</th>
                    <th className="py-2.5 pr-3">Side</th>
                    <th className="py-2.5 pr-3 font-mono">Odds</th>
                    <th className="py-2.5 pr-4">Captured</th>
                  </tr>
                </thead>
                <tbody>
                  {oddsArchive.slice(0, 200).map((r, i) => (
                    <tr key={i} className="border-b border-slate-800/40">
                      <td className="py-1.5 pl-4 pr-3 tabular-nums text-slate-400">
                        {(r.match_date || r.kickoff_at || "").slice(0, 10)}
                      </td>
                      <td className="py-1.5 pr-3 text-slate-300">{r.home_team} v {r.away_team}</td>
                      <td className="py-1.5 pr-3 text-slate-200">{r.team}</td>
                      <td className="py-1.5 pr-3 text-slate-400">{r.bookmaker}</td>
                      <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-200">{r.line}</td>
                      <td className="py-1.5 pr-3">
                        <StatusPill
                          label={(r.side ?? "").toLowerCase() === "over" ? "O" : "U"}
                          tone={(r.side ?? "").toLowerCase() === "over"
                            ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                            : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                        />
                      </td>
                      <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-200">{r.odds_decimal || "-"}</td>
                      <td className="py-1.5 pr-4 text-slate-400">
                        {r.captured_at ? formatRelativeAgeShort(r.captured_at, renderReferenceMillis) : "-"}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        ) : null}

        {/* -- Diagnostics -- */}
        {shadowPerformanceTxt ? (
          <SectionCard collapsible defaultOpen={false} title="Raw shadow performance file" subtitle="Combined tracker output | team-shots-shadow-performance.txt">
            <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-[11px] leading-relaxed text-slate-300 whitespace-pre">
              {shadowPerformanceTxt}
            </pre>
          </SectionCard>
        ) : null}

        {comparisonTxt ? (
          <SectionCard collapsible defaultOpen={false} title="Comparison Report" subtitle="team-shots-comparison.txt">
            <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-[11px] leading-relaxed text-slate-300 whitespace-pre">
              {comparisonTxt}
            </pre>
          </SectionCard>
        ) : null}

        {calibrationTxt ? (
          <SectionCard collapsible defaultOpen={false} title="Calibration Report" subtitle="team-shots-calibration.txt">
            <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-[11px] leading-relaxed text-slate-300 whitespace-pre">
              {calibrationTxt}
            </pre>
          </SectionCard>
        ) : null}

        {backtestReportTxt ? (
          <SectionCard collapsible defaultOpen={false} title="Backtest Report" subtitle="team-shots-backtest-report.txt">
            <pre className="overflow-x-auto rounded-xl border border-slate-800 bg-slate-950/40 p-4 text-[11px] leading-relaxed text-slate-300 whitespace-pre">
              {backtestReportTxt}
            </pre>
          </SectionCard>
        ) : !hasBacktestArtifacts ? (
          <SectionCard collapsible defaultOpen={false} title="Backtest Report" subtitle="Artifacts unavailable">
            <EmptyState message="Backtest report files are missing from the current snapshot source, so no historical report can be shown here." />
          </SectionCard>
        ) : null}

        {recentPredictions.length > 0 ? (
          <SectionCard
            collapsible
            defaultOpen={false}
            title="Recent Predictions"
            subtitle={`Last ${recentPredictions.length} rows`}
          >
            <div className="overflow-x-auto rounded-xl border border-slate-800/60 bg-slate-950/30">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                    {Object.keys(recentPredictions[0] ?? {}).slice(0, 10).map((col) => (
                      <th key={col} className="py-2.5 pl-3 pr-3 font-mono">{col}</th>
                    ))}
                  </tr>
                </thead>
                <tbody>
                  {recentPredictions.slice(0, 50).map((r, i) => (
                    <tr key={i} className="border-b border-slate-800/40">
                      {Object.keys(recentPredictions[0] ?? {}).slice(0, 10).map((col) => (
                        <td key={col} className="py-1.5 pl-3 pr-3 font-mono tabular-nums text-slate-300">
                          {r[col] || "-"}
                        </td>
                      ))}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </SectionCard>
        ) : null}

      </div>
    </div>
  );
}








