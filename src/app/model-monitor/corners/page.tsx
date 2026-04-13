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

export const dynamic = "force-dynamic";

import { MODEL_MONITOR_ENABLED } from "../shared";

type CsvRow = Record<string, string>;
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

function pf(val: string | undefined, fallback = 0): number {
  const n = parseFloat(val ?? "");
  return isNaN(n) ? fallback : n;
}

function maybeFloat(val: string | undefined): number | null {
  const n = parseFloat(val ?? "");
  return Number.isFinite(n) ? n : null;
}

function formatMaybeFixed(val: string | undefined, digits = 2, placeholder = "--"): string {
  const n = maybeFloat(val);
  return n === null ? placeholder : n.toFixed(digits);
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

function formatKickoff(iso: string | undefined): string {
  if (!iso) return "--";
  const d = new Date(iso);
  if (isNaN(d.getTime())) return iso.slice(0, 10);
  const day = d.getUTCDate().toString().padStart(2, "0");
  const mon = ["Jan","Feb","Mar","Apr","May","Jun","Jul","Aug","Sep","Oct","Nov","Dec"][d.getUTCMonth()];
  const hh = d.getUTCHours().toString().padStart(2, "0");
  const mm = d.getUTCMinutes().toString().padStart(2, "0");
  return `${day} ${mon} ${hh}:${mm}`;
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

function isoDateInTimezone(timeZone = "Europe/London", value = new Date()): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(value);
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

const CURRENT_POLICY = "V3";
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
  if (delta >= 0.15) return `↑ hot ${formatSignedPercent(delta * 100)}`;
  if (delta <= -0.15) return `↓ cold ${formatSignedPercent(delta * 100)}`;
  return formatSignedPercent(delta * 100);
}

function formatSignedPercent(value: number | null): string {
  if (value === null || Number.isNaN(value)) return "--";
  return `${value >= 0 ? "+" : ""}${value.toFixed(1)}%`;
}

function policySummaryRows(rows: CsvRow[]): Array<{
  version: string;
  settled: number;
  pending: number;
  pnl: number;
  roi: number | null;
  avgOdds: number | null;
  avgEdge: number | null;
}> {
  const byVersion = new Map<string, CsvRow[]>();
  for (const row of rows) {
    const version = policyVersion(row);
    if (!byVersion.has(version)) byVersion.set(version, []);
    byVersion.get(version)!.push(row);
  }
  return [...byVersion.entries()]
    .map(([version, versionRows]) => {
      const settled = versionRows.filter((row) => row.settled === "yes");
      const pending = versionRows.filter((row) => row.settled !== "yes");
      const pnl = settled.reduce((sum, row) => sum + pf(row.pnl_staked), 0);
      const staked = settled.reduce((sum, row) => sum + pf(row.stake, 1), 0);
      return {
        version,
        settled: settled.length,
        pending: pending.length,
        pnl,
        roi: settled.length > 0 && staked > 0 ? (pnl / staked) * 100 : null,
        avgOdds: settled.length > 0 ? settled.reduce((sum, row) => sum + pf(row.bookie_odds), 0) / settled.length : null,
        avgEdge: settled.length > 0 ? settled.reduce((sum, row) => sum + pf(row.edge), 0) / settled.length * 100 : null,
      };
    })
    .filter((row) => row.settled >= 5 || row.pending > 0)
    .sort((a, b) => a.version.localeCompare(b.version));
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
    backtestReportTxt,
    backtestCsv,
    predictionsCsv,
    pinnacleCornersCsv,
    shortlistTxt,
    valueBetsCsv,
    signalsCsv,
    settledCsv,
    livePnlTxt,
    pipelineStatus,
    pinnacleCornersMtime,
    shortlistMtime,
    predictionsMtime,
    snapshotGeneratedAt,
    shortlistSource,
  ] = await Promise.all([
      readFile("data/corners-ou/corners-ou-calibration.txt"),
      readFile("data/corners-ou/corners-ou-backtest-report.txt"),
      readFile("data/corners-ou/corners-ou-backtest-results.csv"),
      readFile("data/corners-ou/corners-ou-predictions.csv"),
      readFile("data/corners-ou/pinnacle-corners-odds.csv"),
      readFile("data/shortlist/shortlist-latest.txt"),
      readFile("data/shortlist/value-bets-latest.csv"),
      readFile("data/shortlist/signals-latest.csv"),
      readFile("data/shortlist/settled-pnl.csv"),
      readFile("data/shortlist/corners-live-pnl.txt"),
      readJson<TeamPropsStatus>("data/shortlist/team-props-status.json"),
      readKnownFileMtime("data/corners-ou/pinnacle-corners-odds.csv"),
      readKnownFileMtime("data/shortlist/shortlist-latest.txt"),
      readKnownFileMtime("data/corners-ou/corners-ou-predictions.csv"),
      readCornersLiveSnapshotGeneratedAt(),
      inspectCornersLiveSource("data/shortlist/signals-latest.csv"),
    ]);

  const backtestRows = backtestCsv ? parseCsv(backtestCsv) : [];
  const hasBacktestRows = backtestRows.length > 0;
  const hasBacktestArtifacts = Boolean(backtestCsv?.trim() || backtestReportTxt?.trim());
  const predictions = predictionsCsv ? parseCsv(predictionsCsv) : [];
  const pinnacleRows = pinnacleCornersCsv ? parseCsv(pinnacleCornersCsv) : [];
  const valueBets = valueBetsCsv ? parseCsv(valueBetsCsv) : [];
  const signals = signalsCsv ? parseCsv(signalsCsv) : [];
  // Derive line values from column names so the table isn't hardcoded to 9.5/10.5
  const signalLineValues = signals.length > 0
    ? Object.keys(signals[0])
        .filter(k => k.startsWith("fair_over_"))
        .map(k => parseFloat(k.replace("fair_over_", "")))
        .filter(n => !isNaN(n))
        .sort((a, b) => a - b)
    : [9.5, 10.5];
  const signalDateLookup = new Map<string, CsvRow>();
  for (const row of signals) {
    const key = `${(row.league ?? "").trim().toLowerCase()}|${(row.home_team ?? "").trim().toLowerCase()}|${(row.away_team ?? "").trim().toLowerCase()}`;
    signalDateLookup.set(key, row);
  }
  const latestPinnacleCaptureAt =
    [...pinnacleRows]
      .map((r) => r.captured_at ?? "")
      .filter(Boolean)
      .sort()
      .at(-1) ?? null;

  const dedupedCurrentSignals = new Map<string, CurrentValueSignal>();
  for (const row of valueBets) {
    const [homeTeam = "", awayTeam = ""] = (row.match ?? "").split(" vs ");
    const signalKey = `${(row.league ?? "").trim().toLowerCase()}|${homeTeam.trim().toLowerCase()}|${awayTeam.trim().toLowerCase()}`;
    const signalRow = signalDateLookup.get(signalKey);
    const currentSignal: CurrentValueSignal = {
      row,
      displayDate: (signalRow?.kick_off ?? signalRow?.date ?? "").slice(0, 10) || "-",
      edgeValue: pf(row.edge),
    };
    const dedupeKey = `${(row.league ?? "").trim().toLowerCase()}|${(row.match ?? "").trim().toLowerCase()}|${(row.side ?? "").trim().toLowerCase()}`;
    const existing = dedupedCurrentSignals.get(dedupeKey);
    if (!existing || currentSignal.edgeValue > existing.edgeValue) {
      dedupedCurrentSignals.set(dedupeKey, currentSignal);
    }
  }
  const currentValueSignalsAll: CurrentValueSignal[] = [...dedupedCurrentSignals.values()].sort(
    (a, b) => b.edgeValue - a.edgeValue,
  );
  const currentValueSignals = currentValueSignalsAll.filter((entry) => policyVersion(entry.row) === CURRENT_POLICY);

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

  // Collect all line values found across Pinnacle fixtures so the table doesn't silently drop unusual lines
  const pinnacleLineValues = [...new Set(
    pinnacleMatches.flatMap(m => Object.keys(m.lines))
  )].map(l => parseFloat(l)).filter(n => !isNaN(n)).sort((a, b) => a - b);

  // Live P&L from settlement
  const settledRows = settledCsv ? parseCsv(settledCsv) : [];
  const liveSettled = settledRows.filter((r) => r.settled === "yes");
  // Pending sorted by kickoff ascending (soonest game first)
  const livePending = settledRows
    .filter((r) => r.settled === "pending")
    .sort((a, b) => (a.kick_off ?? a.match_date ?? "").localeCompare(b.kick_off ?? b.match_date ?? ""));
  const currentPolicyPending = livePending.filter((row) => policyVersion(row) === CURRENT_POLICY);
  const previousPolicyPending = livePending.filter((row) => policyVersion(row) !== CURRENT_POLICY);
  const livePendingExposure = livePending.reduce((s, r) => s + pf(r.stake, 1), 0);
  const liveWon    = liveSettled.filter((r) => r.won === "yes");
  const liveLost   = liveSettled.filter((r) => r.won === "no");
  const livePushed = liveSettled.filter((r) => r.won === "push");
  const liveDecisive = liveWon.length + liveLost.length; // excludes pushes from win-rate
  const liveTotalStaked = liveSettled.reduce((s, r) => s + pf(r.stake, 1), 0);
  const livePnlFlat = liveSettled.reduce((s, r) => s + pf(r.pnl_units), 0);
  const livePnlStaked = liveSettled.reduce((s, r) => s + pf(r.pnl_staked), 0);
  const liveRoiFlat = liveSettled.length > 0 ? (livePnlFlat / liveSettled.length) * 100 : 0;
  const liveRoiStaked = liveTotalStaked > 0 ? (livePnlStaked / liveTotalStaked) * 100 : 0;
  const liveWinRate = liveDecisive > 0 ? (liveWon.length / liveDecisive) * 100 : 0;
  // Settled sorted by settled_at descending (most recently graded first), falling
  // back to kick_off / match_date for rows written before settled_at was added.
  const recentSettled = [...liveSettled]
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
  const versionSummaries = policySummaryRows(settledRows);

  // Live P&L by league
  const leagueNames = ["serie-a", "la-liga", "bundesliga", "epl", "ligue-1"];
  const liveByLeague = leagueNames.map((lg) => {
    const rows = liveSettled.filter((r) => r.league === lg);
    const won = rows.filter((r) => r.won === "yes").length;
    const staked = rows.reduce((s, r) => s + pf(r.stake, 1), 0);
    const pnlVal = rows.reduce((s, r) => s + pf(r.pnl_staked), 0);
    const roi = staked > 0 ? (pnlVal / staked) * 100 : 0;
    return { lg, n: rows.length, won, pnlVal, roi };
  }).filter((x) => x.n > 0);

  // Team name aliases: our model names â†’ Pinnacle names (lowercase)
  const TEAM_ALIASES: Record<string, string> = {
    "brighton and hove albion": "brighton",
    "atalanta bc": "atalanta",
    "tsg hoffenheim": "hoffenheim",
    "inter milan": "internazionale",
    "fc st. pauli": "st. pauli",
    "vfb stuttgart": "stuttgart",
    "borussia m'gladbach": "borussia monchengladbach",
    "m'gladbach": "borussia monchengladbach",
    "bayer 04 leverkusen": "bayer leverkusen",
    "sc freiburg": "freiburg",
    "1. fc union berlin": "union berlin",
    "wolverhampton wanderers": "wolverhampton",
    "nottingham forest": "nottingham forest",
  };

  function normOurTeam(name: string): string {
    const lower = name.trim().toLowerCase();
    return TEAM_ALIASES[lower] ?? lower;
  }

  // Build Pinnacle match info map: home|away â†’ { match_date, kickoff_iso }
  // (Pinnacle has the correct game date; our settled-pnl match_date is the
  // shortlist run date which differs from actual game date)
  const pinnacleMatchInfoMap = new Map<string, { match_date: string; kickoff_iso: string }>();
  for (const row of pinnacleRows) {
    if (isAggregatePinnacleTeam(row.home_team) || isAggregatePinnacleTeam(row.away_team)) continue;
    const home = normalizePinnacleTeamName(row.home_team).toLowerCase();
    const away = normalizePinnacleTeamName(row.away_team).toLowerCase();
    if (!home || !away) continue;
    const key = `${home}|${away}`;
    if (!pinnacleMatchInfoMap.has(key)) {
      const kickoff = (row.kickoff_iso ?? "").trim();
      const matchDate = (row.match_date ?? "").slice(0, 10);
      if (kickoff && matchDate) pinnacleMatchInfoMap.set(key, { match_date: matchDate, kickoff_iso: kickoff });
    }
  }

  // Render time for kickoff comparison (server-side, force-dynamic)
  const renderNowMs = Date.now();

  // Build current Pinnacle odds map: only pre-kickoff snapshots.
  // Key: home_norm|away_norm|line|side. Keeps last snapshot captured before KO.
  // (No match_date in key - our settled-pnl match_date is the shortlist run date)
  const currentPinnacleOdds = new Map<string, number>();
  const currentPinnacleOddsTs = new Map<string, string>();
  for (const row of pinnacleRows) {
    if (isAggregatePinnacleTeam(row.home_team) || isAggregatePinnacleTeam(row.away_team)) continue;
    const home = normalizePinnacleTeamName(row.home_team).toLowerCase();
    const away = normalizePinnacleTeamName(row.away_team).toLowerCase();
    const line = (row.line ?? "").trim();
    const side = (row.side ?? "").trim().toLowerCase();
    const odds = pf(row.odds_decimal);
    if (!home || !away || !line || !side || odds <= 0) continue;
    const rowTs = row.captured_at ?? "";
    // Skip post-kickoff snapshots so "Now" always shows the last pre-KO price
    const matchInfo = pinnacleMatchInfoMap.get(`${home}|${away}`);
    if (matchInfo?.kickoff_iso && rowTs >= matchInfo.kickoff_iso) continue;
    const key = `${home}|${away}|${line}|${side}`;
    const existingTs = currentPinnacleOddsTs.get(key) ?? "";
    if (!existingTs || rowTs >= existingTs) {
      currentPinnacleOdds.set(key, odds);
      currentPinnacleOddsTs.set(key, rowTs);
    }
  }

  type PinnacleInfo = { odds: number | null; kickedOff: boolean; matchDate: string | null; kickoffIso: string | null };

  function getPinnacleInfo(row: CsvRow): PinnacleInfo {
    const parts = (row.match ?? "").split(" vs ");
    if (parts.length !== 2) return { odds: null, kickedOff: false, matchDate: null, kickoffIso: null };
    const home = normOurTeam(parts[0]);
    const away = normOurTeam(parts[1]);
    const teamKey = `${home}|${away}`;
    const matchInfo = pinnacleMatchInfoMap.get(teamKey);
    const kickoffIso = matchInfo?.kickoff_iso ?? null;
    const matchDate = matchInfo?.match_date ?? null;
    const kickedOff = kickoffIso ? renderNowMs >= Date.parse(kickoffIso) : false;
    const line = (row.line ?? "").trim();
    const side = (row.side ?? "").trim().toLowerCase();
    const oddsKey = `${home}|${away}|${line}|${side}`;
    const odds = currentPinnacleOdds.get(oddsKey) ?? null;
    return { odds, kickedOff, matchDate, kickoffIso };
  }

  // CLV KPI for settled bets
  const settledWithClv = liveSettled.filter((r) => r.clv && r.clv.trim() !== "");
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

  const recentPredictions = predictions.slice(-80).reverse();
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
  const renderReferenceMs = renderReferenceAt ? Date.parse(renderReferenceAt) : Number.NaN;
  const todayIso = renderReferenceAt ? isoDateInTimezone("Europe/London", new Date(renderReferenceAt)) : isoDateInTimezone("Europe/London");
  const pipelineTone =
    pipelineStatus?.state === "failed"
      ? "red"
      : pipelineStatus?.warnings?.length
        ? "amber"
        : "green";

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

        {/* -- Pipeline Health -- */}
        <SectionCard collapsible title="Pipeline Health" subtitle="Data freshness and source status">
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

        {!predictionsCsv && (
          <section className="rounded-2xl border border-amber-700/40 bg-amber-950/30 p-4 text-sm text-amber-200">
            No prediction data found. Run{" "}
            <code className="rounded bg-slate-800 px-1.5 py-0.5 text-xs">python scripts/corners-ou-model.py</code>{" "}
            then{" "}
            <code className="rounded bg-slate-800 px-1.5 py-0.5 text-xs">python scripts/matchday-shortlist.py --all-leagues</code>
          </section>
        )}

        {/* -- KPI strip -- */}
        <section className="grid grid-cols-2 gap-2.5 sm:grid-cols-4 lg:grid-cols-7">
          <StatCard label="Historical matches" value={predictions.length.toLocaleString()} detail="with predictions" />
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
            label="Today value bets"
            value={currentValueSignals.length.toString()}
            detail="V3 active shortlist"
            tone={statTone(currentValueSignals.length > 0 ? "amber" : "default")}
          />
          <StatCard label="Signals tracked" value={signals.length.toString()} detail="upcoming fixtures" />
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

        <p className="rounded-xl border border-slate-800/60 bg-slate-900/30 px-4 py-3 text-xs text-slate-400">
          <strong className="text-slate-200">How to read this page.</strong>{" "}
          <span className="text-slate-300">All model fixtures</span> is the full slate the corners model priced.{" "}
          <span className="text-slate-300">Active signals (V3)</span> is the subset where the calibrated edge cleared the
          15% threshold and survived the divergence gate. Previous-regime bets are still tracked separately until they settle.
        </p>

        {/* -- Current Bettable Signals -- */}
        {currentValueSignals.length > 0 && (
          <SectionCard
            title={`Active signals (V3) - ${currentValueSignals.length} best bets`}
            subtitle={`Deduplicated from ${valueBets.length} raw lines | best-value per match and side | divergence gate active`}
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
                    <th className="py-2 pr-3 font-mono">Fair</th>
                    <th className="py-2 pr-3 font-mono">Edge</th>
                    <th className="py-2 pr-3">Trust</th>
                    <th className="py-2 font-mono">Stake</th>
                  </tr>
                </thead>
                <tbody>
                  {currentValueSignals.map((item, i) => {
                    const row = item.row;
                    const edge = item.edgeValue;
                    const matchDate = (item.displayDate ?? "").trim().slice(0, 10);
                    const isPast = matchDate && matchDate < todayIso;
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
          defaultOpen={liveSettled.length > 0 || livePending.length > 0}
          title={`Bet Tracker${livePending.length > 0 ? ` - ${livePending.length} open` : ""}${liveSettled.length > 0 ? `, ${liveSettled.length} settled` : ""}`}
        >
          {liveSettled.length === 0 && livePending.length === 0 ? (
            <EmptyState message="No bets tracked yet. Run python scripts/shortlist-settle.py after results are in." />
          ) : (
            <div className="space-y-5">
              {/* KPI stats */}
              {liveSettled.length > 0 && (
                <>
                  <div className="grid grid-cols-2 gap-2.5 sm:grid-cols-3 lg:grid-cols-5">
                    <StatCard
                      label="P&L (flat)"
                      value={`${livePnlFlat >= 0 ? "+" : ""}${livePnlFlat.toFixed(2)}u`}
                      detail={`${liveWon.length}W / ${liveLost.length}L`}
                      tone={statTone(livePnlFlat > 0 ? "green" : livePnlFlat < 0 ? "red" : "default")}
                    />
                    <StatCard
                      label="P&L (staked)"
                      value={`${livePnlStaked >= 0 ? "+" : ""}${livePnlStaked.toFixed(2)}u`}
                      detail={`${liveTotalStaked.toFixed(1)}u staked`}
                      tone={statTone(livePnlStaked > 0 ? "green" : livePnlStaked < 0 ? "red" : "default")}
                    />
                    <StatCard
                      label="ROI (flat)"
                      value={`${liveRoiFlat >= 0 ? "+" : ""}${liveRoiFlat.toFixed(1)}%`}
                      tone={statTone(liveRoiFlat > 5 ? "green" : liveRoiFlat < -5 ? "red" : "amber")}
                    />
                    <StatCard
                      label="ROI (staked)"
                      value={`${liveRoiStaked >= 0 ? "+" : ""}${liveRoiStaked.toFixed(1)}%`}
                      detail={`${liveSettled.length} settled`}
                      tone={statTone(liveRoiStaked > 5 ? "green" : liveRoiStaked < -5 ? "red" : "amber")}
                    />
                    <StatCard
                      label="Win rate"
                      value={`${liveWinRate.toFixed(0)}%`}
                      detail={`${liveWon.length}W/${liveLost.length}L${livePushed.length > 0 ? `/${livePushed.length}P` : ""} | ${livePending.length} open`}
                      tone={statTone(liveWinRate > 55 ? "green" : liveWinRate < 45 ? "red" : "default")}
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
                              <td className="py-1.5 pr-4 text-right font-mono tabular-nums text-slate-400">{won}W/{n - won}L</td>
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
                    <div className="overflow-x-auto">
                      <div className="mb-2 text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                        Policy split
                      </div>
                      <table className="w-full text-left text-xs">
                        <thead>
                          <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                            <th className="py-2 pr-4">Version</th>
                            <th className="py-2 pr-4 text-right font-mono">Settled</th>
                            <th className="py-2 pr-4 text-right font-mono">Pending</th>
                            <th className="py-2 pr-4 text-right font-mono">P&L</th>
                            <th className="py-2 pr-4 text-right font-mono">ROI</th>
                            <th className="py-2 pr-4 text-right font-mono">Avg odds</th>
                            <th className="py-2 text-right font-mono">Avg edge</th>
                          </tr>
                        </thead>
                        <tbody>
                          {versionSummaries.map((row) => (
                            <tr key={row.version} className="border-b border-slate-800/40">
                              <td className="py-1.5 pr-4 font-medium text-slate-200">{row.version}</td>
                              <td className="py-1.5 pr-4 text-right font-mono tabular-nums text-slate-400">{row.settled}</td>
                              <td className="py-1.5 pr-4 text-right font-mono tabular-nums text-slate-400">{row.pending}</td>
                              <td className={`py-1.5 pr-4 text-right font-mono tabular-nums ${row.pnl >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                                {row.pnl >= 0 ? "+" : ""}{row.pnl.toFixed(2)}u
                              </td>
                              <td className="py-1.5 pr-4 text-right font-mono tabular-nums text-slate-300">
                                {row.roi === null ? "pending" : `${row.roi >= 0 ? "+" : ""}${row.roi.toFixed(1)}%`}
                              </td>
                              <td className="py-1.5 pr-4 text-right font-mono tabular-nums text-slate-400">
                                {row.avgOdds === null ? "--" : row.avgOdds.toFixed(2)}
                              </td>
                              <td className="py-1.5 text-right font-mono tabular-nums text-slate-400">
                                {row.avgEdge === null ? "--" : `${row.avgEdge >= 0 ? "+" : ""}${row.avgEdge.toFixed(1)}%`}
                              </td>
                            </tr>
                          ))}
                        </tbody>
                      </table>
                    </div>
                  )}
                </>
              )}

              {/* -- Open bets -- */}
              {currentPolicyPending.length > 0 && (
                <div>
                  <div className="mb-2 flex items-baseline gap-3">
                    <span className="text-[10px] font-semibold uppercase tracking-wider text-slate-500">
                      Active signals (V3) pending ({currentPolicyPending.length})
                    </span>
                    <span className="text-[10px] text-slate-600">
                      {currentPolicyPending.reduce((sum, row) => sum + pf(row.stake, 1), 0).toFixed(1)}u exposure
                    </span>
                  </div>
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                          <th className="py-2 pr-3">Kickoff</th>
                          <th className="py-2 pr-3">Match</th>
                          <th className="py-2 pr-3">Line</th>
                          <th className="py-2 pr-3">Side</th>
                          <th className="py-2 pr-3 font-mono">Entry</th>
                          <th className="py-2 pr-3 font-mono">Pinnacle</th>
                          <th className="py-2 pr-3 font-mono">Edge</th>
                          <th className="py-2 pr-3">Trust</th>
                          <th className="py-2 font-mono">Stake</th>
                        </tr>
                      </thead>
                      <tbody>
                        {currentPolicyPending.map((row, i) => {
                          const entryOdds = pf(row.bookie_odds);
                          const { odds: pinOdds, kickedOff } = getPinnacleInfo(row);
                          const kickoffDisplay = formatKickoff(row.kick_off);
                          const oddsMove = !kickedOff && pinOdds !== null && entryOdds > 0 ? pinOdds - entryOdds : null;
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
                              <td className="py-1.5 pr-3 font-mono tabular-nums">
                                {kickedOff ? (
                                  <span className="text-[10px] uppercase tracking-wide text-slate-600">KO</span>
                                ) : pinOdds !== null ? (
                                  <span className={oddsMove !== null && oddsMove > 0.01 ? "text-emerald-300" : oddsMove !== null && oddsMove < -0.01 ? "text-rose-400" : "text-slate-400"}>
                                    {oddsMove !== null && oddsMove > 0.01 ? "â†‘" : oddsMove !== null && oddsMove < -0.01 ? "â†“" : ""}{pinOdds.toFixed(2)}
                                  </span>
                                ) : <span className="text-slate-600">--</span>}
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{(pf(row.edge) * 100).toFixed(1)}%</td>
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
                </div>
              )}

              {previousPolicyPending.length > 0 && (
                <SectionCard
                  collapsible
                  defaultOpen={false}
                  title={`Previous regime pending - ${previousPolicyPending.length} total`}
                  subtitle="Logged under V2 (no divergence gate) — settling at original stake"
                >
                  <div className="overflow-x-auto">
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                          <th className="py-2 pr-3">Kickoff</th>
                          <th className="py-2 pr-3">Match</th>
                          <th className="py-2 pr-3">Line</th>
                          <th className="py-2 pr-3">Side</th>
                          <th className="py-2 pr-3 font-mono">Entry</th>
                          <th className="py-2 pr-3 font-mono">Pinnacle</th>
                          <th className="py-2 pr-3 font-mono">Edge</th>
                          <th className="py-2 font-mono">Stake</th>
                        </tr>
                      </thead>
                      <tbody>
                        {previousPolicyPending.map((row, i) => {
                          const entryOdds = pf(row.bookie_odds);
                          const { odds: pinOdds, kickedOff } = getPinnacleInfo(row);
                          const kickoffDisplay = formatKickoff(row.kick_off);
                          const oddsMove = !kickedOff && pinOdds !== null && entryOdds > 0 ? pinOdds - entryOdds : null;
                          return (
                            <tr key={`${row.match}-${row.line}-${row.side}-${i}`} className={`border-b border-slate-800/40 hover:bg-slate-800/20 ${kickedOff ? "opacity-60" : ""}`}>
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
                              <td className="py-1.5 pr-3 font-mono tabular-nums">
                                {kickedOff ? (
                                  <span className="text-[10px] uppercase tracking-wide text-slate-600">KO</span>
                                ) : pinOdds !== null ? (
                                  <span className={oddsMove !== null && oddsMove > 0.01 ? "text-emerald-300" : oddsMove !== null && oddsMove < -0.01 ? "text-rose-400" : "text-slate-400"}>
                                    {pinOdds.toFixed(2)}
                                  </span>
                                ) : <span className="text-slate-600">--</span>}
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{(pf(row.edge) * 100).toFixed(1)}%</td>
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
                  title={`Recent Results - ${liveSettled.length} total`}
                  subtitle={`Showing the latest ${recentSettled.length} settled bets, grouped by league`}
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
            subtitle="Grouped by league so you can open only what you need"
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
                      {leagueRows.map((row, i) => (
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
                                  <th className="py-2 pr-3 font-mono">Fair over</th>
                                  <th className="py-2 pr-3 font-mono">Fair under</th>
                                  <th className="py-2 pr-3">Consensus</th>
                                  <th className="py-2 font-mono">Divergence</th>
                                </tr>
                              </thead>
                              <tbody>
                                {signalLineValues.map((line) => (
                                  <tr key={`${row.home_team}-${row.away_team}-${line}`} className="border-b border-slate-800/40">
                                    <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-300">{line.toFixed(1)}</td>
                                    <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-100">{formatMaybeFixed(row[`fair_over_${line}`])}</td>
                                    <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{formatMaybeFixed(row[`fair_under_${line}`])}</td>
                                    <td className="py-1.5 pr-3">
                                      <StatusPill label={consensusLabel(consensusState(row.consensus))} tone={consensusTone(consensusState(row.consensus))} />
                                    </td>
                                    <td className="py-1.5 font-mono tabular-nums text-slate-400">
                                      {formatSignedPercent((maybeFloat(row.divergence) ?? 0) * 100)}
                                    </td>
                                  </tr>
                                ))}
                              </tbody>
                            </table>
                          </div>
                        </div>
                      ))}
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

