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

function bestComparison(rows: Array<CsvRow | undefined>): CsvRow | undefined {
  return rows
    .filter((row): row is CsvRow => Boolean(row))
    .sort((a, b) => pf(b.edge) - pf(a.edge))[0];
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

  const comparisonRows = comparisonCsv ? parseCsv(comparisonCsv) : [];

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

  const comparisonLookup = new Map<string, CsvRow>();
  for (const row of comparisonRows) {
    comparisonLookup.set(
      comparisonKey(row.home_team, row.away_team, row.team, row.line),
      row,
  );
}

function FairOddsCell({
  fairOver,
  fairUnder,
  signalRow,
  toneClass,
}: {
  fairOver: number;
  fairUnder: number;
  signalRow?: CsvRow;
  toneClass?: string;
}) {
  const edge = pf(signalRow?.edge);
  return (
    <div className="space-y-1">
      <div className={`font-mono tabular-nums ${toneClass ?? "text-slate-300"}`}>
        {fairOver.toFixed(2)}/{fairUnder.toFixed(2)}
      </div>
      {signalRow ? (
        <div className="text-[10px] leading-tight">
          <span className="font-mono text-slate-200">
            {signalRow.side?.slice(0, 1).toUpperCase()} {pf(signalRow.book_odds).toFixed(2)}
          </span>
          <span className="ml-1 font-mono text-emerald-300">
            {edge >= 0 ? "+" : ""}
            {(edge * 100).toFixed(1)}%
          </span>
        </div>
      ) : null}
    </div>
  );
}

function LiveValueCell({ signalRow }: { signalRow?: CsvRow }) {
  if (!signalRow) {
    return <span className="font-mono tabular-nums text-slate-500">-</span>;
  }

  const edge = pf(signalRow.edge) * 100;
  const side = signalRow.side?.slice(0, 1).toUpperCase() ?? "-";

  return (
    <div className="space-y-1">
      <div className="font-mono tabular-nums text-slate-100">
        {signalRow.line} {side} {pf(signalRow.book_odds).toFixed(2)}
      </div>
      <div className="text-[10px] leading-tight text-emerald-300">
        {signalRow.bookmaker ?? "book"} {edge >= 0 ? "+" : ""}
        {edge.toFixed(1)}%
      </div>
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

                  lambda = expected shots per team. Fair odds at 9.5 / 10.5 / 11.5 / 12.5 from

                  the Poisson model (decimal).

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

                  <div className="overflow-x-auto">

                    <table className="w-full min-w-[960px] text-left text-xs">

                      <thead>

                        <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">

                          <th className="py-2 pr-3">Kickoff (UTC)</th>

                          <th className="py-2 pr-3">Home</th>

                          <th className="py-2 pr-3">Away</th>

                          <th className="py-2 pr-2 font-mono">Lambda H</th>

                          <th className="py-2 pr-2 font-mono">Lambda A</th>

                          <th className="py-2 pr-1 font-mono text-slate-400" colSpan={4}>

                            Home fair O/U

                          </th>

                          <th className="py-2 pr-3 font-mono text-slate-400">

                            Home value

                          </th>

                          <th className="py-2 pr-2 font-mono text-slate-400" colSpan={4}>

                            Away fair O/U

                          </th>

                          <th className="py-2 pr-3 font-mono text-slate-400">

                            Away value

                          </th>

                          <th className="py-2 pr-2">Note</th>

                        </tr>

                        <tr className="border-b border-slate-800/80 text-[10px] text-slate-600">

                          <th className="py-1 pr-3" colSpan={5} />

                          <th className="py-1 pr-1 font-mono">9.5</th>

                          <th className="py-1 pr-1 font-mono text-sky-400/80">10.5</th>

                          <th className="py-1 pr-1 font-mono">11.5</th>

                          <th className="py-1 pr-2 font-mono">12.5</th>

                          <th className="py-1 pr-3" />

                          <th className="py-1 pr-1 font-mono">9.5</th>

                          <th className="py-1 pr-1 font-mono text-sky-400/80">10.5</th>

                          <th className="py-1 pr-1 font-mono">11.5</th>

                          <th className="py-1 pr-2 font-mono">12.5</th>

                          <th className="py-1 pr-3" />

                          <th className="py-1 pr-2" />

                        </tr>

                      </thead>

                      <tbody>

                        {leagueRows.map((row, i) => {

                          const ho95 = pf(row["home_fair_over_9.5"]);

                          const hu95 = pf(row["home_fair_under_9.5"]);

                          const ho105 = pf(row["home_fair_over_10.5"]);

                          const hu105 = pf(row["home_fair_under_10.5"]);

                          const ho115 = pf(row["home_fair_over_11.5"]);

                          const hu115 = pf(row["home_fair_under_11.5"]);

                          const ho125 = pf(row["home_fair_over_12.5"]);

                          const hu125 = pf(row["home_fair_under_12.5"]);

                          const ao95 = pf(row["away_fair_over_9.5"]);

                          const au95 = pf(row["away_fair_under_9.5"]);

                          const ao105 = pf(row["away_fair_over_10.5"]);

                          const au105 = pf(row["away_fair_under_10.5"]);

                          const ao115 = pf(row["away_fair_over_11.5"]);

                          const au115 = pf(row["away_fair_under_11.5"]);

                          const ao125 = pf(row["away_fair_over_12.5"]);

                          const au125 = pf(row["away_fair_under_12.5"]);

                          const home95 = comparisonLookup.get(
                            comparisonKey(row.home_team, row.away_team, row.home_team, "9.5"),
                          );
                          const home105 = comparisonLookup.get(
                            comparisonKey(row.home_team, row.away_team, row.home_team, "10.5"),
                          );
                          const home115 = comparisonLookup.get(
                            comparisonKey(row.home_team, row.away_team, row.home_team, "11.5"),
                          );
                          const home125 = comparisonLookup.get(
                            comparisonKey(row.home_team, row.away_team, row.home_team, "12.5"),
                          );
                          const away95 = comparisonLookup.get(
                            comparisonKey(row.home_team, row.away_team, row.away_team, "9.5"),
                          );
                          const away105 = comparisonLookup.get(
                            comparisonKey(row.home_team, row.away_team, row.away_team, "10.5"),
                          );
                          const away115 = comparisonLookup.get(
                            comparisonKey(row.home_team, row.away_team, row.away_team, "11.5"),
                          );
                          const away125 = comparisonLookup.get(
                            comparisonKey(row.home_team, row.away_team, row.away_team, "12.5"),
                          );
                          const bestHomeValue = bestComparison([home95, home105, home115, home125]);
                          const bestAwayValue = bestComparison([away95, away105, away115, away125]);

                          return (

                            <tr

                              key={`${row.kickoff_iso}-${row.home_team}-${i}`}

                              className="border-b border-slate-800/40 hover:bg-slate-800/20"

                            >

                              <td className="py-2 pr-3 font-mono tabular-nums text-slate-400">

                                {formatKickoffUtc(row.kickoff_iso)}

                              </td>

                              <td className="py-2 pr-3 font-medium text-slate-200">

                                {row.home_team}

                              </td>

                              <td className="py-2 pr-3 font-medium text-slate-200">

                                {row.away_team}

                              </td>

                              <td className="py-2 pr-2 font-mono tabular-nums text-emerald-300">

                                {pf(row.home_lambda).toFixed(2)}

                              </td>

                              <td className="py-2 pr-2 font-mono tabular-nums text-emerald-300">

                                {pf(row.away_lambda).toFixed(2)}

                              </td>

                              <td className="py-2 pr-1 align-top">
                                <FairOddsCell fairOver={ho95} fairUnder={hu95} signalRow={home95} />
                              </td>

                              <td className="py-2 pr-1 align-top">
                                <FairOddsCell fairOver={ho105} fairUnder={hu105} signalRow={home105} toneClass="text-sky-200/90" />
                              </td>

                              <td className="py-2 pr-1 align-top">
                                <FairOddsCell fairOver={ho115} fairUnder={hu115} signalRow={home115} />
                              </td>

                              <td className="py-2 pr-2 align-top">
                                {ho125 > 0 ? (
                                  <FairOddsCell fairOver={ho125} fairUnder={hu125} signalRow={home125} toneClass="text-slate-500" />
                                ) : (
                                  <span className="font-mono tabular-nums text-slate-500">-</span>
                                )}
                              </td>

                              <td className="py-2 pr-3 align-top">
                                <LiveValueCell signalRow={bestHomeValue} />
                              </td>

                              <td className="py-2 pr-1 align-top">
                                <FairOddsCell fairOver={ao95} fairUnder={au95} signalRow={away95} />
                              </td>

                              <td className="py-2 pr-1 align-top">
                                <FairOddsCell fairOver={ao105} fairUnder={au105} signalRow={away105} toneClass="text-sky-200/90" />
                              </td>

                              <td className="py-2 pr-1 align-top">
                                <FairOddsCell fairOver={ao115} fairUnder={au115} signalRow={away115} />
                              </td>

                              <td className="py-2 pr-2 align-top">
                                {ao125 > 0 ? (
                                  <FairOddsCell fairOver={ao125} fairUnder={au125} signalRow={away125} toneClass="text-slate-500" />
                                ) : (
                                  <span className="font-mono tabular-nums text-slate-500">-</span>
                                )}
                              </td>

                              <td className="py-2 pr-3 align-top">
                                <LiveValueCell signalRow={bestAwayValue} />
                              </td>

                              <td className="py-2 pr-2 text-slate-500">

                                {(row.note ?? "").trim() || "-"}

                              </td>

                            </tr>

                          );

                        })}

                      </tbody>

                    </table>

                  </div>

                  <p className="mt-3 text-[11px] text-slate-600">

                    Cells show decimal fair odds as over/under pairs at each line

                    (Poisson). 10.5 columns highlighted for quick scan. 12.5 shown where model has data.

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

