import { promises as fs } from "node:fs";
import Link from "next/link";

import PublicGoalscorerBoard from "./PublicGoalscorerBoard";
import {
  LEAGUE_SOURCES,
  type PublicRow,
  getTodayIsoLondon,
} from "./shared";
import {
  readGoalscorerHostedContent,
  readGoalscorerLiveSnapshotGeneratedAt,
} from "@/lib/goalscorer-live-files";
import { tryGetKnownProjectFilePath } from "@/lib/project-file-paths";

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
      const readLocalText = async (): Promise<string | null> => {
        try {
          const fullPath = tryGetKnownProjectFilePath(league.file);
          if (!fullPath) return null;
          return await fs.readFile(fullPath, "utf8");
        } catch {
          return null;
        }
      };

      // Read local (settled history) and hosted (current picks) independently.
      // We always merge both so that fresh hosted current picks are never dropped
      // just because the local file has a newer mtime from recently settled bets.
      const [localText, hostedText] = await Promise.all([
        readLocalText(),
        readGoalscorerHostedContent(league.file),
      ]);

      const merged = new Map<string, PublicRow>();
      const upsert = (row: PublicRow) => {
        const key = `${row.leagueKey}|${row.date}|${row.player}|${row.match}`;
        const existing = merged.get(key);
        if (!existing) {
          merged.set(key, row);
          return;
        }

        const currentSettled = row.settled;
        const existingSettled = existing.settled;
        if (currentSettled && !existingSettled) {
          merged.set(key, row);
          return;
        }
        if (!currentSettled && existingSettled) {
          return;
        }

        const currentTs = Date.parse(row.settledAt || row.comparedAt || row.kickoff || row.date);
        const existingTs = Date.parse(existing.settledAt || existing.comparedAt || existing.kickoff || existing.date);
        if (Number.isFinite(currentTs) && Number.isFinite(existingTs)) {
          if (currentTs >= existingTs) merged.set(key, row);
          return;
        }
        if (Number.isFinite(currentTs)) {
          merged.set(key, row);
        }
      };

      // Process local first (settled history), then hosted (current picks)
      for (const text of [localText, hostedText]) {
        if (!text) continue;
        for (const row of parseCsv(text).map((csvRow) => parsePublicRow(csvRow, league))) {
          upsert(row);
        }
      }

      return [...merged.values()];
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
