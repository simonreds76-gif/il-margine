import Link from "next/link";
import { notFound } from "next/navigation";

import { readGoalscorerLiveFile } from "@/lib/goalscorer-live-files";

export const dynamic = "force-dynamic";

const GOALSCORER_PAGE_PUBLIC =
  process.env.NODE_ENV !== "production" ||
  process.env.GOALSCORER_PAGE_PUBLIC === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_GOALSCORER_PAGE === "1";

type LeagueKey = "serie-a" | "epl" | "la-liga" | "bundesliga" | "ligue-1";

type CsvRow = Record<string, string>;

type ShadowRow = {
  leagueKey: LeagueKey;
  leagueLabel: string;
  leagueShort: string;
  competition: string;
  date: string;
  kickoff: string;
  match: string;
  player: string;
  team: string;
  opponent: string;
  signalType: string;
  finishingLuck: number;
  fixtureSwing: number;
  penaltyTransfer: boolean;
  penaltyTransferFrom: string;
  positionUpgrade: boolean;
  lineupState: string;
  modelProb: number;
  fairOdds: number;
  bestBookmaker: string;
  bestOdds: number;
  ev: number;
  confidence: string;
  comparedAt: string;
  settled: boolean;
  goalsScored: number;
  betOutcome: string;
  settledAt: string;
  pnlUnits: number;
};

type LeagueSource = {
  key: LeagueKey;
  label: string;
  short: string;
  file: string;
  badgeClass: string;
};

const LEAGUE_SOURCES: LeagueSource[] = [
  {
    key: "serie-a",
    label: "Serie A",
    short: "ITA",
    file: "data/goalscorer/goalscorer-shadow-signals.csv",
    badgeClass: "border-emerald-500/30 bg-emerald-500/12 text-emerald-300",
  },
  {
    key: "epl",
    label: "Premier League",
    short: "ENG",
    file: "data/goalscorer/epl-shadow-signals.csv",
    badgeClass: "border-indigo-500/30 bg-indigo-500/12 text-indigo-200",
  },
  {
    key: "la-liga",
    label: "La Liga",
    short: "ESP",
    file: "data/goalscorer/la-liga-shadow-signals.csv",
    badgeClass: "border-amber-500/30 bg-amber-500/12 text-amber-200",
  },
  {
    key: "bundesliga",
    label: "Bundesliga",
    short: "GER",
    file: "data/goalscorer/bundesliga-shadow-signals.csv",
    badgeClass: "border-rose-500/30 bg-rose-500/12 text-rose-200",
  },
  {
    key: "ligue-1",
    label: "Ligue 1",
    short: "FRA",
    file: "data/goalscorer/ligue-1-shadow-signals.csv",
    badgeClass: "border-cyan-500/30 bg-cyan-500/12 text-cyan-200",
  },
];

const HOW_STEPS = [
  "Model filters focus on selective scoring spots, not every raw probability edge.",
  "Confirmed lineups rerun the board around real starters and suppress bench noise.",
  "Penalty transfers and positional upgrades add conviction when the market is slow to react.",
];

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let current = "";
  let inQuotes = false;

  for (let idx = 0; idx < line.length; idx += 1) {
    const ch = line[idx];
    if (ch === '"') {
      if (inQuotes && line[idx + 1] === '"') {
        current += '"';
        idx += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      out.push(current);
      current = "";
      continue;
    }
    current += ch;
  }

  out.push(current);
  return out;
}

function parseCsv(text: string): CsvRow[] {
  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean);

  if (!lines.length) return [];

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

function parseNumber(value?: string): number {
  const n = Number.parseFloat(value ?? "");
  return Number.isFinite(n) ? n : 0;
}

function parseBoolean(value?: string): boolean {
  const text = (value ?? "").trim().toLowerCase();
  return text === "1" || text === "true" || text === "yes" || text === "settled" || text === "won";
}

function parseShadowRow(row: CsvRow, league: LeagueSource): ShadowRow {
  return {
    leagueKey: league.key,
    leagueLabel: league.label,
    leagueShort: league.short,
    competition: row.competition || league.label,
    date: row.date || "",
    kickoff: row.kickoff || "",
    match: row.match || "",
    player: row.player || "",
    team: row.team || "",
    opponent: row.opponent || "",
    signalType: row.signal_type || "",
    finishingLuck: parseNumber(row.finishing_luck),
    fixtureSwing: parseNumber(row.fixture_swing),
    penaltyTransfer: parseBoolean(row.penalty_transfer),
    penaltyTransferFrom: row.penalty_transfer_from || "",
    positionUpgrade: parseBoolean(row.position_upgrade),
    lineupState: row.lineup_state || "",
    modelProb: parseNumber(row.model_p_atgs),
    fairOdds: parseNumber(row.model_fair_odds),
    bestBookmaker: row.best_bookmaker || "",
    bestOdds: parseNumber(row.best_bookmaker_odds),
    ev: parseNumber(row.ev),
    confidence: row.confidence || "",
    comparedAt: row.compared_at || "",
    settled: parseBoolean(row.settled),
    goalsScored: parseNumber(row.goals_scored),
    betOutcome: row.bet_outcome || "",
    settledAt: row.settled_at || "",
    pnlUnits: parseNumber(row.pnl_units),
  };
}

async function loadShadowRows(): Promise<ShadowRow[]> {
  const loaded = await Promise.all(
    LEAGUE_SOURCES.map(async (league) => {
      const text = await readGoalscorerLiveFile(league.file);
      if (!text) return [] as ShadowRow[];
      return parseCsv(text).map((row) => parseShadowRow(row, league));
    }),
  );

  return loaded.flat();
}

function getPendingSignals(rows: ShadowRow[]): ShadowRow[] {
  return rows
    .filter((row) => row.confidence.toLowerCase() === "high")
    .filter((row) => !row.settled)
    .sort((left, right) => {
      const leftKickoff = Date.parse(left.kickoff || left.date);
      const rightKickoff = Date.parse(right.kickoff || right.date);
      if (Number.isFinite(leftKickoff) && Number.isFinite(rightKickoff) && leftKickoff !== rightKickoff) {
        return leftKickoff - rightKickoff;
      }
      return right.ev - left.ev;
    });
}

function getSettledSignals(rows: ShadowRow[]): ShadowRow[] {
  return rows
    .filter((row) => row.settled)
    .sort((left, right) => {
      const leftTime = Date.parse(left.settledAt || left.kickoff || left.date);
      const rightTime = Date.parse(right.settledAt || right.kickoff || right.date);
      return rightTime - leftTime;
    });
}

function formatPct(value: number, digits = 1): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

function formatUnits(value: number): string {
  return `${value >= 0 ? "+" : ""}${value.toFixed(2)}u`;
}

function formatOdds(value: number): string {
  return value > 0 ? value.toFixed(2) : "n/a";
}

function formatLeagueTime(value: string): string {
  const stamp = Date.parse(value);
  if (!Number.isFinite(stamp)) return value || "TBC";

  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(stamp));
}

function formatResultDate(value: string): string {
  const stamp = Date.parse(value);
  if (!Number.isFinite(stamp)) return value || "";
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: "short",
  }).format(new Date(stamp));
}

function slugifyAnchor(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-zA-Z0-9]+/g, "-")
    .replace(/^-+|-+$/g, "")
    .toLowerCase();
}

function getPenaltyTakersHref(row: ShadowRow): string {
  return `/penalty-takers#${row.leagueKey}-${slugifyAnchor(row.team)}`;
}

function getShadowMetrics(settledRows: ShadowRow[]) {
  const settledCount = settledRows.length;
  const wins = settledRows.filter((row) => row.betOutcome.toLowerCase() === "won").length;
  const pnlUnits = settledRows.reduce((sum, row) => sum + row.pnlUnits, 0);
  const avgOdds =
    settledCount > 0 ? settledRows.reduce((sum, row) => sum + row.bestOdds, 0) / settledCount : 0;

  return {
    settledCount,
    wins,
    pnlUnits,
    winRate: settledCount > 0 ? (wins / settledCount) * 100 : 0,
    roi: settledCount > 0 ? (pnlUnits / settledCount) * 100 : 0,
    avgOdds,
  };
}

function getSignalStrip(row: ShadowRow): string {
  const flags =
    (row.signalType === "stacked" || row.signalType === "both" ? 1 : 0) +
    (row.penaltyTransfer ? 1 : 0) +
    (row.positionUpgrade ? 1 : 0);

  if (flags >= 3) return "Multi-signal";
  if (row.penaltyTransfer) return "Penalty transfer";
  if (row.positionUpgrade) return "Position upgrade";
  return "High conviction";
}

function getWhyText(row: ShadowRow): string {
  const fragments: string[] = [];

  fragments.push(`Finishing luck ${row.finishingLuck.toFixed(2)}`);

  if (row.fixtureSwing > 0) {
    fragments.push(`fixture swing ${row.fixtureSwing.toFixed(2)}x`);
  }

  if (row.penaltyTransfer && row.penaltyTransferFrom) {
    fragments.push(`penalty duty inherited from ${row.penaltyTransferFrom}`);
  }

  if (row.positionUpgrade) {
    fragments.push("confirmed positional upgrade");
  }

  fragments.push(`model fair ${formatOdds(row.fairOdds)}`);

  return `${fragments.join(" / ")}.`;
}

function getLeagueBadgeClass(leagueKey: LeagueKey): string {
  return (
    LEAGUE_SOURCES.find((league) => league.key === leagueKey)?.badgeClass ??
    "border-slate-700 bg-slate-900 text-slate-300"
  );
}

function getPnlClass(value: number): string {
  return value >= 0 ? "text-emerald-300" : "text-rose-300";
}

function getStripClass(strip: string): string {
  if (strip === "Multi-signal") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (strip === "Penalty transfer") return "border-amber-500/30 bg-amber-500/10 text-amber-200";
  if (strip === "Position upgrade") return "border-sky-500/30 bg-sky-500/10 text-sky-200";
  return "border-slate-700/70 bg-slate-900/80 text-slate-200";
}

function getLondonNow() {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).formatToParts(new Date());

  const lookup = Object.fromEntries(parts.map((part) => [part.type, part.value]));
  const hour = Number.parseInt(lookup.hour ?? "0", 10);
  const minute = Number.parseInt(lookup.minute ?? "0", 10);
  return { hour, minute };
}

function getNextScanText(): string {
  const { hour, minute } = getLondonNow();
  const minutesOfDay = hour * 60 + minute;
  const windowStart = 12 * 60;
  const windowEnd = 23 * 60 + 30;

  let diff = 0;
  if (minutesOfDay < windowStart) {
    diff = windowStart - minutesOfDay;
  } else if (minutesOfDay > windowEnd) {
    diff = 24 * 60 - minutesOfDay + windowStart;
  } else {
    const nextSlot = Math.floor(minutesOfDay / 30) * 30 + 30;
    diff = nextSlot - minutesOfDay;
  }

  if (diff < 60) return `${diff} min`;
  const hours = Math.floor(diff / 60);
  const mins = diff % 60;
  return mins === 0 ? `${hours}h` : `${hours}h ${mins}m`;
}

function getLeagueSummaries(rows: ShadowRow[]) {
  return LEAGUE_SOURCES.map((league) => {
    const leagueRows = rows.filter((row) => row.leagueKey === league.key);
    const pending = leagueRows.filter((row) => !row.settled).length;
    const settled = leagueRows.filter((row) => row.settled).length;
    return {
      ...league,
      pending,
      settled,
      total: leagueRows.length,
    };
  });
}

function getThisMatchweekLabel(rows: ShadowRow[]): string {
  const stamps = rows
    .map((row) => Date.parse(row.kickoff || row.date))
    .filter((value) => Number.isFinite(value))
    .sort((left, right) => left - right);

  if (!stamps.length) {
    return new Intl.DateTimeFormat("en-GB", {
      timeZone: "Europe/London",
      day: "numeric",
      month: "short",
    }).format(new Date());
  }

  const first = new Date(stamps[0]);
  const last = new Date(stamps[stamps.length - 1]);
  const start = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: "short",
  }).format(first);
  const end = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: "short",
  }).format(last);

  return start === end ? start : `${start} - ${end}`;
}

function getCardReason(row: ShadowRow): string {
  if (row.penaltyTransfer && row.positionUpgrade) {
    return "Penalty transfer and positional upgrade both stack on this confirmed starter.";
  }
  if (row.penaltyTransfer) {
    return `Penalty duty may shift from ${row.penaltyTransferFrom || "the primary taker"} after lineup confirmation.`;
  }
  if (row.positionUpgrade) {
    return "Confirmed lineup shows a more advanced role than the player's recent baseline.";
  }
  return "Finishing luck and fixture swing aligned strongly enough to clear the high-confidence shadow filter.";
}

export default async function AnytimeGoalscorerPage() {
  if (!GOALSCORER_PAGE_PUBLIC) {
    notFound();
  }

  const allRows = await loadShadowRows();
  const pendingSignals = getPendingSignals(allRows);
  const settledSignals = getSettledSignals(allRows);
  const metrics = getShadowMetrics(settledSignals);
  const nextScan = getNextScanText();
  const showRealStats = metrics.settledCount >= 15;
  const showRecentResults = metrics.settledCount >= 5;
  const leagueSummaries = getLeagueSummaries(allRows);
  const thisMatchweekLabel = getThisMatchweekLabel(pendingSignals.length ? pendingSignals : allRows);

  return (
    <div className="min-h-screen overflow-hidden bg-[#0b0d10] text-neutral-200">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-x-0 top-0 h-80 bg-[radial-gradient(circle_at_top,rgba(16,185,129,0.16),transparent_55%)]" />
        <div className="absolute right-0 top-20 h-64 w-64 rounded-full bg-emerald-500/5 blur-3xl" />
        <div className="absolute left-0 top-56 h-64 w-64 rounded-full bg-sky-500/5 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-5xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="mb-12">
          <div className="mb-5 flex flex-wrap items-center gap-3">
            <div className="flex items-center gap-2 text-[11px] uppercase tracking-[0.28em] text-emerald-400">
              <span className="h-2 w-2 rounded-full bg-emerald-400 shadow-[0_0_18px_rgba(16,185,129,0.8)]" />
              <span>Live signals</span>
            </div>
            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-neutral-400">
              Private preview
            </span>
          </div>

          <div className="mb-4 flex items-center gap-2 text-sm text-neutral-500">
            <Link href="/" className="transition-colors hover:text-neutral-300">
              Home
            </Link>
            <span>/</span>
            <span className="text-neutral-300">Goalscorer Value Picks</span>
          </div>

          <h1 className="mb-3 text-3xl font-semibold tracking-tight text-white sm:text-[2.35rem]">
            Goalscorer value picks
          </h1>
          <p className="max-w-3xl text-sm leading-7 text-neutral-400 sm:text-base">
            Selective anytime-goalscorer signals across Serie A, Premier League, La Liga, Bundesliga and Ligue 1. This is the
            future public-facing picks surface, but it stays in preview mode until the shadow tracker has enough settled
            evidence behind it. For team-by-team spot-kick order, use the{" "}
            <Link href="/penalty-takers" className="text-emerald-300 transition-colors hover:text-emerald-200">
              penalty takers reference
            </Link>
            .
          </p>

          <div className="mt-5 flex flex-wrap gap-2">
            {leagueSummaries.map((league) => (
              <span
                key={league.key}
                className={`inline-flex items-center gap-2 rounded-full border px-3 py-1.5 text-[10px] font-semibold tracking-[0.16em] ${league.badgeClass}`}
              >
                <span>{league.label.toUpperCase()}</span>
                <span className="text-[9px] opacity-75">{league.pending} live</span>
              </span>
            ))}
          </div>
        </div>

        <div className="mb-10 grid gap-3 sm:grid-cols-2 xl:grid-cols-4">
          {showRealStats ? (
            <>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">Season record</div>
                <div className="mt-2 text-2xl font-semibold text-emerald-300">{formatPct(metrics.roi, 1)}</div>
                <div className="mt-1 text-xs text-neutral-500">ROI</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">Settled</div>
                <div className="mt-2 text-2xl font-semibold text-white">{metrics.settledCount}</div>
                <div className="mt-1 text-xs text-neutral-500">picks</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">Win rate</div>
                <div className="mt-2 text-2xl font-semibold text-white">{metrics.winRate.toFixed(1)}%</div>
                <div className="mt-1 text-xs text-neutral-500">
                  {metrics.wins}/{metrics.settledCount} winners
                </div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">P/L</div>
                <div className={`mt-2 text-2xl font-semibold ${getPnlClass(metrics.pnlUnits)}`}>
                  {formatUnits(metrics.pnlUnits)}
                </div>
                <div className="mt-1 text-xs text-neutral-500">avg odds {formatOdds(metrics.avgOdds)}</div>
              </div>
            </>
          ) : (
            <>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">Status</div>
                <div className="mt-2 text-xl font-semibold text-emerald-300">Shadow tracking live</div>
                <div className="mt-1 text-xs text-neutral-500">real record appears after 15 settled picks</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">Coverage</div>
                <div className="mt-2 text-xl font-semibold text-white">{LEAGUE_SOURCES.length} leagues</div>
                <div className="mt-1 text-xs text-neutral-500">Serie A, EPL, La Liga, Bundesliga, Ligue 1</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">Pricing mode</div>
                <div className="mt-2 text-xl font-semibold text-white">Confirmed XI rerun</div>
                <div className="mt-1 text-xs text-neutral-500">starters only, non-starters suppressed</div>
              </div>
              <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
                <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">Next scan</div>
                <div className="mt-2 text-xl font-semibold text-white">{nextScan}</div>
                <div className="mt-1 text-xs text-neutral-500">automated live polling window</div>
              </div>
            </>
          )}
        </div>

        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-neutral-300">This matchweek</h2>
            <p className="mt-1 text-sm text-neutral-500">
              Only unsettled high-confidence shadow signals appear here. The broader analyst board stays private.
            </p>
          </div>
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-neutral-400">
            {thisMatchweekLabel} / {pendingSignals.length} live qualifier{pendingSignals.length === 1 ? "" : "s"}
          </span>
        </div>

        <div className="space-y-4">
          {pendingSignals.length === 0 ? (
            <div className="overflow-hidden rounded-[28px] border border-white/10 bg-[#121417]">
              <div className="border-b border-white/10 px-5 py-4">
                <span className="inline-flex rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-[11px] font-medium text-emerald-300">
                  Tracking live
                </span>
              </div>

              <div className="grid gap-6 px-5 py-6 lg:grid-cols-[1.2fr,0.8fr]">
                <div>
                  <h3 className="text-xl font-semibold text-white">No qualified live picks right now</h3>
                  <p className="mt-3 max-w-2xl text-sm leading-7 text-neutral-400">
                    That is normal. This page only shows high-confidence shadow signals once confirmed lineups,
                    finishing-luck filters, fixture swing and bookmaker value all line up together.
                  </p>
                  <p className="mt-3 text-sm leading-7 text-neutral-500">
                    We are collecting the paper trail quietly first. When the sample is ready, this preview can switch
                    straight into a public-facing feed without changing the product shape.
                  </p>
                </div>

                <div className="grid gap-3 sm:grid-cols-2 lg:grid-cols-1">
                  {leagueSummaries.map((league) => (
                    <div
                      key={league.key}
                      className="rounded-2xl border border-white/10 bg-white/[0.03] px-4 py-3"
                    >
                      <div className="flex items-center justify-between gap-3">
                        <span
                          className={`inline-flex rounded-md border px-2.5 py-1 text-[10px] font-semibold tracking-[0.16em] ${league.badgeClass}`}
                        >
                          {league.short}
                        </span>
                        <span className="text-[11px] uppercase tracking-[0.16em] text-neutral-500">
                          {league.pending} live / {league.settled} settled
                        </span>
                      </div>
                      <div className="mt-3 text-sm font-medium text-white">{league.label}</div>
                      <div className="mt-1 text-xs text-neutral-500">
                        {league.total > 0
                          ? "Shadow tracker already has data in this league."
                          : "Monitoring is armed and waiting for the first qualified signal."}
                      </div>
                    </div>
                  ))}
                </div>
              </div>
            </div>
          ) : (
            pendingSignals.map((row) => {
              const strip = getSignalStrip(row);
              return (
                <article
                  key={`${row.leagueKey}-${row.date}-${row.player}-${row.match}`}
                  className="overflow-hidden rounded-[28px] border border-white/10 bg-[#121417] shadow-[0_12px_40px_rgba(0,0,0,0.25)]"
                >
                  <div className="border-b border-white/10 px-5 py-3">
                    <span className={`inline-flex rounded-full border px-3 py-1 text-[11px] font-medium ${getStripClass(strip)}`}>
                      {strip}
                    </span>
                  </div>

                  <div className="border-b border-white/10 px-5 py-5">
                    <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                      <div>
                        <div className="mb-3 flex flex-wrap items-center gap-2">
                          <span
                            className={`inline-flex rounded-md border px-2.5 py-1 text-[10px] font-semibold tracking-[0.16em] ${getLeagueBadgeClass(row.leagueKey)}`}
                          >
                            {row.leagueLabel.toUpperCase()}
                          </span>
                          <span className="inline-flex rounded-md border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold tracking-[0.16em] text-emerald-300">
                            CONFIRMED XI
                          </span>
                          {row.penaltyTransfer ? (
                            <span className="inline-flex rounded-md border border-amber-500/25 bg-amber-500/10 px-2.5 py-1 text-[10px] font-semibold tracking-[0.16em] text-amber-200">
                              PEN TRANSFER
                            </span>
                          ) : null}
                          {row.positionUpgrade ? (
                            <span className="inline-flex rounded-md border border-sky-500/25 bg-sky-500/10 px-2.5 py-1 text-[10px] font-semibold tracking-[0.16em] text-sky-200">
                              POS UPGRADE
                            </span>
                          ) : null}
                        </div>

                        <h3 className="text-2xl font-semibold tracking-tight text-white">
                          {row.player} <span className="text-lg font-normal text-neutral-400">to score</span>
                        </h3>
                        <p className="mt-2 text-sm text-neutral-400">
                          {row.match} / {formatLeagueTime(row.kickoff)}
                        </p>
                        <Link
                          href={getPenaltyTakersHref(row)}
                          className="mt-2 inline-flex text-xs text-emerald-300 transition-colors hover:text-emerald-200"
                        >
                          View {row.team} penalty order
                        </Link>
                      </div>

                      <div className="shrink-0 text-left lg:text-right">
                        <div className="text-3xl font-semibold text-emerald-300">{formatOdds(row.bestOdds)}</div>
                        <div className="mt-1 text-xs uppercase tracking-[0.18em] text-neutral-500">
                          best @ {row.bestBookmaker || "market"}
                        </div>
                      </div>
                    </div>
                  </div>

                  <div className="grid gap-5 bg-[#171a1f] px-5 py-5 lg:grid-cols-[1.4fr,0.8fr]">
                    <div>
                      <div className="mb-2 text-[11px] uppercase tracking-[0.22em] text-neutral-500">Why this pick</div>
                      <p className="text-sm leading-7 text-neutral-300">{getWhyText(row)}</p>
                      <p className="mt-2 text-xs leading-6 text-neutral-500">{getCardReason(row)}</p>
                    </div>

                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-2">
                      <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-center">
                        <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">EV</div>
                        <div className="mt-2 text-lg font-semibold text-emerald-300">{formatPct(row.ev * 100, 0)}</div>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-center">
                        <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Luck</div>
                        <div className="mt-2 text-lg font-semibold text-amber-200">{row.finishingLuck.toFixed(2)}</div>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-center">
                        <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Swing</div>
                        <div className="mt-2 text-lg font-semibold text-white">{row.fixtureSwing.toFixed(2)}</div>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-center">
                        <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Fair</div>
                        <div className="mt-2 text-lg font-semibold text-white">{formatOdds(row.fairOdds)}</div>
                      </div>
                    </div>
                  </div>
                </article>
              );
            })
          )}
        </div>

        {showRecentResults ? (
          <section className="mt-12">
            <div className="mb-4 flex items-center justify-between gap-4">
              <div>
                <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-neutral-300">Recent results</h2>
                <p className="mt-1 text-sm text-neutral-500">Last 10 settled shadow picks</p>
              </div>
            </div>

            <div className="overflow-hidden rounded-[28px] border border-white/10">
              {settledSignals.slice(0, 10).map((row, index) => (
                <div
                  key={`${row.leagueKey}-${row.date}-${row.player}-${row.match}-settled`}
                  className={`flex flex-wrap items-center gap-3 px-5 py-4 ${index % 2 === 0 ? "bg-[#121417]" : "bg-[#171a1f]"}`}
                >
                  <span className={`h-2.5 w-2.5 rounded-full ${row.betOutcome === "won" ? "bg-emerald-400" : "bg-rose-400"}`} />
                  <span className="w-16 text-sm text-neutral-500">{formatResultDate(row.date)}</span>
                  <span
                    className={`inline-flex rounded-md border px-2 py-0.5 text-[10px] font-semibold tracking-[0.16em] ${getLeagueBadgeClass(row.leagueKey)}`}
                  >
                    {row.leagueShort}
                  </span>
                  <span className="min-w-[160px] flex-1 text-sm text-neutral-200">
                    {row.player} vs {row.opponent}
                  </span>
                  <span className="text-sm text-neutral-500">@ {formatOdds(row.bestOdds)}</span>
                  <span className={`ml-auto text-sm font-semibold ${getPnlClass(row.pnlUnits)}`}>
                    {formatUnits(row.pnlUnits)}
                  </span>
                </div>
              ))}
            </div>
          </section>
        ) : null}

        <section className="mt-12 rounded-[28px] border border-white/10 bg-[#121417] p-6">
          <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-neutral-300">How it works</h2>
          <div className="mt-6 grid gap-5 md:grid-cols-3">
            {HOW_STEPS.map((step, index) => (
              <div key={step}>
                <div className="text-2xl font-semibold text-white/90">0{index + 1}</div>
                <p className="mt-3 text-sm leading-7 text-neutral-400">{step}</p>
              </div>
            ))}
          </div>
        </section>

        <div className="mt-8 rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-4 text-center text-sm text-neutral-500 backdrop-blur">
          Signals update automatically with confirmed lineups. Next scan in {nextScan}.
        </div>
      </div>
    </div>
  );
}
