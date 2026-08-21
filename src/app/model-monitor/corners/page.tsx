import { cache } from "react";
import { notFound } from "next/navigation";
import {
  readCornersLiveFile as readFile,
  readCornersLiveJson as readJson,
  readCornersLiveMtime as readKnownFileMtime,
  readCornersLiveSnapshotGeneratedAt,
  inspectCornersLiveSource,
} from "@/lib/corners-live-files";
import {
  MonitorNav,
  HeroCard,
  LeagueLabel,
  MatchLabel,
  SectionCard,
  StatCard,
  StatusPill,
  EmptyState,
} from "../shared";
import FootballVnextShadowPanel, { type FootballVnextGate } from "@/components/model-monitor/FootballVnextShadowPanel";

export const dynamic = "force-dynamic";

import { MODEL_MONITOR_ENABLED } from "../shared";

type CsvRow = Record<string, string>;
type FootballCountsGatePayload = { team_shots_v4?: FootballVnextGate; corners_v3?: FootballVnextGate };
type CurrentValueSignal = { row: CsvRow; displayDate: string; edgeValue: number };
type ConsensusState = "aligned" | "divergent" | "conflict" | "extreme";
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

type PredictionsSummary = {
  prediction_count?: number;
  recent_predictions?: CsvRow[];
};

type CornersCalibrationParams = {
  lines?: Record<string, { a?: number; b?: number }>;
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

type CornersAllowedConfig = {
  allowed_leagues?: string[];
  blocked_leagues?: string[];
  canonical_only_allowed?: boolean;
  generated_at?: string;
  model?: string;
};

type CornersTotalDiagnostic = {
  generated_at?: string;
  by_league?: Record<
    string,
    {
      n?: number;
      current_mae?: number;
      canonical_mae?: number;
      mae_delta?: number;
      canonical_bias?: number;
      current_bias?: number;
      canonical_worse_share?: number;
    }
  >;
  conclusion?: string[];
};

type CornersV4G0Fold = {
  season?: string;
  variant?: string;
  mae?: number;
  brier?: number;
};

type CornersV4G0Variant = {
  market_rows?: number;
  model_brier?: number;
  market_brier?: number;
  brier_delta?: number;
  g0a_per_line_residual?: string;
  g0b_brier?: string;
  g0_status?: string;
};

type CornersV4G0Diagnostic = {
  generated_at?: string;
  status?: string;
  samples?: { v3?: number; enriched?: number; missing?: Record<string, number> };
  folds?: CornersV4G0Fold[];
  market_g0?: { variants?: Record<string, CornersV4G0Variant> };
};

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

function normalizePinnacleTeamName(value: string | undefined): string {
  return (value ?? "").replace(/\s*\(Corners\)\s*$/i, "").trim();
}

function isAggregatePinnacleTeam(value: string | undefined): boolean {
  return /^(Home Teams|Away Teams)\s*\(\d+\s+Games\)$/i.test(normalizePinnacleTeamName(value));
}

function splitMatchTeams(match: string | undefined): [string, string] {
  const [home = "", away = ""] = (match ?? "").split(" vs ");
  return [home, away];
}

const TEAM_KEY_ALIASES: Record<string, string> = {
  "brighton and hove albion": "brighton",
  brighton: "brighton",
  "atalanta bc": "atalanta",
  atalanta: "atalanta",
  "inter milan": "inter",
  "inter milano": "inter",
  internazionale: "inter",
  inter: "inter",
  "fc st pauli": "st pauli",
  "fc st. pauli": "st pauli",
  "st pauli": "st pauli",
  "vfb stuttgart": "stuttgart",
  stuttgart: "stuttgart",
  "borussia m gladbach": "borussia monchengladbach",
  "borussia monchengladbach": "borussia monchengladbach",
  "m gladbach": "borussia monchengladbach",
  "bayer 04 leverkusen": "bayer leverkusen",
  "bayer leverkusen": "bayer leverkusen",
  "sc freiburg": "freiburg",
  freiburg: "freiburg",
  "1 fc union berlin": "union berlin",
  "union berlin": "union berlin",
  "wolverhampton wanderers": "wolverhampton",
  wolverhampton: "wolverhampton",
  "manchester united": "man united",
  "manchester utd": "man united",
  "man utd": "man united",
  "man united": "man united",
  "rayo vallecano": "vallecano",
  "rayo vallecano de madrid": "vallecano",
  "nottingham forest": "nottingham forest",
};

function normalizeTeamKey(value: string | undefined): string {
  const cleaned = normalizePinnacleTeamName(value)
    .toLowerCase()
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-z0-9]+/g, " ")
    .trim();
  return TEAM_KEY_ALIASES[cleaned] ?? cleaned;
}

function fixtureDateForRow(row: CsvRow): string {
  return (
    (row.kick_off ?? "").trim().slice(0, 10) ||
    (row.match_date ?? "").trim().slice(0, 10) ||
    (row.file_date ?? "").trim().slice(0, 10) ||
    ""
  );
}

function canonicalBetIdentity(row: CsvRow): string {
  const [homeTeam, awayTeam] = splitMatchTeams(row.match);
  return [
    (row.league ?? "").trim().toLowerCase(),
    fixtureDateForRow(row),
    normalizeTeamKey(homeTeam),
    normalizeTeamKey(awayTeam),
    (row.market ?? "").trim().toLowerCase(),
    (row.line ?? "").trim(),
    (row.side ?? "").trim().toLowerCase(),
  ].join("|");
}

function dedupeTrackedBets(rows: CsvRow[]): CsvRow[] {
  const sorted = [...rows].sort((a, b) => {
    const fileA = ((a.file_date ?? "").trim().slice(0, 10)) || "9999-99-99";
    const fileB = ((b.file_date ?? "").trim().slice(0, 10)) || "9999-99-99";
    if (fileA !== fileB) return fileA.localeCompare(fileB);
    const settledA = a.settled === "yes" ? 0 : 1;
    const settledB = b.settled === "yes" ? 0 : 1;
    if (settledA !== settledB) return settledA - settledB;
    const kickoffA = (a.kick_off ?? "").trim() ? 0 : 1;
    const kickoffB = (b.kick_off ?? "").trim() ? 0 : 1;
    if (kickoffA !== kickoffB) return kickoffA - kickoffB;
    return canonicalBetIdentity(a).localeCompare(canonicalBetIdentity(b));
  });

  const byKey = new Map<string, CsvRow>();
  for (const row of sorted) {
    const key = canonicalBetIdentity(row);
    const existing = byKey.get(key);
    if (!existing) {
      byKey.set(key, { ...row });
      continue;
    }
    for (const field of [
      "kick_off",
      "match_date",
      "closing_odds",
      "clv",
      "settled_at",
      "actual_total_corners",
      "won",
      "pnl_units",
      "pnl_staked",
    ]) {
      if (!(existing[field] ?? "").trim() && (row[field] ?? "").trim()) {
        existing[field] = row[field];
      }
    }
  }
  return [...byKey.values()];
}

function markToMarketClv(entryOdds: number, nowOdds: number | null): number | null {
  if (!nowOdds || entryOdds <= 0 || nowOdds <= 0) return null;
  return entryOdds / nowOdds - 1;
}

function probabilityEdge(modelProb: number | null, odds: number | null): number | null {
  if (!modelProb || !odds || modelProb <= 0 || odds <= 1) return null;
  return modelProb * odds - 1;
}

function fairDecimal(probability: number | null): number | null {
  if (probability === null || !Number.isFinite(probability)) return null;
  if (probability <= 0) return 999;
  if (probability >= 1) return 1.001;
  return Math.round((1 / probability) * 1000) / 1000;
}

function calibrateCornersProbability(
  rawProbability: number | null,
  line: number,
  calibrationParams?: CornersCalibrationParams | null,
): number | null {
  if (rawProbability === null || !Number.isFinite(rawProbability)) return null;
  const lineParams = calibrationParams?.lines?.[line.toFixed(1)];
  const a = lineParams?.a;
  const b = lineParams?.b;
  if (!Number.isFinite(a) || !Number.isFinite(b)) return rawProbability;
  const clamped = Math.min(1 - 1e-7, Math.max(1e-7, rawProbability));
  const logit = Math.log(clamped / (1 - clamped));
  const calibrated = 1 / (1 + Math.exp(-((a as number) * logit + (b as number))));
  return Math.min(1 - 1e-7, Math.max(1e-7, calibrated));
}

function formatKickoff(iso: string | undefined): string {
  if (!iso) return "--";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 10);
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "2-digit",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(d);
}

function formatDateTime(value?: string | null): string {
  if (!value) return "missing";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-GB", {
    timeZone: "Europe/London",
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
  const nowMs = Number.isFinite(referenceNowMs) ? (referenceNowMs as number) : Date.now();
  const diffMs = nowMs - stamp;
  if (diffMs < 0) return "just now";
  const diffMinutes = Math.round(diffMs / 60000);
  if (diffMinutes < 60) return `${diffMinutes}m ago`;
  const diffHours = Math.round(diffMinutes / 60);
  if (diffHours < 24) return `${diffHours}h ago`;
  return ">1d";
}

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

function getTodayIsoLondon(now = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(now);
  const year = parts.find((part) => part.type === "year")?.value ?? "0000";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  return `${year}-${month}-${day}`;
}

function newestTimestamp(values: Array<string | null | undefined>): string | null {
  let newestValue: string | null = null;
  let newestMs = Number.NEGATIVE_INFINITY;
  for (const value of values) {
    if (!value) continue;
    const parsed = Date.parse(value);
    if (!Number.isFinite(parsed)) continue;
    if (parsed > newestMs) {
      newestMs = parsed;
      newestValue = value;
    }
  }
  return newestValue;
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

function monitorStaleHours(): number {
  const raw = process.env.MONITOR_STALE_HOURS ?? process.env.TEAM_PROPS_MONITOR_STALE_HOURS;
  const parsed = Number.parseFloat(raw ?? "");
  return Number.isFinite(parsed) && parsed > 0 ? parsed : 18;
}

function currentServerRenderMillis(): number {
  return Date.now();
}

// Tone helper: converts the old "green"/"red"/"amber" strings to CSS class names
// used by the shared StatCard `tone` prop.
function statTone(t?: "default" | "green" | "red" | "amber"): string | undefined {
  if (!t || t === "default") return undefined;
  const map: Record<string, string> = {
    green: "text-emerald-300",
    red: "text-rose-300",
    amber: "text-amber-300",
  };
  return map[t];
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

const CURRENT_POLICY = "V3";
const RESEARCH_POLICY = "V3.1";
const VISIBLE_POLICY_ORDER = ["V3", "V3.1"] as const;
const POLICY_ORDER = ["V3", "V3.1", "V2"] as const;
const LEAGUE_ORDER = ["epl", "la-liga", "serie-a", "bundesliga", "ligue-1"] as const;

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

function groupRowsByLeague<T extends { league?: string }>(rows: T[]): Map<string, T[]> {
  const grouped = new Map<string, T[]>();
  for (const row of rows) {
    const league = (row.league ?? "").trim() || "other";
    if (!grouped.has(league)) grouped.set(league, []);
    grouped.get(league)!.push(row);
  }
  return grouped;
}

function policyVersion(row: CsvRow): string {
  const raw = (row.policy_version ?? "").trim();
  return raw || "V2";
}

function policyOrderIndex(version: string): number {
  const idx = VISIBLE_POLICY_ORDER.indexOf(version as (typeof VISIBLE_POLICY_ORDER)[number]);
  return idx === -1 ? VISIBLE_POLICY_ORDER.length : idx;
}

function policyLaneLabel(version: string): string {
  if (version === "V3") return "Official live lane";
  if (version === "V3.1") return "V3.1 research lane";
  return "Archive";
}

function policyLaneDescription(version: string): string {
  if (version === "V3") return "Current official corners picks. Stricter 15% EV threshold.";
  if (version === "V3.1") return "Research lane only. Same model family, but a looser 8% EV threshold and not official.";
  return "Older archive rows kept off the live surface.";
}

function policyShortLabel(version: string): string {
  if (version === "V3") return "Official";
  if (version === "V3.1") return "V3.1";
  return "Archive";
}

function consensusState(raw: string | undefined): ConsensusState {
  const value = (raw ?? "").trim().toLowerCase();
  if (value === "divergent" || value === "conflict" || value === "extreme") return value;
  return "aligned";
}

function consensusTone(consensus: ConsensusState): string {
  if (consensus === "extreme") return "bg-rose-500/15 text-rose-200 border-rose-500/30";
  if (consensus === "conflict") return "bg-orange-500/15 text-orange-200 border-orange-500/30";
  if (consensus === "divergent") return "bg-amber-500/15 text-amber-200 border-amber-500/30";
  return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
}

function consensusLabel(consensus: ConsensusState): string {
  if (consensus === "extreme") return "EXTREME";
  if (consensus === "conflict") return "CONFLICT";
  if (consensus === "divergent") return "DIVERGENT";
  return "ALIGNED";
}

function trustBadgeLabel(row: CsvRow): string | null {
  const consensus = consensusState(row.consensus);
  const stake = pf(row.stake, 0);
  const edge = pf(row.edge, 0);
  if (consensus === "extreme" && stake <= 0) return "SUPPRESSED";
  if (consensus === "extreme") return "EXTR -stake";
  if (consensus === "conflict" && stake > 0 && edge < 0.20) return "CONF -stake";
  if (consensus === "conflict") return "CONF";
  if (consensus === "divergent") return "DIVG";
  return null;
}

function trustBadgeTone(row: CsvRow): string {
  const consensus = consensusState(row.consensus);
  return consensusTone(consensus);
}

function pctDelta(base: number | null, recent: number | null): number | null {
  if (base === null || recent === null || base <= 0) return null;
  return (recent - base) / base;
}

function toneForDelta(delta: number | null): string {
  if (delta === null) return "text-slate-500";
  if (delta >= 0.15) return "text-emerald-300";
  if (delta <= -0.15) return "text-amber-300";
  return "text-slate-400";
}

function trendLabel(delta: number | null): string {
  if (delta === null) return "n/a";
  if (delta >= 0.15) return `? hot ${formatSignedPercent(delta * 100)}`;
  if (delta <= -0.15) return `? cold ${formatSignedPercent(delta * 100)}`;
  return formatSignedPercent(delta * 100);
}

function formatSignedPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "--";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function valueToneClass(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "text-slate-400";
  if (value > 0) return "text-emerald-300";
  if (value < 0) return "text-rose-300";
  return "text-slate-300";
}

function RecordSummary({
  won,
  lost,
  pushed = 0,
  align = "left",
}: {
  won: number;
  lost: number;
  pushed?: number;
  align?: "left" | "right";
}) {
  const justifyClass = align === "right" ? "justify-end" : "justify-start";
  return (
    <span className={`inline-flex items-center gap-1 font-mono tabular-nums ${justifyClass}`}>
      <span className="text-emerald-300">{won}W</span>
      <span className="text-slate-600">/</span>
      <span className="text-rose-300">{lost}L</span>
      {pushed > 0 ? (
        <>
          <span className="text-slate-600">/</span>
          <span className="text-slate-400">{pushed}P</span>
        </>
      ) : null}
    </span>
  );
}

type PolicySummaryRow = {
  version: string;
  tracked: number;
  settled: number;
  pending: number;
  won: number;
  lost: number;
  pushed: number;
  pnl: number;
  staked: number;
  roi: number | null;
  avgOdds: number | null;
  avgEdge: number | null;
};

function policySummaryRows(rows: CsvRow[]): PolicySummaryRow[] {
  const byVersion = new Map<string, CsvRow[]>();
  for (const version of POLICY_ORDER) {
    byVersion.set(version, []);
  }
  for (const row of rows) {
    const version = policyVersion(row);
    if (!byVersion.has(version)) byVersion.set(version, []);
    byVersion.get(version)!.push(row);
  }
  return [...byVersion.entries()]
    .map(([version, versionRows]) => {
      const settled = versionRows.filter((row) => row.settled === "yes");
      const pending = versionRows.filter((row) => row.settled !== "yes");
      const won = settled.filter((row) => row.won === "yes").length;
      const lost = settled.filter((row) => row.won === "no").length;
      const pushed = settled.filter((row) => row.won === "push").length;
      const pnl = settled.reduce((sum, row) => sum + pf(row.pnl_staked), 0);
      const staked = settled.reduce((sum, row) => sum + pf(row.stake, 1), 0);
      return {
        version,
        tracked: versionRows.length,
        settled: settled.length,
        pending: pending.length,
        won,
        lost,
        pushed,
        pnl,
        staked,
        roi: settled.length > 0 && staked > 0 ? (pnl / staked) * 100 : null,
        avgOdds: settled.length > 0 ? settled.reduce((sum, row) => sum + pf(row.bookie_odds), 0) / settled.length : null,
        avgEdge: settled.length > 0 ? settled.reduce((sum, row) => sum + pf(row.edge), 0) / settled.length * 100 : null,
      };
    })
    .sort((a, b) => {
      const orderDelta = policyOrderIndex(a.version) - policyOrderIndex(b.version);
      return orderDelta !== 0 ? orderDelta : a.version.localeCompare(b.version);
    });
}

function CornersTrustPanel({ row }: { row: CsvRow }) {
  const homeLam = maybeFloat(row.lambda_home);
  const awayLam = maybeFloat(row.lambda_away);
  const totalLam = homeLam !== null && awayLam !== null ? homeLam + awayLam : null;
  const homeRecent = maybeFloat(row.lambda_home_recent);
  const awayRecent = maybeFloat(row.lambda_away_recent);
  const recentAvailable = (homeRecent ?? 0) > 0 && (awayRecent ?? 0) > 0;
  const totalRecent = recentAvailable && homeRecent !== null && awayRecent !== null ? homeRecent + awayRecent : null;
  const divergence = maybeFloat(row.divergence) ?? 0;
  const consensus = consensusState(row.consensus);
  const homeDelta = recentAvailable ? pctDelta(homeLam, homeRecent) : null;
  const awayDelta = recentAvailable ? pctDelta(awayLam, awayRecent) : null;

  return (
    <div className="rounded-xl border border-slate-800/70 bg-slate-950/40 p-3">
      <div className="mb-2 flex flex-wrap items-center justify-between gap-2">
        <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">Lambda Trust Panel</div>
        <StatusPill label={consensusLabel(consensus)} tone={consensusTone(consensus)} />
      </div>
      <div className="grid gap-2 text-xs sm:grid-cols-[110px_repeat(3,minmax(0,1fr))]">
        <div className="text-slate-500" />
        <div className="font-mono text-slate-400">H</div>
        <div className="font-mono text-slate-400">A</div>
        <div className="font-mono text-slate-400">Total</div>
        <div className="text-slate-500">Season EMA</div>
        <div className="font-mono text-emerald-300">{homeLam?.toFixed(2) ?? "--"}</div>
        <div className="font-mono text-sky-300">{awayLam?.toFixed(2) ?? "--"}</div>
        <div className="font-mono text-amber-200">{totalLam?.toFixed(2) ?? "--"}</div>
        <div className="text-slate-500">Recent (6g)</div>
        <div className="font-mono text-emerald-200">{recentAvailable && homeRecent !== null ? homeRecent.toFixed(2) : "--"}</div>
        <div className="font-mono text-sky-200">{recentAvailable && awayRecent !== null ? awayRecent.toFixed(2) : "--"}</div>
        <div className="font-mono text-amber-100">{recentAvailable && totalRecent !== null ? totalRecent.toFixed(2) : "--"}</div>
      </div>
      <div className="mt-3 grid gap-2 text-[11px] sm:grid-cols-3">
        <div className={toneForDelta(homeDelta)}>Recent H trend: {trendLabel(homeDelta)}</div>
        <div className={toneForDelta(awayDelta)}>Recent A trend: {trendLabel(awayDelta)}</div>
        <div className={consensus === "aligned" ? "text-emerald-300" : consensus === "divergent" ? "text-amber-300" : consensus === "conflict" ? "text-orange-300" : "text-rose-300"}>
          Net divergence: {formatSignedPercent(divergence * 100)} ({consensusLabel(consensus)})
        </div>
      </div>
    </div>
  );
}

export default async function CornersMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) {
    notFound();
  }

  const [
    calibrationTxt,
    calibrationParams,
    backtestReportTxt,
    backtestCsv,
    predictionsSummary,
    pinnacleCornersCsv,
    shortlistTxt,
    valueBetsCsv,
    valueBetsV31Csv,
    signalsCsv,
    signalsV31Csv,
    settledCsv,
    livePnlTxt,
    pipelineStatus,
    researchLaneState,
    cornersAllowedConfig,
    cornersClvCsv,
    cornersClvReport,
    cornersTotalDiagnostic,
    pinnacleCornersMtime,
    shortlistMtime,
    predictionsMtime,
    snapshotGeneratedAt,
    shortlistSource,
    cornersV3ClvCsv,
    vnextCandidatesCsv,
    vnextGate,
    cornersV4G0,
    cornersV4G0Report,
  ] = await Promise.all([
      readFile("data/corners-ou/corners-ou-calibration.txt"),
      readJson<CornersCalibrationParams>("data/corners-ou/corners-calibration-params.json"),
      readFile("data/corners-ou/corners-ou-backtest-report.txt"),
      readFile("data/corners-ou/corners-ou-backtest-results.csv"),
      readJson<PredictionsSummary>("data/corners-ou/corners-monitor-summary.json"),
      readFile("data/corners-ou/pinnacle-corners-odds.csv"),
      readFile("data/shortlist/shortlist-latest.txt"),
      readFile("data/shortlist/value-bets-latest.csv"),
      readFile("data/shortlist/value-bets-latest-v31.csv"),
      readFile("data/shortlist/signals-latest.csv"),
      readFile("data/shortlist/signals-latest-v31.csv"),
      readFile("data/shortlist/settled-pnl.csv"),
      readFile("data/shortlist/corners-live-pnl.txt"),
      readJson<TeamPropsStatus>("data/shortlist/team-props-status.json"),
      readJson<ResearchLaneState>("data/football-form/research-lane-state.json"),
      readJson<CornersAllowedConfig>("data/football-form/corners-v0-allowed-leagues.json"),
      readFile("data/football-form/corners-v0-clv-monitor.csv"),
      readFile("data/football-form/corners-v0-clv-monitor.md"),
      readJson<CornersTotalDiagnostic>("data/football-form/corners-total-diagnostic.json"),
      readKnownFileMtime("data/corners-ou/pinnacle-corners-odds.csv"),
      readKnownFileMtime("data/shortlist/shortlist-latest.txt"),
      readKnownFileMtime("data/corners-ou/corners-ou-predictions.csv"),
      readCornersLiveSnapshotGeneratedAt(),
      inspectCornersLiveSource("data/shortlist/signals-latest.csv"),
      readFile("data/football-form/corners-v3-shadow-clv.csv"),
      readFile("data/football-form/football-counts-vnext-candidates.csv"),
      readJson<FootballCountsGatePayload>("data/football-form/football-counts-vnext-gate.json"),
      readJson<CornersV4G0Diagnostic>("data/corners-ou/corners-v4-g0-diagnostic.json"),
      readFile("data/corners-ou/corners-v4-g0-diagnostic.md"),
    ]);

  const backtestRows = backtestCsv ? parseCsvCached(backtestCsv) : [];
  const hasBacktestRows = backtestRows.length > 0;
  const hasBacktestArtifacts = Boolean(backtestCsv?.trim() || backtestReportTxt?.trim());
  const predictionsCsv =
    predictionsSummary ? null : await readFile("data/corners-ou/corners-ou-predictions.csv");
  const predictions = predictionsCsv ? parseCsvCached(predictionsCsv) : [];
  const predictionCount =
    typeof predictionsSummary?.prediction_count === "number"
      ? predictionsSummary.prediction_count
      : predictions.length;
  const pinnacleRows = pinnacleCornersCsv ? parseCsvCached(pinnacleCornersCsv) : [];
  const cornersV3ClvRows = cornersV3ClvCsv ? parseCsvCached(cornersV3ClvCsv) : [];
  const vnextCandidateRows = vnextCandidatesCsv ? parseCsvCached(vnextCandidatesCsv) : [];
  const valueBets = valueBetsCsv ? parseCsvCached(valueBetsCsv) : [];
  const valueBetsV31 = valueBetsV31Csv ? parseCsvCached(valueBetsV31Csv) : [];
  const signals = signalsCsv ? parseCsvCached(signalsCsv) : [];
  const signalsV31 = signalsV31Csv ? parseCsvCached(signalsV31Csv) : [];
  const settledRows = settledCsv ? parseCsvCached(settledCsv) : [];
  // Derive line values from column names so the table isn't hardcoded to 9.5/10.5
  const signalLineValues = signals.length > 0
    ? Object.keys(signals[0])
        .filter(k => k.startsWith("fair_over_"))
        .map(k => parseFloat(k.replace("fair_over_", "")))
        .filter(n => !isNaN(n))
        .sort((a, b) => a - b)
    : [9.5, 10.5];
  const buildSignalDateLookup = (rows: CsvRow[]): Map<string, CsvRow> => {
    const lookup = new Map<string, CsvRow>();
    for (const row of rows) {
      const key = `${(row.league ?? "").trim().toLowerCase()}|${normalizeTeamKey(row.home_team)}|${normalizeTeamKey(row.away_team)}`;
      lookup.set(key, row);
    }
    return lookup;
  };
  const signalDateLookup = buildSignalDateLookup(signals);
  const researchSignalDateLookup = buildSignalDateLookup(signalsV31);
  const latestPinnacleCaptureAt =
    [...pinnacleRows]
      .map((r) => r.captured_at ?? "")
      .filter(Boolean)
      .sort()
      .at(-1) ?? null;

  const collectCurrentSignals = (rows: CsvRow[], lookup: Map<string, CsvRow>): CurrentValueSignal[] => {
    const deduped = new Map<string, CurrentValueSignal>();
    for (const row of rows) {
      const [homeTeam = "", awayTeam = ""] = (row.match ?? "").split(" vs ");
      const signalKey = `${(row.league ?? "").trim().toLowerCase()}|${normalizeTeamKey(homeTeam)}|${normalizeTeamKey(awayTeam)}`;
      const signalRow = lookup.get(signalKey);
      const currentSignal: CurrentValueSignal = {
        row,
        displayDate: (signalRow?.kick_off ?? signalRow?.date ?? row.kick_off ?? "").slice(0, 10) || "-",
        edgeValue: pf(row.edge),
      };
      const dedupeKey = canonicalBetIdentity({
        ...row,
        kick_off: row.kick_off || signalRow?.kick_off || "",
        match_date: row.match_date || signalRow?.date || "",
      });
      const existing = deduped.get(dedupeKey);
      if (!existing || currentSignal.edgeValue > existing.edgeValue) {
        deduped.set(dedupeKey, currentSignal);
      }
    }
    return [...deduped.values()].sort((a, b) => b.edgeValue - a.edgeValue);
  };

  const currentValueSignalsAll = collectCurrentSignals(valueBets, signalDateLookup);
  const researchValueSignalsAll = collectCurrentSignals(valueBetsV31, researchSignalDateLookup);

  // Build grouped Pinnacle table: latest odds per match and line
  type PinnacleMatchRow = {
    match_date: string; league: string; home_team: string; away_team: string;
    lines: Record<string, { over: number; under: number }>;
  };
  const _pinnacleByMatch = new Map<string, PinnacleMatchRow>();
  for (const row of pinnacleRows) {
    if (isAggregatePinnacleTeam(row.home_team) || isAggregatePinnacleTeam(row.away_team)) continue;
    const homeTeam = normalizePinnacleTeamName(row.home_team);
    const awayTeam = normalizePinnacleTeamName(row.away_team);
    const mk = `${row.match_date}|${homeTeam.toLowerCase()}|${awayTeam.toLowerCase()}`;
    if (!_pinnacleByMatch.has(mk)) {
      _pinnacleByMatch.set(mk, {
        match_date: row.match_date ?? "",
        league: row.league ?? "",
        home_team: homeTeam,
        away_team: awayTeam,
        lines: {},
      });
    }
    const entry = _pinnacleByMatch.get(mk)!;
    const line = row.line ?? "";
    if (!entry.lines[line]) entry.lines[line] = { over: 0, under: 0 };
    if (row.side === "over") entry.lines[line].over = pf(row.odds_decimal);
    if (row.side === "under") entry.lines[line].under = pf(row.odds_decimal);
  }
  const pinnacleMatches = [..._pinnacleByMatch.values()]
    .sort((a, b) => a.match_date.localeCompare(b.match_date) || a.league.localeCompare(b.league));
  const pinnacleMatchByFixture = new Map<string, PinnacleMatchRow>();
  for (const match of pinnacleMatches) {
    const key = [
      (match.league ?? "").trim().toLowerCase(),
      (match.match_date ?? "").trim().slice(0, 10),
      normalizeTeamKey(match.home_team),
      normalizeTeamKey(match.away_team),
    ].join("|");
    pinnacleMatchByFixture.set(key, match);
  }

  // Collect all line values found across Pinnacle fixtures so the table doesn't silently drop unusual lines
  const pinnacleLineValues = [...new Set(
    pinnacleMatches.flatMap(m => Object.keys(m.lines))
  )].map(l => parseFloat(l)).filter(n => !isNaN(n)).sort((a, b) => a - b);

  // Live P&L from settlement
  const trackedRows = dedupeTrackedBets(settledRows);
  // Pending sorted by kickoff ascending (soonest game first)
  const livePending = dedupeTrackedBets(
    trackedRows.filter((r) => r.settled === "pending"),
  )
    .sort((a, b) => (a.kick_off ?? a.match_date ?? "").localeCompare(b.kick_off ?? b.match_date ?? ""));
  const trackedPendingKeys = new Set(livePending.map((row) => canonicalBetIdentity(row)));
  const currentValueSignals = currentValueSignalsAll.filter(
    (entry) =>
      policyVersion(entry.row) === CURRENT_POLICY &&
      !trackedPendingKeys.has(
        canonicalBetIdentity({
          ...entry.row,
          match_date: entry.displayDate,
        }),
      ),
  );
  const currentResearchSignals = researchValueSignalsAll.filter(
    (entry) =>
      policyVersion(entry.row) === RESEARCH_POLICY &&
      !trackedPendingKeys.has(
        canonicalBetIdentity({
          ...entry.row,
          match_date: entry.displayDate,
        }),
      ),
  );
  const currentPolicyPending = livePending.filter((row) => policyVersion(row) === CURRENT_POLICY);
  const researchPolicyPending = livePending.filter((row) => policyVersion(row) === RESEARCH_POLICY);
  const officialTrackedRows = trackedRows.filter((row) => policyVersion(row) === CURRENT_POLICY);
  const officialSettled = officialTrackedRows.filter((r) => r.settled === "yes");
  const officialWon = officialSettled.filter((r) => r.won === "yes");
  const officialLost = officialSettled.filter((r) => r.won === "no");
  const officialPushed = officialSettled.filter((r) => r.won === "push");
  const officialDecisive = officialWon.length + officialLost.length;
  const officialTotalStaked = officialSettled.reduce((s, r) => s + pf(r.stake, 1), 0);
  const officialPnlFlat = officialSettled.reduce((s, r) => s + pf(r.pnl_units), 0);
  const officialPnlStaked = officialSettled.reduce((s, r) => s + pf(r.pnl_staked), 0);
  const officialRoiFlat = officialSettled.length > 0 ? (officialPnlFlat / officialSettled.length) * 100 : 0;
  const officialRoiStaked = officialTotalStaked > 0 ? (officialPnlStaked / officialTotalStaked) * 100 : 0;
  const officialWinRate = officialDecisive > 0 ? (officialWon.length / officialDecisive) * 100 : 0;
  // Settled sorted by settled_at descending (most recently graded first), falling
  // back to kick_off / match_date for rows written before settled_at was added.
  const recentSettled = [...officialSettled]
    .sort((a, b) =>
      (b.settled_at ?? b.kick_off ?? b.match_date ?? "").localeCompare(
        a.settled_at ?? a.kick_off ?? a.match_date ?? "",
      ),
    )
    .slice(0, 12);
  const recentSettledByLeague = groupRowsByLeague(recentSettled);
  const recentSettledLeagueKeys = sortLeagueKeys([...recentSettledByLeague.keys()]);
  const signalsByLeague = groupRowsByLeague(signals);
  const signalLeagueKeys = sortLeagueKeys([...signalsByLeague.keys()]);
  const slateAsOfIso = getTodayIsoLondon();
  const currentSlateSignals = [...signals]
    .filter((row) => ((row.kick_off ?? row.date ?? "").slice(0, 10) || "1970-01-01") >= slateAsOfIso)
    .sort((a, b) => (a.kick_off ?? a.date ?? "").localeCompare(b.kick_off ?? b.date ?? ""));
  const currentSlateSignalsByLeague = groupRowsByLeague(currentSlateSignals);
  const currentSlateLeagueKeys = sortLeagueKeys([...currentSlateSignalsByLeague.keys()]);
  const versionSummaries = policySummaryRows(trackedRows).filter(
    (row) => row.version === CURRENT_POLICY || row.version === RESEARCH_POLICY,
  );
  const currentPolicySummary =
    versionSummaries.find((row) => row.version === CURRENT_POLICY) ??
    {
      version: CURRENT_POLICY,
      tracked: 0,
      settled: 0,
      pending: 0,
      won: 0,
      lost: 0,
      pushed: 0,
      pnl: 0,
      staked: 0,
      roi: null,
      avgOdds: null,
      avgEdge: null,
    };
  const latestSettledByPolicy = new Map<string, CsvRow>();
  for (const row of recentSettled) {
    const version = policyVersion(row);
    if (!latestSettledByPolicy.has(version)) {
      latestSettledByPolicy.set(version, row);
    }
  }
  const currentPolicyLatestSettled = latestSettledByPolicy.get(CURRENT_POLICY) ?? null;

  // Live P&L by league
  const leagueNames = ["serie-a", "la-liga", "bundesliga", "epl", "ligue-1"];
  const liveByLeague = leagueNames.map((lg) => {
    const rows = officialSettled.filter((r) => r.league === lg);
    const won = rows.filter((r) => r.won === "yes").length;
    const staked = rows.reduce((s, r) => s + pf(r.stake, 1), 0);
    const pnlVal = rows.reduce((s, r) => s + pf(r.pnl_staked), 0);
    const roi = staked > 0 ? (pnlVal / staked) * 100 : 0;
    return { lg, n: rows.length, won, pnlVal, roi };
  }).filter((x) => x.n > 0);

  // Build Pinnacle fixture info keyed by canonical league/date/teams.
  const pinnacleMatchInfoByFixture = new Map<string, { match_date: string; kickoff_iso: string }>();
  const pinnacleMatchInfoByTeams = new Map<string, { match_date: string; kickoff_iso: string }>();
  for (const row of pinnacleRows) {
    if (isAggregatePinnacleTeam(row.home_team) || isAggregatePinnacleTeam(row.away_team)) continue;
    const league = (row.league ?? "").trim().toLowerCase();
    const home = normalizeTeamKey(row.home_team);
    const away = normalizeTeamKey(row.away_team);
    const kickoff = (row.kickoff_iso ?? "").trim();
    const matchDate = (row.match_date ?? "").slice(0, 10);
    if (!league || !home || !away || !kickoff || !matchDate) continue;
    const fixtureKey = `${league}|${matchDate}|${home}|${away}`;
    const teamKey = `${league}|${home}|${away}`;
    if (!pinnacleMatchInfoByFixture.has(fixtureKey)) {
      pinnacleMatchInfoByFixture.set(fixtureKey, { match_date: matchDate, kickoff_iso: kickoff });
    }
    if (!pinnacleMatchInfoByTeams.has(teamKey)) {
      pinnacleMatchInfoByTeams.set(teamKey, { match_date: matchDate, kickoff_iso: kickoff });
    }
  }

  // Build current Pinnacle odds map: last pre-kickoff price per canonical fixture.
  const currentPinnacleOdds = new Map<string, number>();
  const currentPinnacleOddsTs = new Map<string, string>();
  for (const row of pinnacleRows) {
    if (isAggregatePinnacleTeam(row.home_team) || isAggregatePinnacleTeam(row.away_team)) continue;
    const league = (row.league ?? "").trim().toLowerCase();
    const home = normalizeTeamKey(row.home_team);
    const away = normalizeTeamKey(row.away_team);
    const matchDate = (row.match_date ?? "").slice(0, 10);
    const line = (row.line ?? "").trim();
    const side = (row.side ?? "").trim().toLowerCase();
    const odds = pf(row.odds_decimal);
    if (!league || !home || !away || !matchDate || !line || !side || odds <= 0) continue;
    const rowTs = row.captured_at ?? "";
    const fixtureKey = `${league}|${matchDate}|${home}|${away}`;
    const matchInfo = pinnacleMatchInfoByFixture.get(fixtureKey);
    if (matchInfo?.kickoff_iso && rowTs >= matchInfo.kickoff_iso) continue;
    for (const key of [
      `${league}|${matchDate}|${home}|${away}|${line}|${side}`,
      `${league}|__any__|${home}|${away}|${line}|${side}`,
    ]) {
      const existingTs = currentPinnacleOddsTs.get(key) ?? "";
      if (!existingTs || rowTs >= existingTs) {
        currentPinnacleOdds.set(key, odds);
        currentPinnacleOddsTs.set(key, rowTs);
      }
    }
  }

  type PinnacleInfo = { odds: number | null; kickedOff: boolean; matchDate: string | null; kickoffIso: string | null };

  function getPinnacleInfo(row: CsvRow): PinnacleInfo {
    const parts = (row.match ?? "").split(" vs ");
    if (parts.length !== 2) return { odds: null, kickedOff: false, matchDate: null, kickoffIso: null };
    const league = (row.league ?? "").trim().toLowerCase();
    const home = normalizeTeamKey(parts[0]);
    const away = normalizeTeamKey(parts[1]);
    const fixtureDate = fixtureDateForRow(row);
    const fixtureKey = `${league}|${fixtureDate}|${home}|${away}`;
    const teamKey = `${league}|${home}|${away}`;
    const matchInfo =
      pinnacleMatchInfoByFixture.get(fixtureKey) ??
      pinnacleMatchInfoByTeams.get(teamKey) ??
      null;
    const kickoffIso = matchInfo?.kickoff_iso ?? null;
    const matchDate = matchInfo?.match_date ?? null;
    const kickedOff = kickoffIso ? renderReferenceMs >= Date.parse(kickoffIso) : false;
    const line = (row.line ?? "").trim();
    const side = (row.side ?? "").trim().toLowerCase();
    const exactOddsKey = `${league}|${matchDate ?? fixtureDate}|${home}|${away}|${line}|${side}`;
    const fallbackOddsKey = `${league}|__any__|${home}|${away}|${line}|${side}`;
    const odds = currentPinnacleOdds.get(exactOddsKey) ?? currentPinnacleOdds.get(fallbackOddsKey) ?? null;
    return { odds, kickedOff, matchDate, kickoffIso };
  }

  // CLV KPI for settled bets
  const settledWithClv = officialSettled.filter((r) => r.clv && r.clv.trim() !== "");
  const avgClv = settledWithClv.length > 0
    ? settledWithClv.reduce((s, r) => s + pf(r.clv), 0) / settledWithClv.length * 100
    : null;

  const backtestPnl = backtestRows.reduce((s, r) => s + pf(r.pnl), 0);
  const backtestStaked = backtestRows.reduce((s, r) => s + pf(r.stake, 1), 0);
  const backtestWins = backtestRows.filter(
    (r) => r.won === "True" || r.won === "true",
  ).length;
  const backtestRoi =
    backtestStaked > 0 ? (backtestPnl / backtestStaked) * 100 : null;

  const schedulerHeartbeatAt =
    latestPinnacleCaptureAt ??
    pinnacleCornersMtime ??
    shortlistMtime ??
    predictionsMtime ??
    pipelineStatus?.last_successful_finished_at ??
    pipelineStatus?.updated_at ??
    null;
  const renderReferenceAt = newestTimestamp([
    schedulerHeartbeatAt,
    shortlistMtime,
    predictionsMtime,
    latestPinnacleCaptureAt,
    pinnacleCornersMtime,
    snapshotGeneratedAt,
    pipelineStatus?.last_successful_finished_at,
    pipelineStatus?.updated_at,
  ]);
  const renderReferenceMs = renderReferenceAt ? Date.parse(renderReferenceAt) : 0;
  const staleHours = monitorStaleHours();
  const realNowMillis = currentServerRenderMillis();
  const hostedSnapshotAt = shortlistSource.hostedGeneratedAt ?? null;
  const hostedSnapshotMillis = hostedSnapshotAt ? Date.parse(hostedSnapshotAt) : Number.NaN;
  const hostedSnapshotAgeHours = Number.isFinite(hostedSnapshotMillis)
    ? Math.max(0, (realNowMillis - hostedSnapshotMillis) / (60 * 60 * 1000))
    : null;
  const hostedSnapshotIsStale =
    !shortlistSource.hostedSnapshotAvailable ||
    hostedSnapshotAgeHours === null ||
    hostedSnapshotAgeHours > staleHours ||
    shortlistSource.source !== "hosted";
  const pipelineTone =
    pipelineStatus?.state === "failed"
      ? "red"
      : pipelineStatus?.warnings?.length
        ? "amber"
        : "green";
  const cornersV0Lane = findResearchLane(researchLaneState, "corners_total", "canonical_form_v0");
  const cornersV0AllowedLeagues = cornersAllowedConfig?.allowed_leagues ?? cornersV0Lane?.allowed_leagues ?? [];
  const cornersV0BlockedLeagues = cornersAllowedConfig?.blocked_leagues ?? [];
  const cornersV4Variants = cornersV4G0?.market_g0?.variants ?? {};
  const cornersV4Lean = cornersV4Variants.v4_lean_no_wide_block;
  const latestCornersV4Season = [...(cornersV4G0?.folds ?? [])]
    .map((row) => row.season ?? "")
    .filter(Boolean)
    .sort()
    .at(-1);
  const latestCornersV3Control = (cornersV4G0?.folds ?? []).find(
    (row) => row.season === latestCornersV4Season && row.variant === "v3_control",
  );
  const latestCornersV4LeanFold = (cornersV4G0?.folds ?? []).find(
    (row) => row.season === latestCornersV4Season && row.variant === "v4_lean_no_wide_block",
  );
  const cornersV4MaeDelta =
    latestCornersV3Control?.mae != null && latestCornersV4LeanFold?.mae != null
      ? latestCornersV4LeanFold.mae - latestCornersV3Control.mae
      : null;
  const cornersV0Clv = parseClvMonitorSummary(cornersClvReport);
  const cornersV0ClvRows = cornersClvCsv ? parseCsvCached(cornersClvCsv) : [];
  const cornersV0Summary = researchBetSummary(cornersV0ClvRows);
  const cornersV0SideRows = (["over", "under"] as const).map((side) => {
    const rows = cornersV0ClvRows.filter((row) => (row.side ?? "").trim().toLowerCase() === side);
    return {
      side,
      label: side === "over" ? "Overs" : "Unders",
      summary: researchBetSummary(rows),
      clv: researchAvgPublishedClvPct(rows),
    };
  });
  const cornersV0SettledPicks = cornersV0ClvRows.filter((row) =>
    researchRowIsActive(row) && isSettledResearchRow(row),
  );
  const cornersV0RecentSettledPicks = [...cornersV0SettledPicks]
    .sort((a, b) => researchRowSortKey(b).localeCompare(researchRowSortKey(a)))
    .slice(0, 8);
  const cornersV0PendingPicks = cornersV0ClvRows
    .filter((row) => {
      const result = researchResult(row);
      return (!result || result === "pending") && researchRowIsActive(row);
    })
    .sort((a, b) => (a.kickoff_utc ?? a.match_date ?? "").localeCompare(b.kickoff_utc ?? b.match_date ?? ""));
  const cornersDiagnosticRows = Object.entries(cornersTotalDiagnostic?.by_league ?? {})
    .filter(([league]) => cornersV0BlockedLeagues.includes(league))
    .sort(([a], [b]) => a.localeCompare(b));

  return (
    <div className="min-h-screen bg-[#0a0f19] px-4 py-10 text-slate-200 sm:px-6">
      <div className="mx-auto flex max-w-7xl flex-col gap-4">

        <MonitorNav current="corners" />

        <HeroCard title="Match Corners Monitor" eyebrow="Corners O/U Model">
          <span className="text-slate-300">
            V3 corners policy: pooled 20-game EMA drives the calibrated fair price; pooled 6-game recent EMA is used only as a trust and stake-adjustment layer.
          </span>
          <span className="mx-2 text-slate-700">|</span>
          <span className="text-slate-500">
            Reference odds from Pinnacle. Place on bet365 / Paddy Power if they offer the same or better price.
          </span>
        </HeroCard>

        {hostedSnapshotIsStale ? (
          <section className="rounded-2xl border border-rose-500/35 bg-rose-950/35 p-4 text-sm text-rose-100">
            <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-rose-300">
              Stale hosted corners data
            </div>
            <p className="mt-2">
              Do not trust an empty or quiet corners board until this clears. The canonical hosted `corners_state` snapshot is{" "}
              {hostedSnapshotAt ? `${formatRelativeAgeShort(hostedSnapshotAt, realNowMillis)} old` : "missing"}; threshold is {staleHours.toFixed(0)}h.
            </p>
            <p className="mt-1 text-xs text-rose-200/80">
              Source: {shortlistSource.source} | hosted generated {hostedSnapshotAt ? formatDateTime(hostedSnapshotAt) : "missing"} | local fallback{" "}
              {shortlistSource.localSnapshotGeneratedAt ? formatDateTime(shortlistSource.localSnapshotGeneratedAt) : "missing"}.
            </p>
          </section>
        ) : null}

        <FootballVnextShadowPanel
          title="Corners v3 Prospective Lane"
          model="corners_v3"
          rows={cornersV3ClvRows}
          candidates={vnextCandidateRows}
          gate={vnextGate?.corners_v3 ?? null}
        />

        <SectionCard
          collapsible
          title="Corners v4 G0 Research Gate"
          subtitle="Additive favourite-strength and corners-per-shot test. Diagnostic only; v3 routing and stakes are unchanged."
        >
          <div className="grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
            <StatCard
              label="Enriched count sample"
              value={(cornersV4G0?.samples?.enriched ?? 0).toLocaleString()}
              detail={`of ${(cornersV4G0?.samples?.v3 ?? 0).toLocaleString()} v3 rows`}
            />
            <StatCard
              label="Latest MAE delta"
              value={cornersV4MaeDelta == null ? "-" : `${cornersV4MaeDelta >= 0 ? "+" : ""}${cornersV4MaeDelta.toFixed(4)}`}
              detail={`${latestCornersV4Season ?? "latest fold"}; negative is better`}
              tone={statTone(cornersV4MaeDelta != null && cornersV4MaeDelta < 0 ? "green" : "amber")}
            />
            <StatCard
              label="Raw Brier vs market"
              value={cornersV4Lean?.brier_delta == null ? "-" : `+${cornersV4Lean.brier_delta.toFixed(4)}`}
              detail={`${cornersV4Lean?.market_rows ?? 0} real Pinnacle lines`}
              tone={statTone("amber")}
            />
            <StatCard
              label="G0 decision"
              value={cornersV4Lean?.g0_status ?? "NOT RUN"}
              detail={`per-line ${cornersV4Lean?.g0a_per_line_residual ?? "-"} | Brier ${cornersV4Lean?.g0b_brier ?? "-"}`}
              tone={statTone(cornersV4Lean?.g0_status === "PASS" ? "green" : "red")}
            />
          </div>
          <p className="mt-4 text-sm leading-6 text-slate-400">
            Count accuracy improved marginally, but the real-price calibration gate failed. No v4 candidate is authorized for signals,
            settlement claims or staking until the per-line residual defect is corrected on a locked holdout.
          </p>
          {cornersV4G0?.generated_at ? (
            <p className="mt-2 text-xs text-slate-500">Generated {formatDateTime(cornersV4G0.generated_at)}</p>
          ) : null}
          {cornersV4G0Report ? (
            <details className="mt-4 rounded-xl border border-slate-800/70 bg-slate-950/30 p-4">
              <summary className="cursor-pointer text-xs font-semibold uppercase tracking-[0.16em] text-slate-400">
                Full v4 G0 evidence
              </summary>
              <pre className="mt-4 overflow-x-auto whitespace-pre-wrap text-[11px] leading-relaxed text-slate-400">
                {cornersV4G0Report}
              </pre>
            </details>
          ) : null}
        </SectionCard>

        <SectionCard
          collapsible
          defaultOpen
          title={`Official live lane - ${officialSettled.length} settled | ${currentPolicyPending.length} open`}
          subtitle="This is the active corners policy first. ROI (flat) is level stakes; ROI (staked) uses the real 0.2u-1.5u stake sizing."
        >
          {officialSettled.length === 0 && currentPolicyPending.length === 0 ? (
            <EmptyState message="No official corners bets tracked yet." />
          ) : (
            <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
              <StatCard
                label="P&L (flat)"
                value={`${officialPnlFlat >= 0 ? "+" : ""}${officialPnlFlat.toFixed(2)}u`}
                detail={`${officialWon.length}W / ${officialLost.length}L`}
                tone={statTone(officialPnlFlat > 0 ? "green" : officialPnlFlat < 0 ? "red" : "default")}
              />
              <StatCard
                label="P&L (staked)"
                value={`${officialPnlStaked >= 0 ? "+" : ""}${officialPnlStaked.toFixed(2)}u`}
                detail={`${officialTotalStaked.toFixed(1)}u staked`}
                tone={statTone(officialPnlStaked > 0 ? "green" : officialPnlStaked < 0 ? "red" : "default")}
              />
              <StatCard
                label="ROI (flat)"
                value={`${officialRoiFlat >= 0 ? "+" : ""}${officialRoiFlat.toFixed(1)}%`}
                tone={statTone(officialRoiFlat > 5 ? "green" : officialRoiFlat < -5 ? "red" : "amber")}
              />
              <StatCard
                label="ROI (staked)"
                value={`${officialRoiStaked >= 0 ? "+" : ""}${officialRoiStaked.toFixed(1)}%`}
                detail={`${officialSettled.length} settled`}
                tone={statTone(officialRoiStaked > 5 ? "green" : officialRoiStaked < -5 ? "red" : "amber")}
              />
              <StatCard
                label="Win rate"
                value={`${officialWinRate.toFixed(0)}%`}
                detail={`${officialWon.length}W/${officialLost.length}L${officialPushed.length > 0 ? `/${officialPushed.length}P` : ""} | ${currentPolicyPending.length} open`}
                tone={statTone(officialWinRate > 55 ? "green" : officialWinRate < 45 ? "red" : "default")}
              />
            </div>
          )}
        </SectionCard>

        {predictionCount === 0 && (
          <section className="rounded-2xl border border-amber-700/40 bg-amber-950/30 p-4 text-sm text-amber-200">
            No prediction data found. Run{" "}
            <code className="rounded bg-slate-800 px-1.5 py-0.5 text-xs">python scripts/corners-ou-model.py</code>{" "}
            then{" "}
            <code className="rounded bg-slate-800 px-1.5 py-0.5 text-xs">python scripts/matchday-shortlist.py --all-leagues</code>
          </section>
        )}

        {/* -- KPI strip -- */}
        <section className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 lg:grid-cols-8">
          <StatCard label="Historical matches" value={predictionCount.toLocaleString()} detail="with predictions" />
          <StatCard
            label="Backtest bets"
            value={hasBacktestRows ? backtestRows.length.toLocaleString() : "n/a"}
            detail={hasBacktestRows ? `${backtestWins}W / ${backtestRows.length - backtestWins}L` : "results file missing"}
            tone={statTone(hasBacktestRows ? "default" : "amber")}
          />
          <StatCard
            label="Backtest ROI"
            value={backtestRoi === null ? "n/a" : `${backtestRoi >= 0 ? "+" : ""}${backtestRoi.toFixed(1)}%`}
            detail={
              backtestRoi === null
                ? "backtest artifacts unavailable"
                : `${backtestPnl >= 0 ? "+" : ""}${backtestPnl.toFixed(1)}u PnL on ${backtestStaked.toFixed(1)}u staked`
            }
            tone={statTone(backtestRoi === null ? "amber" : backtestRoi > 0 ? "green" : backtestRoi < -5 ? "red" : "default")}
          />
          <StatCard
            label="Open V3 bets"
            value={currentPolicyPending.length.toString()}
            detail={
              currentValueSignals.length > 0
                ? `${currentValueSignals.length} fresh signal${currentValueSignals.length === 1 ? "" : "s"} this refresh`
                : "no fresh additions this refresh"
            }
            tone={statTone(currentPolicyPending.length > 0 ? "amber" : "default")}
          />
          <StatCard
            label="Open V3.1"
            value={researchPolicyPending.length.toString()}
            detail={
              currentResearchSignals.length > 0
                ? `${currentResearchSignals.length} fresh research signal${currentResearchSignals.length === 1 ? "" : "s"}`
                : `${valueBetsV31.length} V3.1 latest signal${valueBetsV31.length === 1 ? "" : "s"}`
            }
            tone={statTone(researchPolicyPending.length > 0 ? "amber" : "default")}
          />
          <StatCard label="Signals tracked" value={signals.length.toString()} detail={`V3.1 ${signalsV31.length}`} />
          <StatCard
            label="Avg entry edge"
            value={
              valueBets.length > 0
                ? `${(valueBets.reduce((s, r) => s + pf(r.edge), 0) / valueBets.length * 100).toFixed(1)}%`
                : "--"
            }
            tone={statTone(
              valueBets.length > 0 && valueBets.reduce((s, r) => s + pf(r.edge), 0) / valueBets.length > 0.1
                ? "green"
                : "default",
            )}
          />
          <StatCard
            label="Avg CLV (Pinnacle)"
            value={avgClv !== null ? `${avgClv >= 0 ? "+" : ""}${avgClv.toFixed(1)}%` : "--"}
            detail={avgClv !== null ? `${settledWithClv.length} settled w/ close` : "no closing data yet"}
            tone={statTone(avgClv !== null && avgClv > 0 ? "green" : avgClv !== null && avgClv < -3 ? "red" : "default")}
          />
        </section>

        <SectionCard
          collapsible
          defaultOpen
          title="Legacy Corners V0 Control"
          subtitle="Frozen comparison lane | canonical_form_v0 | retained only to benchmark the new corners v3 prospective model"
        >
          {cornersV0Lane || cornersAllowedConfig ? (
            <>
              <div className="grid gap-2.5 sm:grid-cols-2 xl:grid-cols-6">
                <StatCard
                  label="Research state"
                  value={cornersV0Lane?.state ?? "research_partial"}
                  tone={statTone("amber")}
                  detail="V0 total corners"
                />
                <StatCard
                  label="Allowed leagues"
                  value={`${cornersV0AllowedLeagues.length}/5`}
                  tone={statTone(cornersV0AllowedLeagues.length >= 3 ? "green" : "amber")}
                  detail={formatLeagueList(cornersV0AllowedLeagues)}
                />
                <StatCard
                  label="Blocked leagues"
                  value={cornersV0BlockedLeagues.length.toString()}
                  tone={statTone(cornersV0BlockedLeagues.length > 0 ? "amber" : "green")}
                  detail={formatLeagueList(cornersV0BlockedLeagues)}
                />
                <StatCard
                  label="Canonical-only"
                  value={cornersAllowedConfig?.canonical_only_allowed === false ? "blocked" : "allowed"}
                  tone={statTone(cornersAllowedConfig?.canonical_only_allowed === false ? "amber" : "green")}
                  detail="hard guard"
                />
                <StatCard
                  label="CLV picks"
                  value={cornersV0Clv.picks}
                  detail={`${cornersV0Summary.settled} settled | ${cornersV0Summary.total} active`}
                />
                <StatCard
                  label="W / L"
                  value={`${cornersV0Summary.won}W / ${cornersV0Summary.lost}L`}
                  tone={statTone(cornersV0Summary.won >= cornersV0Summary.lost ? "green" : "red")}
                  detail={`${cornersV0Summary.pushed} push | ${cornersV0Summary.pending} open`}
                />
                <StatCard
                  label="P&L flat"
                  value={formatUnits(cornersV0Summary.pnl)}
                  tone={statTone(cornersV0Summary.pnl > 0 ? "green" : cornersV0Summary.pnl < 0 ? "red" : "default")}
                  detail="1u per published pick"
                />
                <StatCard
                  label="ROI flat"
                  value={cornersV0Summary.roi !== null ? formatSignedPercent(cornersV0Summary.roi) : "-"}
                  tone={statTone(
                    cornersV0Summary.roi === null
                      ? "default"
                      : cornersV0Summary.roi > 0
                        ? "green"
                        : cornersV0Summary.roi < 0
                          ? "red"
                          : "default",
                  )}
                  detail={cornersV0Summary.winRate !== null ? `${cornersV0Summary.winRate.toFixed(0)}% win rate` : undefined}
                />
                <StatCard
                  label="Avg CLV"
                  value={cornersV0Clv.avgClv}
                  tone={cornersV0Clv.avgClv.startsWith("+") ? "text-emerald-300" : cornersV0Clv.avgClv.startsWith("-") ? "text-rose-300" : undefined}
                />
              </div>

              <div className="mt-3 grid gap-2.5 md:grid-cols-2">
                {cornersV0SideRows.map(({ side, label, summary, clv }) => (
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

              <div className="mt-3 rounded-xl border border-amber-500/20 bg-amber-500/8 px-3 py-2 text-xs text-amber-100">
                {cornersV0AllowedLeagues.length > 0
                  ? `This is the corners research model being monitored. Allowed leagues: ${formatLeagueList(cornersV0AllowedLeagues)}. Blocked leagues: ${formatLeagueList(cornersV0BlockedLeagues)}.`
                  : "This is the corners research model being monitored. All leagues are currently blocked because the real-odds Pinnacle gate has not passed."}
                {cornersV0Lane?.next_action ? ` Next action: ${cornersV0Lane.next_action}` : ""}
              </div>

              {cornersDiagnosticRows.length > 0 ? (
                <div className="mt-3 overflow-x-auto rounded-xl border border-slate-800/60 bg-slate-950/30">
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                        <th className="py-2.5 pl-4 pr-3">Blocked league</th>
                        <th className="py-2.5 pr-3 font-mono">N</th>
                        <th className="py-2.5 pr-3 font-mono">Current MAE</th>
                        <th className="py-2.5 pr-3 font-mono">V0 MAE</th>
                        <th className="py-2.5 pr-3 font-mono">Delta</th>
                        <th className="py-2.5 pr-4">Read</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cornersDiagnosticRows.map(([league, row]) => {
                        const delta = row.mae_delta ?? null;
                        const blocked = delta !== null && delta > 0;
                        return (
                          <tr key={league} className="border-b border-slate-800/40">
                            <td className="py-2 pl-4 pr-3 text-slate-200">{leagueTitle(league)}</td>
                            <td className="py-2 pr-3 font-mono tabular-nums text-slate-400">{row.n ?? "-"}</td>
                            <td className="py-2 pr-3 font-mono tabular-nums text-slate-300">{row.current_mae?.toFixed(4) ?? "-"}</td>
                            <td className={`py-2 pr-3 font-mono tabular-nums ${blocked ? "text-rose-300" : "text-emerald-300"}`}>
                              {row.canonical_mae?.toFixed(4) ?? "-"}
                            </td>
                            <td className={`py-2 pr-3 font-mono tabular-nums ${blocked ? "text-rose-300" : "text-emerald-300"}`}>
                              {delta === null ? "-" : `${delta >= 0 ? "+" : ""}${delta.toFixed(4)}`}
                            </td>
                            <td className="py-2 pr-4">
                              <StatusPill
                                label={blocked ? "BLOCKED" : "PASS"}
                                tone={blocked
                                  ? "bg-amber-500/10 text-amber-300 border-amber-500/20"
                                  : "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"}
                              />
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>
              ) : null}

              {cornersV0RecentSettledPicks.length > 0 ? (
                <div className="mt-3 overflow-x-auto rounded-xl border border-slate-800/60 bg-slate-950/30">
                  <div className="border-b border-slate-800 px-4 py-2 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-500">
                    Recent Corners V0 Settled
                  </div>
                  <table className="w-full text-left text-xs">
                    <thead>
                      <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                        <th className="py-2.5 pl-4 pr-3">Result</th>
                        <th className="py-2.5 pr-3">Match</th>
                        <th className="py-2.5 pr-3">Pick</th>
                        <th className="py-2.5 pr-3 font-mono">Actual</th>
                        <th className="py-2.5 pr-3 font-mono">P&L</th>
                        <th className="py-2.5 pr-4">Settled</th>
                      </tr>
                    </thead>
                    <tbody>
                      {cornersV0RecentSettledPicks.map((row, index) => {
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
                              {row.line || "-"} {(row.side ?? "").toUpperCase()}
                            </td>
                            <td className="py-2 pr-3 font-mono tabular-nums text-slate-300">{row.actual_total_corners || "-"}</td>
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
            <EmptyState message="Corners V0 research state is missing from the snapshot. Rebuild the corners snapshot." />
          )}
        </SectionCard>

        <SectionCard
          collapsible
          defaultOpen
          title={`Corners V0 Pending Picks - ${cornersV0PendingPicks.length}`}
          subtitle="Research-only published V0 picks waiting for result/close. Blocked Bundesliga/La Liga and canonical-only rows are excluded."
        >
          {cornersV0PendingPicks.length > 0 ? (
            <div className="grid gap-3 xl:grid-cols-2">
              {cornersV0PendingPicks.map((row, index) => {
                const modelFair = maybeFloat(row.model_fair_odds);
                const modelProb = maybeFloat(row.model_implied_prob);
                const publicationOdds = maybeFloat(row.pinnacle_price_at_publication);
                const edgeRaw =
                  modelProb !== null && publicationOdds !== null
                    ? probabilityEdge(modelProb, publicationOdds)
                    : null;
                const edgePct = edgeRaw !== null ? edgeRaw * 100 : null;
                return (
                  <div key={`${row.pick_id || row.match_id || index}`} className="rounded-2xl border border-amber-500/20 bg-amber-500/8 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-amber-300">
                          Corners V0 open
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
                        <div className="mt-1 text-[11px] text-slate-500">
                          {row.kickoff_utc ? formatKickoff(row.kickoff_utc) : row.match_date || "-"}
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
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Pinnacle pub</div>
                        <div className="mt-0.5 font-mono text-slate-200">{publicationOdds !== null ? publicationOdds.toFixed(2) : "-"}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Model fair</div>
                        <div className="mt-0.5 font-mono text-slate-200">{modelFair !== null ? modelFair.toFixed(2) : "-"}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Entry edge</div>
                        <div className={`mt-0.5 font-mono ${edgePct !== null && edgePct >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {formatSignedPercent(edgePct)}
                        </div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">3h / 1h</div>
                        <div className="mt-0.5 font-mono text-slate-300">
                          {(row.pinnacle_price_3h_pre_kickoff || "-")} / {(row.pinnacle_price_1h_pre_kickoff || "-")}
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
            <EmptyState message="No Corners V0 pending research picks right now. The board will fill automatically once the V0 publisher writes open rows into the CLV monitor." />
          )}
        </SectionCard>

        <p className="rounded-xl border border-slate-800/60 bg-slate-900/30 px-4 py-3 text-xs text-slate-400">
          <strong className="text-slate-200">How to read this page.</strong>{" "}
          <span className="text-slate-300">All model fixtures</span> is the full slate the corners model priced.{" "}
          <span className="text-slate-300">Official live signals</span> is the subset where the calibrated edge cleared the
          15% threshold and survived the divergence gate. Bet tracker, signal rows, and the full fixture grid use the{" "}
          <span className="text-slate-300">calibrated fair</span> and compare it against the matched{" "}
          <span className="text-slate-300">Pinnacle odds</span> where available. The live lane view below is split into{" "}
          <span className="text-slate-300">Official live lane</span> (strict 15% EV),{" "}
          <span className="text-slate-300">V3.1 research lane</span> (looser 8% EV, not official), and older archive rows stay in the raw ledger only.
        </p>

        {(currentPolicyPending.length > 0 || currentValueSignals.length > 0) && (
          <SectionCard
            collapsible
            defaultOpen
            title={`Official live board - ${currentPolicyPending.length} tracked open${currentValueSignals.length > 0 ? ` | ${currentValueSignals.length} fresh signal${currentValueSignals.length === 1 ? "" : "s"}` : ""}`}
            subtitle="These are the corners picks to monitor first."
          >
            <div className="grid gap-3 xl:grid-cols-2">
              {currentPolicyPending.map((row, i) => {
                const modelFair = maybeFloat(row.model_fair);
                const entryEdge = maybeFloat(row.edge);
                return (
                  <div key={`pending-${row.match}-${row.line}-${row.side}-${i}`} className="rounded-2xl border border-emerald-500/20 bg-emerald-500/8 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-emerald-300">Tracked open</div>
                        <div className="mt-1">
                          <MatchLabel
                            league={row.league}
                            homeTeam={splitMatchTeams(row.match)[0]}
                            awayTeam={splitMatchTeams(row.match)[1]}
                            iconSize={18}
                            textClassName="text-sm font-medium text-slate-100"
                          />
                        </div>
                        <div className="mt-1 text-[11px] text-slate-500">{formatKickoff(row.kick_off)}</div>
                      </div>
                      <StatusPill
                        label={`${row.line} ${row.side ?? ""}`}
                        tone={row.side === "over" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                      />
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Entry</div>
                        <div className="mt-0.5 font-mono text-slate-200">{pf(row.bookie_odds).toFixed(2)}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Cal fair</div>
                        <div className="mt-0.5 font-mono text-slate-200">{modelFair !== null ? modelFair.toFixed(2) : "--"}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Edge</div>
                        <div className={`mt-0.5 font-mono ${entryEdge !== null && entryEdge >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {formatSignedPercent(entryEdge !== null ? entryEdge * 100 : null)}
                        </div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Stake</div>
                        <div className="mt-0.5 font-mono text-amber-200">{pf(row.stake, 1).toFixed(1)}u</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Trust</div>
                        <div className="mt-0.5 text-slate-300">{trustBadgeLabel(row) ?? "aligned"}</div>
                      </div>
                    </div>
                  </div>
                );
              })}
              {currentValueSignals.map((item, i) => {
                const row = item.row;
                return (
                  <div key={`fresh-${row.match}-${row.line}-${row.side}-${i}`} className="rounded-2xl border border-sky-500/20 bg-sky-500/8 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-sky-300">Fresh signal</div>
                        <div className="mt-1">
                          <MatchLabel
                            league={row.league}
                            homeTeam={splitMatchTeams(row.match)[0]}
                            awayTeam={splitMatchTeams(row.match)[1]}
                            iconSize={18}
                            textClassName="text-sm font-medium text-slate-100"
                          />
                        </div>
                        <div className="mt-1 text-[11px] text-slate-500">{formatKickoff(row.kick_off || item.displayDate)}</div>
                      </div>
                      <StatusPill
                        label={`${row.line} ${row.side ?? ""}`}
                        tone={row.side === "over" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                      />
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Book</div>
                        <div className="mt-0.5 font-mono text-slate-200">{pf(row.bookie_odds).toFixed(2)}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Cal fair</div>
                        <div className="mt-0.5 font-mono text-slate-200">{pf(row.model_fair).toFixed(2)}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Edge</div>
                        <div className={`mt-0.5 font-mono ${item.edgeValue >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {(item.edgeValue * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Stake</div>
                        <div className="mt-0.5 font-mono text-amber-200">{pf(row.stake).toFixed(1)}u</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Trust</div>
                        <div className="mt-0.5 text-slate-300">{trustBadgeLabel(row) ?? "aligned"}</div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </SectionCard>
        )}

        {(researchPolicyPending.length > 0 || currentResearchSignals.length > 0) && (
          <SectionCard
            collapsible
            defaultOpen
            title={`V3.1 research board - ${researchPolicyPending.length} tracked open${currentResearchSignals.length > 0 ? ` | ${currentResearchSignals.length} fresh signal${currentResearchSignals.length === 1 ? "" : "s"}` : ""}`}
            subtitle="Research only: looser 8% EV threshold, not official. Shown separately so it cannot be mistaken for V3."
          >
            <div className="grid gap-3 xl:grid-cols-2">
              {researchPolicyPending.map((row, i) => {
                const modelFair = maybeFloat(row.model_fair);
                const entryEdge = maybeFloat(row.edge);
                return (
                  <div key={`v31-pending-${row.match}-${row.line}-${row.side}-${i}`} className="rounded-2xl border border-amber-500/20 bg-amber-500/8 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-amber-300">V3.1 tracked open</div>
                        <div className="mt-1">
                          <MatchLabel
                            league={row.league}
                            homeTeam={splitMatchTeams(row.match)[0]}
                            awayTeam={splitMatchTeams(row.match)[1]}
                            iconSize={18}
                            textClassName="text-sm font-medium text-slate-100"
                          />
                        </div>
                        <div className="mt-1 text-[11px] text-slate-500">{formatKickoff(row.kick_off)}</div>
                      </div>
                      <StatusPill
                        label={`${row.line} ${row.side ?? ""}`}
                        tone={row.side === "over" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                      />
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Entry</div>
                        <div className="mt-0.5 font-mono text-slate-200">{pf(row.bookie_odds).toFixed(2)}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Cal fair</div>
                        <div className="mt-0.5 font-mono text-slate-200">{modelFair !== null ? modelFair.toFixed(2) : "--"}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Edge</div>
                        <div className={`mt-0.5 font-mono ${entryEdge !== null && entryEdge >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {formatSignedPercent(entryEdge !== null ? entryEdge * 100 : null)}
                        </div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Stake</div>
                        <div className="mt-0.5 font-mono text-amber-200">{pf(row.stake, 1).toFixed(2)}u</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Trust</div>
                        <div className="mt-0.5 text-slate-300">{trustBadgeLabel(row) ?? "aligned"}</div>
                      </div>
                    </div>
                  </div>
                );
              })}
              {currentResearchSignals.map((item, i) => {
                const row = item.row;
                return (
                  <div key={`v31-fresh-${row.match}-${row.line}-${row.side}-${i}`} className="rounded-2xl border border-orange-500/20 bg-orange-500/8 p-4">
                    <div className="flex items-start justify-between gap-3">
                      <div className="min-w-0">
                        <div className="text-[10px] font-semibold uppercase tracking-[0.16em] text-orange-300">V3.1 fresh signal</div>
                        <div className="mt-1">
                          <MatchLabel
                            league={row.league}
                            homeTeam={splitMatchTeams(row.match)[0]}
                            awayTeam={splitMatchTeams(row.match)[1]}
                            iconSize={18}
                            textClassName="text-sm font-medium text-slate-100"
                          />
                        </div>
                        <div className="mt-1 text-[11px] text-slate-500">{formatKickoff(row.kick_off || item.displayDate)}</div>
                      </div>
                      <StatusPill
                        label={`${row.line} ${row.side ?? ""}`}
                        tone={row.side === "over" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                      />
                    </div>
                    <div className="mt-3 grid grid-cols-2 gap-2 text-xs sm:grid-cols-5">
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Book</div>
                        <div className="mt-0.5 font-mono text-slate-200">{pf(row.bookie_odds).toFixed(2)}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Cal fair</div>
                        <div className="mt-0.5 font-mono text-slate-200">{pf(row.model_fair).toFixed(2)}</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Edge</div>
                        <div className={`mt-0.5 font-mono ${item.edgeValue >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                          {(item.edgeValue * 100).toFixed(1)}%
                        </div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Stake</div>
                        <div className="mt-0.5 font-mono text-amber-200">{pf(row.stake).toFixed(2)}u</div>
                      </div>
                      <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                        <div className="text-[10px] uppercase tracking-[0.14em] text-slate-600">Trust</div>
                        <div className="mt-0.5 text-slate-300">{trustBadgeLabel(row) ?? "aligned"}</div>
                      </div>
                    </div>
                  </div>
                );
              })}
            </div>
          </SectionCard>
        )}

        {currentSlateSignals.length > 0 && (
          <SectionCard
            collapsible
            defaultOpen={false}
            title={`Current fixture slate - ${currentSlateSignals.length} fixtures`}
            subtitle={`Matches currently priced by the corners model, even when no official edge clears the threshold.${latestPinnacleCaptureAt ? ` Latest Pinnacle capture ${formatDateTime(latestPinnacleCaptureAt)}.` : ""}`}
          >
            <div className="grid gap-3 xl:grid-cols-2">
              {currentSlateLeagueKeys.map((leagueKey) => {
                const leagueRows = currentSlateSignalsByLeague.get(leagueKey) ?? [];
                return (
                  <div key={leagueKey} className="rounded-2xl border border-slate-800/70 bg-slate-950/30 p-4">
                    <div className="mb-3 flex items-center justify-between gap-2">
                      <LeagueLabel
                        league={leagueKey}
                        label={leagueTitle(leagueKey)}
                        className="text-[14px] font-semibold text-slate-100"
                        iconSize={16}
                      />
                      <span className="text-[11px] text-slate-500">
                        {leagueRows.length} fixture{leagueRows.length !== 1 ? "s" : ""}
                      </span>
                    </div>
                    <div className="space-y-2.5">
                      {leagueRows.map((row, index) => {
                        const fixtureKey = [
                          (row.league ?? "").trim().toLowerCase(),
                          (row.date ?? "").trim().slice(0, 10),
                          normalizeTeamKey(row.home_team),
                          normalizeTeamKey(row.away_team),
                        ].join("|");
                        const pinnacleFixture = pinnacleMatchByFixture.get(fixtureKey);
                        return (
                          <div
                            key={`${leagueKey}-${row.home_team}-${row.away_team}-${index}`}
                            className="flex flex-wrap items-start justify-between gap-3 rounded-xl border border-slate-800/70 bg-slate-900/40 px-3 py-3"
                          >
                            <div>
                              <MatchLabel
                                league={row.league}
                                homeTeam={row.home_team}
                                awayTeam={row.away_team}
                                iconSize={16}
                                textClassName="text-sm font-medium text-slate-100"
                              />
                              <div className="mt-1 text-[11px] text-slate-500">
                                {formatKickoff(row.kick_off)}
                              </div>
                            </div>
                            <div className="flex flex-wrap items-center justify-end gap-2">
                              <StatusPill
                                label={consensusLabel(consensusState(row.consensus))}
                                tone={consensusTone(consensusState(row.consensus))}
                              />
                              <span className="text-[11px] text-slate-500">
                                {pinnacleFixture ? "Pinnacle matched" : "Missing in latest Pinnacle capture"}
                              </span>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </div>
                );
              })}
            </div>
          </SectionCard>
        )}

        {/* -- Pipeline Health -- */}
        <SectionCard collapsible defaultOpen={false} title="Pipeline Health" subtitle="Data freshness and source status">
          <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 xl:grid-cols-6">
            <StatCard
              label="Scheduler heartbeat"
              value={formatDateTime(schedulerHeartbeatAt)}
              detail={formatRelativeAgeShort(schedulerHeartbeatAt, renderReferenceMs)}
              tone={statTone(pipelineTone)}
            />
            <StatCard
              label="Latest shortlist"
              value={formatDateTime(shortlistMtime)}
              detail={formatRelativeAgeShort(shortlistMtime, renderReferenceMs)}
              tone={statTone(shortlistMtime ? "default" : "amber")}
            />
            <StatCard
              label="Predictions file"
              value={formatDateTime(predictionsMtime)}
              detail={formatRelativeAgeShort(predictionsMtime, renderReferenceMs)}
              tone={statTone(predictionsMtime ? "default" : "amber")}
            />
            <StatCard
              label="Pinnacle odds"
              value={formatDateTime(latestPinnacleCaptureAt ?? pinnacleCornersMtime)}
              detail={`${pinnacleMatches.length} fixtures | ${formatRelativeAgeShort(latestPinnacleCaptureAt ?? pinnacleCornersMtime, renderReferenceMs)}`}
              tone={statTone(pinnacleMatches.length > 0 ? "default" : "amber")}
            />
            <StatCard
              label="Hosted snapshot"
              value={formatDateTime(snapshotGeneratedAt)}
              detail={formatRelativeAgeShort(snapshotGeneratedAt, renderReferenceMs)}
              tone={statTone(snapshotGeneratedAt ? "green" : "red")}
            />
            <StatCard
              label="Signals source"
              value={shortlistSource.source}
              detail={formatSourceReason(shortlistSource.reason)}
              tone={statTone(sourceTone(shortlistSource.source))}
            />
          </div>
          <details className="mt-3">
            <summary className="cursor-pointer select-none text-[10px] uppercase tracking-wider text-slate-600 hover:text-slate-500">
              pipeline detail
            </summary>
            <div className="mt-1.5 space-y-0.5 text-[11px] text-slate-600">
              <div><span className="text-slate-500">State:</span> {pipelineStatus?.state ?? "missing"}{pipelineStatus?.current_step ? <> &middot; {pipelineStatus.current_step}</> : null}</div>
              <div><span className="text-slate-500">Message:</span> {pipelineStatus?.message ?? "n/a"}</div>
              <div><span className="text-slate-500">Source:</span> {shortlistSource.source} &middot; hosted {shortlistSource.hostedSnapshotAvailable ? "ok" : "missing"} &middot; local {shortlistSource.localSnapshotAvailable ? "ok" : "missing"}</div>
            </div>
          </details>
        </SectionCard>

        {/* -- Current Bettable Signals -- */}
        {currentValueSignals.length > 0 && (
          <SectionCard
            title={`New official signals - ${currentValueSignals.length} best bets`}
            subtitle={`Deduplicated from ${valueBets.length} raw lines | excludes already tracked open bets | best-value per match and side`}
          >
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3">League</th>
                    <th className="py-2 pr-3">Match</th>
                    <th className="py-2 pr-3">Line</th>
                    <th className="py-2 pr-3">Side</th>
                    <th className="py-2 pr-3 font-mono">Book</th>
                    <th className="py-2 pr-3 font-mono">Cal fair</th>
                    <th className="py-2 pr-3 font-mono">Edge</th>
                    <th className="py-2 pr-3">Trust</th>
                    <th className="py-2 font-mono">Stake</th>
                  </tr>
                </thead>
                <tbody>
                  {currentValueSignals.map((item, i) => {
                    const row = item.row;
                    const edge = item.edgeValue;
                    return (
                      <tr key={i} className="border-b border-slate-800/40 hover:bg-slate-800/20">
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{item.displayDate}</td>
                        <td className="py-1.5 pr-3 text-slate-400">
                          <LeagueLabel league={row.league} label={row.league} iconSize={14} />
                        </td>
                        <td className="py-1.5 pr-3 font-medium">
                          <MatchLabel
                            league={row.league}
                            homeTeam={splitMatchTeams(row.match)[0]}
                            awayTeam={splitMatchTeams(row.match)[1]}
                            iconSize={16}
                            textClassName="font-medium text-slate-200"
                          />
                        </td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums">{row.line}</td>
                        <td className="py-1.5 pr-3">
                          <StatusPill
                            label={row.side ?? ""}
                            tone={row.side === "over" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                          />
                        </td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-100">{pf(row.bookie_odds).toFixed(2)}</td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{pf(row.model_fair).toFixed(2)}</td>
                        <td className={`py-1.5 pr-3 font-mono tabular-nums ${edge >= 0.15 ? "text-emerald-300" : edge >= 0.10 ? "text-amber-300" : "text-slate-300"}`}>
                          {(edge * 100).toFixed(1)}%
                        </td>
                        <td className="py-1.5 pr-3">
                          {trustBadgeLabel(row) ? (
                            <StatusPill label={trustBadgeLabel(row)!} tone={trustBadgeTone(row)} />
                          ) : (
                            <span className="text-[11px] text-slate-600">aligned</span>
                          )}
                        </td>
                        <td className="py-1.5 font-mono tabular-nums text-amber-200">{pf(row.stake).toFixed(1)}u</td>
                      </tr>
                    );
                  })}
                </tbody>
              </table>
            </div>
          </SectionCard>
        )}

        {/* -- Bet Tracker -- */}
        <SectionCard
          collapsible
          defaultOpen={officialSettled.length > 0 || currentPolicyPending.length > 0}
          title={`Official tracker${currentPolicyPending.length > 0 ? ` - ${currentPolicyPending.length} open` : ""}${officialSettled.length > 0 ? `, ${officialSettled.length} settled` : ""}`}
          subtitle="Official live lane only. V3.1 research lane remains separate below."
        >
          {officialSettled.length === 0 && currentPolicyPending.length === 0 ? (
            <EmptyState message="No bets tracked yet. Run python scripts/shortlist-settle.py after results are in." />
          ) : (
            <div className="space-y-5">
              {/* KPI stats */}
              {officialSettled.length > 0 && (
                <>
                  <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
                    <StatCard
                      label="P&L (flat)"
                      value={`${officialPnlFlat >= 0 ? "+" : ""}${officialPnlFlat.toFixed(2)}u`}
                      detail={`${officialWon.length}W / ${officialLost.length}L`}
                      tone={statTone(officialPnlFlat > 0 ? "green" : officialPnlFlat < 0 ? "red" : "default")}
                    />
                    <StatCard
                      label="P&L (staked)"
                      value={`${officialPnlStaked >= 0 ? "+" : ""}${officialPnlStaked.toFixed(2)}u`}
                      detail={`${officialTotalStaked.toFixed(1)}u staked`}
                      tone={statTone(officialPnlStaked > 0 ? "green" : officialPnlStaked < 0 ? "red" : "default")}
                    />
                    <StatCard
                      label="ROI (flat)"
                      value={`${officialRoiFlat >= 0 ? "+" : ""}${officialRoiFlat.toFixed(1)}%`}
                      tone={statTone(officialRoiFlat > 5 ? "green" : officialRoiFlat < -5 ? "red" : "amber")}
                    />
                    <StatCard
                      label="ROI (staked)"
                      value={`${officialRoiStaked >= 0 ? "+" : ""}${officialRoiStaked.toFixed(1)}%`}
                      detail={`${officialSettled.length} settled`}
                      tone={statTone(officialRoiStaked > 5 ? "green" : officialRoiStaked < -5 ? "red" : "amber")}
                    />
                    <StatCard
                      label="Win rate"
                      value={`${officialWinRate.toFixed(0)}%`}
                      detail={`${officialWon.length}W/${officialLost.length}L${officialPushed.length > 0 ? `/${officialPushed.length}P` : ""} | ${currentPolicyPending.length} open`}
                      tone={statTone(officialWinRate > 55 ? "green" : officialWinRate < 45 ? "red" : "default")}
                    />
                  </div>

                  {liveByLeague.length > 1 && (
                    <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                            <th className="py-2 pr-4">League</th>
                            <th className="py-2 pr-4 text-right font-mono">Bets</th>
                            <th className="py-2 pr-4 text-right font-mono">W/L</th>
                            <th className="py-2 pr-4 text-right font-mono">P&L</th>
                            <th className="py-2 text-right font-mono">ROI</th>
                          </tr>
                        </thead>
                        <tbody>
                          {liveByLeague.map(({ lg, n, won, pnlVal, roi }) => (
                            <tr key={lg} className="border-b border-slate-800/40">
                              <td className="py-1.5 pr-4 font-medium">
                                <LeagueLabel league={lg} label={lg} iconSize={14} />
                              </td>
                              <td className="py-1.5 pr-4 text-right font-mono tabular-nums text-slate-400">{n}</td>
                              <td className="py-1.5 pr-4 text-right">
                                <RecordSummary won={won} lost={n - won} align="right" />
                              </td>
                              <td className={`py-1.5 pr-4 text-right font-mono tabular-nums ${pnlVal >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                                {pnlVal >= 0 ? "+" : ""}{pnlVal.toFixed(2)}u
                              </td>
                              <td className={`py-1.5 text-right font-mono tabular-nums ${roi >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                                {roi >= 0 ? "+" : ""}{roi.toFixed(1)}%
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}

                  {versionSummaries.length > 0 && (
                    <div className="space-y-3">
                      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Active lanes
                      </div>
                      <div className="grid gap-3 lg:grid-cols-2">
                        {versionSummaries.map((row) => (
                          <div key={row.version} className="rounded-xl border border-slate-800/70 bg-slate-950/40 p-4">
                            <div className="flex items-start justify-between gap-3">
                              <div>
                                <div className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                                  {policyLaneLabel(row.version)}
                                </div>
                                <div className="mt-1 text-xs text-slate-400">
                                  {policyLaneDescription(row.version)}
                                </div>
                              </div>
                              <StatusPill
                                label={row.pending > 0 ? `${row.pending} open` : `${row.settled} settled`}
                                tone={
                                  row.pending > 0
                                    ? "bg-amber-500/10 text-amber-200 border-amber-500/20"
                                    : row.pnl > 0
                                      ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"
                                      : row.pnl < 0
                                        ? "bg-rose-500/10 text-rose-300 border-rose-500/20"
                                        : "bg-slate-500/10 text-slate-300 border-slate-500/20"
                                }
                              />
                            </div>
                            <div className="mt-4 grid grid-cols-2 gap-3 text-xs">
                              <div>
                                <div className="text-slate-500">Tracked</div>
                                <div className="font-mono tabular-nums text-slate-200">{row.tracked}</div>
                              </div>
                              <div>
                                <div className="text-slate-500">Record</div>
                                <div className="pt-0.5">
                                  <RecordSummary won={row.won} lost={row.lost} pushed={row.pushed} />
                                </div>
                              </div>
                              <div>
                                <div className="text-slate-500">P&amp;L</div>
                                <div className={`font-mono tabular-nums ${row.pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                                  {row.pnl >= 0 ? "+" : ""}{row.pnl.toFixed(2)}u
                                </div>
                              </div>
                              <div>
                                <div className="text-slate-500">ROI</div>
                                <div className={`font-mono tabular-nums ${valueToneClass(row.roi)}`}>
                                  {row.roi === null ? "--" : `${row.roi >= 0 ? "+" : ""}${row.roi.toFixed(1)}%`}
                                </div>
                              </div>
                              <div>
                                <div className="text-slate-500">Settled / open</div>
                                <div className="font-mono tabular-nums">
                                  <span className="text-emerald-300">{row.settled}</span>
                                  <span className="text-slate-600"> / </span>
                                  <span className={row.pending > 0 ? "text-amber-300" : "text-slate-400"}>{row.pending}</span>
                                </div>
                              </div>
                              <div>
                                <div className="text-slate-500">Avg edge</div>
                                <div className={`font-mono tabular-nums ${valueToneClass(row.avgEdge)}`}>
                                  {row.avgEdge === null ? "--" : `${row.avgEdge >= 0 ? "+" : ""}${row.avgEdge.toFixed(1)}%`}
                                </div>
                              </div>
                            </div>
                          </div>
                        ))}
                      </div>
                      <div className="overflow-x-auto">
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                            <th className="py-2 pr-4">Lane</th>
                            <th className="py-2 pr-4 text-right font-mono">Tracked</th>
                            <th className="py-2 pr-4 text-right font-mono">Settled</th>
                            <th className="py-2 pr-4 text-right font-mono">Pending</th>
                            <th className="py-2 pr-4 text-right font-mono">Record</th>
                            <th className="py-2 pr-4 text-right font-mono">P&L</th>
                            <th className="py-2 pr-4 text-right font-mono">ROI</th>
                            <th className="py-2 pr-4 text-right font-mono">Avg odds</th>
                            <th className="py-2 text-right font-mono">Avg edge</th>
                          </tr>
                        </thead>
                        <tbody>
                          {versionSummaries.map((row) => (
                            <tr key={row.version} className="border-b border-slate-800/40">
                              <td className="py-1.5 pr-4">
                                <div className="font-medium text-slate-200">{policyLaneLabel(row.version)}</div>
                                <div className="text-[11px] text-slate-500">{policyLaneDescription(row.version)}</div>
                              </td>
                              <td className="py-1.5 pr-4 text-right font-mono tabular-nums text-slate-400">{row.tracked}</td>
                              <td className="py-1.5 pr-4 text-right font-mono tabular-nums text-slate-400">{row.settled}</td>
                              <td className="py-1.5 pr-4 text-right font-mono tabular-nums text-slate-400">{row.pending}</td>
                              <td className="py-1.5 pr-4 text-right">
                                <RecordSummary won={row.won} lost={row.lost} pushed={row.pushed} align="right" />
                              </td>
                              <td className={`py-1.5 pr-4 text-right font-mono tabular-nums ${row.pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                                {row.pnl >= 0 ? "+" : ""}{row.pnl.toFixed(2)}u
                              </td>
                              <td className={`py-1.5 pr-4 text-right font-mono tabular-nums ${valueToneClass(row.roi)}`}>
                                {row.roi === null ? "--" : `${row.roi >= 0 ? "+" : ""}${row.roi.toFixed(1)}%`}
                              </td>
                              <td className="py-1.5 pr-4 text-right font-mono tabular-nums text-slate-400">
                                {row.avgOdds === null ? "--" : row.avgOdds.toFixed(2)}
                              </td>
                              <td className={`py-1.5 text-right font-mono tabular-nums ${valueToneClass(row.avgEdge)}`}>
                                {row.avgEdge === null ? "--" : `${row.avgEdge >= 0 ? "+" : ""}${row.avgEdge.toFixed(1)}%`}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                    </div>
                  )}
                </>
              )}

              {/* -- Open bets -- */}
              <div>
                <div className="mb-2 flex flex-wrap items-baseline gap-3">
                  <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                    Official live lane pending ({currentPolicyPending.length})
                  </span>
                  <span className={`text-[10px] ${currentPolicyPending.length > 0 ? "text-amber-300" : "text-slate-500"}`}>
                    {currentPolicyPending.reduce((sum, row) => sum + pf(row.stake, 1), 0).toFixed(1)}u exposure
                  </span>
                  <span className="text-[10px] text-slate-500">
                    <span className="text-emerald-300">{currentPolicySummary.settled}</span> settled{" "}
                    <span className="text-slate-600">|</span>{" "}
                    <RecordSummary won={currentPolicySummary.won} lost={currentPolicySummary.lost} pushed={currentPolicySummary.pushed} />
                  </span>
                  <span className={`text-[10px] ${valueToneClass(currentPolicySummary.pnl)}`}>
                    {currentPolicySummary.pnl >= 0 ? "+" : ""}{currentPolicySummary.pnl.toFixed(2)}u P&amp;L
                    {currentPolicySummary.roi !== null ? (
                      <>
                        {" "}
                        <span className="text-slate-600">|</span>{" "}
                        <span className={valueToneClass(currentPolicySummary.roi)}>
                          {currentPolicySummary.roi >= 0 ? "+" : ""}{currentPolicySummary.roi.toFixed(1)}% ROI
                        </span>
                      </>
                    ) : ""}
                  </span>
                </div>
                {currentPolicyPending.length > 0 ? (
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                          <th className="py-2 pr-3">Kickoff</th>
                          <th className="py-2 pr-3">Match</th>
                          <th className="py-2 pr-3">Line</th>
                          <th className="py-2 pr-3">Side</th>
                          <th className="py-2 pr-3 font-mono">Entry</th>
                          <th className="py-2 pr-3 font-mono">Cal fair</th>
                          <th className="py-2 pr-3 font-mono">Now</th>
                          <th className="py-2 pr-3 font-mono">Move</th>
                          <th className="py-2 pr-3 font-mono">Cal edge</th>
                          <th className="py-2 pr-3 font-mono">Cal now</th>
                          <th className="py-2 pr-3">Trust</th>
                          <th className="py-2 font-mono">Stake</th>
                        </tr>
                      </thead>
                      <tbody>
                        {currentPolicyPending.map((row, i) => {
                          const entryOdds = pf(row.bookie_odds);
                          const modelProb = maybeFloat(row.model_prob);
                          const modelFair = maybeFloat(row.model_fair);
                          const entryEdge = maybeFloat(row.edge) ?? probabilityEdge(modelProb, entryOdds);
                          const { odds: pinOdds, kickedOff } = getPinnacleInfo(row);
                          const kickoffDisplay = formatKickoff(row.kick_off);
                          const movePct = !kickedOff ? markToMarketClv(entryOdds, pinOdds) : null;
                          const nowEdge = !kickedOff ? probabilityEdge(modelProb, pinOdds) : null;
                          return (
                            <tr key={i} className={`border-b border-slate-800/40 hover:bg-slate-800/20 ${kickedOff ? "opacity-60" : ""}`}>
                              <td className="py-1.5 pr-3 font-mono tabular-nums text-[11px] text-slate-400">{kickoffDisplay}</td>
                              <td className="py-1.5 pr-3 font-medium">
                                <MatchLabel
                                  league={row.league}
                                  homeTeam={splitMatchTeams(row.match)[0]}
                                  awayTeam={splitMatchTeams(row.match)[1]}
                                  iconSize={16}
                                  textClassName="font-medium text-slate-200"
                                />
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">{row.line}</td>
                              <td className="py-1.5 pr-3">
                                <StatusPill
                                  label={row.side ?? ""}
                                  tone={row.side === "over" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                                />
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">{entryOdds.toFixed(2)}</td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">
                                {modelFair !== null ? modelFair.toFixed(2) : "--"}
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">
                                {kickedOff ? (
                                  <span className="text-[10px] uppercase tracking-wide text-slate-600">KO</span>
                                ) : pinOdds !== null ? (
                                  <span className={movePct !== null && movePct > 0.01 ? "text-emerald-300" : movePct !== null && movePct < -0.01 ? "text-rose-400" : "text-slate-400"}>
                                    {pinOdds.toFixed(2)}
                                  </span>
                                ) : <span className="text-slate-600">--</span>}
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">
                                {kickedOff ? (
                                  <span className="text-[10px] uppercase tracking-wide text-slate-600">KO</span>
                                ) : (
                                  <span className={movePct !== null && movePct > 0 ? "text-emerald-300" : movePct !== null && movePct < 0 ? "text-rose-400" : "text-slate-400"}>
                                    {formatSignedPercent(movePct !== null ? movePct * 100 : null)}
                                  </span>
                                )}
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">
                                {formatSignedPercent(entryEdge !== null ? entryEdge * 100 : null)}
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">
                                {kickedOff ? (
                                  <span className="text-[10px] uppercase tracking-wide text-slate-600">KO</span>
                                ) : (
                                  <span className={nowEdge !== null && nowEdge > 0 ? "text-emerald-300" : nowEdge !== null && nowEdge < 0 ? "text-rose-400" : "text-slate-400"}>
                                    {formatSignedPercent(nowEdge !== null ? nowEdge * 100 : null)}
                                  </span>
                                )}
                              </td>
                              <td className="py-1.5 pr-3">
                                {trustBadgeLabel(row) ? (
                                  <StatusPill label={trustBadgeLabel(row)!} tone={trustBadgeTone(row)} />
                                ) : (
                                  <span className="text-[11px] text-slate-600">aligned</span>
                                )}
                              </td>
                              <td className="py-1.5 font-mono tabular-nums text-amber-200">{pf(row.stake, 1).toFixed(1)}u</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                ) : (
                  <div className="rounded-xl border border-slate-800/70 bg-slate-950/40 p-4 text-sm text-slate-300">
                    <div className="font-medium text-slate-100">No tracked V3 pending bets right now.</div>
                    <div className="mt-1 text-xs text-slate-400">
                      The official live lane is still active; it just has no already-tracked pending bets in the settlement ledger.
                      {currentValueSignals.length > 0 ? (
                        <>
                          {" "}There {currentValueSignals.length === 1 ? "is" : "are"}{" "}
                          <span className="text-slate-200">{currentValueSignals.length}</span>{" "}
                          fresh official V3 signal{currentValueSignals.length === 1 ? "" : "s"} from the latest refresh shown above.
                        </>
                      ) : null}
                      {currentPolicyLatestSettled ? (
                        <>
                          {" "}Latest settled V3 result:{" "}
                          <span className="text-slate-200">{currentPolicyLatestSettled.match}</span>{" "}
                          {currentPolicyLatestSettled.line} {currentPolicyLatestSettled.side}{" "}
                          {currentPolicyLatestSettled.won === "yes" ? "won" : currentPolicyLatestSettled.won === "push" ? "pushed" : "lost"} for{" "}
                          <span className={pf(currentPolicyLatestSettled.pnl_staked) >= 0 ? "text-emerald-300" : "text-rose-300"}>
                            {pf(currentPolicyLatestSettled.pnl_staked) >= 0 ? "+" : ""}{pf(currentPolicyLatestSettled.pnl_staked).toFixed(2)}u
                          </span>.
                        </>
                      ) : null}
                    </div>
                  </div>
                )}
              </div>

              {researchPolicyPending.length > 0 && (
                <SectionCard
                  collapsible
                  defaultOpen
                  title={`V3.1 research lane pending - ${researchPolicyPending.length} total`}
                  subtitle="These are not current official bets. They were logged under V3.1 and are settling at original stake."
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                          <th className="py-2 pr-3">Lane</th>
                          <th className="py-2 pr-3">Kickoff</th>
                          <th className="py-2 pr-3">Match</th>
                          <th className="py-2 pr-3">Line</th>
                          <th className="py-2 pr-3">Side</th>
                          <th className="py-2 pr-3 font-mono">Entry</th>
                          <th className="py-2 pr-3 font-mono">Cal fair</th>
                          <th className="py-2 pr-3 font-mono">Now</th>
                          <th className="py-2 pr-3 font-mono">Move</th>
                          <th className="py-2 pr-3 font-mono">Cal edge</th>
                          <th className="py-2 pr-3 font-mono">Cal now</th>
                          <th className="py-2 font-mono">Stake</th>
                        </tr>
                      </thead>
                      <tbody>
                        {researchPolicyPending.map((row, i) => {
                          const entryOdds = pf(row.bookie_odds);
                          const modelProb = maybeFloat(row.model_prob);
                          const modelFair = maybeFloat(row.model_fair);
                          const entryEdge = maybeFloat(row.edge) ?? probabilityEdge(modelProb, entryOdds);
                          const { odds: pinOdds, kickedOff } = getPinnacleInfo(row);
                          const kickoffDisplay = formatKickoff(row.kick_off);
                          const movePct = !kickedOff ? markToMarketClv(entryOdds, pinOdds) : null;
                          const nowEdge = !kickedOff ? probabilityEdge(modelProb, pinOdds) : null;
                          return (
                            <tr key={`${row.match}-${row.line}-${row.side}-${i}`} className={`border-b border-slate-800/40 hover:bg-slate-800/20 ${kickedOff ? "opacity-60" : ""}`}>
                              <td className="py-1.5 pr-3">
                                <StatusPill
                                  label={policyShortLabel(policyVersion(row))}
                                  tone="bg-amber-500/10 text-amber-300 border-amber-500/20"
                                />
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums text-[11px] text-slate-400">{kickoffDisplay}</td>
                              <td className="py-1.5 pr-3 font-medium">
                                <MatchLabel
                                  league={row.league}
                                  homeTeam={splitMatchTeams(row.match)[0]}
                                  awayTeam={splitMatchTeams(row.match)[1]}
                                  iconSize={16}
                                  textClassName="font-medium text-slate-200"
                                />
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">{row.line}</td>
                              <td className="py-1.5 pr-3">
                                <StatusPill
                                  label={row.side ?? ""}
                                  tone={row.side === "over" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                                />
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">{entryOdds.toFixed(2)}</td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">
                                {modelFair !== null ? modelFair.toFixed(2) : "--"}
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">
                                {kickedOff ? (
                                  <span className="text-[10px] uppercase tracking-wide text-slate-600">KO</span>
                                ) : pinOdds !== null ? (
                                  <span className={movePct !== null && movePct > 0.01 ? "text-emerald-300" : movePct !== null && movePct < -0.01 ? "text-rose-400" : "text-slate-400"}>
                                    {pinOdds.toFixed(2)}
                                  </span>
                                ) : <span className="text-slate-600">--</span>}
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">
                                {kickedOff ? (
                                  <span className="text-[10px] uppercase tracking-wide text-slate-600">KO</span>
                                ) : (
                                  <span className={movePct !== null && movePct > 0 ? "text-emerald-300" : movePct !== null && movePct < 0 ? "text-rose-400" : "text-slate-400"}>
                                    {formatSignedPercent(movePct !== null ? movePct * 100 : null)}
                                  </span>
                                )}
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">
                                {formatSignedPercent(entryEdge !== null ? entryEdge * 100 : null)}
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">
                                {kickedOff ? (
                                  <span className="text-[10px] uppercase tracking-wide text-slate-600">KO</span>
                                ) : (
                                  <span className={nowEdge !== null && nowEdge > 0 ? "text-emerald-300" : nowEdge !== null && nowEdge < 0 ? "text-rose-400" : "text-slate-400"}>
                                    {formatSignedPercent(nowEdge !== null ? nowEdge * 100 : null)}
                                  </span>
                                )}
                              </td>
                              <td className="py-1.5 font-mono tabular-nums text-amber-200">{pf(row.stake, 1).toFixed(1)}u</td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                </SectionCard>
              )}

              {/* -- Recent Results - desktop table + mobile cards -- */}
              {recentSettled.length > 0 && (
                <SectionCard
                  collapsible
                  defaultOpen={false}
                  title={`Recent official results - ${officialSettled.length} total`}
                  subtitle={`Showing the latest ${recentSettled.length} official settled bets, grouped by league`}
                >
                  <div className="space-y-3">
                    {recentSettledLeagueKeys.map((leagueKey) => {
                      const leagueRows = recentSettledByLeague.get(leagueKey) ?? [];
                      return (
                        <SectionCard
                          key={leagueKey}
                          collapsible
                          defaultOpen={false}
                          title={<LeagueLabel league={leagueKey} label={leagueKey} className="text-[14px] font-semibold text-slate-100" iconSize={16} />}
                          subtitle={`${leagueRows.length} recent result${leagueRows.length !== 1 ? "s" : ""}`}
                        >
                          <div className="space-y-2 lg:hidden">
                            {leagueRows.map((row, i) => {
                              const isPush = row.won === "push";
                              const won = row.won === "yes";
                              const pnlFlat = pf(row.pnl_units);
                              const clvVal = maybeFloat(row.clv);
                              const rowTone = won ? "bg-emerald-950/25" : isPush ? "" : "bg-rose-950/25";
                              return (
                                <div key={i} className={`rounded-xl border border-slate-800/60 px-3 py-3 ${rowTone}`}>
                                  <div className="flex items-start justify-between gap-2">
                                    <div className="min-w-0">
                                      <MatchLabel
                                        league={row.league}
                                        homeTeam={splitMatchTeams(row.match)[0]}
                                        awayTeam={splitMatchTeams(row.match)[1]}
                                        iconSize={16}
                                        textClassName="truncate text-sm font-medium text-white"
                                      />
                                      <div className="mt-0.5 text-[11px] text-slate-500">
                                        {formatKickoff(row.kick_off) !== "--" ? formatKickoff(row.kick_off) : (row.match_date?.slice(0, 10) ?? "--")} | {row.line} {row.side}
                                      </div>
                                    </div>
                                    <div className="flex shrink-0 flex-col items-end gap-1">
                                      <StatusPill
                                        label={won ? "won" : isPush ? "push" : "lost"}
                                        tone={won ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : isPush ? "bg-slate-700/40 text-slate-400 border-slate-600/40" : "bg-rose-500/10 text-rose-300 border-rose-500/20"}
                                      />
                                      <span className={`font-mono text-sm font-semibold ${pnlFlat >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                                        {pnlFlat >= 0 ? "+" : ""}{pnlFlat.toFixed(2)}u
                                      </span>
                                    </div>
                                  </div>
                                  {clvVal !== null && (
                                    <div className="mt-1.5 text-[11px]">
                                      <span className="text-slate-600">CLV </span>
                                      <span className={clvVal > 0 ? "text-emerald-400" : "text-rose-400"}>
                                        {clvVal >= 0 ? "+" : ""}{(clvVal * 100).toFixed(1)}%
                                      </span>
                                      {row.actual_total_corners ? (
                                        <span className="ml-3 text-slate-600">Actual: <span className="text-slate-400">{row.actual_total_corners}</span></span>
                                      ) : null}
                                    </div>
                                  )}
                                </div>
                              );
                            })}
                          </div>

                          <div className="hidden lg:block">
                            <div className="grid grid-cols-[minmax(220px,2.2fr)_70px_80px_80px_80px_80px_70px_70px_60px_80px] gap-x-3 border-b border-slate-800 pb-2 text-[10px] uppercase tracking-wider text-slate-500">
                              <div>Match / KO</div>
                              <div>Line</div>
                              <div>Side</div>
                              <div className="text-right font-mono">Entry</div>
                              <div className="text-right font-mono">Close</div>
                              <div className="text-right font-mono">CLV</div>
                              <div className="text-right font-mono">Actual</div>
                              <div className="text-right font-mono">Stake</div>
                              <div className="text-center">W/L</div>
                              <div className="text-right font-mono">P&L</div>
                            </div>
                            <div className="divide-y divide-slate-800/40">
                              {leagueRows.map((row, i) => {
                                const isPush = row.won === "push";
                                const won = row.won === "yes";
                                const pnlFlat = pf(row.pnl_units);
                                const closingOdds = maybeFloat(row.closing_odds);
                                const clvVal = maybeFloat(row.clv);
                                const kickoffStr = formatKickoff(row.kick_off) !== "--"
                                  ? formatKickoff(row.kick_off)
                                  : (row.match_date?.slice(0, 10) ?? "--");
                                const rowTone = won ? "bg-emerald-950/20" : isPush ? "" : "bg-rose-950/20";
                                return (
                                  <div
                                    key={i}
                                    className={`grid grid-cols-[minmax(220px,2.2fr)_70px_80px_80px_80px_80px_70px_70px_60px_80px] items-center gap-x-3 px-1 py-2 text-xs hover:bg-slate-800/15 ${rowTone}`}
                                  >
                                    <div className="min-w-0">
                                      <MatchLabel
                                        league={row.league}
                                        homeTeam={splitMatchTeams(row.match)[0]}
                                        awayTeam={splitMatchTeams(row.match)[1]}
                                        iconSize={16}
                                        textClassName="truncate font-medium text-slate-100"
                                      />
                                      <div className="text-[10px] tabular-nums text-slate-600">{kickoffStr}</div>
                                    </div>
                                    <div className="font-mono tabular-nums text-slate-200">{row.line}</div>
                                    <div>
                                      <StatusPill
                                        label={row.side ?? ""}
                                        tone={row.side === "over" ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-sky-500/10 text-sky-300 border-sky-500/20"}
                                      />
                                    </div>
                                    <div className="text-right font-mono tabular-nums text-slate-200">{pf(row.bookie_odds).toFixed(2)}</div>
                                    <div className="text-right font-mono tabular-nums text-slate-400">
                                      {closingOdds !== null ? closingOdds.toFixed(2) : <span className="text-slate-700">--</span>}
                                    </div>
                                    <div className="text-right font-mono tabular-nums">
                                      {clvVal !== null ? (
                                        <span className={clvVal > 0 ? "text-emerald-300" : "text-rose-400"}>
                                          {clvVal >= 0 ? "+" : ""}{(clvVal * 100).toFixed(1)}%
                                        </span>
                                      ) : <span className="text-slate-700">--</span>}
                                    </div>
                                    <div className="text-right font-mono tabular-nums text-slate-400">{row.actual_total_corners || "--"}</div>
                                    <div className="text-right font-mono tabular-nums text-amber-200">{pf(row.stake, 1).toFixed(1)}u</div>
                                    <div className="text-center">
                                      <span className={`font-semibold ${won ? "text-emerald-300" : isPush ? "text-slate-400" : "text-rose-300"}`}>
                                        {won ? "W" : isPush ? "P" : "L"}
                                      </span>
                                    </div>
                                    <div className={`text-right font-mono tabular-nums ${pnlFlat > 0 ? "text-emerald-300" : pnlFlat < 0 ? "text-rose-300" : "text-slate-400"}`}>
                                      {pnlFlat >= 0 ? "+" : ""}{pnlFlat.toFixed(2)}u
                                    </div>
                                  </div>
                                );
                              })}
                            </div>
                          </div>
                        </SectionCard>
                      );
                    })}
                  </div>
                </SectionCard>
              )}
            </div>
          )}
        </SectionCard>

        {/* -- All Model Fixtures -- */}
        {signals.length > 0 && (
          <SectionCard
            collapsible
            defaultOpen
            title={`All Model Fixtures - ${signals.length} fixtures`}
            subtitle="Grouped by league. Calibrated fair prices are shown beside matched Pinnacle lines so you can judge the slate directly."
          >
            <div className="space-y-4">
              {signalLeagueKeys.map((leagueKey) => {
                const leagueRows = signalsByLeague.get(leagueKey) ?? [];
                return (
                  <SectionCard
                    key={leagueKey}
                    collapsible
                    defaultOpen={false}
                    title={<LeagueLabel league={leagueKey} label={leagueKey} className="text-[14px] font-semibold text-slate-100" iconSize={16} />}
                    subtitle={`${leagueRows.length} fixture${leagueRows.length !== 1 ? "s" : ""}`}
                  >
                    <div className="space-y-4">
                      {leagueRows.map((row, i) => {
                        const fixtureKey = [
                          (row.league ?? "").trim().toLowerCase(),
                          (row.date ?? "").trim().slice(0, 10),
                          normalizeTeamKey(row.home_team),
                          normalizeTeamKey(row.away_team),
                        ].join("|");
                        const pinnacleFixture = pinnacleMatchByFixture.get(fixtureKey);
                        return (
                          <div key={`${row.home_team}-${row.away_team}-${i}`} className="rounded-2xl border border-slate-800/70 bg-slate-950/30 p-4">
                            <div className="mb-3 flex flex-wrap items-start justify-between gap-2">
                              <div>
                                <MatchLabel
                                  league={row.league}
                                  homeTeam={row.home_team}
                                  awayTeam={row.away_team}
                                  iconSize={18}
                                  textClassName="text-sm font-semibold text-slate-100"
                                />
                                <div className="mt-1 text-[11px] text-slate-500">
                                  <LeagueLabel league={row.league} label={row.league} iconSize={14} />{" "}
                                  <span className="ml-2">{formatKickoff(row.kick_off)}</span>
                                  <span className="ml-2 text-slate-600">
                                    {pinnacleFixture ? "Pinnacle matched" : "Missing in latest Pinnacle capture"}
                                  </span>
                                </div>
                              </div>
                              <div className="text-right text-[11px] text-slate-500">
                                policy {policyVersion(row)}
                              </div>
                            </div>

                            <CornersTrustPanel row={row} />

                            <div className="mt-3 overflow-x-auto">
                              <table className="w-full text-left text-xs">
                                <thead>
                                  <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                                    <th className="py-2 pr-3">Line</th>
                                    <th className="py-2 pr-3 font-mono">Cal fair O</th>
                                    <th className="py-2 pr-3 font-mono">Book O</th>
                                    <th className="py-2 pr-3 font-mono">Value O</th>
                                    <th className="py-2 pr-3 font-mono">Cal fair U</th>
                                    <th className="py-2 pr-3 font-mono">Book U</th>
                                    <th className="py-2 pr-3 font-mono">Value U</th>
                                    <th className="py-2 pr-3">Consensus</th>
                                    <th className="py-2 font-mono">Divergence</th>
                                  </tr>
                                </thead>
                                <tbody>
                                  {signalLineValues.map((line) => {
                                    const rawOver = maybeFloat(row[`p_over_${line}`]);
                                    const calOver = calibrateCornersProbability(rawOver, line, calibrationParams);
                                    const calUnder = calOver === null ? null : 1 - calOver;
                                    const calFairOver = fairDecimal(calOver);
                                    const calFairUnder = fairDecimal(calUnder);
                                    const lineData = pinnacleFixture?.lines[line.toFixed(1)] ?? null;
                                    const overOdds = lineData?.over ?? null;
                                    const underOdds = lineData?.under ?? null;
                                    const overEdge = probabilityEdge(calOver, overOdds);
                                    const underEdge = probabilityEdge(calUnder, underOdds);
                                    return (
                                      <tr key={`${row.home_team}-${row.away_team}-${line}`} className="border-b border-slate-800/40">
                                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-300">{line.toFixed(1)}</td>
                                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-100">
                                          {calFairOver !== null ? calFairOver.toFixed(2) : "--"}
                                        </td>
                                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-300">
                                          {overOdds !== null && overOdds > 0 ? overOdds.toFixed(2) : "--"}
                                        </td>
                                        <td className="py-1.5 pr-3 font-mono tabular-nums">
                                          <span className={overEdge !== null && overEdge > 0 ? "text-emerald-300" : overEdge !== null && overEdge < 0 ? "text-rose-400" : "text-slate-500"}>
                                            {formatSignedPercent(overEdge !== null ? overEdge * 100 : null)}
                                          </span>
                                        </td>
                                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-100">
                                          {calFairUnder !== null ? calFairUnder.toFixed(2) : "--"}
                                        </td>
                                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-300">
                                          {underOdds !== null && underOdds > 0 ? underOdds.toFixed(2) : "--"}
                                        </td>
                                        <td className="py-1.5 pr-3 font-mono tabular-nums">
                                          <span className={underEdge !== null && underEdge > 0 ? "text-emerald-300" : underEdge !== null && underEdge < 0 ? "text-rose-400" : "text-slate-500"}>
                                            {formatSignedPercent(underEdge !== null ? underEdge * 100 : null)}
                                          </span>
                                        </td>
                                        <td className="py-1.5 pr-3">
                                          <StatusPill label={consensusLabel(consensusState(row.consensus))} tone={consensusTone(consensusState(row.consensus))} />
                                        </td>
                                        <td className="py-1.5 font-mono tabular-nums text-slate-400">
                                          {formatSignedPercent((maybeFloat(row.divergence) ?? 0) * 100)}
                                        </td>
                                      </tr>
                                    );
                                  })}
                                </tbody>
                              </table>
                            </div>
                          </div>
                        );
                      })}
                    </div>
                  </SectionCard>
                );
              })}
            </div>
          </SectionCard>
        )}

        {/* -- Pinnacle Corners Lines -- */}
        {pinnacleMatches.length > 0 && (
          <SectionCard collapsible defaultOpen={false} title={`Pinnacle Corners Lines - ${pinnacleMatches.length} fixtures`}>
            <div className="overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3">League</th>
                    <th className="py-2 pr-3">Match</th>
                    {pinnacleLineValues.flatMap((l) => [
                      <th key={`${l}-o`} className="py-2 pr-1 text-center font-mono">{`O ${l.toFixed(1)}`}</th>,
                      <th key={`${l}-u`} className="py-2 pr-3 text-center font-mono">{`U ${l.toFixed(1)}`}</th>,
                    ])}
                  </tr>
                </thead>
                <tbody>
                  {pinnacleMatches.map((m, i) => (
                    <tr key={i} className="border-b border-slate-800/40 hover:bg-slate-800/20">
                      <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-500">{m.match_date.slice(5)}</td>
                      <td className="py-1.5 pr-3 text-slate-500">
                        <LeagueLabel league={m.league} label={m.league} iconSize={14} />
                      </td>
                      <td className="py-1.5 pr-3 font-medium text-slate-200">
                        <MatchLabel
                          league={m.league}
                          homeTeam={m.home_team}
                          awayTeam={m.away_team}
                          iconSize={16}
                          separator="v"
                          textClassName="font-medium text-slate-200"
                        />
                      </td>
                      {pinnacleLineValues.flatMap((l) => {
                        const lineData = m.lines[l.toFixed(1)] ?? { over: 0, under: 0 };
                        return [
                          <td key={`${i}-${l}-o`} className="py-1.5 pr-1 text-center font-mono tabular-nums text-slate-300">{lineData.over > 0 ? lineData.over.toFixed(2) : "-"}</td>,
                          <td key={`${i}-${l}-u`} className="py-1.5 pr-3 text-center font-mono tabular-nums text-slate-500">{lineData.under > 0 ? lineData.under.toFixed(2) : "-"}</td>,
                        ];
                      })}
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
            <p className="mt-2 text-[11px] text-slate-600">
              Pinnacle closing-line reference. Capture: {latestPinnacleCaptureAt ?? "--"}
            </p>
          </SectionCard>
        )}

        {/* -- Reports & Tools -- */}
        {livePnlTxt && (
          <SectionCard collapsible defaultOpen={false} title="Full Live P&L Report">
            <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">{livePnlTxt}</pre>
          </SectionCard>
        )}

        {shortlistTxt && (
          <SectionCard collapsible defaultOpen={false} title="Latest Shortlist (full output)">
            <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">{shortlistTxt}</pre>
          </SectionCard>
        )}

        {calibrationTxt && (
          <SectionCard collapsible defaultOpen={false} title="Model Calibration Report">
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">{calibrationTxt}</pre>
          </SectionCard>
        )}

        {backtestReportTxt ? (
          <SectionCard collapsible defaultOpen={false} title="Backtest Report">
            <pre className="max-h-80 overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">{backtestReportTxt}</pre>
          </SectionCard>
        ) : !hasBacktestArtifacts ? (
          <SectionCard collapsible defaultOpen={false} title="Backtest Report" subtitle="Artifacts unavailable">
            <EmptyState message="Backtest report files are missing from the current snapshot source, so ROI and bet counts are unavailable here." />
          </SectionCard>
        ) : null}

        <SectionCard collapsible defaultOpen={false} title="How to use">
          <div className="space-y-3 text-sm text-slate-300">
            <div>
              <h3 className="font-medium text-slate-200">1. Generate predictions</h3>
              <code className="mt-1 block rounded bg-slate-800 px-3 py-2 text-xs">
                python scripts/matchday-shortlist.py --all-leagues --min-edge 0.08
              </code>
            </div>
            <div>
              <h3 className="font-medium text-slate-200">2. Check this page</h3>
              <p className="text-xs text-slate-400">Refresh to see the latest shortlist, value bets, and model signals.</p>
            </div>
            <div>
              <h3 className="font-medium text-slate-200">3. Settle results</h3>
              <code className="mt-1 block rounded bg-slate-800 px-3 py-2 text-xs">
                python scripts/shortlist-settle.py
              </code>
            </div>
          </div>
        </SectionCard>

      </div>
    </div>
  );
}

