import Link from "next/link";
import { promises as fs } from "fs";
import path from "path";
import { notFound } from "next/navigation";

type CsvRow = Record<string, string>;
type FixtureGroup = {
  key: string;
  matchDate: string;
  bookmaker: string;
  homeTeam: string;
  awayTeam: string;
  homeRows: CsvRow[];
  awayRows: CsvRow[];
};
type LineupPlayer = {
  name: string;
  position: string;
};
type FixtureLineup = {
  homeTeam: string;
  awayTeam: string;
  homeKey: string;
  awayKey: string;
  homeStatus: string;
  awayStatus: string;
  homePlayers: LineupPlayer[];
  awayPlayers: LineupPlayer[];
};

export const dynamic = "force-dynamic";

const MODEL_MONITOR_PUBLIC =
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
const ROTOWIRE_LINEUPS_URL = "https://www.rotowire.com/soccer/lineups.php?league=SERI";
const TEAM_ALIASES: Record<string, string> = {
  "ac milan": "milan",
  milan: "milan",
  inter: "inter",
  "inter milan": "inter",
  internazionale: "inter",
  "lazio rome": "lazio",
  lazio: "lazio",
  "ss lazio": "lazio",
  "as roma": "roma",
  roma: "roma",
  "como 1907": "como",
  como: "como",
  "pisa sc": "pisa",
  pisa: "pisa",
  "cagliari calcio": "cagliari",
  cagliari: "cagliari",
  "sassuolo calcio": "sassuolo",
  sassuolo: "sassuolo",
  "bologna fc": "bologna",
  "bologna fc 1909": "bologna",
  bologna: "bologna",
  "us cremonese": "cremonese",
  cremonese: "cremonese",
  "acf fiorentina": "fiorentina",
  fiorentina: "fiorentina",
  verona: "verona",
  "hellas verona": "verona",
  genoa: "genoa",
  "genoa cfc": "genoa",
};

function parseCsvLine(line: string): string[] {
  const out: string[] = [];
  let cur = "";
  let inQuotes = false;
  for (let i = 0; i < line.length; i += 1) {
    const ch = line[i];
    if (ch === '"') {
      if (inQuotes && line[i + 1] === '"') {
        cur += '"';
        i += 1;
      } else {
        inQuotes = !inQuotes;
      }
      continue;
    }
    if (ch === "," && !inQuotes) {
      out.push(cur);
      cur = "";
      continue;
    }
    cur += ch;
  }
  out.push(cur);
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
    headers.forEach((header, idx) => {
      row[header] = values[idx] ?? "";
    });
    return row;
  });
}

function stripTags(text: string): string {
  return text.replace(/<[^>]+>/g, " ");
}

function decodeHtml(text: string): string {
  return text
    .replace(/&amp;/g, "&")
    .replace(/&#039;/g, "'")
    .replace(/&quot;/g, '"')
    .replace(/&nbsp;/g, " ")
    .replace(/&rsquo;/g, "'")
    .replace(/&ldquo;/g, '"')
    .replace(/&rdquo;/g, '"')
    .replace(/&uuml;/g, "ü")
    .replace(/&ouml;/g, "ö")
    .replace(/&eacute;/g, "é")
    .replace(/&Eacute;/g, "É");
}

async function readLocalFile(relPath: string): Promise<string | null> {
  try {
    return await fs.readFile(path.join(process.cwd(), relPath), "utf8");
  } catch {
    return null;
  }
}

async function readLocalMtime(relPath: string): Promise<string | null> {
  try {
    const stat = await fs.stat(path.join(process.cwd(), relPath));
    return stat.mtime.toISOString();
  } catch {
    return null;
  }
}

async function fetchRotowireHtml(): Promise<string | null> {
  try {
    const response = await fetch(ROTOWIRE_LINEUPS_URL, {
      headers: {
        "User-Agent": "Mozilla/5.0",
      },
      next: { revalidate: 300 },
    });
    if (!response.ok) return null;
    return await response.text();
  } catch {
    return null;
  }
}

function parseFloatMaybe(value?: string): number | undefined {
  if (!value) return undefined;
  const n = Number.parseFloat(value);
  return Number.isFinite(n) ? n : undefined;
}

function formatPct(value?: number, digits = 1): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}%`;
}

function formatDecimal(value?: number, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return value.toFixed(digits);
}

function formatSigned(value?: number, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
}

function toneForAction(action?: string): string {
  if (action === "surface") return "text-emerald-300";
  if (action === "surface_with_caveat") return "text-amber-300";
  return "text-slate-400";
}

function badgeClass(action?: string): string {
  if (action === "surface") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (action === "surface_with_caveat") return "border-amber-500/30 bg-amber-500/10 text-amber-200";
  return "border-slate-700 bg-slate-900 text-slate-300";
}

function confidenceClass(confidence?: string): string {
  if (confidence === "high") return "border-emerald-500/20 bg-emerald-500/8";
  if (confidence === "medium") return "border-amber-500/20 bg-amber-500/8";
  return "border-slate-800/80 bg-slate-950/45";
}

function confidenceRank(confidence?: string): number {
  if (confidence === "high") return 3;
  if (confidence === "medium") return 2;
  return 1;
}

function positionBand(position?: string): "gk" | "def" | "mid" | "att" | "util" {
  const text = (position ?? "").split(",")[0].trim().toUpperCase();
  if (!text) return "util";
  if (text.startsWith("GK")) return "gk";
  if (text.startsWith("D")) return "def";
  if (text.startsWith("M")) return "mid";
  if (text.startsWith("F")) return "att";
  return "util";
}

function normText(value?: string): string {
  const decoded = decodeHtml(value ?? "")
    .toLowerCase()
    .normalize("NFD")
    .replace(/\p{Diacritic}/gu, "");
  return decoded.replace(/[^a-z0-9]+/g, " ").trim().replace(/\s+/g, " ");
}

function teamKey(name?: string): string {
  const cleaned = normText(name);
  return TEAM_ALIASES[cleaned] ?? cleaned;
}

function playerMatchScore(left?: string, right?: string): number {
  const a = normText(left);
  const b = normText(right);
  if (!a || !b) return 0;
  if (a === b) return 100;
  const aTokens = a.split(" ");
  const bTokens = b.split(" ");
  const aFirst = aTokens[0];
  const bFirst = bTokens[0];
  const aLast = aTokens[aTokens.length - 1];
  const bLast = bTokens[bTokens.length - 1];

  if (aLast === bLast) {
    if (aFirst === bFirst) return 96;
    if (aFirst.startsWith(bFirst) || bFirst.startsWith(aFirst)) return 90;
    return 82;
  }
  if (a.includes(b) || b.includes(a)) return 76;
  const overlap = aTokens.filter((token) => bTokens.includes(token)).length;
  if (overlap >= 2) return 68;
  return 0;
}

function parseLineupPlayers(listHtml: string): LineupPlayer[] {
  const players: LineupPlayer[] = [];
  const playerRegex =
    /<li class="lineup__player">[\s\S]*?<div class="lineup__pos[^"]*">([^<]*)<\/div>[\s\S]*?<a[^>]*title="([^"]+)"[\s\S]*?<\/li>/g;
  let match = playerRegex.exec(listHtml);
  while (match && players.length < 11) {
    players.push({
      position: decodeHtml(stripTags(match[1])).trim(),
      name: decodeHtml(match[2]).trim(),
    });
    match = playerRegex.exec(listHtml);
  }
  return players;
}

function parseRotowireLineups(html: string): FixtureLineup[] {
  const blocks = html
    .split('<div class="lineup is-soccer')
    .slice(1)
    .map((part) => `<div class="lineup is-soccer${part}`);
  const parsed: FixtureLineup[] = [];

  for (const block of blocks) {
    const homeTeamMatch = block.match(/<div class="lineup__mteam is-home">\s*([\s\S]*?)<span class="lineup__wl">/);
    const awayTeamMatch = block.match(/<div class="lineup__mteam is-visit">\s*([\s\S]*?)<span class="lineup__wl">/);
    const homeListMatch = block.match(/<ul class="lineup__list is-home">([\s\S]*?)<\/ul>/);
    const awayListMatch = block.match(/<ul class="lineup__list is-visit">([\s\S]*?)<\/ul>/);
    if (!homeTeamMatch || !awayTeamMatch || !homeListMatch || !awayListMatch) continue;

    const homeTeam = decodeHtml(stripTags(homeTeamMatch[1])).trim();
    const awayTeam = decodeHtml(stripTags(awayTeamMatch[1])).trim();
    const homeStatus = decodeHtml(stripTags(homeListMatch[1].match(/<li class="lineup__status[^"]*">([\s\S]*?)<\/li>/)?.[1] ?? "")).trim();
    const awayStatus = decodeHtml(stripTags(awayListMatch[1].match(/<li class="lineup__status[^"]*">([\s\S]*?)<\/li>/)?.[1] ?? "")).trim();
    const homePlayers = parseLineupPlayers(homeListMatch[1]);
    const awayPlayers = parseLineupPlayers(awayListMatch[1]);
    if (!homePlayers.length || !awayPlayers.length) continue;

    parsed.push({
      homeTeam,
      awayTeam,
      homeKey: teamKey(homeTeam),
      awayKey: teamKey(awayTeam),
      homeStatus,
      awayStatus,
      homePlayers,
      awayPlayers,
    });
  }

  return parsed;
}

function buildFixtureGroups(rows: CsvRow[]): FixtureGroup[] {
  const fixtureMap = new Map<string, FixtureGroup>();
  for (const row of rows) {
    const homeTeam = row.home_team ?? "";
    const awayTeam = row.away_team ?? "";
    if (!homeTeam || !awayTeam) continue;
    const key = `${row.match_date}|${row.bookmaker}|${homeTeam}|${awayTeam}`;
    const existing = fixtureMap.get(key) ?? {
      key,
      matchDate: row.match_date ?? "",
      bookmaker: row.bookmaker ?? "",
      homeTeam,
      awayTeam,
      homeRows: [],
      awayRows: [],
    };
    const isHome = (row.is_home ?? "") === "1";
    const isAway = (row.is_home ?? "") === "0";
    if (isHome) {
      existing.homeRows.push(row);
    } else if (isAway) {
      existing.awayRows.push(row);
    }
    fixtureMap.set(key, existing);
  }
  return [...fixtureMap.values()].sort((a, b) => a.key.localeCompare(b.key));
}

function rankTeamRows(rows: CsvRow[]): CsvRow[] {
  return [...rows].sort((a, b) => {
    const minuteDiff = (parseFloatMaybe(b.expected_minutes) ?? 0) - (parseFloatMaybe(a.expected_minutes) ?? 0);
    if (minuteDiff !== 0) return minuteDiff;
    const confidenceDiff = confidenceRank(b.signal_confidence) - confidenceRank(a.signal_confidence);
    if (confidenceDiff !== 0) return confidenceDiff;
    return (parseFloatMaybe(b.ev) ?? 0) - (parseFloatMaybe(a.ev) ?? 0);
  });
}

function buildProjectedPitch(rows: CsvRow[]) {
  const ranked = rankTeamRows(rows);
  const keeper = ranked.find((row) => positionBand(row.position) === "gk");
  const outfield = ranked.filter((row) => positionBand(row.position) !== "gk").slice(0, 10);

  const defenders: CsvRow[] = [];
  const midfielders: CsvRow[] = [];
  const attackers: CsvRow[] = [];
  const utilities: CsvRow[] = [];

  for (const row of outfield) {
    const band = positionBand(row.position);
    if (band === "def") defenders.push(row);
    else if (band === "mid") midfielders.push(row);
    else if (band === "att") attackers.push(row);
    else utilities.push(row);
  }

  for (const row of utilities) {
    if (midfielders.length <= defenders.length && midfielders.length <= attackers.length) midfielders.push(row);
    else if (attackers.length <= defenders.length) attackers.push(row);
    else defenders.push(row);
  }

  return {
    keeper,
    defenders,
    midfielders,
    attackers,
    omittedCount: Math.max(0, ranked.length - (keeper ? 11 : 10)),
  };
}

function resolveLineupRows(lineupPlayers: LineupPlayer[], teamRows: CsvRow[]): Array<{ lineup: LineupPlayer; row?: CsvRow }> {
  const used = new Set<number>();
  return lineupPlayers.map((lineupPlayer) => {
    let bestIdx = -1;
    let bestScore = 0;
    for (let idx = 0; idx < teamRows.length; idx += 1) {
      if (used.has(idx)) continue;
      const score = playerMatchScore(lineupPlayer.name, teamRows[idx].player_name);
      if (score > bestScore) {
        bestScore = score;
        bestIdx = idx;
      }
    }
    if (bestIdx >= 0 && bestScore >= 68) {
      used.add(bestIdx);
      return { lineup: lineupPlayer, row: teamRows[bestIdx] };
    }
    return { lineup: lineupPlayer };
  });
}

function Stat({
  label,
  value,
  tone = "text-slate-100",
}: {
  label: string;
  value: string;
  tone?: string;
}) {
  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 px-3 py-3">
      <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{label}</div>
      <div className={`mt-1 text-lg font-semibold ${tone}`}>{value}</div>
    </div>
  );
}

function PlayerTile({ row }: { row: CsvRow }) {
  return (
    <div className={`min-w-[124px] rounded-xl border px-3 py-2 text-center shadow-[0_8px_25px_rgba(0,0,0,0.18)] ${confidenceClass(row.signal_confidence)}`}>
      <div className="truncate text-sm font-semibold text-slate-100">{row.player_name}</div>
      <div className="mt-1 text-[11px] uppercase tracking-[0.16em] text-slate-500">{row.position || "UTIL"}</div>
      <div className="mt-2 grid gap-1 text-xs">
        <div className="text-slate-300">Fair {formatDecimal(parseFloatMaybe(row.model_fair_odds_atgs), 2)}</div>
        <div className={toneForAction(row.public_action)}>EV {formatPct((parseFloatMaybe(row.ev) ?? 0) * 100, 1)}</div>
        <div className="text-slate-500">Min {formatDecimal(parseFloatMaybe(row.expected_minutes), 0)}</div>
      </div>
    </div>
  );
}

function LineupTile({ lineup, row }: { lineup: LineupPlayer; row?: CsvRow }) {
  if (!row) {
    return (
      <div className="min-w-[124px] rounded-xl border border-dashed border-slate-700/80 bg-slate-950/45 px-3 py-2 text-center shadow-[0_8px_25px_rgba(0,0,0,0.18)]">
        <div className="truncate text-sm font-semibold text-slate-100">{lineup.name}</div>
        <div className="mt-1 text-[11px] uppercase tracking-[0.16em] text-slate-500">{lineup.position || "UTIL"}</div>
        <div className="mt-2 text-xs text-slate-500">No price matched</div>
      </div>
    );
  }

  return <PlayerTile row={{ ...row, position: lineup.position || row.position }} />;
}

function PitchRow({ rows }: { rows: CsvRow[] }) {
  if (!rows.length) return <div className="min-h-8" />;
  return (
    <div className="flex flex-wrap items-center justify-center gap-3">
      {rows.map((row) => (
        <PlayerTile key={`${row.player_name}-${row.player_team}-${row.bookmaker}`} row={row} />
      ))}
    </div>
  );
}

function LineupPitchRow({ rows }: { rows: Array<{ lineup: LineupPlayer; row?: CsvRow }> }) {
  if (!rows.length) return <div className="min-h-8" />;
  return (
    <div className="flex flex-wrap items-center justify-center gap-3">
      {rows.map(({ lineup, row }) => (
        <LineupTile key={`${lineup.name}-${lineup.position}`} lineup={lineup} row={row} />
      ))}
    </div>
  );
}

function TeamPitch({
  team,
  rows,
  lineupPlayers,
  lineupStatus,
}: {
  team: string;
  rows: CsvRow[];
  lineupPlayers?: LineupPlayer[];
  lineupStatus?: string;
}) {
  const lineupRows = lineupPlayers ? resolveLineupRows(lineupPlayers, rows) : [];
  const hasLineup = lineupRows.length > 0;
  const pitch = buildProjectedPitch(rows);
  const lineupKeeper = lineupRows.find((item) => positionBand(item.lineup.position) === "gk");
  const lineupOutfield = lineupRows.filter((item) => positionBand(item.lineup.position) !== "gk");
  const lineupDefenders = lineupOutfield.filter((item) => positionBand(item.lineup.position) === "def");
  const lineupMidfielders = lineupOutfield.filter((item) => positionBand(item.lineup.position) === "mid");
  const lineupAttackers = lineupOutfield.filter((item) => positionBand(item.lineup.position) === "att");
  const lineupUtilities = lineupOutfield.filter((item) => positionBand(item.lineup.position) === "util");

  for (const item of lineupUtilities) {
    if (lineupMidfielders.length <= lineupDefenders.length && lineupMidfielders.length <= lineupAttackers.length) lineupMidfielders.push(item);
    else if (lineupAttackers.length <= lineupDefenders.length) lineupAttackers.push(item);
    else lineupDefenders.push(item);
  }

  return (
    <div className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(32,73,58,0.95),rgba(20,52,42,0.98))] p-4 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.03)]">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">{team}</h3>
          <p className="text-xs leading-5 text-emerald-100/75">
            {hasLineup
              ? `${lineupStatus || "Predicted Lineup"} from RotoWire. Tiles show fair odds and EV where a model row exists.`
              : "Projected priced XI from expected minutes. GK is not part of ATGS pricing."}
          </p>
        </div>
        <div className="rounded-full border border-slate-700/70 bg-slate-950/35 px-3 py-1 text-xs text-slate-200">
          {hasLineup ? `${lineupRows.length} lineup players` : `${rows.length} priced players`}
        </div>
      </div>

      <div className="space-y-5 rounded-2xl border border-white/6 bg-[linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01))] p-4">
        {hasLineup ? (
          <>
            <LineupPitchRow rows={lineupAttackers} />
            <div className="h-px bg-white/10" />
            <LineupPitchRow rows={lineupMidfielders} />
            <div className="h-px bg-white/10" />
            <LineupPitchRow rows={lineupDefenders} />
            <div className="h-px bg-white/10" />
            <div className="flex justify-center">
              {lineupKeeper ? (
                <LineupTile lineup={lineupKeeper.lineup} row={lineupKeeper.row} />
              ) : (
                <div className="min-w-[124px] rounded-xl border border-dashed border-slate-700/80 bg-slate-950/35 px-3 py-2 text-center">
                  <div className="text-sm font-semibold text-slate-200">GK</div>
                  <div className="mt-1 text-xs text-slate-500">Not priced in ATGS</div>
                </div>
              )}
            </div>
          </>
        ) : (
          <>
            <PitchRow rows={pitch.attackers} />
            <div className="h-px bg-white/10" />
            <PitchRow rows={pitch.midfielders} />
            <div className="h-px bg-white/10" />
            <PitchRow rows={pitch.defenders} />
            <div className="h-px bg-white/10" />
            <div className="flex justify-center">
              {pitch.keeper ? (
                <PlayerTile row={pitch.keeper} />
              ) : (
                <div className="min-w-[124px] rounded-xl border border-dashed border-slate-700/80 bg-slate-950/35 px-3 py-2 text-center">
                  <div className="text-sm font-semibold text-slate-200">GK</div>
                  <div className="mt-1 text-xs text-slate-500">Not priced in ATGS</div>
                </div>
              )}
            </div>
          </>
        )}
      </div>

      <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-400">
        <span>
          {hasLineup
            ? `${lineupRows.filter((item) => item.row).length}/${lineupRows.length} lineup players matched to current model rows`
            : pitch.omittedCount > 0
              ? `${pitch.omittedCount} additional priced players hidden`
              : "Top priced XI shown"}
        </span>
        <span className="rounded-full border border-emerald-500/20 bg-emerald-500/8 px-2 py-1 text-emerald-200">high = public-ready</span>
        <span className="rounded-full border border-amber-500/20 bg-amber-500/8 px-2 py-1 text-amber-100">medium = caveat</span>
      </div>
    </div>
  );
}

export default async function GoalscorerMonitorPage() {
  if (process.env.NODE_ENV === "production" && !MODEL_MONITOR_PUBLIC) {
    notFound();
  }

  const [comparisonCsv, comparisonTxt, comparisonMtime, rotowireHtml] = await Promise.all([
    readLocalFile("data/goalscorer/goalscorer-live-comparison.csv"),
    readLocalFile("data/goalscorer/goalscorer-live-comparison.txt"),
    readLocalMtime("data/goalscorer/goalscorer-live-comparison.csv"),
    fetchRotowireHtml(),
  ]);

  const rows = comparisonCsv ? parseCsv(comparisonCsv) : [];
  const publicRows = rows.filter((row) => {
    const action = row.public_action ?? "";
    const ev = parseFloatMaybe(row.ev) ?? 0;
    return ev >= 0.05 && (action === "surface" || action === "surface_with_caveat");
  });
  const highRows = publicRows.filter((row) => row.public_action === "surface");
  const caveatRows = publicRows.filter((row) => row.public_action === "surface_with_caveat");
  const suppressedRows = rows.filter((row) => row.public_action === "suppress");

  publicRows.sort((a, b) => (parseFloatMaybe(b.ev) ?? 0) - (parseFloatMaybe(a.ev) ?? 0));
  highRows.sort((a, b) => (parseFloatMaybe(b.ev) ?? 0) - (parseFloatMaybe(a.ev) ?? 0));
  caveatRows.sort((a, b) => (parseFloatMaybe(b.ev) ?? 0) - (parseFloatMaybe(a.ev) ?? 0));

  const comparedAt = rows[0]?.compared_at ?? "n/a";
  const matchedRows = rows.length;
  const avgEv =
    rows.length > 0
      ? rows.reduce((sum, row) => sum + (parseFloatMaybe(row.ev) ?? 0), 0) / rows.length
      : undefined;
  const historyResolved = rows.filter((row) => row.resolver_source === "history").length;
  const rosterResolved = rows.filter((row) => row.resolver_source === "live_roster").length;
  const lowConfidence = rows.filter((row) => row.signal_confidence === "low").length;
  const fixtures = buildFixtureGroups(rows);
  const lineupFixtures = parseRotowireLineups(rotowireHtml ?? "");
  const lineupMap = new Map(
    lineupFixtures.map((fixture) => [`${fixture.homeKey}|${fixture.awayKey}`, fixture]),
  );

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(244,63,94,0.08),_transparent_22%),#0b0f14] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Link href="/model-monitor" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Model Monitor
          </Link>
          <Link href="/anytime-goalscorer" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Public Placeholder
          </Link>
        </div>

        <section className="mb-8 overflow-hidden rounded-3xl border border-slate-800 bg-[linear-gradient(135deg,rgba(16,185,129,0.12),rgba(15,23,42,0.92)_40%,rgba(244,63,94,0.08))] p-6 sm:p-8">
          <div className="flex flex-col gap-5 lg:flex-row lg:items-end lg:justify-between">
            <div className="max-w-3xl">
              <div className="mb-3 inline-flex items-center rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-emerald-300">
                Internal Preview
              </div>
              <h1 className="text-3xl font-semibold tracking-tight text-white sm:text-4xl">Goalscorer live monitor</h1>
              <p className="mt-3 max-w-2xl text-sm leading-6 text-slate-300 sm:text-base">
                This page reads the latest local goalscorer comparison output directly. It is for internal review only:
                high-confidence signals are separated from caveated roster-resolved rows before anything touches the public site.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 px-4 py-3 text-sm text-slate-300">
              <div><span className="text-slate-500">Compared at:</span> {comparedAt}</div>
              <div><span className="text-slate-500">CSV updated:</span> {comparisonMtime ?? "missing"}</div>
            </div>
          </div>
        </section>

        {!comparisonCsv ? (
          <section className="rounded-2xl border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-100">
            Missing `data/goalscorer/goalscorer-live-comparison.csv`. Run the goalscorer live compare pipeline locally first.
          </section>
        ) : null}

        <div className="mb-8 grid gap-4 lg:grid-cols-6">
          <Stat label="Matched Rows" value={`${matchedRows}`} />
          <Stat label="Public High" value={`${highRows.length}`} tone="text-emerald-300" />
          <Stat label="Public Caveats" value={`${caveatRows.length}`} tone="text-amber-300" />
          <Stat label="Suppressed" value={`${suppressedRows.length}`} tone="text-slate-400" />
          <Stat label="History Resolver" value={`${historyResolved}`} tone="text-emerald-300" />
          <Stat label="Live Roster Resolver" value={`${rosterResolved}`} tone="text-amber-300" />
        </div>

        <div className="mb-8 grid gap-4 lg:grid-cols-4">
          <Stat label="Average EV" value={formatPct((avgEv ?? 0) * 100, 1)} tone={avgEv != null && avgEv >= 0 ? "text-emerald-300" : "text-rose-300"} />
          <Stat label="Low Confidence Rows" value={`${lowConfidence}`} tone="text-slate-400" />
          <Stat label="Top Public EV" value={formatPct((parseFloatMaybe(publicRows[0]?.ev) ?? 0) * 100, 1)} tone={toneForAction(publicRows[0]?.public_action)} />
          <Stat label="Top Public Fair Odds" value={formatDecimal(parseFloatMaybe(publicRows[0]?.model_fair_odds_atgs), 2)} />
        </div>

        <section className="mb-8 rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Fixture pitch view</h2>
              <p className="mt-1 text-sm text-slate-400">
                This is the shape you described: team vs team, player by player, with fair odds and EV visible at a glance.
                For now it is a projected priced XI based on expected minutes, not a true probable-lineup feed.
              </p>
            </div>
          </div>

          <div className="space-y-6">
            {fixtures.map((fixture) => (
              <div key={fixture.key} className="rounded-2xl border border-slate-800/80 bg-slate-950/35 p-4">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <h3 className="text-lg font-semibold text-white">{fixture.homeTeam} vs {fixture.awayTeam}</h3>
                    <p className="text-sm text-slate-400">{fixture.matchDate} · {fixture.bookmaker}</p>
                  </div>
                  <div className="rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-300">
                    {fixture.homeRows.length + fixture.awayRows.length} matched player prices
                  </div>
                </div>

                <div className="grid gap-5 xl:grid-cols-2">
                  {(() => {
                    const lineup = lineupMap.get(`${teamKey(fixture.homeTeam)}|${teamKey(fixture.awayTeam)}`);
                    return (
                      <>
                        <TeamPitch
                          team={fixture.homeTeam}
                          rows={fixture.homeRows}
                          lineupPlayers={lineup?.homePlayers}
                          lineupStatus={lineup?.homeStatus}
                        />
                        <TeamPitch
                          team={fixture.awayTeam}
                          rows={fixture.awayRows}
                          lineupPlayers={lineup?.awayPlayers}
                          lineupStatus={lineup?.awayStatus}
                        />
                      </>
                    );
                  })()}
                </div>
              </div>
            ))}
            {fixtures.length === 0 ? (
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-sm text-slate-500">
                No fixture groups yet. Run the live comparison first.
              </div>
            ) : null}
          </div>
        </section>

        <div className="mb-8 grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <section className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">High-confidence signals</h2>
                <p className="mt-1 text-sm text-slate-400">History-resolved, model-backed, and above the minimum historical-minutes gate.</p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="text-left text-slate-500">
                  <tr className="border-b border-slate-800">
                    <th className="px-3 py-3 font-medium">Player</th>
                    <th className="px-3 py-3 font-medium">Fixture</th>
                    <th className="px-3 py-3 font-medium">Odds</th>
                    <th className="px-3 py-3 font-medium">Fair</th>
                    <th className="px-3 py-3 font-medium">EV</th>
                    <th className="px-3 py-3 font-medium">Hist Min</th>
                  </tr>
                </thead>
                <tbody>
                  {highRows.map((row) => (
                    <tr key={`${row.player_name}-${row.match_date}-${row.bookmaker}`} className="border-b border-slate-900/80">
                      <td className="px-3 py-3">
                        <div className="font-medium text-slate-100">{row.player_name}</div>
                        <div className="text-xs text-slate-500">{row.player_team}</div>
                      </td>
                      <td className="px-3 py-3 text-slate-300">{row.player_team} vs {row.opponent}</td>
                      <td className="px-3 py-3 text-slate-300">{formatDecimal(parseFloatMaybe(row.odds_decimal), 2)}</td>
                      <td className="px-3 py-3 text-slate-300">{formatDecimal(parseFloatMaybe(row.model_fair_odds_atgs), 2)}</td>
                      <td className="px-3 py-3 text-emerald-300">{formatPct((parseFloatMaybe(row.ev) ?? 0) * 100, 1)}</td>
                      <td className="px-3 py-3 text-slate-400">{formatSigned(parseFloatMaybe(row.historical_minutes), 0)}</td>
                    </tr>
                  ))}
                  {highRows.length === 0 ? (
                    <tr>
                      <td colSpan={6} className="px-3 py-6 text-center text-slate-500">No high-confidence public signals yet.</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">Caveated signals</h2>
                <p className="mt-1 text-sm text-slate-400">Model-backed rows resolved via the live roster layer. Useful to inspect, not to expose cleanly yet.</p>
              </div>
            </div>
            <div className="space-y-3">
              {caveatRows.map((row) => (
                <div key={`${row.player_name}-${row.match_date}-${row.bookmaker}`} className="rounded-xl border border-amber-500/15 bg-amber-500/5 p-4">
                  <div className="flex items-start justify-between gap-3">
                    <div>
                      <div className="font-medium text-slate-100">{row.player_name}</div>
                      <div className="text-sm text-slate-400">{row.player_team} vs {row.opponent}</div>
                    </div>
                    <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${badgeClass(row.public_action)}`}>
                      {row.signal_confidence}
                    </span>
                  </div>
                  <div className="mt-3 grid gap-2 sm:grid-cols-3 text-sm">
                    <div className="text-slate-300">Odds {formatDecimal(parseFloatMaybe(row.odds_decimal), 2)}</div>
                    <div className="text-slate-300">Fair {formatDecimal(parseFloatMaybe(row.model_fair_odds_atgs), 2)}</div>
                    <div className="text-amber-300">EV {formatPct((parseFloatMaybe(row.ev) ?? 0) * 100, 1)}</div>
                  </div>
                  <div className="mt-2 text-xs text-slate-500">{row.confidence_reason}</div>
                </div>
              ))}
              {caveatRows.length === 0 ? (
                <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-sm text-slate-500">No caveated signals in the latest run.</div>
              ) : null}
            </div>
          </section>
        </div>

        <section className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Raw monitor summary</h2>
              <p className="mt-1 text-sm text-slate-400">Direct text output from the latest comparison run.</p>
            </div>
          </div>
          <pre className="overflow-x-auto whitespace-pre-wrap rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-xs leading-6 text-slate-300">
            {comparisonTxt ?? "Missing goalscorer live summary."}
          </pre>
        </section>
      </div>
    </div>
  );
}
