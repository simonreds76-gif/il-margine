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

export const dynamic = "force-dynamic";



type CsvRow = Record<string, string>;
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
      return { label: "SIGNAL ⚠", tone: "bg-amber-500/10 text-amber-300 border-amber-500/20" };
    }
    if (side === "under") {
      return { label: "UNDER ★", tone: "bg-cyan-500/10 text-cyan-300 border-cyan-500/20" };
    }
    return { label: "SIGNAL", tone: "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" };
  }
  return { label: "WATCH", tone: "bg-slate-700/30 text-slate-300 border-slate-600/30" };
}

function effectiveStake(edgeDecimal: number, consensus: ConsensusState): number {
  let stake = shadowStakeUnits(edgeDecimal);
  let numericStake = pf(stake.replace("u", ""), 0);
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



function formatRelativeAgeShort(value?: string | null): string {

  if (!value) return "n/a";

  const stamp = Date.parse(value);

  if (Number.isNaN(stamp)) return "n/a";

  const diffMs = Date.now() - stamp;

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

    predictionsCsv,

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

  ] = await Promise.all([

    readFile("data/team-shots/team-shots-calibration.txt"),
    readJson<CalibrationPayload>("data/team-shots/team-shots-calibration-params.json"),

    readFile("data/team-shots/team-shots-backtest-report.txt"),

    readFile("data/team-shots/team-shots-backtest-results.csv"),

    readFile("data/team-shots/shadow/team-shots-shadow-signals.csv"),

    readFile("data/team-shots/shadow/team-shots-shadow-performance.txt"),

    readFile("data/team-shots/team-shots-predictions.csv"),

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

  ]);



  const shadowSignals = shadowSignalsCsv ? parseCsv(shadowSignalsCsv) : [];
  const comparisonRows = (comparisonCsv ? parseCsv(comparisonCsv) : []).filter(
    (row) => (row.league ?? "").trim() !== "ligue-1",
  );

  const backtestRows = backtestCsv ? parseCsv(backtestCsv) : [];
  const hasBacktestArtifacts = Boolean(backtestCsv?.trim() || backtestReportTxt?.trim());

  const predictions = predictionsCsv ? parseCsv(predictionsCsv) : [];

  const oddsArchiveRaw = oddsArchiveCsv ? parseCsv(oddsArchiveCsv) : [];

  const oddsArchive = oddsArchiveRaw.filter(

    (r) =>

      (r.market || "").toUpperCase() === "TEAM_SHOTS" ||

      ((r.team || "").trim() !== "" && !(r.player || "").trim()),

  );



  const settledShadow = shadowSignals.filter(

    (r) => r.result === "won" || r.result === "lost" || r.result === "push",

  );

  const pendingShadow = shadowSignals.filter((r) => r.result === "pending");

  const shadowPnl = settledShadow.reduce((s, r) => s + pf(r.pnl), 0);

  const shadowPnlStaked = settledShadow.reduce((s, r) => s + pf(r.pnl_staked), 0);

  const shadowStakedTotal = settledShadow.reduce((s, r) => s + pf(r.stake_units || "1"), 0);

  const shadowWins = settledShadow.filter((r) => r.result === "won").length;

  const shadowRoi =

    settledShadow.length > 0 ? (shadowPnl / settledShadow.length) * 100 : 0;

  const shadowRoiStaked =

    shadowStakedTotal > 0 ? (shadowPnlStaked / shadowStakedTotal) * 100 : 0;

  const clvSettled = settledShadow.filter((r) => r.clv && r.clv.trim() !== "");
  const avgClv = clvSettled.length > 0
    ? clvSettled.reduce((s, r) => s + pf(r.clv), 0) / clvSettled.length * 100
    : null;



  const backtestPnl = backtestRows.reduce((s, r) => s + pf(r.pnl), 0);

  const backtestWins = backtestRows.filter(

    (r) => r.won === "True" || r.won === "true",

  ).length;

  const backtestRoi =

    backtestRows.length > 0 ? (backtestPnl / backtestRows.length) * 100 : 0;



  const recentPredictions = predictions.slice(-100).reverse();

  const currentShadowLive = [...comparisonRows]
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
    });



  const upcomingRows = (upcomingCsv ? parseCsv(upcomingCsv) : []).filter(
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

  const pipelineTone =

    pipelineStatus?.state === "failed"

      ? "red"

      : pipelineStatus?.warnings?.length

        ? "amber"

        : "green";

  // Use a stable snapshot-based day boundary so server/client render the same split.
  const asOfIso = (
    snapshotGeneratedAt ??
    comparisonMtime ??
    upcomingMtime ??
    predictionsMtime ??
    new Date().toISOString()
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
    pendingState: "upcoming" | "awaiting result";
    currentOdds: number | null;
    delta: number | null;
    currentLine: string | null;
    currentBookmaker: string | null;
    lineMoved: boolean;
  };

  const pendingShadowRows: PendingShadowRow[] = pendingShadow
    .map((row): PendingShadowRow => {
      const matchDate = (row.date ?? "").slice(0, 10);
      const teamKey = `${matchKey(matchDate, row.home_team, row.away_team)}|${normalizeTeamName(row.team)}`;
      const currentTeamLines = liveOddsByMatchTeam.get(teamKey);
      const lineKey = `${(row.bookmaker ?? "").trim()}|${(row.line ?? "").trim()}`;
      const currentLine = currentTeamLines?.get(lineKey);
      const sameBookLines = [...(currentTeamLines?.values() ?? [])].filter(
        (line) => line.bookmaker === (row.bookmaker ?? "").trim(),
      );
      const fallbackLine =
        currentLine ??
        sameBookLines
          .slice()
          .sort((a, b) => Math.abs(a.line - pf(row.line, 0)) - Math.abs(b.line - pf(row.line, 0)))[0];
      const currentOdds =
        fallbackLine
          ? (row.side === "over" ? fallbackLine.overOdds : fallbackLine.underOdds) ?? null
          : null;
      const loggedOdds = pf(row.book_odds, Number.NaN);
      const delta =
        currentOdds !== null && !Number.isNaN(loggedOdds) ? currentOdds - loggedOdds : null;
      const currentModel = upcomingModelByMatchTeam.get(teamKey);
      const currentMetrics =
        fallbackLine && currentModel
          ? computeLineMetrics(currentModel.row, currentModel.side, fallbackLine, calibrationParams)
          : null;
      let currentFairOdds =
        currentMetrics
          ? row.side === "over"
            ? currentMetrics.fairOver
            : currentMetrics.fairUnder
          : null;
      let currentEdgePct =
        currentMetrics
          ? row.side === "over"
            ? currentMetrics.overEdge
            : currentMetrics.underEdge
          : null;
      if (currentFairOdds === null || currentEdgePct === null) {
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
          currentFairOdds = Number.isNaN(fair) ? null : fair;
          currentEdgePct = Number.isNaN(edge) ? null : edge * 100;
        }
      }
      const storedEdge = pf(row.edge, Number.NaN);
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
        entryEdgePct: Number.isNaN(storedEdge) ? null : storedEdge * 100,
        currentFairOdds,
        currentEdgePct,
        pendingState: matchDate > asOfIso ? "upcoming" : "awaiting result",
        currentOdds,
        delta,
        currentLine: fallbackLine ? fallbackLine.lineLabel : null,
        currentBookmaker: fallbackLine ? fallbackLine.bookmaker : null,
        lineMoved: Boolean(fallbackLine && currentLine !== fallbackLine),
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

  const recentSettledShadow = [...settledShadow]
    .sort((a, b) =>
      (b.settled_at ?? b.date ?? "").localeCompare(a.settled_at ?? a.date ?? ""),
    )
    .slice(0, 15);

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

        {/* Pipeline health */}
        <SectionCard collapsible title="Pipeline Health" subtitle={pipelineStatus?.state ?? "unknown"}>
          <div className="grid gap-2 sm:grid-cols-3 xl:grid-cols-6">
            <StatCard
              label="Pipeline state"
              value={pipelineStatus?.state ?? "-"}
              tone={statTone(pipelineTone)}
            />
            <StatCard
              label="Last heartbeat"
              value={schedulerHeartbeatAt ? formatRelativeAgeShort(schedulerHeartbeatAt) : "-"}
            />
            <StatCard
              label="Data source"
              value={comparisonSource?.source ?? "-"}
              tone={statTone(sourceTone(comparisonSource?.source ?? "missing"))}
              detail={comparisonSource ? formatSourceReason(comparisonSource.reason) : undefined}
            />
            <StatCard label="Predictions" value={predictionsMtime ? formatRelativeAgeShort(predictionsMtime) : "-"} />
            <StatCard label="Comparison"  value={comparisonMtime  ? formatRelativeAgeShort(comparisonMtime)  : "-"} />
            <StatCard label="Upcoming"    value={upcomingMtime    ? formatRelativeAgeShort(upcomingMtime)    : "-"} />
          </div>
          {pipelineStatus?.message ? (
            <p className="mt-3 rounded-lg border border-slate-700/50 bg-slate-900/50 px-3 py-2 text-xs text-slate-400">
              {pipelineStatus.message}
            </p>
          ) : null}
          {(pipelineStatus?.warnings?.length ?? 0) > 0 ? (
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
        </SectionCard>

        {/* -- KPI strip -- */}
        <section className="grid gap-2.5 sm:grid-cols-3 xl:grid-cols-5">
          <StatCard
            label="Shadow bets"
            value={String(settledShadow.length + pendingShadow.length)}
            detail={`${settledShadow.length} settled | ${pendingShadow.length} pending`}
          />
          <StatCard
            label="P&L flat"
            value={`${shadowPnl >= 0 ? "+" : ""}${shadowPnl.toFixed(2)}u`}
            tone={shadowPnl >= 0 ? "text-emerald-300" : "text-rose-300"}
          />
          <StatCard
            label="ROI flat"
            value={`${shadowRoi >= 0 ? "+" : ""}${shadowRoi.toFixed(1)}%`}
            tone={shadowRoi >= 0 ? "text-emerald-300" : "text-rose-300"}
            detail={`${shadowWins}/${settledShadow.length} wins`}
          />
          <StatCard
            label="P&L staked"
            value={`${shadowPnlStaked >= 0 ? "+" : ""}${shadowPnlStaked.toFixed(2)}u`}
            tone={shadowPnlStaked >= 0 ? "text-emerald-300" : "text-rose-300"}
          />
          <StatCard
            label="Avg CLV"
            value={avgClv !== null ? `${avgClv >= 0 ? "+" : ""}${avgClv.toFixed(1)}%` : "-"}
            tone={avgClv !== null ? (avgClv >= 0 ? "text-emerald-300" : "text-rose-300") : undefined}
          />
        </section>

        {/* Recent settled shadow bets */}
        {recentSettledShadow.length > 0 ? (
          <SectionCard
            collapsible
            title={`Recent Settled Shadow Bets - ${settledShadow.length} total`}
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
            title={`Pending Shadow Bets - ${pendingShadowRows.length} total`}
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
                        const curEdge = row.currentEdgePct;
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
                            <div className="mt-2 grid grid-cols-2 gap-1 sm:grid-cols-6">
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
                                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Now odds</div>
                                <div className="mt-0.5 font-mono text-xs text-slate-200">
                                  {row.currentOdds !== null ? row.currentOdds.toFixed(2) : "-"}
                                  {deltaOdds !== null ? (
                                    <span className={`ml-1 ${deltaOdds > 0 ? "text-emerald-300" : deltaOdds < 0 ? "text-rose-300" : "text-slate-500"}`}>
                                      ({deltaOdds > 0 ? "+" : deltaOdds < 0 ? "-" : ""}{Math.abs(deltaOdds).toFixed(2)})
                                    </span>
                                  ) : null}
                                </div>
                              </div>
                              <div className="rounded-lg border border-slate-800/70 bg-slate-950/40 px-2 py-1.5">
                                <div className="text-[10px] font-semibold uppercase tracking-[0.14em] text-slate-600">Now edge</div>
                                <div className={`mt-0.5 font-mono text-xs ${curEdge !== null && curEdge >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                                  {curEdge !== null ? formatSignedPercent(curEdge) : "-"}
                                </div>
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
                                Line moved - now {row.currentBookmaker} {row.currentLine}
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
        {upcomingLeagueKeys.length === 0 && predictions.length === 0 ? (
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
                        {r.captured_at ? formatRelativeAgeShort(r.captured_at) : "-"}
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
          <SectionCard collapsible defaultOpen={false} title="Shadow Performance" subtitle="team-shots-shadow-performance.txt">
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



