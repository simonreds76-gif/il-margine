import Link from "next/link";

import PublicGoalscorerBoard from "./PublicGoalscorerBoard";
import {
  LEAGUE_SOURCES,
  type PublicRow,
  getTodayIsoLondon,
} from "./shared";
import {
  readGoalscorerLiveFile,
  readGoalscorerLiveSnapshotGeneratedAt,
} from "@/lib/goalscorer-live-files";

export const dynamic = "force-dynamic";

type CsvRow = Record<string, string>;

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

function parsePublicRow(row: CsvRow, league: (typeof LEAGUE_SOURCES)[number]): PublicRow {
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
    modelProb: parseNumber(row.model_p_atgs),
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
    penaltyDependencyShare: parseNumber(row.penalty_dependency_share),
    position: row.position || row.position_group || "",
    finishingLuck: parseNumber(row.finishing_luck),
    fixtureSwing: parseNumber(row.fixture_swing),
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

export default async function AnytimeGoalscorerPage() {
  const [allRows, snapshotGeneratedAt] = await Promise.all([
    loadPublicRows(),
    readGoalscorerLiveSnapshotGeneratedAt(),
  ]);
  const todayIso = getTodayIsoLondon();

  return (
    <div className="min-h-screen overflow-hidden bg-[#0b0d10] text-neutral-200">
      <div className="pointer-events-none absolute inset-0">
        <div className="absolute inset-x-0 top-0 h-80 bg-[radial-gradient(circle_at_top,rgba(16,185,129,0.16),transparent_55%)]" />
        <div className="absolute right-0 top-20 h-64 w-64 rounded-full bg-emerald-500/5 blur-3xl" />
        <div className="absolute left-0 top-56 h-64 w-64 rounded-full bg-sky-500/5 blur-3xl" />
      </div>

      <div className="relative mx-auto max-w-6xl px-4 py-10 sm:px-6 lg:px-8">
        <div className="mb-10">
          <div className="mb-4 flex items-center gap-2 text-sm text-neutral-500">
            <Link href="/" className="transition-colors hover:text-neutral-300">
              Home
            </Link>
            <span>/</span>
            <span className="text-neutral-300">Anytime Goalscorer</span>
          </div>

          <h1 className="mb-3 text-3xl font-semibold tracking-tight text-white sm:text-[2.45rem]">
            Anytime goalscorer picks
          </h1>
          <p className="max-w-3xl text-sm leading-7 text-neutral-400 sm:text-base">
            Public picks only go live when the lineup is right, the role is strong, and the market price leaves real edge.
            For team-by-team spot-kick order, use the{" "}
            <Link href="/penalty-takers" className="text-emerald-300 transition-colors hover:text-emerald-200">
              penalty takers reference
            </Link>
            .
          </p>
        </div>

        <PublicGoalscorerBoard rows={allRows} snapshotGeneratedAt={snapshotGeneratedAt} todayIso={todayIso} />

        <div className="mt-8 rounded-2xl border border-white/10 bg-white/[0.04] px-5 py-4 text-center text-sm text-neutral-500 backdrop-blur">
          Testing preview. Public picks update from the latest confirmed-lineup pass and will later move onto admin-backed records.
        </div>
      </div>
    </div>
  );
}
