import Link from "next/link";

import {
  readGoalscorerLiveFile,
  readGoalscorerLiveSnapshotGeneratedAt,
} from "@/lib/goalscorer-live-files";

export const dynamic = "force-dynamic";


type LeagueKey = "serie-a" | "epl" | "la-liga" | "bundesliga" | "ligue-1";
type CsvRow = Record<string, string>;

type PublicRow = {
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
  bestBookmaker: string;
  bestOdds: number;
  fairOdds: number;
  ev: number;
  lineupState: string;
  comparedAt: string;
  settled: boolean;
  betOutcome: string;
  settledAt: string;
  pnlUnits: number;
  stakeUnits: number;
  stakeBand: string;
  stakeLabel: string;
  penaltyDependent: boolean;
  penaltyTransfer: boolean;
  positionUpgrade: boolean;
};

type LeagueSource = {
  key: LeagueKey;
  label: string;
  short: string;
  file: string;
  logoPath: string;
  badgeClass: string;
};

const LEAGUE_SOURCES: LeagueSource[] = [
  {
    key: "serie-a",
    label: "Serie A",
    short: "ITA",
    file: "data/goalscorer/goalscorer-public-signals.csv",
    logoPath: "/league-logos/serie-a.png",
    badgeClass: "border-emerald-500/30 bg-emerald-500/12 text-emerald-300",
  },
  {
    key: "epl",
    label: "Premier League",
    short: "ENG",
    file: "data/goalscorer/epl-public-signals.csv",
    logoPath: "/league-logos/epl.png",
    badgeClass: "border-indigo-500/30 bg-indigo-500/12 text-indigo-200",
  },
  {
    key: "la-liga",
    label: "La Liga",
    short: "ESP",
    file: "data/goalscorer/la-liga-public-signals.csv",
    logoPath: "/league-logos/la-liga.png",
    badgeClass: "border-amber-500/30 bg-amber-500/12 text-amber-200",
  },
  {
    key: "bundesliga",
    label: "Bundesliga",
    short: "GER",
    file: "data/goalscorer/bundesliga-public-signals.csv",
    logoPath: "/league-logos/bundesliga.png",
    badgeClass: "border-rose-500/30 bg-rose-500/12 text-rose-200",
  },
  {
    key: "ligue-1",
    label: "Ligue 1",
    short: "FRA",
    file: "data/goalscorer/ligue-1-public-signals.csv",
    logoPath: "/league-logos/ligue-1.png",
    badgeClass: "border-cyan-500/30 bg-cyan-500/12 text-cyan-200",
  },
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

function parsePublicRow(row: CsvRow, league: LeagueSource): PublicRow {
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
    bestBookmaker: row.best_bookmaker || "",
    bestOdds: parseNumber(row.best_bookmaker_odds),
    fairOdds: parseNumber(row.model_fair_odds),
    ev: parseNumber(row.ev),
    lineupState: row.lineup_state || "",
    comparedAt: row.compared_at || "",
    settled: parseBoolean(row.settled),
    betOutcome: row.bet_outcome || "",
    settledAt: row.settled_at || "",
    pnlUnits: parseNumber(row.pnl_units),
    stakeUnits: parseNumber(row.recommended_stake_units) || 1,
    stakeBand: row.recommended_stake_band || "",
    stakeLabel: row.recommended_stake_label || "",
    penaltyDependent: parseBoolean(row.penalty_dependent),
    penaltyTransfer: parseBoolean(row.penalty_transfer),
    positionUpgrade: parseBoolean(row.position_upgrade),
  };
}

async function loadPublicRows(): Promise<PublicRow[]> {
  const loaded = await Promise.all(
    LEAGUE_SOURCES.map(async (league) => {
      const text = await readGoalscorerLiveFile(league.file);
      if (!text) return [] as PublicRow[];
      return parseCsv(text).map((row) => parsePublicRow(row, league));
    }),
  );

  return loaded.flat();
}

function getLiveSignals(rows: PublicRow[]): PublicRow[] {
  return rows
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

function getSettledPublished(rows: PublicRow[]): PublicRow[] {
  return rows
    .filter((row) => row.settled && row.betOutcome.toLowerCase() !== "void")
    .sort((left, right) => {
      const leftTime = Date.parse(left.settledAt || left.kickoff || left.date);
      const rightTime = Date.parse(right.settledAt || right.kickoff || right.date);
      return rightTime - leftTime;
    });
}

function getMetrics(rows: PublicRow[]) {
  const settledCount = rows.length;
  const wins = rows.filter((row) => row.betOutcome.toLowerCase() === "won").length;
  const losses = rows.filter((row) => row.betOutcome.toLowerCase() === "lost").length;
  const stakedUnits = rows.reduce((sum, row) => sum + (row.stakeUnits > 0 ? row.stakeUnits : 1), 0);
  const pnlUnits = rows.reduce((sum, row) => sum + row.pnlUnits, 0);

  return {
    settledCount,
    wins,
    losses,
    stakedUnits,
    pnlUnits,
    roi: stakedUnits > 0 ? (pnlUnits / stakedUnits) * 100 : 0,
    winRate: settledCount > 0 ? (wins / settledCount) * 100 : 0,
  };
}

function getLeagueSummaries(rows: PublicRow[]) {
  return LEAGUE_SOURCES.map((league) => {
    const leagueRows = rows.filter((row) => row.leagueKey === league.key);
    const live = leagueRows.filter((row) => !row.settled).length;
    const settled = leagueRows.filter((row) => row.settled && row.betOutcome.toLowerCase() !== "void").length;
    return {
      ...league,
      live,
      settled,
      total: leagueRows.length,
    };
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

function formatDateTime(value: string | null): string {
  if (!value) return "n/a";
  const stamp = Date.parse(value);
  if (!Number.isFinite(stamp)) return value;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    dateStyle: "medium",
    timeStyle: "short",
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

function getPenaltyTakersHref(row: PublicRow): string {
  return `/penalty-takers#${row.leagueKey}-${slugifyAnchor(row.team)}`;
}

function getPnlClass(value: number): string {
  return value >= 0 ? "text-emerald-300" : "text-rose-300";
}

function getLeagueBadgeClass(leagueKey: LeagueKey): string {
  return (
    LEAGUE_SOURCES.find((league) => league.key === leagueKey)?.badgeClass ??
    "border-slate-700 bg-slate-900 text-slate-300"
  );
}

function getLeagueSource(leagueKey: LeagueKey): LeagueSource | undefined {
  return LEAGUE_SOURCES.find((league) => league.key === leagueKey);
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

function getStakeTone(row: PublicRow): string {
  if (row.stakeBand === "core") return "border-emerald-500/25 bg-emerald-500/10 text-emerald-300";
  if (row.stakeBand === "standard") return "border-cyan-500/25 bg-cyan-500/10 text-cyan-200";
  return "border-amber-500/25 bg-amber-500/10 text-amber-200";
}

function LeagueLogo({
  league,
  variant = "chip",
}: {
  league: LeagueSource;
  variant?: "chip" | "card" | "row";
}) {
  const wrapperClass =
    variant === "card"
      ? "flex h-11 w-11 shrink-0 items-center justify-center overflow-hidden rounded-xl border border-slate-300/70 bg-gradient-to-b from-white to-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]"
      : variant === "row"
        ? "flex h-7 w-7 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-300/70 bg-gradient-to-b from-white to-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]"
        : "flex h-6 w-6 shrink-0 items-center justify-center overflow-hidden rounded-lg border border-slate-300/70 bg-gradient-to-b from-white to-slate-100 shadow-[inset_0_1px_0_rgba(255,255,255,0.7)]";
  const imageClass =
    variant === "card"
      ? "h-7 w-7 object-contain"
      : variant === "row"
        ? "h-4.5 w-4.5 object-contain"
        : "h-4 w-4 object-contain";

  return (
    <span className={wrapperClass}>
      <img
        src={league.logoPath}
        alt={`${league.label} logo`}
        className={imageClass}
        loading="lazy"
      />
    </span>
  );
}

export default async function AnytimeGoalscorerPage() {
  const [allRows, snapshotGeneratedAt] = await Promise.all([
    loadPublicRows(),
    readGoalscorerLiveSnapshotGeneratedAt(),
  ]);
  const liveSignals = getLiveSignals(allRows);
  const settledSignals = getSettledPublished(allRows);
  const metrics = getMetrics(settledSignals);
  const leagueSummaries = getLeagueSummaries(allRows);
  const nextScan = getNextScanText();
  const showMetrics = settledSignals.length >= 5;

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
              <span>Beta</span>
            </div>
            <span className="rounded-full border border-white/10 bg-white/5 px-2.5 py-1 text-[10px] uppercase tracking-[0.18em] text-neutral-400">
              Confirmed lineups only
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
            Anytime goalscorer picks
          </h1>
          <p className="max-w-3xl text-sm leading-7 text-neutral-400 sm:text-base">
            Published only when the lineup is confirmed, the role is right, the price is disciplined, and the edge is
            worth staking. For team-by-team spot-kick order, use the{" "}
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
                <LeagueLogo league={league} variant="chip" />
                <span>{league.label.toUpperCase()}</span>
                {league.live > 0 ? <span className="text-[9px] opacity-75">{league.live} live</span> : null}
              </span>
            ))}
          </div>
        </div>

        {showMetrics ? (
          <div className="mb-10 grid gap-3 sm:grid-cols-2 xl:grid-cols-5">
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
              <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">Live picks</div>
              <div className="mt-2 text-2xl font-semibold text-emerald-300">{liveSignals.length}</div>
              <div className="mt-1 text-xs text-neutral-500">current published qualifiers</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
              <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">Settled record</div>
              <div className="mt-2 text-2xl font-semibold text-white">{metrics.settledCount}</div>
              <div className="mt-1 text-xs text-neutral-500">published picks only</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
              <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">W / L</div>
              <div className="mt-2 text-2xl font-semibold text-white">
                {metrics.wins} / {metrics.losses}
              </div>
              <div className="mt-1 text-xs text-neutral-500">voids kept off the public record</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
              <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">ROI</div>
              <div className={`mt-2 text-2xl font-semibold ${getPnlClass(metrics.roi)}`}>{formatPct(metrics.roi, 1)}</div>
              <div className="mt-1 text-xs text-neutral-500">on {metrics.stakedUnits.toFixed(2)}u staked</div>
            </div>
            <div className="rounded-2xl border border-white/10 bg-white/[0.04] p-4 backdrop-blur">
              <div className="text-[11px] uppercase tracking-[0.22em] text-neutral-500">P/L</div>
              <div className={`mt-2 text-2xl font-semibold ${getPnlClass(metrics.pnlUnits)}`}>{formatUnits(metrics.pnlUnits)}</div>
              <div className="mt-1 text-xs text-neutral-500">updated {formatDateTime(snapshotGeneratedAt)}</div>
            </div>
          </div>
        ) : null}

        <div className="mb-4 flex items-center justify-between gap-4">
          <div>
            <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-neutral-300">Live picks</h2>
            <p className="mt-1 text-sm text-neutral-500">
              Once a pick is logged, the record stays append-only.
            </p>
          </div>
          <span className="rounded-full border border-white/10 bg-white/[0.04] px-3 py-1 text-xs text-neutral-400">
            Updates in {nextScan}
          </span>
        </div>

        <div className="space-y-4">
          {liveSignals.length === 0 ? (
            <div className="overflow-hidden rounded-[28px] border border-white/10 bg-[#121417]">
              <div className="border-b border-white/10 px-5 py-4">
                <span className="inline-flex rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-[11px] font-medium text-emerald-300">
                  No picks live right now
                </span>
              </div>

              <div className="px-5 py-6">
                <p className="max-w-3xl text-sm leading-7 text-neutral-400">
                  No picks are live right now. This page only publishes when a confirmed starter clears our full filter on
                  lineup, role, price band, and edge. When someone qualifies, the pick appears here automatically.
                </p>
              </div>
            </div>
          ) : (
            liveSignals.map((row) => (
              <article
                key={`${row.leagueKey}-${row.date}-${row.player}-${row.match}`}
                className="overflow-hidden rounded-[28px] border border-white/10 bg-[#121417] shadow-[0_12px_40px_rgba(0,0,0,0.25)]"
              >
                <div className="border-b border-white/10 px-5 py-3">
                  <div className="flex flex-col gap-3 sm:flex-row sm:items-center sm:justify-between">
                    <div className="flex items-center gap-3">
                      {getLeagueSource(row.leagueKey) ? <LeagueLogo league={getLeagueSource(row.leagueKey)!} variant="card" /> : null}
                      <div>
                        <div className="text-[11px] font-semibold uppercase tracking-[0.18em] text-neutral-400">{row.leagueLabel}</div>
                        <div className="mt-1 text-sm text-neutral-500">{row.match}</div>
                      </div>
                    </div>

                    <div className="flex flex-wrap items-center gap-2">
                      <span className="inline-flex rounded-md border border-emerald-500/25 bg-emerald-500/10 px-2.5 py-1 text-[10px] font-semibold tracking-[0.16em] text-emerald-300">
                        CONFIRMED STARTER
                      </span>
                      <span className={`inline-flex rounded-md border px-2.5 py-1 text-[10px] font-semibold tracking-[0.16em] ${getStakeTone(row)}`}>
                        {row.stakeLabel || `${row.stakeUnits.toFixed(2)}u`}
                      </span>
                    </div>
                  </div>
                  {row.penaltyDependent ? (
                    <div className="mt-3 text-xs text-amber-200">Includes penalty component</div>
                  ) : null}
                </div>

                <div className="border-b border-white/10 px-5 py-5">
                  <div className="flex flex-col gap-5 lg:flex-row lg:items-start lg:justify-between">
                    <div>
                      <h3 className="text-2xl font-semibold tracking-tight text-white">
                        {row.player} <span className="text-lg font-normal text-neutral-400">to score</span>
                      </h3>
                      <p className="mt-2 text-sm text-neutral-400">
                        {formatLeagueTime(row.kickoff)}
                      </p>
                      <div className="mt-3 flex flex-wrap gap-3 text-sm text-neutral-400">
                        <span>Book {formatOdds(row.bestOdds)} @ {row.bestBookmaker || "market"}</span>
                        <span>Fair {formatOdds(row.fairOdds)}</span>
                        <span className="text-emerald-300">EV {formatPct(row.ev * 100, 1)}</span>
                      </div>
                      <Link
                        href={getPenaltyTakersHref(row)}
                        className="mt-3 inline-flex text-xs text-emerald-300 transition-colors hover:text-emerald-200"
                      >
                        View {row.team} penalty order
                      </Link>
                    </div>

                    <div className="grid grid-cols-2 gap-3 sm:grid-cols-4 lg:grid-cols-2">
                      <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-center">
                        <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Stake</div>
                        <div className="mt-2 text-lg font-semibold text-white">{row.stakeUnits.toFixed(2)}u</div>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-center">
                        <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Odds</div>
                        <div className="mt-2 text-lg font-semibold text-emerald-300">{formatOdds(row.bestOdds)}</div>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-center">
                        <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Fair</div>
                        <div className="mt-2 text-lg font-semibold text-white">{formatOdds(row.fairOdds)}</div>
                      </div>
                      <div className="rounded-2xl border border-white/10 bg-black/20 p-3 text-center">
                        <div className="text-[10px] uppercase tracking-[0.18em] text-neutral-500">Edge</div>
                        <div className="mt-2 text-lg font-semibold text-emerald-300">{formatPct(row.ev * 100, 0)}</div>
                      </div>
                    </div>
                  </div>
                </div>
              </article>
            ))
          )}
        </div>

        <section className="mt-12">
          <div className="mb-4 flex items-center justify-between gap-4">
            <div>
              <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-neutral-300">Published record</h2>
              <p className="mt-1 text-sm text-neutral-500">
                Settled public picks only. Non-runners stay in the internal audit trail and are kept off the public record.
              </p>
            </div>
          </div>

          {settledSignals.length === 0 ? (
            <div className="rounded-[28px] border border-white/10 bg-[#121417] px-5 py-6 text-sm leading-7 text-neutral-400">
              No settled picks yet.
            </div>
          ) : (
            <div className="overflow-hidden rounded-[28px] border border-white/10">
              <div className="grid grid-cols-[80px,110px,1.8fr,120px,110px,90px,90px,100px] gap-3 bg-[#171a1f] px-5 py-3 text-[11px] uppercase tracking-[0.18em] text-neutral-500">
                <span>Date</span>
                <span>League</span>
                <span>Pick</span>
                <span>Odds / Fair</span>
                <span>Stake</span>
                <span>Result</span>
                <span>P/L</span>
                <span>Book</span>
              </div>
              {settledSignals.slice(0, 30).map((row, index) => (
                <div
                  key={`${row.leagueKey}-${row.date}-${row.player}-${row.match}-settled`}
                  className={`grid grid-cols-[80px,110px,1.8fr,120px,110px,90px,90px,100px] gap-3 px-5 py-4 text-sm ${index % 2 === 0 ? "bg-[#121417]" : "bg-[#171a1f]"}`}
                >
                  <span className="text-neutral-500">{formatResultDate(row.date)}</span>
                  <span className="flex items-center gap-2">
                    {getLeagueSource(row.leagueKey) ? <LeagueLogo league={getLeagueSource(row.leagueKey)!} variant="row" /> : null}
                    <span className={`inline-flex rounded-md border px-2 py-0.5 text-[10px] font-semibold tracking-[0.16em] ${getLeagueBadgeClass(row.leagueKey)}`}>
                      {row.leagueShort}
                    </span>
                  </span>
                  <span className="text-neutral-200">
                    <span className="font-medium text-white">{row.player}</span>
                    <span className="mt-1 block text-xs text-neutral-500">{row.match}</span>
                  </span>
                  <span className="text-neutral-300">{formatOdds(row.bestOdds)} / {formatOdds(row.fairOdds)}</span>
                  <span className="text-neutral-300">{row.stakeUnits.toFixed(2)}u</span>
                  <span className={row.betOutcome.toLowerCase() === "won" ? "text-emerald-300" : "text-rose-300"}>
                    {row.betOutcome.toUpperCase()}
                  </span>
                  <span className={getPnlClass(row.pnlUnits)}>{formatUnits(row.pnlUnits)}</span>
                  <span className="text-neutral-500">{row.bestBookmaker || "market"}</span>
                </div>
              ))}
            </div>
          )}
        </section>

        <section className="mt-12 rounded-[28px] border border-white/10 bg-[#121417] p-6">
          <h2 className="text-sm font-semibold uppercase tracking-[0.22em] text-neutral-300">Publication rules</h2>
          <div className="mt-6 grid gap-5 md:grid-cols-3">
            <div>
              <div className="text-2xl font-semibold text-white/90">01</div>
              <p className="mt-3 text-sm leading-7 text-neutral-400">
                Confirmed starters only, verified fixtures only, and attacking roles only. Expected-lineup rows and speculative defenders stay off this page.
              </p>
            </div>
            <div>
              <div className="text-2xl font-semibold text-white/90">02</div>
              <p className="mt-3 text-sm leading-7 text-neutral-400">
                Published prices must sit between 1.60 and 7.00, clear the +8% edge floor, and keep model fair odds at 6.00 or shorter.
              </p>
            </div>
            <div>
              <div className="text-2xl font-semibold text-white/90">03</div>
              <p className="mt-3 text-sm leading-7 text-neutral-400">
                Public staking is banded: 1.25u core, 1.00u standard, 0.50u extended. Penalty-dependent picks are automatically downgraded a band.
              </p>
            </div>
          </div>
        </section>

        <div className="mt-8 rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-4 text-center text-sm text-neutral-500 backdrop-blur">
          Beta preview. Signals update automatically once confirmed lineups land. Hosted snapshot last refreshed {formatDateTime(snapshotGeneratedAt)}.
        </div>
      </div>
    </div>
  );
}
