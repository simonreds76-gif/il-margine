import Link from "next/link";
import { notFound } from "next/navigation";
import {
  readCornersLiveFile as readFile,
  readCornersLiveJson as readJson,
  readCornersLiveMtime as readKnownFileMtime,
} from "@/lib/corners-live-files";

export const dynamic = "force-dynamic";

const MODEL_MONITOR_ENABLED =
  process.env.MODEL_MONITOR_PUBLIC === "true" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "true" ||
  process.env.VERCEL_ENV === "preview";

type CsvRow = Record<string, string>;
type CurrentValueSignal = { row: CsvRow; displayDate: string; edgeValue: number };
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

function normalizePinnacleTeamName(value: string | undefined): string {
  return (value ?? "").replace(/\s*\(Corners\)\s*$/i, "").trim();
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

export default async function CornersMonitorPage() {
  if (process.env.NODE_ENV === "production" && !MODEL_MONITOR_ENABLED) {
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
    ]);

  const backtestRows = backtestCsv ? parseCsv(backtestCsv) : [];
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
  const currentValueSignals: CurrentValueSignal[] = [...dedupedCurrentSignals.values()].sort(
    (a, b) => b.edgeValue - a.edgeValue,
  );

  // Build grouped Pinnacle table: latest odds per match and line
  type PinnacleMatchRow = {
    match_date: string; league: string; home_team: string; away_team: string;
    lines: Record<string, { over: number; under: number }>;
  };
  const _pinnacleByMatch = new Map<string, PinnacleMatchRow>();
  for (const row of pinnacleRows) {
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
  const livePending = settledRows.filter((r) => r.settled === "pending");
  const liveWon = liveSettled.filter((r) => r.won === "yes");
  const liveLost = liveSettled.filter((r) => r.won === "no");
  const liveTotalStaked = liveSettled.reduce((s, r) => s + pf(r.stake, 1), 0);
  const livePnlFlat = liveSettled.reduce((s, r) => s + pf(r.pnl_units), 0);
  const livePnlStaked = liveSettled.reduce((s, r) => s + pf(r.pnl_staked), 0);
  const liveRoiFlat = liveSettled.length > 0 ? (livePnlFlat / liveSettled.length) * 100 : 0;
  const liveRoiStaked = liveTotalStaked > 0 ? (livePnlStaked / liveTotalStaked) * 100 : 0;
  const liveWinRate = liveSettled.length > 0 ? (liveWon.length / liveSettled.length) * 100 : 0;
  const recentSettled = [...liveSettled]
    .sort((a, b) => (b.match_date ?? "").localeCompare(a.match_date ?? ""))
    .slice(0, 12);

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

  const backtestPnl = backtestRows.reduce((s, r) => s + pf(r.pnl), 0);
  const backtestWins = backtestRows.filter(
    (r) => r.won === "True" || r.won === "true",
  ).length;
  const backtestRoi =
    backtestRows.length > 0 ? (backtestPnl / backtestRows.length) * 100 : 0;

  const recentPredictions = predictions.slice(-80).reverse();
  const schedulerHeartbeatAt =
    latestPinnacleCaptureAt ??
    pinnacleCornersMtime ??
    shortlistMtime ??
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
          <Link
            href="/model-monitor/team-shots"
            className="rounded-full border border-slate-700 px-3 py-1 text-slate-400 hover:text-slate-200"
          >
            Team Shots
          </Link>
          <span className="rounded-full border border-amber-600/40 bg-amber-500/10 px-3 py-1 text-amber-300">
            Corners
          </span>
        </nav>

        {/* Hero */}
        <section className="mb-8 rounded-3xl border border-slate-800 bg-gradient-to-br from-slate-900/80 to-slate-950/80 p-6">
          <div className="flex items-center gap-3">
            <span className="rounded-full bg-amber-500/15 px-2.5 py-0.5 text-[11px] font-medium uppercase tracking-wider text-amber-300">
              Corners O/U Model
            </span>
          </div>
          <h1 className="mt-3 text-2xl font-semibold tracking-tight">
            Match Corners Monitor
          </h1>
          <p className="mt-1 max-w-2xl text-sm text-slate-400">
            Poisson model for total match corners. Rolling EMA per team
            (attack/defence), home advantage, league baselines. Reference odds
            from Pinnacle (sharpest bookmaker). Place bets on bet365 / Paddy
            Power if they offer the same or better price on the line.
          </p>
        </section>

        <MonitorCard title="Pipeline Health">
          <div className="grid grid-cols-2 gap-3 sm:grid-cols-4">
            <Stat
              label="Scheduler heartbeat"
              value={formatDateTime(schedulerHeartbeatAt)}
              sub={formatRelativeAgeShort(schedulerHeartbeatAt)}
              tone={pipelineTone}
            />
            <Stat
              label="Latest shortlist"
              value={formatDateTime(shortlistMtime)}
              sub={formatRelativeAgeShort(shortlistMtime)}
              tone={shortlistMtime ? "default" : "amber"}
            />
            <Stat
              label="Predictions file"
              value={formatDateTime(predictionsMtime)}
              sub={formatRelativeAgeShort(predictionsMtime)}
              tone={predictionsMtime ? "default" : "amber"}
            />
            <Stat
              label="Pinnacle odds"
              value={formatDateTime(latestPinnacleCaptureAt ?? pinnacleCornersMtime)}
              sub={`${pinnacleMatches.length} fixtures - ${formatRelativeAgeShort(latestPinnacleCaptureAt ?? pinnacleCornersMtime)}`}
              tone={pinnacleMatches.length > 0 ? "default" : "amber"}
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


        {!predictionsCsv && (
          <section className="mb-6 rounded-2xl border border-amber-700/40 bg-amber-950/30 p-4 text-sm text-amber-200">
            No prediction data found. Run{" "}
            <code className="rounded bg-slate-800 px-1.5 py-0.5 text-xs">
              python scripts/corners-ou-model.py
            </code>{" "}
            then{" "}
            <code className="rounded bg-slate-800 px-1.5 py-0.5 text-xs">
              python scripts/matchday-shortlist.py --all-leagues
            </code>
          </section>
        )}

        {/* KPI strip */}
        <div className="mb-6 grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-6">
          <Stat
            label="Historical matches"
            value={predictions.length.toLocaleString()}
            sub="with predictions"
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
            label="Today value bets"
            value={valueBets.length.toString()}
            sub="from latest shortlist"
            tone={valueBets.length > 0 ? "amber" : "default"}
          />
          <Stat
            label="Signals tracked"
            value={signals.length.toString()}
            sub="upcoming fixtures"
          />
          <Stat
            label="Avg edge"
            value={
              valueBets.length > 0
                ? `${(valueBets.reduce((s, r) => s + pf(r.edge), 0) / valueBets.length * 100).toFixed(1)}%`
                : "---"
            }
            tone={
              valueBets.length > 0 &&
              valueBets.reduce((s, r) => s + pf(r.edge), 0) / valueBets.length >
                0.1
                ? "green"
                : "default"
            }
          />
        </div>

        <section className="mb-4 rounded-2xl border border-slate-800 bg-slate-900/40 p-4 text-sm text-slate-400">
          <strong className="text-slate-200">How to read this page.</strong>{" "}
          <span className="text-slate-300">All model fixtures</span> is the full slate the corners model priced.
          <span className="text-slate-300"> Bettable value bets</span> is the smaller subset where current bookmaker odds
          cleared the edge threshold and staking rules. So if you see 48 fixtures and 32 value bets, that means 32 of the
          priced fixtures currently qualify as playable rather than 32 separate random signals.
        </section>

        {/* Value bets (the shortlist) */}
        {valueBets.length > 0 && (
          <MonitorCard
            title={`Current Bettable Signals - ${currentValueSignals.length} best bets from ${valueBets.length} raw lines`}
          >
            <p className="mb-3 text-xs text-slate-500">
              Kept only the best-value line per match and side, so the same over or under is not stacked twice.
            </p>
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
                    <th className="py-2 pr-3 font-mono">Stake</th>
                    <th className="py-2 pr-3">Result</th>
                    <th className="py-2 pr-3 font-mono">PnL</th>
                    <th className="py-2 font-mono">PnL (staked)</th>
                  </tr>
                </thead>
                <tbody>
                  {currentValueSignals.map((item, i) => {
                      const row = item.row;
                      const edge = item.edgeValue;
                      const matchDate = (item.displayDate ?? "").trim().slice(0, 10);
                      const todayIso = new Date().toISOString().slice(0, 10);
                      const result = matchDate && matchDate < todayIso ? "awaiting result" : "pending";
                      return (
                        <tr
                          key={i}
                            className="border-b border-slate-800/40 hover:bg-slate-800/20"
                        >
                          <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">
                            {item.displayDate}
                          </td>
                          <td className="py-1.5 pr-3 text-slate-400">
                            {row.league}
                          </td>
                          <td className="py-1.5 pr-3 font-medium">
                            {row.match}
                          </td>
                          <td className="py-1.5 pr-3 font-mono tabular-nums">
                            {row.line}
                          </td>
                          <td className="py-1.5 pr-3">
                            <span
                              className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase ${
                                row.side === "over"
                                  ? "bg-emerald-500/15 text-emerald-300"
                                  : "bg-sky-500/15 text-sky-300"
                              }`}
                            >
                              {row.side}
                            </span>
                          </td>
                          <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-100">
                            {pf(row.bookie_odds).toFixed(2)}
                          </td>
                          <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">
                            {pf(row.model_fair).toFixed(2)}
                          </td>
                          <td
                            className={`py-1.5 pr-3 font-mono tabular-nums ${
                              edge >= 0.15
                                ? "text-emerald-300"
                                : edge >= 0.10
                                  ? "text-amber-300"
                                  : "text-slate-300"
                            }`}
                          >
                            {(edge * 100).toFixed(1)}%
                          </td>
                          <td className="py-1.5 pr-3 font-mono tabular-nums text-amber-200">
                            {pf(row.stake).toFixed(1)}u
                          </td>
                          <td className="py-1.5 pr-3">
                            <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase ${
                              result === "awaiting result"
                                ? "bg-amber-500/15 text-amber-300"
                                : "bg-slate-700/30 text-slate-400"
                            }`}>
                              {result}
                            </span>
                          </td>
                          <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-500">-</td>
                          <td className="py-1.5 font-mono tabular-nums text-slate-500">-</td>
                        </tr>
                      );
                    })}
                </tbody>
              </table>
            </div>
          </MonitorCard>
        )}

        {/* Live P&L */}
        <div className="mt-6">
          <MonitorCard title={`Live P&L Archive - ${liveSettled.length} settled${livePending.length > 0 ? `, ${livePending.length} pending tracked` : ""}`}>
            {liveSettled.length === 0 ? (
              <p className="text-sm text-slate-500">
                No settled bets yet. Run{" "}
                <code className="rounded bg-slate-800 px-1.5 py-0.5 text-xs">
                  python scripts/shortlist-settle.py
                </code>{" "}
                after results are in.
              </p>
            ) : (
              <>
                <div className="grid grid-cols-2 gap-3 sm:grid-cols-3 lg:grid-cols-5">
                  <Stat
                    label="P&L (flat)"
                    value={`${livePnlFlat >= 0 ? "+" : ""}${livePnlFlat.toFixed(2)}u`}
                    sub={`${liveWon.length}W / ${liveLost.length}L`}
                    tone={livePnlFlat > 0 ? "green" : livePnlFlat < 0 ? "red" : "default"}
                  />
                  <Stat
                    label="P&L (staked)"
                    value={`${livePnlStaked >= 0 ? "+" : ""}${livePnlStaked.toFixed(2)}u`}
                    sub={`${liveTotalStaked.toFixed(1)}u staked`}
                    tone={livePnlStaked > 0 ? "green" : livePnlStaked < 0 ? "red" : "default"}
                  />
                  <Stat
                    label="ROI (flat)"
                    value={`${liveRoiFlat >= 0 ? "+" : ""}${liveRoiFlat.toFixed(1)}%`}
                    tone={liveRoiFlat > 5 ? "green" : liveRoiFlat < -5 ? "red" : "amber"}
                  />
                  <Stat
                    label="ROI (staked)"
                    value={`${liveRoiStaked >= 0 ? "+" : ""}${liveRoiStaked.toFixed(1)}%`}
                    sub={`${liveSettled.length} settled`}
                    tone={liveRoiStaked > 5 ? "green" : liveRoiStaked < -5 ? "red" : "amber"}
                  />
                  <Stat
                    label="Win rate"
                    value={`${liveWinRate.toFixed(0)}%`}
                    sub={`${livePending.length} pending`}
                    tone={liveWinRate > 55 ? "green" : liveWinRate < 45 ? "red" : "default"}
                  />
                </div>

                {liveByLeague.length > 1 && (
                  <div className="mt-4 overflow-x-auto">
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
                            <td className="py-1.5 pr-4 font-medium">{lg}</td>
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

                {recentSettled.length > 0 && (
                  <div className="mt-4 overflow-x-auto">
                    <div className="mb-1 text-[10px] uppercase tracking-wider text-slate-500">Recent results</div>
                    <table className="w-full text-left text-xs">
                      <thead>
                        <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                          <th className="py-2 pr-3">Date</th>
                          <th className="py-2 pr-3">Match</th>
                          <th className="py-2 pr-3">Line</th>
                          <th className="py-2 pr-3">Side</th>
                          <th className="py-2 pr-3 font-mono">Edge</th>
                          <th className="py-2 pr-3 font-mono">Odds</th>
                          <th className="py-2 pr-3 font-mono">Total</th>
                          <th className="py-2 pr-3 font-mono">Stake</th>
                          <th className="py-2 pr-3">W/L</th>
                          <th className="py-2 pr-3 font-mono">P&L</th>
                          <th className="py-2 font-mono">P&L (staked)</th>
                        </tr>
                      </thead>
                      <tbody>
                        {recentSettled.map((row, i) => {
                          const won = row.won === "yes";
                          const pnlFlat = pf(row.pnl_units);
                          const pnlStaked = pf(row.pnl_staked);
                          return (
                            <tr key={i} className="border-b border-slate-800/40 hover:bg-slate-800/20">
                              <td className="py-1.5 pr-3 text-slate-400">{row.match_date?.slice(0, 10)}</td>
                              <td className="py-1.5 pr-3 font-medium">{(row.match ?? "").slice(0, 26)}</td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">{row.line}</td>
                              <td className="py-1.5 pr-3">
                                <span className={`rounded-full px-1.5 py-0.5 text-[10px] font-medium uppercase ${row.side === "over" ? "bg-emerald-500/15 text-emerald-300" : "bg-sky-500/15 text-sky-300"}`}>
                                  {row.side}
                                </span>
                              </td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{(pf(row.edge) * 100).toFixed(1)}%</td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums">{pf(row.bookie_odds).toFixed(2)}</td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">{row.actual_total_corners || "-"}</td>
                              <td className="py-1.5 pr-3 font-mono tabular-nums text-amber-200">{pf(row.stake, 1).toFixed(1)}u</td>
                              <td className="py-1.5 pr-3">
                                <span className={`font-medium ${won ? "text-emerald-300" : "text-rose-300"}`}>{won ? "W" : "L"}</span>
                              </td>
                              <td className={`py-1.5 pr-3 font-mono tabular-nums ${pnlFlat >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                                {pnlFlat >= 0 ? "+" : ""}{pnlFlat.toFixed(2)}u
                              </td>
                              <td className={`py-1.5 font-mono tabular-nums ${pnlStaked >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                                {pnlStaked >= 0 ? "+" : ""}{pnlStaked.toFixed(2)}u
                              </td>
                            </tr>
                          );
                        })}
                      </tbody>
                    </table>
                  </div>
                )}
              </>
            )}
          </MonitorCard>
        </div>

        {/* Upcoming signals (model predictions for today) */}
        {signals.length > 0 && (
          <div className="mt-6">
            <CollapsibleSection title={`All Model Fixtures — ${signals.length} fixtures`} defaultOpen={false}>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                      <th className="py-2 pr-3">Match</th>
                      <th className="py-2 pr-3">League</th>
                      <th className="py-2 pr-3 font-mono">Lam H</th>
                      <th className="py-2 pr-3 font-mono">Lam A</th>
                      <th className="py-2 pr-3 font-mono">Total</th>
                      {signalLineValues.flatMap((l) => [
                        <th key={`h-o-${l}`} className="py-2 pr-1 font-mono">O {l.toFixed(1)}</th>,
                        <th key={`h-u-${l}`} className="py-2 pr-3 font-mono text-slate-500">U {l.toFixed(1)}</th>,
                      ])}
                    </tr>
                  </thead>
                  <tbody>
                    {signals.map((row, i) => (
                      <tr
                        key={i}
                        className="border-b border-slate-800/40 hover:bg-slate-800/20"
                      >
                        <td className="py-1.5 pr-3 font-medium">
                          {row.home_team} vs {row.away_team}
                        </td>
                        <td className="py-1.5 pr-3 text-slate-400">
                          {row.league}
                        </td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-emerald-300">
                          {pf(row.lambda_home).toFixed(2)}
                        </td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-sky-300">
                          {pf(row.lambda_away).toFixed(2)}
                        </td>
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-amber-200">
                          {pf(row.lambda_total).toFixed(2)}
                        </td>
                        {signalLineValues.flatMap((l) => [
                          <td key={`${i}-o-${l}`} className="py-1.5 pr-1 font-mono tabular-nums">
                            {pf(row[`fair_over_${l}`]).toFixed(2)}
                          </td>,
                          <td key={`${i}-u-${l}`} className="py-1.5 pr-3 font-mono tabular-nums text-slate-400">
                            {pf(row[`fair_under_${l}`]).toFixed(2)}
                          </td>,
                        ])}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
            </CollapsibleSection>
          </div>
        )}

        <div className="mt-6 space-y-4">
          {/* Pinnacle corners lines */}
          {pinnacleMatches.length > 0 && (
            <CollapsibleSection title={`Pinnacle Corners Lines (${pinnacleMatches.length} fixtures)`} defaultOpen={false}>
              <div className="overflow-x-auto">
                <table className="w-full text-left text-xs">
                  <thead>
                    <tr className="border-b border-slate-800 text-[10px] uppercase tracking-wider text-slate-500">
                      <th className="py-2 pr-3">Date</th>
                      <th className="py-2 pr-3">League</th>
                      <th className="py-2 pr-3">Match</th>
                      {pinnacleLineValues.map((l) => (
                        <th key={l} className="py-2 pr-1 text-center" colSpan={2}>{l.toFixed(1)}</th>
                      ))}
                    </tr>
                    <tr className="border-b border-slate-800/60 text-[10px] text-slate-600">
                      <th colSpan={3} />
                      {pinnacleLineValues.flatMap((l) => [
                        <th key={`${l}-o`} className="py-1 pr-1 text-center font-mono">O</th>,
                        <th key={`${l}-u`} className="py-1 pr-3 text-center font-mono">U</th>,
                      ])}
                    </tr>
                  </thead>
                  <tbody>
                    {pinnacleMatches.map((m, i) => (
                      <tr key={i} className="border-b border-slate-800/40 hover:bg-slate-800/20">
                        <td className="py-1.5 pr-3 font-mono tabular-nums text-slate-500">
                          {m.match_date.slice(5)}
                        </td>
                        <td className="py-1.5 pr-3 text-slate-500">{m.league}</td>
                        <td className="py-1.5 pr-3 font-medium text-slate-200">
                          {m.home_team} v {m.away_team}
                        </td>
                        {pinnacleLineValues.flatMap((l) => {
                          const lineData = m.lines[l.toFixed(1)] ?? { over: 0, under: 0 };
                          return [
                            <td key={`${i}-${l}-o`} className="py-1.5 pr-1 text-center font-mono tabular-nums text-slate-300">
                              {lineData.over > 0 ? lineData.over.toFixed(2) : "-"}
                            </td>,
                            <td key={`${i}-${l}-u`} className="py-1.5 pr-3 text-center font-mono tabular-nums text-slate-500">
                              {lineData.under > 0 ? lineData.under.toFixed(2) : "-"}
                            </td>,
                          ];
                        })}
                      </tr>
                    ))}
                  </tbody>
                </table>
              </div>
              <p className="mt-2 text-[11px] text-slate-600">
                Pinnacle closing-line reference. American odds converted to decimal. All lines found in the data are shown.
                Capture: {latestPinnacleCaptureAt ?? "—"}
              </p>
            </CollapsibleSection>
          )}

          {/* Full P&L report */}
          {livePnlTxt && (
            <CollapsibleSection title="Full Live P&L Report" defaultOpen={false}>
              <pre className="max-h-[500px] overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">
                {livePnlTxt}
              </pre>
            </CollapsibleSection>
          )}

          {/* Full shortlist output */}
          {shortlistTxt && (
            <CollapsibleSection title="Latest Shortlist (full output)" defaultOpen>
              <pre className="max-h-[600px] overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">
                {shortlistTxt}
              </pre>
            </CollapsibleSection>
          )}

          {/* Calibration report */}
          {calibrationTxt && (
            <CollapsibleSection title="Model Calibration Report">
              <pre className="max-h-80 overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">
                {calibrationTxt}
              </pre>
            </CollapsibleSection>
          )}

          {/* Backtest report */}
          {backtestReportTxt && (
            <CollapsibleSection title="Backtest Report (vs smart baseline)">
              <pre className="max-h-80 overflow-auto whitespace-pre-wrap font-mono text-xs text-slate-300">
                {backtestReportTxt}
              </pre>
            </CollapsibleSection>
          )}

          {/* How to use */}
          <CollapsibleSection title="How to use">
            <div className="space-y-3 text-sm text-slate-300">
              <div>
                <h3 className="font-medium text-slate-200">
                  1. Generate predictions
                </h3>
                <code className="mt-1 block rounded bg-slate-800 px-3 py-2 text-xs">
                  python scripts/matchday-shortlist.py --all-leagues --min-edge
                  0.08
                </code>
              </div>
              <div>
                <h3 className="font-medium text-slate-200">
                  2. Check this page
                </h3>
                <p className="text-xs text-slate-400">
                  Refresh this page to see the latest shortlist, value bets, and
                  model signals.
                </p>
              </div>
              <div>
                <h3 className="font-medium text-slate-200">
                  3. Settle results
                </h3>
                <code className="mt-1 block rounded bg-slate-800 px-3 py-2 text-xs">
                  python scripts/shortlist-settle.py
                </code>
              </div>
            </div>
          </CollapsibleSection>
        </div>

        <footer className="mt-12 border-t border-slate-800/60 pt-4 text-center text-[11px] text-slate-600">
          Corners O/U Model Monitor - Il Margine
        </footer>
      </div>
    </div>
  );
}
