import Link from "next/link";
import { promises as fs } from "node:fs";
import { notFound } from "next/navigation";

import { tryGetKnownProjectFilePath } from "@/lib/project-file-paths";

import {
  EmptyState,
  HeroCard,
  LeagueLabel,
  MatchLabel,
  MODEL_MONITOR_ENABLED,
  MonitorNav,
  SectionCard,
  StatCard,
  StatusPill,
  cn,
  formatDateTimeLabel,
  formatOdds,
  formatUnits,
  toneClass,
} from "../shared";

export const dynamic = "force-dynamic";

type CsvRow = Record<string, string>;

type LedgerSummary = {
  signals: number;
  settled: number;
  pending: number;
  won: number;
  lost: number;
  voided: number;
  pnl: number;
  staked: number;
  roiPct: number | null;
  avgEdge: number | null;
};

type LeagueLedgerSummary = LedgerSummary & {
  leagueKey: string;
  leagueLabel: string;
};

const SIGNALS_PATH = "data/assist-value/assist-value-shadow-signals.csv";
const SHADOW_REPORT_PATH = "data/assist-value/assist-value-shadow-report.txt";
const MODEL_REPORT_PATH = "data/assist-value/assist-value-model-report.txt";
const PERFORMANCE_REPORT_PATH = "data/assist-value/assist-value-shadow-performance.txt";

function parseCsvLine(line: string): string[] {
  const cells: string[] = [];
  let current = "";
  let quoted = false;

  for (let index = 0; index < line.length; index += 1) {
    const char = line[index];
    if (char === '"' && quoted && line[index + 1] === '"') {
      current += '"';
      index += 1;
      continue;
    }
    if (char === '"') {
      quoted = !quoted;
      continue;
    }
    if (char === "," && !quoted) {
      cells.push(current);
      current = "";
      continue;
    }
    current += char;
  }

  cells.push(current);
  return cells.map((cell) => cell.trim());
}

function parseCsv(text: string | null): CsvRow[] {
  const lines = (text ?? "").split(/\r?\n/).filter(Boolean);
  if (lines.length < 2) return [];

  const headers = parseCsvLine(lines[0]);
  return lines.slice(1).map((line) => {
    const values = parseCsvLine(line);
    const row: CsvRow = {};
    headers.forEach((header, index) => {
      row[header] = values[index] ?? "";
    });
    return row;
  });
}

function numeric(row: CsvRow, key: string): number | null {
  const raw = row[key];
  if (raw === undefined || raw === "") return null;
  const value = Number(raw);
  return Number.isFinite(value) ? value : null;
}

function sum(values: Array<number | null>): number {
  return values.reduce<number>((total, value) => total + (value ?? 0), 0);
}

function avg(values: Array<number | null>): number | null {
  const clean = values.filter((value): value is number => value !== null && Number.isFinite(value));
  if (clean.length === 0) return null;
  return sum(clean) / clean.length;
}

function signedPp(value: number | null, digits = 1): string {
  if (value === null) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)} pp`;
}

function signedPct(value: number | null, digits = 1): string {
  if (value === null) return "-";
  const sign = value > 0 ? "+" : "";
  return `${sign}${value.toFixed(digits)}%`;
}

function pct(value: number | null, digits = 1): string {
  if (value === null) return "-";
  return `${value.toFixed(digits)}%`;
}

function probPct(value: number | null, digits = 1): string {
  if (value === null) return "-";
  return `${(value * 100).toFixed(digits)}%`;
}

function cleanStatus(value?: string | null): string {
  return (value ?? "").trim().toLowerCase();
}

function isSignal(row: CsvRow): boolean {
  return cleanStatus(row.signal_status) === "shadow_signal";
}

function isSettled(row: CsvRow): boolean {
  const settled = cleanStatus(row.settled);
  const outcome = cleanStatus(row.bet_outcome);
  return settled === "1" || settled === "true" || settled === "yes" || outcome === "won" || outcome === "lost" || outcome === "void";
}

function outcome(row: CsvRow): "won" | "lost" | "void" | "pending" {
  const value = cleanStatus(row.bet_outcome);
  if (value === "won" || value === "lost" || value === "void") return value;
  return isSettled(row) ? "void" : "pending";
}

function pnlUnits(row: CsvRow): number {
  const explicit = numeric(row, "pnl_units");
  if (explicit !== null) return explicit;

  const result = outcome(row);
  if (result === "won") return Math.max(0, numeric(row, "market_odds") ?? 1) - 1;
  if (result === "lost") return -1;
  return 0;
}

function settlementColumnsPresent(rows: CsvRow[]): boolean {
  if (rows.length === 0) return true;
  return "settled" in rows[0] && "bet_outcome" in rows[0] && "pnl_units" in rows[0];
}

function summarize(rows: CsvRow[]): LedgerSummary {
  const signals = rows.filter(isSignal);
  const settledRows = signals.filter(isSettled);
  const won = settledRows.filter((row) => outcome(row) === "won").length;
  const lost = settledRows.filter((row) => outcome(row) === "lost").length;
  const voided = settledRows.filter((row) => outcome(row) === "void").length;
  const staked = won + lost;
  const pnl = sum(settledRows.map(pnlUnits));

  return {
    signals: signals.length,
    settled: settledRows.length,
    pending: Math.max(0, signals.length - settledRows.length),
    won,
    lost,
    voided,
    pnl,
    staked,
    roiPct: staked > 0 ? (pnl / staked) * 100 : null,
    avgEdge: avg(signals.map((row) => numeric(row, "edge_pp"))),
  };
}

function leagueSummaries(rows: CsvRow[]): LeagueLedgerSummary[] {
  const byLeague = new Map<string, CsvRow[]>();

  rows.filter(isSignal).forEach((row) => {
    const key = row.league_key || row.competition || "unknown";
    byLeague.set(key, [...(byLeague.get(key) ?? []), row]);
  });

  return [...byLeague.entries()]
    .map(([leagueKey, leagueRows]) => ({
      ...summarize(leagueRows),
      leagueKey,
      leagueLabel: leagueRows[0]?.competition || leagueKey,
    }))
    .sort((a, b) => b.signals - a.signals || b.pnl - a.pnl);
}

function maxValue(rows: CsvRow[], key: string): string {
  return rows
    .map((row) => row[key])
    .filter(Boolean)
    .sort()
    .at(-1) ?? "-";
}

function reportValue(report: string | null, label: string): string {
  const match = (report ?? "").match(new RegExp(`${label}:\\s*([^\\n\\r]+)`, "i"));
  return match?.[1]?.trim() ?? "-";
}

function timestampMs(value: string | null | undefined): number | null {
  const text = (value ?? "").trim();
  if (!text || text === "-") return null;
  const parsed = Date.parse(text);
  return Number.isFinite(parsed) ? parsed : null;
}

async function readLocalFile(relativePath: string): Promise<string | null> {
  try {
    const fullPath = tryGetKnownProjectFilePath(relativePath);
    if (!fullPath) return null;
    return await fs.readFile(fullPath, "utf8");
  } catch {
    return null;
  }
}

async function readLocalMtime(relativePath: string): Promise<string | null> {
  try {
    const fullPath = tryGetKnownProjectFilePath(relativePath);
    if (!fullPath) return null;
    const stat = await fs.stat(fullPath);
    return stat.mtime.toISOString();
  } catch {
    return null;
  }
}

function confidenceTone(confidence: string): string {
  const value = confidence.toLowerCase();
  if (value === "high") return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (value === "medium") return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  return "bg-slate-700/40 text-slate-400 border-slate-600/40";
}

function signalTone(status: string): string {
  const value = status.toLowerCase();
  if (value === "shadow_signal") return "bg-cyan-500/10 text-cyan-300 border-cyan-500/20";
  if (value === "watch") return "bg-amber-500/10 text-amber-300 border-amber-500/20";
  return "bg-slate-700/40 text-slate-400 border-slate-600/40";
}

function outcomeTone(value: string): string {
  if (value === "won") return "bg-emerald-500/10 text-emerald-300 border-emerald-500/20";
  if (value === "lost") return "bg-rose-500/10 text-rose-300 border-rose-500/20";
  if (value === "void") return "bg-slate-700/40 text-slate-400 border-slate-600/40";
  return "bg-amber-500/10 text-amber-300 border-amber-500/20";
}

function displayLeague(row: CsvRow): string {
  return row.league_key || row.competition || "league";
}

function settlementLabel(row: CsvRow): string {
  const result = outcome(row);
  if (result === "pending") return "pending";
  return `${result} ${formatUnits(pnlUnits(row), 2)}`;
}

function PriceTile({ label, value, detail, tone }: { label: string; value: string; detail?: string; tone?: string }) {
  return (
    <div className="rounded-xl border border-slate-800/70 bg-slate-950/55 px-3 py-3">
      <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">{label}</div>
      <div className={cn("mt-1.5 text-lg font-semibold tabular-nums", tone ?? "text-slate-100")}>{value}</div>
      {detail ? <div className="mt-1 text-[11px] text-slate-500">{detail}</div> : null}
    </div>
  );
}

function AssistSignalCard({ row, rank }: { row: CsvRow; rank: number }) {
  const result = outcome(row);
  const edge = numeric(row, "edge_pp");
  const ev = numeric(row, "ev_pct");
  const fairOdds = numeric(row, "fair_odds");
  const marketOdds = numeric(row, "market_odds");
  const setPieceShare = numeric(row, "setpiece_share_last5_pct");
  const cornerShare = numeric(row, "corner_share_last5_pct");
  const fkShare = numeric(row, "fk_share_last5_pct");
  const modelProb = numeric(row, "model_prob");
  const expectedMinutes = numeric(row, "expected_minutes");

  return (
    <article className="group relative overflow-hidden rounded-2xl border border-slate-800/90 bg-[radial-gradient(circle_at_top_left,rgba(20,184,166,0.12),transparent_34%),linear-gradient(135deg,rgba(15,23,42,0.95),rgba(2,6,23,0.98))] p-4 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
      <div className="absolute inset-y-0 left-0 w-1 bg-gradient-to-b from-emerald-400 via-cyan-400 to-sky-500" />
      <div className="flex flex-wrap items-start justify-between gap-4 pl-2">
        <div className="min-w-0 flex-1">
          <div className="flex flex-wrap items-center gap-2 text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-500">
            <span className="rounded-full border border-slate-700/70 bg-slate-950/60 px-2 py-0.5 text-slate-300">#{rank}</span>
            <LeagueLabel league={displayLeague(row)} label={row.competition || row.league_key} iconSize={14} />
          </div>
          <h3 className="mt-2 text-xl font-semibold tracking-tight text-white">{row.player_name || "Unknown player"}</h3>
          <div className="mt-1 flex flex-wrap items-center gap-2 text-sm text-slate-400">
            <MatchLabel
              league={displayLeague(row)}
              homeTeam={row.home_team}
              awayTeam={row.away_team}
              iconSize={20}
              textClassName="text-sm text-slate-400"
            />
            <span className="text-slate-700">|</span>
            <span>{formatDateTimeLabel(row.kickoff_at || row.match_date)}</span>
          </div>
          <div className="mt-2 text-xs text-slate-500">
            {row.player_team || "player team"} attack side vs {row.opponent_team || "opponent"} | {row.position || "pos n/a"} | {expectedMinutes !== null ? `${expectedMinutes.toFixed(0)} projected mins` : "minutes n/a"}
          </div>
        </div>

        <div className="flex shrink-0 flex-wrap justify-end gap-1.5">
          <StatusPill label={row.signal_status?.replaceAll("_", " ") || "shadow"} tone={signalTone(row.signal_status || "shadow_signal")} />
          <StatusPill label={row.confidence || "unrated"} tone={confidenceTone(row.confidence || "")} />
          <StatusPill label={settlementLabel(row)} tone={outcomeTone(result)} />
        </div>
      </div>

      <div className="mt-4 grid gap-2 pl-2 sm:grid-cols-2 lg:grid-cols-6">
        <PriceTile label="Fair" value={formatOdds(fairOdds, 2)} detail={probPct(modelProb)} />
        <PriceTile label="Market" value={formatOdds(marketOdds, 2)} detail={row.bookmaker || "book"} />
        <PriceTile label="Edge" value={signedPp(edge, 2)} tone={toneClass(edge)} />
        <PriceTile label="EV" value={signedPct(ev, 1)} tone={toneClass(ev)} />
        <PriceTile label="Set pieces" value={pct(setPieceShare, 1)} detail={`CK ${pct(cornerShare, 0)} | FK ${pct(fkShare, 0)}`} />
        <PriceTile label="P/L" value={isSettled(row) ? formatUnits(pnlUnits(row), 2) : "pending"} tone={isSettled(row) ? toneClass(pnlUnits(row)) : "text-amber-300"} />
      </div>

      {row.notes ? <div className="mt-3 pl-2 text-[11px] text-slate-600">{row.notes}</div> : null}
    </article>
  );
}

function LeagueLedger({ leagues }: { leagues: LeagueLedgerSummary[] }) {
  if (leagues.length === 0) return <EmptyState message="No shadow signals yet, so no league ledger is available." />;

  return (
    <div className="grid gap-3 lg:grid-cols-2 xl:grid-cols-3">
      {leagues.map((league) => (
        <div key={league.leagueKey} className="rounded-xl border border-slate-800/80 bg-slate-950/45 p-4">
          <div className="flex items-start justify-between gap-3">
            <div className="min-w-0">
              <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">League ledger</div>
              <div className="mt-1 text-sm font-semibold text-slate-100">
                <LeagueLabel league={league.leagueKey} label={league.leagueLabel} iconSize={16} />
              </div>
            </div>
            <StatusPill label={`${league.pending} pending`} tone="bg-amber-500/10 text-amber-300 border-amber-500/20" />
          </div>
          <div className="mt-4 grid grid-cols-2 gap-2">
            <StatCard compact label="Signals" value={`${league.signals}`} detail={`${league.settled} settled`} />
            <StatCard compact label="W-L-V" value={`${league.won}-${league.lost}-${league.voided}`} />
            <StatCard compact label="P/L" value={formatUnits(league.pnl, 2)} tone={toneClass(league.pnl)} />
            <StatCard compact label="ROI" value={signedPct(league.roiPct ?? 0, 1)} detail={league.staked > 0 ? `${league.staked}u staked` : "no settled stake"} tone={toneClass(league.roiPct ?? 0)} />
          </div>
          <div className="mt-3 text-xs text-slate-500">Avg edge: {signedPp(league.avgEdge, 2)}</div>
        </div>
      ))}
    </div>
  );
}

export default async function AssistValueMonitorPage() {
  if (!MODEL_MONITOR_ENABLED) {
    notFound();
  }

  const [signalsText, shadowReport, modelReport, performanceReport, signalsMtime] = await Promise.all([
    readLocalFile(SIGNALS_PATH),
    readLocalFile(SHADOW_REPORT_PATH),
    readLocalFile(MODEL_REPORT_PATH),
    readLocalFile(PERFORMANCE_REPORT_PATH),
    readLocalMtime(SIGNALS_PATH),
  ]);

  const rows = parseCsv(signalsText);
  const signals = rows.filter(isSignal);
  const watchRows = rows.filter((row) => cleanStatus(row.signal_status) === "watch");
  const noEdgeRows = rows.filter((row) => cleanStatus(row.signal_status) === "no_edge");
  const sortedSignals = [...signals].sort((a, b) => (numeric(b, "edge_pp") ?? -999) - (numeric(a, "edge_pp") ?? -999));
  const generatedAt = maxValue(rows, "generated_at");
  const capturedAt = maxValue(rows, "captured_at");
  const latestKickoff = maxValue(rows, "kickoff_at");
  const ledger = summarize(rows);
  const leagues = leagueSummaries(rows);
  const hasSettlementColumns = settlementColumnsPresent(rows);
  const roleMatchRate = reportValue(shadowReport, "role_match_rate_pct");
  const publicStatus = reportValue(shadowReport, "public_signal_status");
  const performanceGeneratedAt = reportValue(performanceReport, "generated_at_utc");
  const latestSignalTimestamp = timestampMs(generatedAt) ?? timestampMs(signalsMtime);
  const performanceTimestamp = timestampMs(performanceGeneratedAt);
  const hasPerformanceReport = Boolean(performanceReport);
  const performanceIsStale =
    hasPerformanceReport &&
    latestSignalTimestamp !== null &&
    performanceTimestamp !== null &&
    performanceTimestamp + 5 * 60 * 1000 < latestSignalTimestamp;
  const settlementUnderReview = !/settlement_valid_for_roi:\s*true/i.test(performanceReport ?? "");
  const latestKickoffTimestamp = timestampMs(latestKickoff);
  const capturedTimestamp = timestampMs(capturedAt);
  const artifactTimestamp = timestampMs(signalsMtime) ?? latestSignalTimestamp ?? performanceTimestamp;
  const fixtureSourceIsStale =
    latestKickoffTimestamp !== null &&
    artifactTimestamp !== null &&
    latestKickoffTimestamp + 48 * 60 * 60 * 1000 < artifactTimestamp;
  const captureSourceIsStale =
    capturedTimestamp !== null &&
    artifactTimestamp !== null &&
    capturedTimestamp + 48 * 60 * 60 * 1000 < artifactTimestamp;
  const sourceIsStale = fixtureSourceIsStale || captureSourceIsStale;
  const visibleSignals = sourceIsStale ? [] : sortedSignals;

  return (
    <main className="min-h-screen bg-[#050b12] px-4 py-6 text-slate-100 sm:px-6 lg:px-8">
      <div className="mx-auto max-w-7xl space-y-5">
        <div className="flex flex-wrap items-center justify-between gap-3">
          <Link href="/model-monitor" className="text-sm font-semibold text-emerald-300 hover:text-emerald-200">
            Back to model monitor
          </Link>
          <MonitorNav current="assist-value" />
        </div>

        <HeroCard title="Assist Value Shadow Monitor" eyebrow="Research lane, no public betting output">
          <div className="max-w-4xl text-slate-400">
            Bet365 assist odds are compared with the internal assist fair line. The lane is paused while settlement and calibration are under review; stale/offseason odds are now blocked from being displayed as current candidates.
          </div>
          <div className="mt-4 flex flex-wrap gap-2">
            <StatusPill label={publicStatus === "-" ? "private shadow" : publicStatus.replaceAll("_", " ")} tone="bg-amber-500/10 text-amber-300 border-amber-500/20" />
            <StatusPill
              label={sourceIsStale ? "offseason / stale source" : "fresh source"}
              tone={sourceIsStale ? "bg-rose-500/10 text-rose-300 border-rose-500/20" : "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"}
            />
            <StatusPill label="settlement under review" tone="bg-rose-500/10 text-rose-300 border-rose-500/20" />
            <StatusPill label={`${ledger.pending} pending`} tone="bg-cyan-500/10 text-cyan-300 border-cyan-500/20" />
            <StatusPill label={hasSettlementColumns ? "settlement columns ready" : "settlement columns missing locally"} tone={hasSettlementColumns ? "bg-emerald-500/10 text-emerald-300 border-emerald-500/20" : "bg-rose-500/10 text-rose-300 border-rose-500/20"} />
            <StatusPill
              label={!hasPerformanceReport ? "performance missing" : performanceIsStale ? "performance stale" : "performance fresh"}
              tone={!hasPerformanceReport || performanceIsStale ? "bg-rose-500/10 text-rose-300 border-rose-500/20" : "bg-emerald-500/10 text-emerald-300 border-emerald-500/20"}
            />
          </div>
        </HeroCard>

        {sourceIsStale ? (
          <div className="rounded-2xl border border-amber-500/30 bg-amber-500/10 px-5 py-4 text-sm text-amber-100">
            Assist Value is paused because the latest source fixture/odds are stale
            {latestKickoff !== "-" ? <>: latest kickoff <span className="font-semibold">{formatDateTimeLabel(latestKickoff)}</span></> : null}
            {capturedAt !== "-" ? <>; latest capture <span className="font-semibold">{formatDateTimeLabel(capturedAt)}</span></> : null}.
            Current candidate cards are hidden so old club-season prices cannot be mistaken for live fair odds.
          </div>
        ) : null}

        {settlementUnderReview ? (
          <div className="rounded-2xl border border-rose-500/30 bg-rose-500/10 px-5 py-4 text-sm text-rose-100">
            Assist settlement is paused for model-risk review. The current W/L, P/L and ROI are not valid promotion evidence until FotMob assist extraction is revalidated, old rows are resettled with <span className="font-semibold">--resettle</span>, and a calibration/CLV report exists.
          </div>
        ) : null}

        {!hasSettlementColumns ? (
          <div className="rounded-2xl border border-amber-500/25 bg-amber-500/10 px-5 py-4 text-sm text-amber-100">
            The local signal CSV does not yet include settlement columns. The monitor still exposes P/L and ROI as zero-settled/pending, and the hosted settler will populate result columns after the next assist workflow run.
          </div>
        ) : null}

        {performanceIsStale ? (
          <div className="rounded-2xl border border-rose-500/25 bg-rose-500/10 px-5 py-4 text-sm text-rose-100">
            Assist settlement is stale: the signal artifact is newer than the performance report. Do not trust the
            P/L/ROI panel until the next assist workflow run refreshes <span className="font-semibold">assist-value-shadow-performance.txt</span>.
          </div>
        ) : null}

        <section className="grid gap-3 md:grid-cols-2 xl:grid-cols-4">
          <StatCard label="Shadow signals" value={`${ledger.signals}`} detail={`${watchRows.length} watch rows | ${noEdgeRows.length} no-edge rows`} />
          <StatCard label="Settled / pending" value={`${ledger.settled} / ${ledger.pending}`} detail={`${ledger.won}-${ledger.lost}-${ledger.voided} W-L-V`} />
          <StatCard label="Shadow P/L" value={formatUnits(ledger.pnl, 2)} detail={`${ledger.staked}u settled stake`} tone={toneClass(ledger.pnl)} />
          <StatCard label="Shadow ROI" value={signedPct(ledger.roiPct ?? 0, 1)} detail={settlementUnderReview ? "invalid while settlement is under review" : ledger.roiPct === null ? "no settled stake yet" : "settled signals only"} tone={settlementUnderReview ? "text-rose-300" : toneClass(ledger.roiPct ?? 0)} />
          <StatCard label="Average edge" value={signedPp(ledger.avgEdge, 2)} detail="shadow signals only" tone={toneClass(ledger.avgEdge)} />
          <StatCard label="Role match" value={roleMatchRate === "-" ? "-" : `${roleMatchRate}%`} detail="source audit row match" />
          <StatCard label="Generated" value={generatedAt === "-" ? "-" : formatDateTimeLabel(generatedAt)} detail={signalsMtime ? `file ${formatDateTimeLabel(signalsMtime)}` : "file timestamp unavailable"} />
          <StatCard label="Captured" value={capturedAt === "-" ? "-" : formatDateTimeLabel(capturedAt)} detail="latest odds capture in CSV" tone={captureSourceIsStale ? "text-rose-300" : undefined} />
          <StatCard label="Latest kickoff" value={latestKickoff === "-" ? "-" : formatDateTimeLabel(latestKickoff)} detail={fixtureSourceIsStale ? "stale source fixture" : "source fixture freshness"} tone={fixtureSourceIsStale ? "text-rose-300" : "text-emerald-300"} />
          <StatCard
            label="Performance"
            value={performanceGeneratedAt === "-" ? "missing" : formatDateTimeLabel(performanceGeneratedAt)}
            detail={performanceIsStale ? "stale vs signal file" : "settlement summary"}
            tone={!hasPerformanceReport || performanceIsStale ? "text-rose-300" : "text-emerald-300"}
          />
        </section>

        <SectionCard title="League P/L" subtitle="Diagnostic only while assist settlement is under review; do not use for promotion.">
          <LeagueLedger leagues={leagues} />
        </SectionCard>

        <section className="grid gap-5 xl:grid-cols-[minmax(0,1fr)_360px]">
          <SectionCard title="Assist Value Signals" subtitle="Goalscorer-style cards with fair odds, market odds, edge, set-piece role and settlement state.">
            {sourceIsStale ? (
              <EmptyState message="Assist candidate cards are hidden because the latest source odds/fixtures are stale. This lane will show candidates again only when fresh club assist odds are captured." />
            ) : visibleSignals.length === 0 ? (
              <EmptyState message="No assist shadow signals in the current artifact." />
            ) : (
              <div className="space-y-3">
                {visibleSignals.slice(0, 24).map((row, index) => (
                  <AssistSignalCard
                    key={`${row.player_name}-${row.home_team}-${row.away_team}-${row.kickoff_at}-${index}`}
                    row={row}
                    rank={index + 1}
                  />
                ))}
              </div>
            )}
          </SectionCard>

          <aside className="space-y-5">
            <SectionCard title="Settlement Source" subtitle="FotMob assist events only; Understat assist settlement is not wired.">
              <div className="space-y-3 text-sm text-slate-400">
                <div className="rounded-xl border border-slate-800/70 bg-slate-950/45 p-3">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">Current state</div>
                  <div className="mt-1 text-slate-200">
                    {settlementUnderReview
                      ? "Settlement is paused for model-risk review"
                      : performanceIsStale
                        ? "Performance report is stale; settlement workflow needs to refresh it"
                        : hasSettlementColumns
                          ? "CSV can hold settlement results"
                          : "Awaiting local settled artifact"}
                  </div>
                </div>
                <div className="rounded-xl border border-slate-800/70 bg-slate-950/45 p-3">
                  <div className="text-[10px] font-semibold uppercase tracking-[0.18em] text-slate-600">Performance report</div>
                  <pre className="mt-2 max-h-56 overflow-auto whitespace-pre-wrap text-xs leading-5 text-slate-400">
                    {performanceReport || "No performance report found locally yet. Ledger above is computed directly from the signal CSV."}
                  </pre>
                </div>
              </div>
            </SectionCard>

            <SectionCard title="Shadow Report" subtitle="Pipeline guardrails and source-match quality.">
              <div className="grid gap-2">
                <StatCard compact label="Shadow status" value={reportValue(shadowReport, "shadow_status")} />
                <StatCard compact label="Public status" value={publicStatus} />
                <StatCard compact label="Model status" value={reportValue(shadowReport, "model_status")} />
                <StatCard compact label="Fair odds" value={reportValue(shadowReport, "fair_odds_status")} />
              </div>
            </SectionCard>

            <SectionCard title="Model Report" subtitle="Raw research report, kept collapsed for sanity." collapsible defaultOpen={false}>
              <pre className="max-h-[520px] overflow-auto whitespace-pre-wrap rounded-xl bg-black/25 p-3 text-xs leading-5 text-slate-400">
                {modelReport || "No assist model report found in hosted artifacts."}
              </pre>
            </SectionCard>
          </aside>
        </section>
      </div>
    </main>
  );
}
