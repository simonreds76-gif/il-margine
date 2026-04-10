import Link from "next/link";
import { notFound } from "next/navigation";
import {
  readTeamShotsLiveFile as readFile,
  readTeamShotsLiveJson as readJson,
  readTeamShotsLiveMtime as readKnownFileMtime,
  readTeamShotsLiveSnapshotGeneratedAt,
  inspectTeamShotsLiveSource,
} from "@/lib/team-shots-live-files";



export const dynamic = "force-dynamic";



const MODEL_MONITOR_ENABLED =

  process.env.MODEL_MONITOR_PUBLIC === "true" ||

  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "true" ||

  process.env.VERCEL_ENV === "preview";



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
    const lam = pf(row[`${side}_lambda`], Number.NaN);
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



function Stat({

  label,

  value,

  sub,

  tone = "default",

}: {

  label: string;

  value: string;

  sub?: string;

  tone?: "default" | "green" | "red" | "amber";

}) {

  const toneMap = {

    default: "border-slate-800 bg-slate-900/60",

    green: "border-emerald-700/40 bg-emerald-950/30",

    red: "border-rose-700/40 bg-rose-950/30",

    amber: "border-amber-700/40 bg-amber-950/30",

  };

  return (

    <div className={`rounded-2xl border p-4 ${toneMap[tone]}`}>

      <div className="text-[11px] uppercase tracking-wider text-slate-500">

        {label}

      </div>

      <div className="mt-1 font-mono text-xl tabular-nums text-slate-100">

        {value}

      </div>

      {sub && (

        <div className="mt-0.5 text-xs text-slate-400">{sub}</div>

      )}

    </div>

  );

}



function MonitorCard({

  title,

  children,

}: {

  title: string;

  children: React.ReactNode;

}) {

  return (

    <section className="rounded-2xl border border-slate-800 bg-slate-900/40 p-5">

      <h2 className="mb-3 text-sm font-medium text-slate-300">{title}</h2>

      {children}

    </section>

  );

}



function CollapsibleSection({

  title,

  defaultOpen = false,

  children,

}: {

  title: string;

  defaultOpen?: boolean;

  children: React.ReactNode;

}) {

  return (

    <details

      open={defaultOpen}

      className="group rounded-2xl border border-slate-800 bg-slate-900/40"

    >

      <summary className="cursor-pointer select-none px-5 py-3 text-sm font-medium text-slate-300 hover:text-slate-100">

        <span className="ml-1">{title}</span>

      </summary>

      <div className="border-t border-slate-800/60 px-5 py-4">{children}</div>

    </details>

  );

}



export default async function TeamShotsMonitorPage() {

  if (process.env.NODE_ENV === "production" && !MODEL_MONITOR_ENABLED) {

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
  teamName,
  row,
  side,
  lines,
  calibration,
}: {
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
  const lambda = pf(row[`${side}_lambda`]);
  if (!(lambda > 0)) {
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
  const bestLiveText = bestLive
    ? `${bestLive.line.bookmaker} ${bestLive.line.lineLabel} ${
        bestLive.metrics.overEdge !== null && bestLive.metrics.overEdge === bestLive.bestEdge ? "O" : "U"
      } ${formatSignedPercent(bestLive.bestEdge)}`
    : "-";
  const bestShadowText = bestShadow
    ? `${bestShadow.line.bookmaker} ${bestShadow.line.lineLabel} ${
        bestShadow.metrics.overEdge !== null && bestShadow.metrics.overEdge === bestShadow.bestEdge ? "O" : "U"
      } ${formatSignedPercent(bestShadow.bestEdge)}`
    : "none";

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-950/40">
      <div className="border-b border-slate-800 px-4 py-3">
        <div className="text-sm font-medium text-slate-100">{teamName}</div>
        <div className="text-xs text-slate-500">lambda {lambda.toFixed(2)}</div>
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
            <th className="py-2 pr-3">Shadow</th>
            <th className="py-2 pr-3 font-mono">Line</th>
            <th className="py-2 pr-3 font-mono">Fair O/U</th>
            <th className="py-2 pr-3 font-mono">Book O/U</th>
            <th className="py-2 pr-4 font-mono">Value O/U</th>
          </tr>
        </thead>
        <tbody>
          {primaryLines.map(({ line, metrics, overShadow, underShadow }, i) => {
            return (
              <tr key={`${line.bookmaker}-${line.lineLabel}-${i}`} className="border-b border-slate-800/40">
                <td className="py-2 pl-4 pr-3 text-slate-300">{line.bookmaker}</td>
                <td className="py-2 pr-3">
                  <span className={`rounded-full px-1.5 py-0.5 text-[10px] uppercase ${
                    overShadow || underShadow
                      ? "bg-emerald-500/15 text-emerald-300"
                      : "bg-slate-700/30 text-slate-500"
                  }`}>
                    {overShadow || underShadow ? "yes" : "no"}
                  </span>
                </td>
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
                  <td className="py-2 pr-3">
                    <span className={`rounded-full px-1.5 py-0.5 text-[10px] uppercase ${
                      overShadow || underShadow
                        ? "bg-emerald-500/15 text-emerald-300"
                        : "bg-slate-700/30 text-slate-500"
                    }`}>
                      {overShadow || underShadow ? "yes" : "no"}
                    </span>
                  </td>
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



  // All comparison rows that pass shadow policy (edge ≥ 5%, odds 1.5–5), sorted by edge.
  const recentShadow = [...currentShadowLive].sort((a, b) => {
    const edgeCmp = pf(b.edge) - pf(a.edge);
    if (Math.abs(edgeCmp) > 1e-9) return edgeCmp;
    return (b.date ?? "").localeCompare(a.date ?? "");
  });

  // Use a stable snapshot-based day boundary so server/client render the same split.
  const asOfIso = (
    snapshotGeneratedAt ??
    comparisonMtime ??
    upcomingMtime ??
    predictionsMtime ??
    new Date().toISOString()
  ).slice(0, 10);
  const upcomingShadowCount = recentShadow.filter(r => (r.date ?? "").slice(0, 10) > asOfIso).length;
  const awaitingResultShadow = recentShadow.filter(r => {
    const d = (r.date ?? "").slice(0, 10);
    return d && d <= asOfIso;
  });

  // Shadow signal count per league — counts upcoming signals only (fixture card auto-open logic).
  const shadowCountByLeague = new Map<string, number>();
  for (const row of currentShadowLive) {
    const d = (row.date ?? "").slice(0, 10);
    if (d > asOfIso) {
      const lg = (row.league ?? "").trim() || "other";
      shadowCountByLeague.set(lg, (shadowCountByLeague.get(lg) ?? 0) + 1);
    }
  }

  const stalePendingShadow = pendingShadow.filter((row) => {
    const shadowKey = [
      (row.date ?? "").trim(),
      normalizeTeamName(row.home_team),
      normalizeTeamName(row.away_team),
      normalizeTeamName(row.team),
      (row.line ?? "").trim(),
      (row.side ?? "").trim().toLowerCase(),
      (row.bookmaker ?? "").trim().toLowerCase(),
    ].join("|");

    return !currentShadowLive.some(
      (live) =>
        [
          (live.date ?? "").trim(),
          normalizeTeamName(live.home_team),
          normalizeTeamName(live.away_team),
          normalizeTeamName(live.team),
          (live.line ?? "").trim(),
          (live.side ?? "").trim().toLowerCase(),
          (live.bookmaker ?? "").trim().toLowerCase(),
        ].join("|") === shadowKey,
    );
  });

  // Archive bets split by date: future = logged bet, odds moved off threshold since logging.
  // Past = genuinely awaiting result, same as the live-tracker rows.
  const archiveUpcoming = stalePendingShadow.filter(r => (r.date ?? "").slice(0, 10) > asOfIso);
  const archivePastAwaiting = stalePendingShadow.filter(r => {
    const d = (r.date ?? "").slice(0, 10);
    return d && d <= asOfIso;
  });



  return (

    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(244,63,94,0.08),_transparent_22%),#0b0f14] text-slate-100">

      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">

        {/* Nav */}

        <nav className="mb-6 flex flex-wrap gap-2 text-xs">

          <Link

            href="/model-monitor"

            className="rounded-full border border-slate-700 px-3 py-1 text-slate-400 hover:text-slate-200"

          >

            Tennis

          </Link>

          <Link

            href="/model-monitor/goalscorer"

            className="rounded-full border border-slate-700 px-3 py-1 text-slate-400 hover:text-slate-200"

          >

            Goalscorer

          </Link>

          <span className="rounded-full border border-emerald-600/40 bg-emerald-500/10 px-3 py-1 text-emerald-300">

            Team Shots

          </span>

          <Link

            href="/model-monitor/corners"

            className="rounded-full border border-slate-700 px-3 py-1 text-slate-400 hover:text-slate-200"

          >

            Corners

          </Link>

        </nav>



        {/* Hero */}

        <section className="mb-8 rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900/80 to-slate-950/80 p-6">

          <div className="flex items-center gap-3">

            <span className="rounded-full bg-emerald-500/15 px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wider text-emerald-300">

              Team Shots Model

            </span>

          </div>

          <h1 className="mt-3 text-2xl font-semibold tracking-tight">

            Team Total Shots Monitor

          </h1>

          <p className="mt-1 max-w-2xl text-sm text-slate-400">

            Poisson model for expected team shots (lambda) and fair O/U lines. Upcoming

            fixtures below use The Odds API for kickoff times; book team totals (when

            scraped) come from Odds-API.io / BetsAPI. Scheduled with corners:

            Tue/Wed/Fri/Sat/Sun.

          </p>

        </section>





        <MonitorCard title="Pipeline Health">
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-3 xl:grid-cols-6">

            <Stat

              label="Scheduler heartbeat"

              value={formatDateTime(schedulerHeartbeatAt)}

              sub={formatRelativeAgeShort(schedulerHeartbeatAt)}

              tone={pipelineTone}

            />

            <Stat

              label="Predictions file"

              value={formatDateTime(predictionsMtime)}

              sub={formatRelativeAgeShort(predictionsMtime)}

              tone={predictionsMtime ? "default" : "amber"}

            />

            <Stat

              label="Comparison file"

              value={formatDateTime(comparisonMtime)}

              sub={formatRelativeAgeShort(comparisonMtime)}

              tone={comparisonMtime ? "default" : "amber"}

            />

            <Stat

              label="Upcoming file"

              value={formatDateTime(upcomingMtime)}

              sub={formatRelativeAgeShort(upcomingMtime)}

              tone={upcomingMtime ? "default" : "amber"}

            />

            <Stat
              label="Hosted snapshot"
              value={formatDateTime(snapshotGeneratedAt)}
              sub={formatRelativeAgeShort(snapshotGeneratedAt)}
              tone={snapshotGeneratedAt ? "green" : "red"}
            />

            <Stat
              label="Comparison source"
              value={comparisonSource.source}
              sub={formatSourceReason(comparisonSource.reason)}
              tone={sourceTone(comparisonSource.source)}
            />

          </div>

          <details className="mt-3">
            <summary className="cursor-pointer text-[10px] uppercase tracking-wider text-slate-600 hover:text-slate-500 select-none">
              pipeline detail
            </summary>
            <div className="mt-1.5 space-y-0.5 text-[11px] text-slate-600">
              <div><span className="text-slate-500">State:</span> {pipelineStatus?.state ?? "missing"}{pipelineStatus?.current_step ? <> &middot; {pipelineStatus.current_step}</> : null}</div>
              <div><span className="text-slate-500">Message:</span> {pipelineStatus?.message ?? "n/a"}</div>
              <div><span className="text-slate-500">Source:</span> {comparisonSource.source} &middot; hosted {comparisonSource.hostedSnapshotAvailable ? "ok" : "missing"} &middot; local {comparisonSource.localSnapshotAvailable ? "ok" : "missing"}</div>
            </div>
          </details>
        </MonitorCard>

        {/* KPI strip — model track record before showing live signals */}
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-4">
          <Stat label="Predictions" value={predictions.length.toLocaleString()} sub="team lambda + fair lines" />
          <Stat
            label="Team odds rows"
            value={oddsArchive.length.toLocaleString()}
            sub={oddsArchive.length > 0 ? "team total shots from books" : "run scrape when fixtures list team markets"}
            tone={oddsArchive.length > 0 ? "default" : "amber"}
          />
          <Stat
            label="Backtest bets"
            value={backtestRows.length.toLocaleString()}
            sub={`${backtestWins}W / ${backtestRows.length - backtestWins}L`}
          />
          <Stat
            label="Backtest ROI"
            value={`${backtestRoi >= 0 ? "+" : ""}${backtestRoi.toFixed(1)}%`}
            sub={`${backtestPnl >= 0 ? "+" : ""}${backtestPnl.toFixed(1)}u PnL`}
            tone={backtestRoi > 0 ? "green" : backtestRoi < -5 ? "red" : "default"}
          />
          <Stat
            label="Upcoming signals"
            value={(upcomingShadowCount + archiveUpcoming.length).toString()}
            sub={`${awaitingResultShadow.length + archivePastAwaiting.length} awaiting result`}
            tone={(upcomingShadowCount + archiveUpcoming.length) > 0 ? "green" : "default"}
          />
          <Stat
            label="Shadow PnL"
            value={settledShadow.length > 0 ? `${shadowPnl >= 0 ? "+" : ""}${shadowPnl.toFixed(1)}u` : "—"}
            sub={settledShadow.length > 0 ? `${shadowWins}W / ${settledShadow.length - shadowWins}L` : "collecting data"}
            tone={shadowPnl > 0 ? "green" : shadowPnl < 0 ? "red" : "default"}
          />
          <Stat
            label="Shadow ROI (flat)"
            value={settledShadow.length > 0 ? `${shadowRoi >= 0 ? "+" : ""}${shadowRoi.toFixed(1)}%` : "—"}
            tone={shadowRoi > 5 ? "green" : shadowRoi < -5 ? "red" : "default"}
          />
          <Stat
            label="Shadow ROI (staked)"
            value={settledShadow.length > 0 ? `${shadowRoiStaked >= 0 ? "+" : ""}${shadowRoiStaked.toFixed(1)}%` : "—"}
            sub={settledShadow.length > 0 ? `${shadowPnlStaked >= 0 ? "+" : ""}${shadowPnlStaked.toFixed(2)}u on ${shadowStakedTotal.toFixed(1)}u` : "collecting data"}
            tone={shadowRoiStaked > 5 ? "green" : shadowRoiStaked < -5 ? "red" : "default"}
          />
        </div>

        {(awaitingResultShadow.length > 0 || archivePastAwaiting.length > 0 || archiveUpcoming.length > 0) && (
          <MonitorCard
            title={`Shadow signals — ${awaitingResultShadow.length + archivePastAwaiting.length} awaiting result${archiveUpcoming.length > 0 ? ` · ${archiveUpcoming.length} upcoming logged` : ""}`}
          >
            <p className="mb-3 text-xs text-slate-500">
              All shadow bets not yet settled. Past matches are awaiting result entry.
              &ldquo;Odds moved&rdquo; rows were logged when edge was &ge; 5% but the live tracker no longer confirms that threshold — the bet was real at time of logging.
            </p>
            <div className="max-h-[min(70vh,56rem)] overflow-y-auto overflow-x-auto">
              <table className="w-full text-left text-xs">
                <thead>
                  <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                    <th className="py-2 pr-3">Date</th>
                    <th className="py-2 pr-3">League</th>
                    <th className="py-2 pr-3">Match</th>
                    <th className="py-2 pr-3">Team</th>
                    <th className="py-2 pr-3">Line</th>
                    <th className="py-2 pr-3">Side</th>
                    <th className="py-2 pr-3 font-mono">Book</th>
                    <th className="py-2 pr-3 font-mono">Fair</th>
                    <th className="py-2 pr-3 font-mono">Edge</th>
                    <th className="py-2 pr-3 font-mono">Stake</th>
                    <th className="py-2 pr-3">Shots</th>
                    <th className="py-2 pr-3">Result</th>
                    <th className="py-2 pr-3 font-mono">PnL</th>
                    <th className="py-2 font-mono">PnL (staked)</th>
                  </tr>
                </thead>
                <tbody>
                  {awaitingResultShadow.map((row, i) => {
                    const result = "awaiting result";
                    return (
                      <tr key={i} className="border-b border-slate-800/40 hover:bg-slate-800/20">
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{row.date}</td>
                        <td className="py-1.5 pr-3 text-slate-400">{row.league}</td>
                        <td className="py-1.5 pr-3">{row.home_team} v {row.away_team}</td>
                        <td className="py-1.5 pr-3 font-medium">{row.team}</td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums">{row.line}</td>
                        <td className="py-1.5 pr-3">
                          <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase ${
                            row.side === "over"
                              ? "bg-emerald-500/15 text-emerald-300"
                              : "bg-sky-500/15 text-sky-300"
                          }`}>
                            {row.side}
                          </span>
                        </td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums">{pf(row.book_odds).toFixed(2)}</td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{pf(row.model_fair_odds).toFixed(2)}</td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-emerald-300">{(pf(row.edge) * 100).toFixed(1)}%</td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-300">{shadowStakeUnits(pf(row.edge))}</td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums">-</td>
                        <td className="py-1.5 pr-3">
                          <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase ${
                            result === "awaiting result"
                              ? "bg-amber-500/15 text-amber-300"
                              : "bg-slate-700/30 text-slate-400"
                          }`}>
                            {result}
                          </span>
                        </td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">-</td>
                        <td className="py-1.5 font-mono tabular-nums text-slate-400">-</td>
                      </tr>
                    );
                  })}
                  {archivePastAwaiting.map((row, i) => (
                    <tr key={`arch-past-${i}`} className="border-b border-slate-800/40 hover:bg-slate-800/20">
                      <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{row.date}</td>
                      <td className="py-1.5 pr-3 text-slate-400">{row.league}</td>
                      <td className="py-1.5 pr-3">{row.home_team} v {row.away_team}</td>
                      <td className="py-1.5 pr-3 font-medium">{row.team}</td>
                      <td className="py-1.5 pr-3 font-mono tabular-nums">{row.line}</td>
                      <td className="py-1.5 pr-3">
                        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase ${
                          row.side === "over" ? "bg-emerald-500/15 text-emerald-300" : "bg-sky-500/15 text-sky-300"
                        }`}>{row.side}</span>
                      </td>
                      <td className="py-1.5 pr-3 font-mono tabular-nums">{pf(row.book_odds).toFixed(2)}</td>
                      <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{pf(row.model_fair_odds).toFixed(2)}</td>
                      <td className="py-1.5 pr-3 font-mono tabular-nums text-emerald-300">{(pf(row.edge) * 100).toFixed(1)}%</td>
                      <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-300">{shadowStakeUnits(pf(row.edge))}</td>
                      <td className="py-1.5 pr-3 font-mono tabular-nums">-</td>
                      <td className="py-1.5 pr-3">
                        <span className="rounded-full bg-amber-500/15 px-1.5 py-0.5 text-[10px] font-medium uppercase text-amber-300">awaiting result</span>
                      </td>
                      <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">-</td>
                      <td className="py-1.5 font-mono tabular-nums text-slate-400">-</td>
                    </tr>
                  ))}
                  {archiveUpcoming.length > 0 && (
                    <>
                      <tr>
                        <td colSpan={14} className="py-2 px-3">
                          <div className="flex items-center gap-2 text-[10px] uppercase tracking-wider text-slate-600">
                            <div className="flex-1 border-t border-slate-800" />
                            <span>upcoming — logged bets, P&L settled at logged odds</span>
                            <div className="flex-1 border-t border-slate-800" />
                          </div>
                        </td>
                      </tr>
                      {archiveUpcoming.map((row, i) => {
                        const loggedOdds = pf(row.book_odds);
                        const matchDate = (row.date ?? "").slice(0, 10);
                        const teamKey = `${matchKey(matchDate, row.home_team, row.away_team)}|${normalizeTeamName(row.team)}`;
                        const currentTeamLines = liveOddsByMatchTeam.get(teamKey);
                        const lineKey = `${(row.bookmaker ?? "").trim()}|${(row.line ?? "").trim()}`;
                        const currentLine = currentTeamLines?.get(lineKey);
                        const currentOdds = currentLine
                          ? (row.side === "over" ? currentLine.overOdds : currentLine.underOdds) ?? null
                          : null;
                        const delta = currentOdds !== null ? currentOdds - loggedOdds : null;
                        return (
                          <tr key={`arch-up-${i}`} className="border-b border-slate-800/30 hover:bg-slate-800/20">
                            <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{row.date}</td>
                            <td className="py-1.5 pr-3 text-slate-400">{row.league}</td>
                            <td className="py-1.5 pr-3">{row.home_team} v {row.away_team}</td>
                            <td className="py-1.5 pr-3 font-medium">{row.team}</td>
                            <td className="py-1.5 pr-3 font-mono tabular-nums">{row.line}</td>
                            <td className="py-1.5 pr-3">
                              <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase ${
                                row.side === "over" ? "bg-emerald-500/15 text-emerald-300" : "bg-sky-500/15 text-sky-300"
                              }`}>{row.side}</span>
                            </td>
                            <td className="py-1.5 pr-3 font-mono tabular-nums">
                              <span>{loggedOdds.toFixed(2)}</span>
                              {delta !== null && Math.abs(delta) >= 0.02 && (
                                <span className={`ml-1.5 text-[10px] ${delta > 0 ? "text-emerald-400" : "text-rose-400"}`}>
                                  {delta > 0 ? "↑" : "↓"}{currentOdds!.toFixed(2)}
                                </span>
                              )}
                            </td>
                            <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{pf(row.model_fair_odds).toFixed(2)}</td>
                            <td className="py-1.5 pr-3 font-mono tabular-nums text-emerald-300">{(pf(row.edge) * 100).toFixed(1)}%</td>
                            <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-300">{shadowStakeUnits(pf(row.edge))}</td>
                            <td className="py-1.5 pr-3 font-mono tabular-nums">-</td>
                            <td className="py-1.5 pr-3">
                              <span className="rounded-full bg-sky-700/20 px-1.5 py-0.5 text-[10px] font-medium uppercase text-sky-400">pre-match</span>
                            </td>
                            <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">-</td>
                            <td className="py-1.5 font-mono tabular-nums text-slate-400">-</td>
                          </tr>
                        );
                      })}
                    </>
                  )}
                </tbody>
              </table>
            </div>
          </MonitorCard>
        )}
        {/* Upcoming: both teams lambda + fair lines by league */}

        {upcomingRows.length > 0 ? (

          <section className="mb-8 space-y-6">

            <div className="flex flex-wrap items-end justify-between gap-3">

              <div>

                <h2 className="text-lg font-semibold text-slate-100">

                  Upcoming matches - model estimates

                </h2>

                <p className="mt-1 text-sm text-slate-500">

                  lambda = expected shots per team. Open a fixture to see all live bookmaker lines.
                  Value and shadow tags now use the same calibrated edge logic as the comparison tracker.

                </p>

              </div>

              <span className="rounded-full border border-emerald-700/40 bg-emerald-950/40 px-3 py-1 text-[11px] font-medium text-emerald-300">

                {upcomingRows.length} fixtures

              </span>

            </div>

            {upcomingLeagueKeys.map((leagueKey) => {

              const leagueRows = upcomingByLeague.get(leagueKey) ?? [];

              return (

                <CollapsibleSection

                  key={leagueKey}

                  defaultOpen={(shadowCountByLeague.get(leagueKey) ?? 0) > 0}

                  title={(() => {
                    const sc = shadowCountByLeague.get(leagueKey) ?? 0;
                    return [
                      `${leagueTitle(leagueKey)} — ${leagueRows.length} fixture${leagueRows.length === 1 ? "" : "s"}`,
                      sc > 0 ? `${sc} shadow signal${sc === 1 ? "" : "s"}` : null,
                    ].filter(Boolean).join(" · ");
                  })()}

                >
                  <div className="space-y-3">
                    {leagueRows.map((row, i) => {
                      const date = (row.kickoff_iso ?? "").slice(0, 10);
                      const homeKey = `${matchKey(date, row.home_team, row.away_team)}|${normalizeTeamName(row.home_team)}`;
                      const awayKey = `${matchKey(date, row.home_team, row.away_team)}|${normalizeTeamName(row.away_team)}`;
                      const homeLines = [...(liveOddsByMatchTeam.get(homeKey)?.values() ?? [])]
                        .sort(
                        (a, b) => a.line - b.line || a.bookmaker.localeCompare(b.bookmaker),
                      );
                      const awayLines = [...(liveOddsByMatchTeam.get(awayKey)?.values() ?? [])]
                        .sort(
                        (a, b) => a.line - b.line || a.bookmaker.localeCompare(b.bookmaker),
                      );
                      return (
                        <details
                          key={`${row.kickoff_iso}-${row.home_team}-${i}`}
                          className="group rounded-2xl border border-slate-800 bg-slate-950/30"
                        >
                          <summary className="cursor-pointer list-none px-4 py-3">
                            <div className="flex flex-col gap-3 lg:flex-row lg:items-center lg:justify-between">
                              <div>
                                <div className="text-xs text-slate-400">{formatKickoffUtc(row.kickoff_iso)}</div>
                                <div className="mt-1 text-sm font-medium text-slate-100">
                                  {row.home_team} v {row.away_team}
                                </div>
                              </div>
                              <div className="grid gap-2 text-xs sm:grid-cols-2 lg:min-w-[560px]">
                                {(() => {
                                  const homeLive = bestLineSummary(homeLines, row, "home", calibrationParams);
                                  const homeShadow = bestLineSummary(homeLines, row, "home", calibrationParams, true);
                                  const awayLive = bestLineSummary(awayLines, row, "away", calibrationParams);
                                  const awayShadow = bestLineSummary(awayLines, row, "away", calibrationParams, true);
                                  const hasHomeShadow = !homeShadow.startsWith("No shadow");
                                  const hasAwayShadow = !awayShadow.startsWith("No shadow");
                                  const liveColor = (s: string) =>
                                    s.startsWith("No") ? "text-slate-500" :
                                    s.includes("(+") ? "text-emerald-300" :
                                    s.includes("(-") ? "text-rose-400" : "text-slate-300";
                                  return (
                                    <>
                                      <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
                                        <div className="text-slate-500">Home · λ <span className="font-mono text-emerald-300">{pf(row.home_lambda).toFixed(2)}</span></div>
                                        <div className={`mt-1 font-mono ${liveColor(homeLive)}`}>{homeLive}</div>
                                        <div className={`mt-0.5 font-mono ${hasHomeShadow ? "text-emerald-300 font-semibold" : "text-slate-600"}`}>{homeShadow}</div>
                                      </div>
                                      <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
                                        <div className="text-slate-500">Away · λ <span className="font-mono text-emerald-300">{pf(row.away_lambda).toFixed(2)}</span></div>
                                        <div className={`mt-1 font-mono ${liveColor(awayLive)}`}>{awayLive}</div>
                                        <div className={`mt-0.5 font-mono ${hasAwayShadow ? "text-emerald-300 font-semibold" : "text-slate-600"}`}>{awayShadow}</div>
                                      </div>
                                    </>
                                  );
                                })()}
                              </div>
                            </div>
                            {(row.note ?? "").trim() ? (
                              <div className="mt-2 text-xs text-slate-500">{row.note}</div>
                            ) : null}
                          </summary>
                          <div className="grid gap-4 border-t border-slate-800 px-4 py-4 lg:grid-cols-2">
                            <LiveLineTable
                              teamName={row.home_team ?? "Home"}
                              row={row}
                              side="home"
                              lines={homeLines}
                              calibration={calibrationParams}
                            />
                            <LiveLineTable
                              teamName={row.away_team ?? "Away"}
                              row={row}
                              side="away"
                              lines={awayLines}
                              calibration={calibrationParams}
                            />
                          </div>
                        </details>
                      );
                    })}
                  </div>

                  <p className="mt-3 text-[11px] text-slate-600">
                    Shadow label turns green when any line meets the policy: edge ≥ 5% and book odds 1.50–5.00. Expand a fixture to see all bookmaker lines.
                  </p>

                </CollapsibleSection>

              );

            })}

          </section>

        ) : (

          <section className="mb-8 rounded-2xl border border-amber-700/30 bg-amber-950/20 p-4 text-sm text-amber-100/90">

            <strong className="text-amber-200">No upcoming fixture file.</strong>{" "}

            Run{" "}

            <code className="rounded bg-slate-900 px-1.5 py-0.5 font-mono text-xs">

              python scripts/team_shots_upcoming.py

            </code>{" "}

            after the team shots model (or run the corners pipeline) to populate{" "}

            <code className="rounded bg-slate-900 px-1.5 py-0.5 font-mono text-xs">

              data/team-shots/team-shots-upcoming.csv

            </code>

            .

          </section>

        )}



        {/* Missing data alert */}

        {!predictionsCsv && (

          <section className="mb-6 rounded-2xl border border-amber-700/40 bg-amber-950/30 p-4 text-sm text-amber-200">

            No prediction data found. Run{" "}

            <code className="rounded bg-slate-800 px-1.5 py-0.5 text-xs">

              python scripts/run-team-shots-pipeline.py

            </code>{" "}

            to generate model outputs.

          </section>

        )}




        {/* Team total shots odds (latest 50) — empty until Odds-API.io / BetsAPI returns team markets */}

        {oddsArchive.length > 0 ? (

          <MonitorCard title={`Team total shots — book lines (latest ${Math.min(50, oddsArchive.length)})`}>

            <div className="max-h-80 overflow-auto">

              <table className="w-full text-left text-xs">

                <thead className="sticky top-0 bg-slate-900">

                  <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">

                    <th className="py-2 pr-3">Date</th>

                    <th className="py-2 pr-3">League</th>

                    <th className="py-2 pr-3">Match</th>

                    <th className="py-2 pr-3">Team</th>

                    <th className="py-2 pr-3">Line</th>

                    <th className="py-2 pr-3">Side</th>

                    <th className="py-2 pr-3 font-mono">Odds</th>

                    <th className="py-2 pr-3">Book</th>

                  </tr>

                </thead>

                <tbody>

                  {oddsArchive.slice(-50).reverse().map((row, i) => (

                    <tr key={i} className="border-b border-slate-800/40 hover:bg-slate-800/20">

                      <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{row.match_date}</td>

                      <td className="py-1.5 pr-3 text-slate-400">{row.competition}</td>

                      <td className="py-1.5 pr-3">{row.home_team} v {row.away_team}</td>

                      <td className="py-1.5 pr-3 font-medium">{row.team}</td>

                      <td className="py-1.5 pr-3 font-mono tabular-nums">{row.line}</td>

                      <td className="py-1.5 pr-3">

                        <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase ${

                          row.side === "over" ? "bg-emerald-500/15 text-emerald-300" : "bg-sky-500/15 text-sky-300"

                        }`}>{row.side}</span>

                      </td>

                      <td className="py-1.5 pr-3 font-mono tabular-nums">{pf(row.odds_decimal).toFixed(2)}</td>

                      <td className="py-1.5 pr-3 text-slate-500">{row.bookmaker}</td>

                    </tr>

                  ))}

                </tbody>

              </table>

            </div>

          </MonitorCard>

        ) : (

          <section className="mb-6 rounded-2xl border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-400">

            No <strong className="text-slate-200">team total shots</strong> lines in the archive yet.

            The pipeline scrapes Odds-API.io / BetsAPI (team markets). The Odds API key used for corners does not list team shots.

          </section>

        )}



        <div className="mt-6 space-y-4">

          {/* Recent predictions */}

          {recentPredictions.length > 0 && (

            <CollapsibleSection

              title={`Recent Predictions (latest ${recentPredictions.length})`}

            >

              <div className="max-h-96 overflow-auto">

                <table className="w-full text-left text-xs">

                  <thead className="sticky top-0 bg-slate-900">

                    <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">

                      <th className="py-2 pr-3">Date</th>

                      <th className="py-2 pr-3">League</th>

                      <th className="py-2 pr-3">Team</th>

                      <th className="py-2 pr-3">vs</th>

                      <th className="py-2 pr-3">Venue</th>

                      <th className="py-2 pr-3 font-mono">Lambda</th>

                      <th className="py-2 pr-3 font-mono">Actual</th>

                      <th className="py-2 pr-3 font-mono">O10.5</th>

                      <th className="py-2 pr-3 font-mono">U10.5</th>

                      <th className="py-2 pr-3 font-mono">O12.5</th>

                      <th className="py-2 font-mono">U12.5</th>

                    </tr>

                  </thead>

                  <tbody>

                    {recentPredictions.map((row, i) => (

                      <tr

                        key={i}

                        className="border-b border-slate-800/40 hover:bg-slate-800/20"

                      >

                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">

                          {row.date}

                        </td>

                        <td className="py-1.5 pr-3 text-slate-400">

                          {row.league}

                        </td>

                        <td className="py-1.5 pr-3 font-medium">{row.team}</td>

                        <td className="py-1.5 pr-3 text-slate-400">

                          {row.opponent}

                        </td>

                        <td className="py-1.5 pr-3 text-slate-500">

                          {row.venue}

                        </td>

                        <td className="py-1.5 pr-3 font-mono tabular-nums text-emerald-300">

                          {pf(row.lambda_shots).toFixed(1)}

                        </td>

                        <td className="py-1.5 pr-3 font-mono tabular-nums">

                          {row.actual_shots}

                        </td>

                        <td className="py-1.5 pr-3 font-mono tabular-nums">

                          {pf(row["fair_over_10.5"]).toFixed(2)}

                        </td>

                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">

                          {pf(row["fair_under_10.5"]).toFixed(2)}

                        </td>

                        <td className="py-1.5 pr-3 font-mono tabular-nums">

                          {pf(row["fair_over_12.5"]).toFixed(2)}

                        </td>

                        <td className="py-1.5 font-mono tabular-nums text-slate-400">

                          {pf(row["fair_under_12.5"]).toFixed(2)}

                        </td>

                      </tr>

                    ))}

                  </tbody>

                </table>

              </div>

            </CollapsibleSection>

          )}



          {/* Calibration report */}

          {calibrationTxt && (

            <CollapsibleSection title="Calibration Report">

              <pre className="max-h-80 overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">

                {calibrationTxt}

              </pre>

            </CollapsibleSection>

          )}



          {/* Backtest report */}

          {backtestReportTxt && (

            <CollapsibleSection title="Backtest Report">

              <pre className="max-h-80 overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">

                {backtestReportTxt}

              </pre>

            </CollapsibleSection>

          )}



          {/* Shadow performance summary */}

          {shadowPerformanceTxt && (

            <CollapsibleSection title="Shadow Performance Summary">

              <pre className="whitespace-pre-wrap font-mono text-xs text-slate-300">

                {shadowPerformanceTxt}

              </pre>

            </CollapsibleSection>

          )}



          {/* Comparison summary (live odds) */}

          {comparisonTxt && (

            <CollapsibleSection title="Model vs Bookmaker Comparison">

              <pre className="whitespace-pre-wrap font-mono text-xs text-slate-300">

                {comparisonTxt}

              </pre>

            </CollapsibleSection>

          )}

        </div>



        {/* Footer */}

        <footer className="mt-12 border-t border-slate-800/60 pt-4 text-center text-[11px] text-slate-600">

          Team Shots Model Monitor — Il Margine

        </footer>

      </div>

    </div>

  );

}
