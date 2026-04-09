import Link from "next/link";

import { promises as fs } from "fs";

import { notFound } from "next/navigation";

import { tryGetKnownProjectFilePath } from "@/lib/project-file-paths";



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

  "ligue-1",

] as const;
const SHADOW_ELIGIBLE_LINES = new Set([9.5, 10.5, 11.5]);



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
  return (value ?? "")
    .normalize("NFD")
    .replace(/[\u0300-\u036f]/g, "")
    .toLowerCase()
    .replace(/[^a-z0-9\s]/g, " ")
    .split(/\s+/)
    .filter(Boolean)
    .filter((token) => !["fc", "afc", "sc", "cf", "ac", "club"].includes(token))
    .join(" ");
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

function poissonFairOdds(lambda: number, line: number, side: "over" | "under"): number {
  if (!(lambda > 0) || !(line >= 0)) return 0;
  const threshold = Math.floor(line);
  let probability = Math.exp(-lambda);
  let cumulative = probability;
  for (let k = 1; k <= threshold; k += 1) {
    probability = (probability * lambda) / k;
    cumulative += probability;
  }
  const underProb = Math.min(Math.max(cumulative, 1e-9), 1 - 1e-9);
  const overProb = Math.min(Math.max(1 - underProb, 1e-9), 1 - 1e-9);
  return side === "over" ? 1 / overProb : 1 / underProb;
}

function formatSignedPercent(edge: number | null): string {
  if (edge === null || Number.isNaN(edge)) return "-";
  return `${edge >= 0 ? "+" : ""}${edge.toFixed(1)}%`;
}

function bestLineSummary(lines: TeamShotsLiveLine[], lambda: number): string {
  let best:
    | { bookmaker: string; lineLabel: string; side: "O" | "U"; odds: number; edge: number }
    | undefined;

  for (const line of lines) {
    const fairOver = poissonFairOdds(lambda, line.line, "over");
    const fairUnder = poissonFairOdds(lambda, line.line, "under");
    if (line.overOdds) {
      const edge = (line.overOdds / fairOver - 1) * 100;
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
      const edge = (line.underOdds / fairUnder - 1) * 100;
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

  if (!best) return "No live team-shots line";
  return `${best.bookmaker} ${best.lineLabel} ${best.side} ${best.odds.toFixed(2)} (${formatSignedPercent(best.edge)})`;
}

function bestEligibleLineSummary(lines: TeamShotsLiveLine[], lambda: number): string {
  const eligibleLines = lines.filter((line) => SHADOW_ELIGIBLE_LINES.has(line.line));
  if (eligibleLines.length === 0) return "No shadow-eligible line";
  return bestLineSummary(eligibleLines, lambda);
}



async function readFile(relativePath: string): Promise<string | null> {

  const resolved = tryGetKnownProjectFilePath(relativePath);

  if (!resolved) return null;

  try {

    return await fs.readFile(resolved, "utf-8");

  } catch {

    return null;

  }

}



async function readJson<T>(relativePath: string): Promise<T | null> {

  try {

    const text = await readFile(relativePath);

    if (!text) return null;

    return JSON.parse(text) as T;

  } catch {

    return null;

  }

}



async function readKnownFileMtime(relativePath: string): Promise<string | null> {

  const resolved = tryGetKnownProjectFilePath(relativePath);

  if (!resolved) return null;

  try {

    const stat = await fs.stat(resolved);

    return stat.mtime.toISOString();

  } catch {

    return null;

  }

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

  ] = await Promise.all([

    readFile("data/team-shots/team-shots-calibration.txt"),

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

  ]);



  const shadowSignals = shadowSignalsCsv ? parseCsv(shadowSignalsCsv) : [];

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



  const upcomingRows = upcomingCsv ? parseCsv(upcomingCsv) : [];
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
  lambda,
  lines,
}: {
  teamName: string;
  lambda: number;
  lines: TeamShotsLiveLine[];
}) {
  if (lines.length === 0) {
    return (
      <div className="rounded-2xl border border-slate-800 bg-slate-950/40 p-4 text-sm text-slate-500">
        No live bookmaker lines yet.
      </div>
    );
  }

  return (
    <div className="overflow-x-auto rounded-2xl border border-slate-800 bg-slate-950/40">
      <div className="border-b border-slate-800 px-4 py-3">
        <div className="text-sm font-medium text-slate-100">{teamName}</div>
        <div className="text-xs text-slate-500">lambda {lambda.toFixed(2)}</div>
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
          {lines.map((line, i) => {
            const fairOver = poissonFairOdds(lambda, line.line, "over");
            const fairUnder = poissonFairOdds(lambda, line.line, "under");
            const overEdge = line.overOdds ? (line.overOdds / fairOver - 1) * 100 : null;
            const underEdge = line.underOdds ? (line.underOdds / fairUnder - 1) * 100 : null;
            return (
              <tr key={`${line.bookmaker}-${line.lineLabel}-${i}`} className="border-b border-slate-800/40">
                <td className="py-2 pl-4 pr-3 text-slate-300">{line.bookmaker}</td>
                <td className="py-2 pr-3">
                  {SHADOW_ELIGIBLE_LINES.has(line.line) ? (
                    <span className="rounded-full bg-emerald-500/15 px-1.5 py-0.5 text-[10px] uppercase text-emerald-300">
                      yes
                    </span>
                  ) : (
                    <span className="rounded-full bg-slate-700/30 px-1.5 py-0.5 text-[10px] uppercase text-slate-500">
                      no
                    </span>
                  )}
                </td>
                <td className="py-2 pr-3 font-mono tabular-nums text-slate-100">{line.lineLabel}</td>
                <td className="py-2 pr-3 font-mono tabular-nums text-slate-400">
                  {fairOver.toFixed(2)} / {fairUnder.toFixed(2)}
                </td>
                <td className="py-2 pr-3 font-mono tabular-nums text-slate-100">
                  {line.overOdds ? line.overOdds.toFixed(2) : "-"} / {line.underOdds ? line.underOdds.toFixed(2) : "-"}
                </td>
                <td className="py-2 pr-4 font-mono tabular-nums">
                  <span className={overEdge !== null && overEdge >= 0 ? "text-emerald-300" : "text-slate-500"}>
                    {formatSignedPercent(overEdge)}
                  </span>
                  <span className="text-slate-600"> / </span>
                  <span className={underEdge !== null && underEdge >= 0 ? "text-emerald-300" : "text-slate-500"}>
                    {formatSignedPercent(underEdge)}
                  </span>
                </td>
              </tr>
            );
          })}
        </tbody>
      </table>
    </div>
  );
}

  const upcomingByLeague = groupUpcomingByLeague(upcomingRows);

  const upcomingLeagueKeys = sortLeagueKeys([...upcomingByLeague.keys()]);

  const schedulerHeartbeatAt =

    pipelineStatus?.last_successful_finished_at ??
    pipelineStatus?.updated_at ??
    comparisonMtime ??
    upcomingMtime ??
    predictionsMtime ??
    null;

  const pipelineTone =

    pipelineStatus?.state === "failed"

      ? "red"

      : pipelineStatus?.warnings?.length

        ? "amber"

        : "green";



  const recentShadow = [...shadowSignals]

    .sort((a, b) => (b.date ?? "").localeCompare(a.date ?? ""))

    .slice(0, 50);



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
          <div className="grid grid-cols-1 gap-3 sm:grid-cols-4">

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

          </div>

          <div className="mt-3 text-xs text-slate-400">

            <span className="text-slate-500">State:</span> {pipelineStatus?.state ?? "missing"}

            {pipelineStatus?.current_step ? (

              <span className="text-slate-500"> - Step:</span>

            ) : null}{" "}

            {pipelineStatus?.current_step ?? null}

          </div>

          <div className="mt-1 text-xs text-slate-400">
            <span className="text-slate-500">Message:</span>{" "}
            {pipelineStatus?.message ?? "No pipeline status JSON yet."}
          </div>
        </MonitorCard>

        {recentShadow.length > 0 && (
          <MonitorCard title={`Shadow Signals (latest ${recentShadow.length})`}>
            <div className="overflow-x-auto">
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
                  {recentShadow.map((row, i) => {
                    const result = row.result ?? "pending";
                    const pnlVal = pf(row.pnl);
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
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-300">
                          {row.stake_units ? `${pf(row.stake_units).toFixed(1)}u` : "-"}
                        </td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums">
                          {row.actual_shots || "—"}
                        </td>
                        <td className="py-1.5 pr-3">
                          <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase ${
                            result === "won"
                              ? "bg-emerald-500/15 text-emerald-300"
                              : result === "lost"
                                ? "bg-rose-500/15 text-rose-300"
                                : result === "push"
                                  ? "bg-amber-500/15 text-amber-200"
                                  : "bg-slate-700/30 text-slate-400"
                          }`}>
                            {result}
                          </span>
                        </td>
                        <td className={`py-1.5 pr-3 font-mono tabular-nums ${pnlVal > 0 ? "text-emerald-300" : pnlVal < 0 ? "text-rose-300" : "text-slate-400"}`}>
                          {result !== "pending" ? `${pnlVal >= 0 ? "+" : ""}${pnlVal.toFixed(2)}` : "-"}
                        </td>
                        <td className={`py-1.5 font-mono tabular-nums ${pf(row.pnl_staked) > 0 ? "text-emerald-300" : pf(row.pnl_staked) < 0 ? "text-rose-300" : "text-slate-400"}`}>
                          {result !== "pending" && row.pnl_staked ? `${pf(row.pnl_staked) >= 0 ? "+" : ""}${pf(row.pnl_staked).toFixed(2)}` : "-"}
                        </td>
                      </tr>
                    );
                  })}
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
                  Shadow-eligible lines are tagged.

                </p>

              </div>

              <span className="rounded-full border border-emerald-700/40 bg-emerald-950/40 px-3 py-1 text-[11px] font-medium text-emerald-300">

                {upcomingRows.length} fixtures

              </span>

            </div>

            {upcomingLeagueKeys.map((leagueKey) => {

              const leagueRows = upcomingByLeague.get(leagueKey) ?? [];

              return (

                <MonitorCard

                  key={leagueKey}

                  title={`${leagueTitle(leagueKey)} (${leagueRows.length})`}

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
                                <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
                                  <div className="text-slate-500">Home</div>
                                  <div className="font-mono text-emerald-300">lambda {pf(row.home_lambda).toFixed(2)}</div>
                                  <div className="mt-1 text-slate-300">Live: {bestLineSummary(homeLines, pf(row.home_lambda))}</div>
                                  <div className="mt-1 text-slate-500">Shadow: {bestEligibleLineSummary(homeLines, pf(row.home_lambda))}</div>
                                </div>
                                <div className="rounded-xl border border-slate-800 bg-slate-900/60 px-3 py-2">
                                  <div className="text-slate-500">Away</div>
                                  <div className="font-mono text-emerald-300">lambda {pf(row.away_lambda).toFixed(2)}</div>
                                  <div className="mt-1 text-slate-300">Live: {bestLineSummary(awayLines, pf(row.away_lambda))}</div>
                                  <div className="mt-1 text-slate-500">Shadow: {bestEligibleLineSummary(awayLines, pf(row.away_lambda))}</div>
                                </div>
                              </div>
                            </div>
                            {(row.note ?? "").trim() ? (
                              <div className="mt-2 text-xs text-slate-500">{row.note}</div>
                            ) : null}
                          </summary>
                          <div className="grid gap-4 border-t border-slate-800 px-4 py-4 lg:grid-cols-2">
                            <LiveLineTable
                              teamName={row.home_team ?? "Home"}
                              lambda={pf(row.home_lambda)}
                              lines={homeLines}
                            />
                            <LiveLineTable
                              teamName={row.away_team ?? "Away"}
                              lambda={pf(row.away_lambda)}
                              lines={awayLines}
                            />
                          </div>
                        </details>
                      );
                    })}
                  </div>

                  <p className="mt-3 text-[11px] text-slate-600">

                    All live lines are shown here. The shadow tracker only logs 9.5 / 10.5 / 11.5, so non-eligible lines are marked.

                  </p>

                </MonitorCard>

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



        {/* KPI strip */}

        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-4">

          <Stat label="Predictions" value={predictions.length.toLocaleString()} sub="team lambda + fair lines" />

          <Stat

            label="Team odds rows"

            value={oddsArchive.length.toLocaleString()}

            sub={

              oddsArchive.length > 0

                ? "team total shots from books"

                : "run scrape when fixtures list team markets"

            }

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

            label="Shadow signals"

            value={shadowSignals.length.toString()}

            sub={`${pendingShadow.length} pending`}

          />

          <Stat

            label="Shadow PnL"

            value={

              settledShadow.length > 0

                ? `${shadowPnl >= 0 ? "+" : ""}${shadowPnl.toFixed(1)}u`

                : "—"

            }

            sub={

              settledShadow.length > 0

                ? `${shadowWins}W / ${settledShadow.length - shadowWins}L`

                : "collecting data"

            }

            tone={shadowPnl > 0 ? "green" : shadowPnl < 0 ? "red" : "default"}

          />

          <Stat

            label="Shadow ROI (flat)"

            value={

              settledShadow.length > 0

                ? `${shadowRoi >= 0 ? "+" : ""}${shadowRoi.toFixed(1)}%`

                : "—"

            }

            tone={shadowRoi > 5 ? "green" : shadowRoi < -5 ? "red" : "default"}

          />

          <Stat

            label="Shadow ROI (staked)"

            value={

              settledShadow.length > 0

                ? `${shadowRoiStaked >= 0 ? "+" : ""}${shadowRoiStaked.toFixed(1)}%`

                : "—"

            }

            sub={

              settledShadow.length > 0

                ? `${shadowPnlStaked >= 0 ? "+" : ""}${shadowPnlStaked.toFixed(2)}u on ${shadowStakedTotal.toFixed(1)}u`

                : "collecting data"

            }

            tone={shadowRoiStaked > 5 ? "green" : shadowRoiStaked < -5 ? "red" : "default"}

          />

        </div>

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

