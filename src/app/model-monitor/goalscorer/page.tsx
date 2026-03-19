import Link from "next/link";
import { notFound } from "next/navigation";
import { readGoalscorerLiveFile, readGoalscorerLiveMtime } from "@/lib/goalscorer-live-files";

type CsvRow = Record<string, string>;
type FixtureGroup = {
  key: string;
  leagueKey: string;
  leagueLabel: string;
  competition: string;
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
  leagueKey: string;
  homeTeam: string;
  awayTeam: string;
  homeKey: string;
  awayKey: string;
  homeStatus: string;
  awayStatus: string;
  homePlayers: LineupPlayer[];
  awayPlayers: LineupPlayer[];
};

type ShadowSummary = {
  signals: number;
  settled: number;
  open: number;
  wins: number;
  losses: number;
  voids: number;
  roi: number;
  winRate: number;
  pnlUnits: number;
};

export const dynamic = "force-dynamic";

const MODEL_MONITOR_PUBLIC =
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
const SHADOW_SIGNAL_FILES = [
  "data/goalscorer/goalscorer-shadow-signals.csv",
  "data/goalscorer/epl-shadow-signals.csv",
  "data/goalscorer/la-liga-shadow-signals.csv",
  "data/goalscorer/bundesliga-shadow-signals.csv",
  "data/goalscorer/ligue-1-shadow-signals.csv",
];
const LIVE_COMPARE_CONFIGS = [
  {
    key: "serie-a",
    label: "Serie A",
    comparisonCsv: "data/goalscorer/goalscorer-live-comparison.csv",
    comparisonTxt: "data/goalscorer/goalscorer-live-comparison.txt",
    lineupsJson: "data/goalscorer/confirmed-lineups.json",
  },
  {
    key: "epl",
    label: "Premier League",
    comparisonCsv: "data/goalscorer/epl/goalscorer-live-comparison.csv",
    comparisonTxt: "data/goalscorer/epl/goalscorer-live-comparison.txt",
    lineupsJson: "data/goalscorer/epl-confirmed-lineups.json",
  },
  {
    key: "la-liga",
    label: "La Liga",
    comparisonCsv: "data/goalscorer/la-liga/goalscorer-live-comparison.csv",
    comparisonTxt: "data/goalscorer/la-liga/goalscorer-live-comparison.txt",
    lineupsJson: "data/goalscorer/la-liga-confirmed-lineups.json",
  },
  {
    key: "bundesliga",
    label: "Bundesliga",
    comparisonCsv: "data/goalscorer/bundesliga/goalscorer-live-comparison.csv",
    comparisonTxt: "data/goalscorer/bundesliga/goalscorer-live-comparison.txt",
    lineupsJson: "data/goalscorer/bundesliga-confirmed-lineups.json",
  },
  {
    key: "ligue-1",
    label: "Ligue 1",
    comparisonCsv: "data/goalscorer/ligue-1/goalscorer-live-comparison.csv",
    comparisonTxt: "data/goalscorer/ligue-1/goalscorer-live-comparison.txt",
    lineupsJson: "data/goalscorer/ligue-1-confirmed-lineups.json",
  },
] as const;
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
  "juventus turin": "juventus",
  "parma calcio": "parma",
  "burnley fc": "burnley",
  "chelsea fc": "chelsea",
  "everton fc": "everton",
  "fulham fc": "fulham",
  "liverpool fc": "liverpool",
  "leeds united": "leeds",
  "1 fc heidenheim": "fc heidenheim",
  "1 fc cologne": "fc cologne",
  "toulouse fc": "toulouse",
  "fc lorient": "lorient",
  "ogc nice": "nice",
  "racing club de lens": "lens",
  "angers sco": "angers",
  "aj auxerre": "auxerre",
  "stade brest 29": "brest",
  "paris saint germain": "paris saint germain",
  "paris saint-germain": "paris saint germain",
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

function repairMojibake(value: string): string {
  if (!value) return value;
  const normalized = value.normalize("NFC");
  if (!/[\u00C3\u00C2\u00E2]/.test(normalized)) return normalized;

  try {
    const repaired = Buffer.from(normalized, "latin1").toString("utf8").normalize("NFC");
    const penaltyScore = (text: string) => (text.match(/[\u00C3\u00C2\u00E2\uFFFD]/g) ?? []).length;
    return penaltyScore(repaired) < penaltyScore(normalized) ? repaired : normalized;
  } catch {
    return normalized;
  }
}

function decodeHtml(text: string): string {
  return repairMojibake(
    text
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
    .replace(/&Eacute;/g, "É"),
  );
}

function parseStoredLineups(text: string | null, leagueKey: string): FixtureLineup[] {
  if (!text) return [];
  try {
    const payload = JSON.parse(text) as {
      fixtures?: Array<{
        home_team?: string;
        away_team?: string;
        home_status?: string;
        away_status?: string;
        home_starters?: Array<{ name?: string; role_group?: string }>;
        away_starters?: Array<{ name?: string; role_group?: string }>;
        home_players?: string[];
        away_players?: string[];
      }>;
    };
    return (payload.fixtures ?? [])
      .map((fixture) => {
        const homeTeam = decodeHtml(fixture.home_team ?? "").trim();
        const awayTeam = decodeHtml(fixture.away_team ?? "").trim();
        const homeStarterEntries = fixture.home_starters ?? [];
        const awayStarterEntries = fixture.away_starters ?? [];
        const homePlayers =
          homeStarterEntries.length > 0
            ? homeStarterEntries.map((entry) => ({
                name: decodeHtml(entry.name ?? "").trim(),
                position: decodeHtml(entry.role_group ?? "").trim(),
              }))
            : (fixture.home_players ?? []).map((name) => ({
                name: decodeHtml(name).trim(),
                position: "",
              }));
        const awayPlayers =
          awayStarterEntries.length > 0
            ? awayStarterEntries.map((entry) => ({
                name: decodeHtml(entry.name ?? "").trim(),
                position: decodeHtml(entry.role_group ?? "").trim(),
              }))
            : (fixture.away_players ?? []).map((name) => ({
                name: decodeHtml(name).trim(),
                position: "",
              }));

        if (!homeTeam || !awayTeam || !homePlayers.length || !awayPlayers.length) return null;

        return {
          leagueKey,
          homeTeam,
          awayTeam,
          homeKey: teamKey(homeTeam),
          awayKey: teamKey(awayTeam),
          homeStatus: decodeHtml(fixture.home_status ?? "").trim(),
          awayStatus: decodeHtml(fixture.away_status ?? "").trim(),
          homePlayers,
          awayPlayers,
        } satisfies FixtureLineup;
      })
      .filter((fixture): fixture is FixtureLineup => fixture !== null);
  } catch {
    return [];
  }
}

function parseFloatMaybe(value?: string): number | undefined {
  if (!value) return undefined;
  const n = Number.parseFloat(value);
  return Number.isFinite(n) ? n : undefined;
}

function parseIntMaybe(value?: string): number | undefined {
  if (!value) return undefined;
  const cleaned = value.replace(/,/g, "").trim();
  const n = Number.parseInt(cleaned, 10);
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

function formatWLV(wins: number, losses: number, voids: number): string {
  return `${wins}/${losses}/${voids}`;
}

function formatLineupLabel(row: CsvRow): string {
  if (row.lineup_status) return row.lineup_status;
  if (row.lineup_input === "confirmed_xi") return "Confirmed XI";
  if (row.lineup_input === "expected_xi") return "FotMob Expected XI";
  return "No XI yet";
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

function buildFixtureGroups(rows: CsvRow[], leagueKey: string, leagueLabel: string): FixtureGroup[] {
  const fixtureMap = new Map<string, FixtureGroup>();
  for (const row of rows) {
    const homeTeam = row.home_team ?? "";
    const awayTeam = row.away_team ?? "";
    if (!homeTeam || !awayTeam) continue;
    const key = `${row.match_date}|${row.bookmaker}|${homeTeam}|${awayTeam}`;
      const existing = fixtureMap.get(key) ?? {
      key,
      leagueKey,
      leagueLabel,
      competition: row.competition ?? leagueLabel,
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

function isoDateInTimezone(timeZone: string): string {
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(new Date());
  const year = parts.find((part) => part.type === "year")?.value ?? "0000";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  return `${year}-${month}-${day}`;
}

function addDaysIso(isoDate: string, days: number): string {
  const [year, month, day] = isoDate.split("-").map(Number);
  const date = new Date(Date.UTC(year, (month || 1) - 1, day || 1));
  date.setUTCDate(date.getUTCDate() + days);
  return date.toISOString().slice(0, 10);
}

function filterActiveRows(rows: CsvRow[]): CsvRow[] {
  const today = isoDateInTimezone("Europe/London");
  const horizon = addDaysIso(today, 3);
  return rows.filter((row) => {
    const matchDate = (row.match_date ?? "").slice(0, 10);
    return Boolean(matchDate) && matchDate >= today && matchDate <= horizon;
  });
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

function parseSummaryMetrics(text: string | null): Record<string, string> {
  if (!text) return {};
  const metrics: Record<string, string> = {};
  for (const rawLine of text.split(/\r?\n/)) {
    const line = rawLine.trim();
    if (!line || /^=+$/.test(line)) continue;
    const match = line.match(/^(.+?)\s{2,}(.+)$/);
    if (!match) continue;
    metrics[match[1].trim()] = match[2].trim();
  }
  return metrics;
}

function isSettledShadowRow(row: CsvRow): boolean {
  const value = (row.settled ?? "").trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "settled";
}

function computeShadowSummary(rows: CsvRow[]): ShadowSummary {
  const settled = rows.filter(isSettledShadowRow);
  const wins = settled.filter((row) => (row.bet_outcome ?? "").trim().toLowerCase() === "won").length;
  const losses = settled.filter((row) => (row.bet_outcome ?? "").trim().toLowerCase() === "lost").length;
  const voids = settled.filter((row) => {
    const outcome = (row.bet_outcome ?? "").trim().toLowerCase();
    return outcome === "void" || outcome === "push";
  }).length;
  const pnlUnits = settled.reduce((sum, row) => sum + (parseFloatMaybe(row.pnl_units) ?? 0), 0);

  return {
    signals: rows.length,
    settled: settled.length,
    open: Math.max(0, rows.length - settled.length),
    wins,
    losses,
    voids,
    roi: settled.length > 0 ? (pnlUnits / settled.length) * 100 : 0,
    winRate: settled.length > 0 ? (wins / settled.length) * 100 : 0,
    pnlUnits,
  };
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

function signalRowClass(action?: string, hasRow = true): string {
  if (!hasRow) return "border-dashed border-slate-700/70 bg-slate-950/25";
  if (action === "surface") return "border-emerald-500/20 bg-emerald-500/8";
  if (action === "surface_with_caveat") return "border-amber-500/20 bg-amber-500/8";
  if (action === "suppress") return "border-slate-800/80 bg-slate-950/30 opacity-80";
  return "border-slate-800/80 bg-slate-950/35";
}

function signalBadge(action?: string): string {
  if (action === "surface") return "border-emerald-500/20 bg-emerald-500/10 text-emerald-300";
  if (action === "surface_with_caveat") return "border-amber-500/20 bg-amber-500/10 text-amber-200";
  if (action === "suppress") return "border-slate-700/80 bg-slate-900/80 text-slate-500";
  return "border-slate-700/80 bg-slate-900/80 text-slate-300";
}

function PlayerSignalRow({
  name,
  position,
  row,
  note,
}: {
  name: string;
  position: string;
  row?: CsvRow;
  note?: string;
}) {
  const hasRow = Boolean(row);
  const action = row?.public_action;
  const evPct = row ? formatPct((parseFloatMaybe(row.ev) ?? 0) * 100, 1) : "unpriced";

  return (
    <div className={`rounded-xl border px-3 py-3 ${signalRowClass(action, hasRow)}`}>
      <div className="flex flex-col gap-3 lg:grid lg:grid-cols-[minmax(0,1.7fr)_72px_72px_72px_64px_auto] lg:items-center">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-sm font-semibold leading-tight text-slate-100">{name}</div>
            <span className="rounded-full border border-slate-700/80 bg-slate-950/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              {position || "UTIL"}
            </span>
          </div>
          {note ? <div className="mt-1 text-xs text-slate-500">{note}</div> : null}
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4 lg:contents">
          <div className="rounded-lg bg-black/15 px-2 py-1.5 lg:bg-transparent lg:px-0 lg:py-0">
            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Odds</div>
            <div className="mt-1 font-semibold text-slate-200">{hasRow ? formatDecimal(parseFloatMaybe(row?.odds_decimal), 2) : "n/a"}</div>
          </div>
          <div className="rounded-lg bg-black/15 px-2 py-1.5 lg:bg-transparent lg:px-0 lg:py-0">
            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Fair</div>
            <div className="mt-1 font-semibold text-slate-300">{hasRow ? formatDecimal(parseFloatMaybe(row?.model_fair_odds_atgs), 2) : "n/a"}</div>
          </div>
          <div className="rounded-lg bg-black/15 px-2 py-1.5 lg:bg-transparent lg:px-0 lg:py-0">
            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">EV</div>
            <div className={`mt-1 font-semibold ${hasRow ? toneForAction(action) : "text-slate-500"}`}>{evPct}</div>
          </div>
          <div className="rounded-lg bg-black/15 px-2 py-1.5 lg:bg-transparent lg:px-0 lg:py-0">
            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Min</div>
            <div className="mt-1 font-semibold text-slate-500">{hasRow ? formatDecimal(parseFloatMaybe(row?.expected_minutes), 0) : "n/a"}</div>
          </div>
        </div>
        <div className="lg:justify-self-end">
          <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${signalBadge(action)}`}>
            {hasRow ? (action === "surface" ? "live" : action || "monitor") : "unpriced"}
          </span>
        </div>
      </div>
    </div>
  );
}

function GroupBlock({
  title,
  items,
}: {
  title: string;
  items: Array<{
    key: string;
    name: string;
    position: string;
    row?: CsvRow;
    note?: string;
  }>;
}) {
  return (
    <div className="rounded-2xl border border-white/6 bg-[linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01))] p-3">
      <div className="mb-3 flex items-center justify-between gap-3">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{title}</div>
        <div className="text-xs text-slate-500">{items.length}</div>
      </div>
      <div className="space-y-2.5">
        {items.length > 0 ? (
          items.map((item) => (
            <PlayerSignalRow
              key={item.key}
              name={item.name}
              position={item.position}
              row={item.row}
              note={item.note}
            />
          ))
        ) : (
          <div className="rounded-xl border border-dashed border-slate-800/80 bg-slate-950/20 px-3 py-3 text-sm text-slate-500">
            No players in this band.
          </div>
        )}
      </div>
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
  const displayedCount = lineupRows.length;
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

  const groupedItems = hasLineup
    ? {
        attackers: lineupAttackers.map(({ lineup, row }) => ({
          key: `${lineup.name}-${lineup.position}`,
          name: lineup.name,
          position: lineup.position || row?.position || "UTIL",
          row: row ? { ...row, position: lineup.position || row.position } : undefined,
          note: row ? undefined : "No price matched",
        })),
        midfielders: lineupMidfielders.map(({ lineup, row }) => ({
          key: `${lineup.name}-${lineup.position}`,
          name: lineup.name,
          position: lineup.position || row?.position || "UTIL",
          row: row ? { ...row, position: lineup.position || row.position } : undefined,
          note: row ? undefined : "No price matched",
        })),
        defenders: lineupDefenders.map(({ lineup, row }) => ({
          key: `${lineup.name}-${lineup.position}`,
          name: lineup.name,
          position: lineup.position || row?.position || "UTIL",
          row: row ? { ...row, position: lineup.position || row.position } : undefined,
          note: row ? undefined : "No price matched",
        })),
        keeper: lineupKeeper
          ? {
              key: `${lineupKeeper.lineup.name}-${lineupKeeper.lineup.position}`,
              name: lineupKeeper.lineup.name,
              position: lineupKeeper.lineup.position || "GK",
              row: lineupKeeper.row ? { ...lineupKeeper.row, position: lineupKeeper.lineup.position || lineupKeeper.row.position } : undefined,
              note: lineupKeeper.row ? undefined : "ATGS not priced",
            }
          : null,
      }
    : {
        attackers: [],
        midfielders: [],
        defenders: [],
        keeper: null,
      };

  return (
    <div className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(23,32,44,0.96),rgba(12,18,28,0.98))] p-4 shadow-[inset_0_0_0_1px_rgba(255,255,255,0.03)]">
      <div className="mb-3 flex items-start justify-between gap-3">
        <div>
          <h3 className="text-lg font-semibold text-white">{team}</h3>
          <p className="text-xs leading-5 text-slate-300/80">
            {hasLineup
              ? `${lineupStatus || "Confirmed Lineup"} from the local FotMob feed. Starters stay visible even when the market has not priced them yet.`
              : "No FotMob expected XI for this team yet. We hide the model fallback here rather than pretending it is a probable lineup."}
          </p>
        </div>
        <div className="rounded-full border border-slate-700/70 bg-slate-950/35 px-3 py-1 text-xs text-slate-200">
          {hasLineup ? `${displayedCount} lineup players` : `${rows.length} priced rows`}
        </div>
      </div>

      {hasLineup ? (
        <>
          <div className="space-y-3">
            <GroupBlock title="Attack" items={groupedItems.attackers} />
            <GroupBlock title="Midfield" items={groupedItems.midfielders} />
            <GroupBlock title="Defence" items={groupedItems.defenders} />
          </div>

          <div className="mt-3 rounded-2xl border border-white/6 bg-[linear-gradient(180deg,rgba(255,255,255,0.03),rgba(255,255,255,0.01))] p-3">
            <div className="mb-3 flex items-center justify-between gap-3">
              <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">Goalkeeper / extra context</div>
              <div className="text-xs text-slate-500">starter lens</div>
            </div>
            {groupedItems.keeper ? (
              <PlayerSignalRow
                name={groupedItems.keeper.name}
                position={groupedItems.keeper.position}
                row={groupedItems.keeper.row}
                note={groupedItems.keeper.note}
              />
            ) : (
              <div className="rounded-xl border border-dashed border-slate-800/80 bg-slate-950/20 px-3 py-3 text-sm text-slate-500">
                Goalkeeper is not part of ATGS pricing.
              </div>
            )}
          </div>

          <div className="mt-3 flex flex-wrap items-center gap-3 text-xs text-slate-400">
            <span>{`${lineupRows.filter((item) => item.row).length}/${lineupRows.length} lineup players matched to current model rows`}</span>
            <span className="rounded-full border border-emerald-500/20 bg-emerald-500/8 px-2 py-1 text-emerald-200">high = public-ready</span>
            <span className="rounded-full border border-amber-500/20 bg-amber-500/8 px-2 py-1 text-amber-100">medium = caveat</span>
          </div>
        </>
      ) : (
        <div className="rounded-2xl border border-dashed border-slate-800/80 bg-slate-950/20 p-4 text-sm text-slate-400">
          No FotMob lineup published yet for this team. The monitor still prices the market in the table above, but this team panel waits for a real expected or confirmed XI instead of inventing one from model minutes.
        </div>
      )}
    </div>
  );
}

export default async function GoalscorerMonitorPage() {
  if (process.env.NODE_ENV === "production" && !MODEL_MONITOR_PUBLIC) {
    notFound();
  }

  const [leagueDatasets, shadowContents] = await Promise.all([
    Promise.all(
      LIVE_COMPARE_CONFIGS.map(async (config) => {
        const [comparisonCsv, comparisonTxt, comparisonMtime, lineupsJson] = await Promise.all([
          readGoalscorerLiveFile(config.comparisonCsv),
          readGoalscorerLiveFile(config.comparisonTxt),
          readGoalscorerLiveMtime(config.comparisonCsv),
          readGoalscorerLiveFile(config.lineupsJson),
        ]);
        const rawRows = comparisonCsv ? parseCsv(comparisonCsv) : [];
        const rows = filterActiveRows(rawRows);
        const fixtures = buildFixtureGroups(rows, config.key, config.label);
        const lineupFixtures = parseStoredLineups(lineupsJson, config.key);
        const lineupMap = new Map(
          lineupFixtures.map((fixture) => [
            `${config.key}|${fixture.homeKey}|${fixture.awayKey}`,
            fixture,
          ]),
        );

        return {
          ...config,
          comparisonCsv,
          comparisonTxt,
          comparisonMtime,
          lineupsJson,
          rows,
          fixtures,
          lineupMap,
          summary: parseSummaryMetrics(comparisonTxt),
        };
      }),
    ),
    Promise.all(SHADOW_SIGNAL_FILES.map((file) => readGoalscorerLiveFile(file))),
  ]);

  const rows = leagueDatasets.flatMap((dataset) => dataset.rows);
  const shadowRows = shadowContents.flatMap((text) => (text ? parseCsv(text) : []));
  const shadowSummary = computeShadowSummary(shadowRows);
  const settledShadowRows = shadowRows
    .filter(isSettledShadowRow)
    .sort((left, right) => {
      const leftTime = Date.parse(left.settled_at || left.kickoff || left.date || "");
      const rightTime = Date.parse(right.settled_at || right.kickoff || right.date || "");
      return rightTime - leftTime;
    });
  const openShadowRows = shadowRows
    .filter((row) => !isSettledShadowRow(row))
    .sort((left, right) => (parseFloatMaybe(right.ev) ?? 0) - (parseFloatMaybe(left.ev) ?? 0));
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

  const comparedAt = rows
    .map((row) => row.compared_at ?? "")
    .filter(Boolean)
    .sort()
    .at(-1) ?? "n/a";
  const comparisonMtime =
    leagueDatasets
      .map((dataset) => dataset.comparisonMtime ?? "")
      .filter(Boolean)
      .sort()
      .at(-1) ?? null;
  const matchedRows = rows.length;
  const avgEv =
    rows.length > 0
      ? rows.reduce((sum, row) => sum + (parseFloatMaybe(row.ev) ?? 0), 0) / rows.length
      : undefined;
  const historyResolved = rows.filter((row) => row.resolver_source === "history").length;
  const rosterResolved = rows.filter((row) => row.resolver_source === "live_roster").length;
  const lowConfidence = rows.filter((row) => row.signal_confidence === "low").length;
  const starterRows = rows.filter((row) => (row.lineup_state ?? "").toLowerCase() === "starter").length;
  const expectedStarterRows = rows.filter((row) => (row.lineup_state ?? "").toLowerCase() === "expected_starter").length;
  const benchRows = rows.filter((row) => (row.lineup_state ?? "").toLowerCase() === "bench").length;
  const expectedBenchRows = rows.filter((row) => (row.lineup_state ?? "").toLowerCase() === "expected_bench").length;
  const notInSquadRows = rows.filter((row) => (row.lineup_state ?? "").toLowerCase() === "not_in_squad").length;
  const expectedOutRows = rows.filter((row) => (row.lineup_state ?? "").toLowerCase() === "expected_out").length;
  const missingHistoryRows = leagueDatasets.reduce(
    (sum, dataset) => sum + (parseIntMaybe(dataset.summary["Missing Player History"]) ?? 0),
    0,
  );
  const fallbackRows = leagueDatasets.reduce(
    (sum, dataset) => sum + (parseIntMaybe(dataset.summary["Fallback Rows"]) ?? 0),
    0,
  );
  const fixturesWithConfirmedLineups = leagueDatasets.reduce(
    (sum, dataset) => sum + (parseIntMaybe(dataset.summary["Fixtures With Confirmed Lineups"]) ?? 0),
    0,
  );
  const fixturesWithExpectedXIs = leagueDatasets.reduce(
    (sum, dataset) => sum + (parseIntMaybe(dataset.summary["Fixtures With Expected Lineups"]) ?? 0),
    0,
  );
  const fixtures = leagueDatasets.flatMap((dataset) => dataset.fixtures);
  const lineupMap = new Map(
    leagueDatasets.flatMap((dataset) =>
      [...dataset.lineupMap.entries()].map(([key, value]) => [key, value] as const),
    ),
  );
  const liveSummaryAvailable = leagueDatasets.filter((dataset) => dataset.comparisonCsv);
  const leagueStatus = leagueDatasets.map((dataset) => {
    const leagueRows = dataset.rows;
    const leaguePublicRows = leagueRows.filter((row) => {
      const action = row.public_action ?? "";
      const ev = parseFloatMaybe(row.ev) ?? 0;
      return ev >= 0.05 && (action === "surface" || action === "surface_with_caveat");
    });
    return {
      key: dataset.key,
      label: dataset.label,
      hasOutput: Boolean(dataset.comparisonCsv),
      hasLineups: Boolean(dataset.lineupsJson),
      rows: leagueRows.length,
      publicHigh: leagueRows.filter((row) => row.public_action === "surface" && (parseFloatMaybe(row.ev) ?? 0) >= 0.05).length,
      publicCaveats: leagueRows.filter((row) => row.public_action === "surface_with_caveat" && (parseFloatMaybe(row.ev) ?? 0) >= 0.05).length,
      totalPublic: leaguePublicRows.length,
      competition: leagueRows[0]?.competition ?? dataset.label,
      updatedAt: dataset.comparisonMtime,
    };
  });
  const rawMonitorSummary = leagueDatasets
    .filter((dataset) => dataset.comparisonTxt)
    .map((dataset) => {
      const updated = dataset.comparisonMtime
        ? `Updated ${new Date(dataset.comparisonMtime).toLocaleString("en-GB", {
            dateStyle: "medium",
            timeStyle: "short",
          })}`
        : "Update time unavailable";
      return `=== ${dataset.label} | ${updated} ===\n${dataset.comparisonTxt ?? "Missing goalscorer live summary."}`;
    })
    .join("\n\n");

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
                This page reads the latest live goalscorer comparison output directly. It is for internal review only:
                confirmed-XI signals are separated from softer expected-XI or no-XI reads before anything touches the public site.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-800/80 bg-slate-950/40 px-4 py-3 text-sm text-slate-300">
              <div><span className="text-slate-500">Compared at:</span> {comparedAt}</div>
              <div><span className="text-slate-500">CSV updated:</span> {comparisonMtime ?? "missing"}</div>
            </div>
          </div>
        </section>

        {liveSummaryAvailable.length === 0 ? (
          <section className="rounded-2xl border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-100">
            No live comparison files found. Run the goalscorer live compare pipeline locally first.
          </section>
        ) : null}

        <section className="mb-8 grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <div className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-slate-100">What this page is actually showing</h2>
              <p className="mt-1 text-sm text-slate-400">
                The top half is the latest live comparison run: every player we matched to bookmaker ATGS odds, plus the
                rows that would be public-ready right now. Expected XIs feed a soft pre-lineup simulation; confirmed XIs are still the hard trigger for tracked bets.
              </p>
            </div>
            <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Stat label="Matched Prices" value={`${matchedRows}`} />
              <Stat label="Current Public-Ready" value={`${highRows.length}`} tone="text-emerald-300" />
              <Stat label="Current Caveats" value={`${caveatRows.length}`} tone="text-amber-300" />
              <Stat label="Suppressed" value={`${suppressedRows.length}`} tone="text-slate-400" />
              <Stat label="Starter Rows" value={`${starterRows}`} tone="text-emerald-300" />
              <Stat label="Expected Starters" value={`${expectedStarterRows}`} tone="text-cyan-300" />
              <Stat label="Bench Rows" value={`${benchRows}`} tone="text-amber-300" />
              <Stat label="Expected Bench" value={`${expectedBenchRows}`} tone="text-amber-200" />
              <Stat label="Not In Squad" value={`${notInSquadRows}`} tone="text-rose-300" />
              <Stat label="Expected Out" value={`${expectedOutRows}`} tone="text-rose-200" />
              <Stat
                label="Fixtures With Confirmed XI"
                value={`${fixturesWithConfirmedLineups}`}
                tone="text-slate-200"
              />
              <Stat
                label="Fixtures With Expected XI"
                value={`${fixturesWithExpectedXIs}`}
                tone="text-cyan-300"
              />
            </div>
            <div className="mt-4 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
              {leagueStatus.map((league) => (
                <div key={league.key} className="rounded-xl border border-slate-800/80 bg-slate-950/35 px-4 py-3">
                  <div className="text-[11px] uppercase tracking-[0.18em] text-slate-500">{league.label}</div>
                  <div className="mt-2 flex items-center justify-between gap-3">
                    <div className="text-lg font-semibold text-slate-100">{league.rows}</div>
                    <div className={league.hasOutput ? "text-xs text-emerald-300" : "text-xs text-amber-300"}>
                      {league.hasOutput ? "live file" : "not run yet"}
                    </div>
                  </div>
                  <div className="mt-2 text-xs text-slate-400">
                    public {league.totalPublic} | lineups {league.hasLineups ? "yes" : "no"}
                  </div>
                </div>
              ))}
            </div>
            <div className="mt-4 rounded-2xl border border-slate-800/80 bg-slate-950/35 p-4 text-sm leading-6 text-slate-300">
              <div className="font-medium text-slate-100">Void policy</div>
              <p className="mt-1 text-slate-400">
                With the current confirmed-XI flow, a player who does not start is filtered out before a shadow pick is logged.
                So this board does not treat non-starters as settled voids later. They simply never enter the historical file.
              </p>
            </div>
          </div>

          <div className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
            <div className="mb-4">
              <h2 className="text-lg font-semibold text-slate-100">Resolver quality</h2>
              <p className="mt-1 text-sm text-slate-400">
                These counts explain how the player row was matched before confidence is assigned. History-resolved rows are
                cleaner. Live-roster rows are usable, but less proven.
              </p>
            </div>
            <div className="grid gap-4 sm:grid-cols-2">
              <Stat label="Mapped By History" value={`${historyResolved}`} tone="text-emerald-300" />
              <Stat label="Mapped By Live Roster" value={`${rosterResolved}`} tone="text-amber-300" />
              <Stat label="Missing Player History" value={`${missingHistoryRows}`} tone="text-rose-300" />
              <Stat label="Fallback Rows" value={`${fallbackRows}`} tone="text-slate-300" />
              <Stat
                label="Average EV"
                value={formatPct((avgEv ?? 0) * 100, 1)}
                tone={avgEv != null && avgEv >= 0 ? "text-emerald-300" : "text-rose-300"}
              />
              <Stat label="Low Confidence Rows" value={`${lowConfidence}`} tone="text-slate-400" />
            </div>
            <div className="mt-4 rounded-2xl border border-slate-800/80 bg-slate-950/35 p-4 text-sm leading-6 text-slate-400">
              <div><span className="font-medium text-slate-200">History resolver:</span> matched directly to historical player logs.</div>
              <div><span className="font-medium text-slate-200">Live roster resolver:</span> matched through the current lineup and roster layer when the clean historical match was weaker.</div>
            </div>
          </div>
        </section>

        <div className="mb-8 grid gap-6 xl:grid-cols-[1.15fr_0.85fr]">
          <section className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">Current public-ready rows</h2>
                <p className="mt-1 text-sm text-slate-400">
                  These are the live comparison rows that would qualify cleanly right now. They are not historical settled picks
                  unless they also exist in the shadow tracker above.
                </p>
              </div>
            </div>
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead className="text-left text-slate-500">
                  <tr className="border-b border-slate-800">
                    <th className="px-3 py-3 font-medium">League</th>
                    <th className="px-3 py-3 font-medium">Player</th>
                    <th className="px-3 py-3 font-medium">Fixture</th>
                    <th className="px-3 py-3 font-medium">Odds</th>
                    <th className="px-3 py-3 font-medium">Fair</th>
                    <th className="px-3 py-3 font-medium">EV</th>
                    <th className="px-3 py-3 font-medium">XI</th>
                    <th className="px-3 py-3 font-medium">Hist Min</th>
                  </tr>
                </thead>
                <tbody>
                  {highRows.map((row) => (
                    <tr key={`${row.player_name}-${row.match_date}-${row.bookmaker}`} className="border-b border-slate-900/80">
                      <td className="px-3 py-3 text-xs text-slate-500">{row.competition || row.league || "n/a"}</td>
                      <td className="px-3 py-3">
                        <div className="font-medium text-slate-100">{row.player_name}</div>
                        <div className="text-xs text-slate-500">{row.player_team}</div>
                      </td>
                      <td className="px-3 py-3 text-slate-300">{row.player_team} vs {row.opponent}</td>
                      <td className="px-3 py-3 text-slate-300">{formatDecimal(parseFloatMaybe(row.odds_decimal), 2)}</td>
                      <td className="px-3 py-3 text-slate-300">{formatDecimal(parseFloatMaybe(row.model_fair_odds_atgs), 2)}</td>
                      <td className="px-3 py-3 text-emerald-300">{formatPct((parseFloatMaybe(row.ev) ?? 0) * 100, 1)}</td>
                      <td className="px-3 py-3 text-xs text-slate-400">{formatLineupLabel(row)}</td>
                      <td className="px-3 py-3 text-slate-400">{formatSigned(parseFloatMaybe(row.historical_minutes), 0)}</td>
                    </tr>
                  ))}
                  {highRows.length === 0 ? (
                    <tr>
                      <td colSpan={8} className="px-3 py-6 text-center text-slate-500">No clean public-ready rows in the latest run.</td>
                    </tr>
                  ) : null}
                </tbody>
              </table>
            </div>
          </section>

          <section className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
            <div className="mb-4 flex items-start justify-between gap-4">
              <div>
                <h2 className="text-lg font-semibold text-slate-100">Current caveated rows</h2>
                <p className="mt-1 text-sm text-slate-400">
                  These are the live pre-lineup ideas: expected-XI simulations, no-XI reads, or weaker resolver cases that still need confirmation.
                </p>
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
                  <div className="mt-2 text-xs text-slate-500">{formatLineupLabel(row)}</div>
                  <div className="mt-2 text-xs text-slate-500">{row.confidence_reason}</div>
                </div>
              ))}
              {caveatRows.length === 0 ? (
                <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-sm text-slate-500">No caveated signals in the latest run.</div>
              ) : null}
            </div>
          </section>
        </div>

        <section className="mb-8 rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Shadow tracker history</h2>
              <p className="mt-1 text-sm text-slate-400">
                This is the actual historical record for public-ready goalscorer picks. Right now it is almost empty because
                the tracker only logs high-confidence starters after the lineup rerun, and we have not built a settled sample yet.
              </p>
            </div>
            <Link
              href="/anytime-goalscorer"
              className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300"
            >
              Public preview
            </Link>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-6">
            <Stat label="Tracked Signals" value={`${shadowSummary.signals}`} />
            <Stat label="Settled" value={`${shadowSummary.settled}`} />
            <Stat label="Open" value={`${shadowSummary.open}`} tone="text-amber-300" />
            <Stat label="W/L/V" value={formatWLV(shadowSummary.wins, shadowSummary.losses, shadowSummary.voids)} tone="text-slate-200" />
            <Stat label="ROI" value={formatPct(shadowSummary.roi, 1)} tone={shadowSummary.roi >= 0 ? "text-emerald-300" : "text-rose-300"} />
            <Stat label="P/L Units" value={formatSigned(shadowSummary.pnlUnits, 2)} tone={shadowSummary.pnlUnits >= 0 ? "text-emerald-300" : "text-rose-300"} />
          </div>

          <div className="mt-4 grid gap-6 xl:grid-cols-[0.9fr_1.1fr]">
            <div className="rounded-2xl border border-slate-800/80 bg-slate-950/35 p-4">
              <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">What counts as public-high history</h3>
              <p className="mt-3 text-sm leading-6 text-slate-400">
                Only rows that pass the high-confidence filter and confirm as starters get written into the shadow tracker. So
                this section is the real historical record for eventual public picks, not the whole comparison board.
              </p>
              <div className="mt-4 rounded-xl border border-slate-800/80 bg-slate-950/60 p-3 text-sm text-slate-300">
                Win rate {formatPct(shadowSummary.winRate, 1)} | voids are typically zero because bench and not-in-squad rows are filtered before logging.
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800/80 bg-slate-950/35 p-4">
              <h3 className="text-sm font-semibold uppercase tracking-[0.18em] text-slate-400">Latest tracked rows</h3>
              {shadowRows.length === 0 ? (
                <div className="mt-3 rounded-xl border border-slate-800/80 bg-slate-950/50 p-4 text-sm leading-6 text-slate-500">
                  No goalscorer shadow signals have been logged yet. The live monitor can still show current public-ready rows,
                  but there is no historical shadow sample to judge yet.
                </div>
              ) : (
                <div className="mt-3 space-y-3">
                  {openShadowRows.slice(0, 3).map((row) => (
                    <div key={`open-${row.date}-${row.player}-${row.match}`} className="rounded-xl border border-emerald-500/15 bg-emerald-500/5 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-medium text-slate-100">{row.player}</div>
                          <div className="text-sm text-slate-400">{row.match}</div>
                        </div>
                        <div className="text-sm font-medium text-emerald-300">EV {formatPct((parseFloatMaybe(row.ev) ?? 0) * 100, 1)}</div>
                      </div>
                    </div>
                  ))}
                  {settledShadowRows.slice(0, 2).map((row) => (
                    <div key={`settled-${row.date}-${row.player}-${row.match}`} className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3">
                      <div className="flex items-start justify-between gap-3">
                        <div>
                          <div className="font-medium text-slate-100">{row.player}</div>
                          <div className="text-sm text-slate-400">{row.match}</div>
                        </div>
                        <div className={(row.bet_outcome ?? "").toLowerCase() === "won" ? "text-sm font-medium text-emerald-300" : "text-sm font-medium text-rose-300"}>
                          {(row.bet_outcome ?? "open").toUpperCase()}
                        </div>
                      </div>
                    </div>
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="mb-8 rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
          <div className="mb-5 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Fixture lineup view</h2>
              <p className="mt-1 text-sm text-slate-400">
                Upcoming fixtures only, capped to the next three days. Teams are grouped by role, with player prices,
                fair odds and EV shown in a readable list rather than a pitch diagram.
              </p>
            </div>
          </div>

          <div className="space-y-6">
            {fixtures.map((fixture) => (
              <div key={fixture.key} className="rounded-2xl border border-slate-800/80 bg-slate-950/35 p-4">
                <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                  <div>
                    <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-emerald-300">
                      {fixture.competition || fixture.leagueLabel}
                    </div>
                    <h3 className="text-lg font-semibold text-white">{fixture.homeTeam} vs {fixture.awayTeam}</h3>
                    <p className="text-sm text-slate-400">{fixture.matchDate} | {fixture.bookmaker}</p>
                  </div>
                  <div className="rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-300">
                    {fixture.homeRows.length + fixture.awayRows.length} matched player prices
                  </div>
                </div>

                <div className="grid gap-5 xl:grid-cols-2">
                  {(() => {
                    const lineup = lineupMap.get(`${fixture.leagueKey}|${teamKey(fixture.homeTeam)}|${teamKey(fixture.awayTeam)}`);
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
                No upcoming fixture groups in the next three days.
              </div>
            ) : null}
          </div>
        </section>

        <section className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
          <div className="mb-4 flex items-start justify-between gap-4">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Raw monitor summary</h2>
              <p className="mt-1 text-sm text-slate-400">Direct text output from the latest comparison run.</p>
            </div>
          </div>
          <pre className="overflow-x-auto whitespace-pre-wrap rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-xs leading-6 text-slate-300">
            {rawMonitorSummary || "Missing goalscorer live summary."}
          </pre>
        </section>
      </div>
    </div>
  );
}

