import Link from "next/link";
import { notFound } from "next/navigation";
import {
  readGoalscorerLiveFile,
  readGoalscorerLiveJson,
  readGoalscorerLiveMtime,
  readGoalscorerLiveSnapshotGeneratedAt,
} from "@/lib/goalscorer-live-files";
import { readPenaltyReviewState } from "@/lib/goalscorer-penalty-review-state";
import { PenaltyReviewActions } from "./PenaltyReviewActions";

type CsvRow = Record<string, string>;
type FixtureGroup = {
  key: string;
  leagueKey: string;
  leagueLabel: string;
  competition: string;
  matchDate: string;
  kickoff: string;
  bookmaker: string;
  homeTeam: string;
  awayTeam: string;
  homeRows: CsvRow[];
  awayRows: CsvRow[];
};
type LineupPlayer = {
  name: string;
  position: string;
  positionId?: number;
};
type LiveBoardPayload = {
  schema_version?: number;
  generated_at?: string;
  league?: string;
  row_count?: number;
  stats?: Record<string, number | string>;
  fixtures?: Array<Record<string, unknown>>;
  rows?: Array<Record<string, unknown>>;
};
type FixtureHealth = {
  league: string;
  match_date: string;
  home_team: string;
  away_team: string;
  competition?: string;
  bookmaker?: string;
  lineup_input?: string;
  trust_tier?: string;
  corruption_score?: string;
  corruption_flags?: string[];
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
  pending: number;
  open: number;
  wins: number;
  losses: number;
  voids: number;
  roi: number;
  winRate: number;
  pnlUnits: number;
};

type ShadowLeagueDataset = {
  key: string;
  label: string;
  file: string;
  rows: CsvRow[];
  mtime: string | null;
};

type LeagueScoreRow = {
  key: string;
  label: string;
  statusLabel: string;
  statusClassName: string;
  statusDetail?: string;
  updatedAt: string | null;
  liveRows: number;
  publicNow: number;
  shadowNow: number;
  cleanFixtures: number;
  degradedFixtures: number;
  quarantinedFixtures: number;
  trackedSignals: number;
  settledSignals: number;
  openSignals: number;
  wins: number;
  losses: number;
  voids: number;
  roi: number;
  pnlUnits: number;
};

type PenaltyReviewRow = {
  date?: string;
  league?: string;
  review_source?: string;
  match?: string;
  team?: string;
  opponent?: string;
  actual_taker?: string;
  actual_role_pre_match?: string;
  penalties_attempted?: number | string;
  penalties_scored?: number | string;
  distinct_takers_in_match?: number | string;
  minute?: string;
  event_type?: string;
  event_result?: string;
  primary_pre_match?: string;
  secondary_pre_match?: string;
  tertiary_pre_match?: string;
  primary_lineup_status?: string;
  secondary_lineup_status?: string;
  tertiary_lineup_status?: string;
  active_taker_pre_match?: string;
  active_slot_pre_match?: string;
  team_lineup_status?: string;
  review_type?: string;
  review_priority?: string;
  editorial_note?: string;
  context_generated_at?: string;
  context_source_path?: string;
};

type PenaltyReviewPayload = {
  schema_version?: number;
  generated_at?: string;
  row_count?: number;
  rows?: PenaltyReviewRow[];
};

type GoalscorerMonitorRow = {
  key: string;
  status: "PUBLIC" | "SHADOW";
  league: string;
  player: string;
  match: string;
  kickoff: string;
  lineupShort: string;
  lineupLabel: string;
  odds?: number;
  fair?: number;
  edgePct?: number;
  row: CsvRow;
};

export const dynamic = "force-dynamic";

const MODEL_MONITOR_PUBLIC =
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
const MODEL_MONITOR_ENABLED =
  MODEL_MONITOR_PUBLIC || process.env.VERCEL_ENV === "preview";
const GOALSCORER_ODDS_HISTORY_FILE = "data/goalscorer/goalscorer-odds-history.csv";
const SHADOW_SIGNAL_CONFIGS = [
  { key: "serie-a", label: "Serie A", file: "data/goalscorer/goalscorer-shadow-signals.csv" },
  { key: "epl", label: "Premier League", file: "data/goalscorer/epl-shadow-signals.csv" },
  { key: "la-liga", label: "La Liga", file: "data/goalscorer/la-liga-shadow-signals.csv" },
  { key: "bundesliga", label: "Bundesliga", file: "data/goalscorer/bundesliga-shadow-signals.csv" },
  { key: "ligue-1", label: "Ligue 1", file: "data/goalscorer/ligue-1-shadow-signals.csv" },
] as const;
const LIVE_COMPARE_CONFIGS = [
  {
    key: "serie-a",
    label: "Serie A",
    comparisonJson: "data/goalscorer/live-board.json",
    comparisonCsv: "data/goalscorer/goalscorer-live-comparison.csv",
    comparisonTxt: "data/goalscorer/goalscorer-live-comparison.txt",
    lineupsJson: "data/goalscorer/confirmed-lineups.json",
    penaltyReviewJson: "data/goalscorer/penalty-duty-review.json",
    livePenaltyReviewJson: "data/goalscorer/penalty-duty-live-review.json",
  },
  {
    key: "epl",
    label: "Premier League",
    comparisonJson: "data/goalscorer/epl/live-board.json",
    comparisonCsv: "data/goalscorer/epl/goalscorer-live-comparison.csv",
    comparisonTxt: "data/goalscorer/epl/goalscorer-live-comparison.txt",
    lineupsJson: "data/goalscorer/epl-confirmed-lineups.json",
    penaltyReviewJson: "data/goalscorer/epl-penalty-duty-review.json",
    livePenaltyReviewJson: "data/goalscorer/epl-penalty-duty-live-review.json",
  },
  {
    key: "la-liga",
    label: "La Liga",
    comparisonJson: "data/goalscorer/la-liga/live-board.json",
    comparisonCsv: "data/goalscorer/la-liga/goalscorer-live-comparison.csv",
    comparisonTxt: "data/goalscorer/la-liga/goalscorer-live-comparison.txt",
    lineupsJson: "data/goalscorer/la-liga-confirmed-lineups.json",
    penaltyReviewJson: "data/goalscorer/la-liga-penalty-duty-review.json",
    livePenaltyReviewJson: "data/goalscorer/la-liga-penalty-duty-live-review.json",
  },
  {
    key: "bundesliga",
    label: "Bundesliga",
    comparisonJson: "data/goalscorer/bundesliga/live-board.json",
    comparisonCsv: "data/goalscorer/bundesliga/goalscorer-live-comparison.csv",
    comparisonTxt: "data/goalscorer/bundesliga/goalscorer-live-comparison.txt",
    lineupsJson: "data/goalscorer/bundesliga-confirmed-lineups.json",
    penaltyReviewJson: "data/goalscorer/bundesliga-penalty-duty-review.json",
    livePenaltyReviewJson: "data/goalscorer/bundesliga-penalty-duty-live-review.json",
  },
  {
    key: "ligue-1",
    label: "Ligue 1",
    comparisonJson: "data/goalscorer/ligue-1/live-board.json",
    comparisonCsv: "data/goalscorer/ligue-1/goalscorer-live-comparison.csv",
    comparisonTxt: "data/goalscorer/ligue-1/goalscorer-live-comparison.txt",
    lineupsJson: "data/goalscorer/ligue-1-confirmed-lineups.json",
    penaltyReviewJson: "data/goalscorer/ligue-1-penalty-duty-review.json",
    livePenaltyReviewJson: "data/goalscorer/ligue-1-penalty-duty-live-review.json",
  },
] as const;
const TEAM_ALIASES: Record<string, string> = {
  "ac milan": "milan",
  milan: "milan",
  inter: "inter",
  "inter milan": "inter",
  "inter milano": "inter",
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
  "ssc napoli": "napoli",
  napoli: "napoli",
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
  udinese: "udinese",
  "udinese calcio": "udinese",
  "juventus turin": "juventus",
  juventus: "juventus",
  "parma calcio": "parma",
  torino: "torino",
  "torino fc": "torino",
  burnley: "burnley",
  "burnley fc": "burnley",
  bournemouth: "bournemouth",
  "afc bournemouth": "bournemouth",
  chelsea: "chelsea",
  "chelsea fc": "chelsea",
  everton: "everton",
  "everton fc": "everton",
  fulham: "fulham",
  "fulham fc": "fulham",
  liverpool: "liverpool",
  "liverpool fc": "liverpool",
  "leeds united": "leeds",
  "brighton hove albion": "brighton hove albion",
  "brentford fc": "brentford",
  "tsg hoffenheim": "hoffenheim",
  hoffenheim: "hoffenheim",
  "vfl wolfsburg": "wolfsburg",
  wolfsburg: "wolfsburg",
  "1 fc koln": "fc cologne",
  "1 fc heidenheim": "fc heidenheim",
  "1 fc cologne": "fc cologne",
  "atalanta bc": "atalanta",
  "us lecce": "lecce",
  "sunderland afc": "sunderland",
  "fc st pauli": "st pauli",
  "sc freiburg": "freiburg",
  "fc augsburg": "augsburg",
  "vfb stuttgart": "stuttgart",
  "toulouse fc": "toulouse",
  "fc lorient": "lorient",
  "ogc nice": "nice",
  "racing club de lens": "lens",
  "angers sco": "angers",
  "aj auxerre": "auxerre",
  "stade brest 29": "brest",
  "real betis": "real betis",
  "real betis seville": "real betis",
  "real betis balompie": "real betis",
  espanyol: "espanyol",
  "rcd espanyol": "espanyol",
  "espanyol barcelona": "espanyol",
  "real sociedad": "real sociedad",
  "real sociedad san sebastian": "real sociedad",
  "real sociedad de futbol": "real sociedad",
  elche: "elche",
  "elche cf": "elche",
  levante: "levante",
  "levante ud": "levante",
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

function stringifyCell(value: unknown): string {
  if (value == null) return "";
  if (typeof value === "string") return value;
  if (typeof value === "number" || typeof value === "boolean") return String(value);
  return JSON.stringify(value);
}

function parseLiveBoardRows(payload: LiveBoardPayload | null): CsvRow[] {
  const rows = payload?.rows;
  if (!Array.isArray(rows)) return [];
  return rows.map((row) => {
    const normalized: CsvRow = {};
    for (const [key, value] of Object.entries(row)) {
      normalized[key] = stringifyCell(value);
    }
    return normalized;
  });
}

function parseLiveBoardFixtures(payload: LiveBoardPayload | null, leagueKey: string): FixtureHealth[] {
  const fixtures = payload?.fixtures;
  if (!Array.isArray(fixtures)) return [];
  return fixtures.map((fixture) => {
    const normalized: Record<string, unknown> = {};
    for (const [key, value] of Object.entries(fixture)) {
      normalized[key] = value;
    }
    return {
      league: String(normalized.league ?? leagueKey),
      match_date: String(normalized.match_date ?? ""),
      home_team: String(normalized.home_team ?? ""),
      away_team: String(normalized.away_team ?? ""),
      competition: String(normalized.competition ?? ""),
      bookmaker: String(normalized.bookmaker ?? ""),
      lineup_input: String(normalized.lineup_input ?? ""),
      trust_tier: String(normalized.trust_tier ?? ""),
      corruption_score: stringifyCell(normalized.corruption_score),
      corruption_flags: Array.isArray(normalized.corruption_flags)
        ? normalized.corruption_flags.map((item) => stringifyCell(item)).filter(Boolean)
        : [],
    };
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
        home_starters?: Array<{ name?: string; role_group?: string; position_id?: number | string }>;
        away_starters?: Array<{ name?: string; role_group?: string; position_id?: number | string }>;
        home_players?: string[];
        away_players?: string[];
      }>;
    };
    const fixtures = (payload.fixtures ?? []).map((fixture): FixtureLineup | null => {
        const homeTeam = decodeHtml(fixture.home_team ?? "").trim();
        const awayTeam = decodeHtml(fixture.away_team ?? "").trim();
        const homeStarterEntries = fixture.home_starters ?? [];
        const awayStarterEntries = fixture.away_starters ?? [];
        const homePlayers =
          homeStarterEntries.length > 0
            ? homeStarterEntries.map((entry) => ({
                name: decodeHtml(entry.name ?? "").trim(),
                position: decodeHtml(entry.role_group ?? "").trim(),
                positionId: Number.isFinite(Number(entry.position_id)) ? Number(entry.position_id) : undefined,
              }))
            : (fixture.home_players ?? []).map((name) => ({
                name: decodeHtml(name).trim(),
                position: "",
                positionId: undefined,
              }));
        const awayPlayers =
          awayStarterEntries.length > 0
            ? awayStarterEntries.map((entry) => ({
                name: decodeHtml(entry.name ?? "").trim(),
                position: decodeHtml(entry.role_group ?? "").trim(),
                positionId: Number.isFinite(Number(entry.position_id)) ? Number(entry.position_id) : undefined,
              }))
            : (fixture.away_players ?? []).map((name) => ({
                name: decodeHtml(name).trim(),
                position: "",
                positionId: undefined,
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
      });
    return fixtures.filter((fixture): fixture is FixtureLineup => fixture !== null);
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

function formatDateTime(value?: string | null): string {
  if (!value) return "missing";
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;
  return parsed.toLocaleString("en-GB", {
    dateStyle: "medium",
    timeStyle: "short",
  });
}

function isDateOnly(value?: string | null): boolean {
  return Boolean(value && /^\d{4}-\d{2}-\d{2}$/.test(value.trim()));
}

function formatKickoff(value?: string | null): string {
  if (!value) return "TBC";
  if (isDateOnly(value)) return formatShortDate(value);
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value;
  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    weekday: "short",
    day: "numeric",
    month: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(new Date(parsed));
}

function isoDateForValueInTimezone(value?: string | null, timeZone = "Europe/London"): string | null {
  if (!value) return null;
  if (isDateOnly(value)) return value.trim().slice(0, 10);
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return null;
  const parts = new Intl.DateTimeFormat("en-GB", {
    timeZone,
    year: "numeric",
    month: "2-digit",
    day: "2-digit",
  }).formatToParts(parsed);
  const year = parts.find((part) => part.type === "year")?.value ?? "0000";
  const month = parts.find((part) => part.type === "month")?.value ?? "01";
  const day = parts.find((part) => part.type === "day")?.value ?? "01";
  return `${year}-${month}-${day}`;
}

function formatOpsKickoff(value?: string | null, todayIso = isoDateInTimezone("Europe/London")): string {
  if (!value) return "TBC";
  if (isDateOnly(value)) return formatShortDate(value);
  const parsed = new Date(value);
  if (Number.isNaN(parsed.getTime())) return value;

  const dateIso = isoDateForValueInTimezone(value);
  const tomorrowIso = addDaysIso(todayIso, 1);
  const timeLabel = new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(parsed);

  if (dateIso === todayIso) return timeLabel;
  if (dateIso === tomorrowIso) return `Tomorrow ${timeLabel}`;

  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    weekday: "short",
    hour: "2-digit",
    minute: "2-digit",
    hourCycle: "h23",
  }).format(parsed);
}

function kickoffUrgencyMeta(value?: string | null): { label: string; className: string; startsSoon: boolean } {
  if (!value || isDateOnly(value)) {
    return {
      label: "scheduled",
      className: "text-slate-400",
      startsSoon: false,
    };
  }

  const kickoff = Date.parse(value);
  if (Number.isNaN(kickoff)) {
    return {
      label: "scheduled",
      className: "text-slate-400",
      startsSoon: false,
    };
  }

  const minutesUntil = Math.round((kickoff - Date.now()) / 60000);
  if (minutesUntil < 0) {
    return {
      label: "started",
      className: "text-rose-300",
      startsSoon: false,
    };
  }
  if (minutesUntil < 30) {
    return {
      label: "<30m",
      className: "font-semibold text-rose-300",
      startsSoon: true,
    };
  }
  if (minutesUntil < 60) {
    return {
      label: "<60m",
      className: "font-semibold text-amber-300",
      startsSoon: true,
    };
  }
  if (minutesUntil < 180) {
    return {
      label: "today",
      className: "text-slate-200",
      startsSoon: false,
    };
  }
  return {
    label: "later",
    className: "text-slate-400",
    startsSoon: false,
  };
}

function formatUnits(value?: number, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}u`;
}

function metricTone(value?: number): string {
  if (value == null || Number.isNaN(value)) return "text-slate-300";
  if (value > 0) return "text-emerald-300";
  if (value < 0) return "text-rose-300";
  return "text-slate-300";
}

function freshnessBadge(value?: string | null): { label: string; className: string } {
  if (!value) {
    return { label: "missing", className: "text-rose-300" };
  }
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) {
    return { label: "unknown", className: "text-amber-300" };
  }
  const ageMinutes = Math.max(0, Math.round((Date.now() - parsed) / 60000));
  if (ageMinutes <= 20) {
    return { label: `${ageMinutes}m old`, className: "text-emerald-300" };
  }
  if (ageMinutes <= 60) {
    return { label: `${ageMinutes}m old`, className: "text-amber-300" };
  }
  return { label: `${ageMinutes}m old`, className: "text-rose-300" };
}

function formatWLV(wins: number, losses: number, voids: number): string {
  return `${wins}/${losses}/${voids}`;
}

function formatShortDate(value?: string): string {
  if (!value) return "n/a";
  const parsed = Date.parse(value);
  if (Number.isNaN(parsed)) return value.slice(0, 10) || value;
  return new Date(parsed).toLocaleDateString("en-GB", {
    day: "2-digit",
    month: "short",
    year: "numeric",
  });
}

function kickoffSortValue(value?: string | null): number {
  if (!value) return Number.MAX_SAFE_INTEGER;
  if (isDateOnly(value)) {
    const parsedDateOnly = Date.parse(`${value}T23:59:59Z`);
    return Number.isNaN(parsedDateOnly) ? Number.MAX_SAFE_INTEGER : parsedDateOnly;
  }
  const parsed = Date.parse(value);
  return Number.isNaN(parsed) ? Number.MAX_SAFE_INTEGER : parsed;
}

function extractEventId(value?: string): string {
  const match = (value ?? "").match(/(?:^|;)event_id=([^;]+)/);
  return match?.[1]?.trim() ?? "";
}

function buildKickoffLookup(text: string | null, eventIds: Set<string>): Map<string, string> {
  const lookup = new Map<string, string>();
  if (!text || eventIds.size === 0) return lookup;

  const lines = text
    .split(/\r?\n/)
    .map((line) => line.trimEnd())
    .filter(Boolean);
  if (lines.length < 2) return lookup;

  const headers = parseCsvLine(lines[0]);
  const eventIdIndex = headers.indexOf("event_id");
  const kickoffIndex = headers.indexOf("kickoff_at");
  if (eventIdIndex === -1 || kickoffIndex === -1) return lookup;

  for (const line of lines.slice(1)) {
    const values = parseCsvLine(line);
    const eventId = (values[eventIdIndex] ?? "").trim();
    if (!eventIds.has(eventId) || lookup.has(eventId)) continue;
    const kickoff = (values[kickoffIndex] ?? "").trim();
    if (!kickoff) continue;
    lookup.set(eventId, kickoff);
    if (lookup.size >= eventIds.size) break;
  }

  return lookup;
}

function resolveRowKickoff(row: CsvRow, kickoffLookup: Map<string, string>): string {
  const explicitKickoff = (row.kickoff ?? "").trim();
  if (explicitKickoff) return explicitKickoff;

  const eventId = extractEventId(row.notes);
  if (eventId) {
    const archiveKickoff = kickoffLookup.get(eventId);
    if (archiveKickoff) return archiveKickoff;
  }

  return (row.match_date ?? "").trim();
}

function compareRowsByKickoffThenEv(left: CsvRow, right: CsvRow, kickoffLookup: Map<string, string>): number {
  const kickoffDiff =
    kickoffSortValue(resolveRowKickoff(left, kickoffLookup)) -
    kickoffSortValue(resolveRowKickoff(right, kickoffLookup));
  if (kickoffDiff !== 0) return kickoffDiff;
  return (parseFloatMaybe(right.ev) ?? 0) - (parseFloatMaybe(left.ev) ?? 0);
}

function priorityRank(priority?: string): number {
  if (priority === "high") return 3;
  if (priority === "medium") return 2;
  return 1;
}

function penaltyReviewSourceRank(source?: string): number {
  if (source === "settled_logs") return 2;
  if (source === "fotmob_live") return 1;
  return 0;
}

function penaltyReviewSourceLabel(source?: string): string {
  if (source === "settled_logs") return "Settled log";
  if (source === "fotmob_live") return "Live event";
  return "Review";
}

function penaltyReviewTakerKey(name?: string): string {
  const normalized = normText(name);
  if (!normalized) return "";
  const tokens = normalized.split(" ").filter(Boolean);
  return tokens[tokens.length - 1] || normalized;
}

function penaltyReviewIdentity(row: PenaltyReviewRow): string {
  return [
    row.date ?? "",
    row.league ?? "",
    teamKey(row.team ?? ""),
    teamKey(row.opponent ?? ""),
    penaltyReviewTakerKey(row.actual_taker ?? ""),
  ]
    .map((part) => part.trim().toLowerCase())
    .join("|");
}

function penaltyReviewIsOlderThan(row: PenaltyReviewRow, cutoffIso: string): boolean {
  const rowDate = (row.date ?? "").slice(0, 10);
  if (!rowDate) return false;
  return rowDate < cutoffIso;
}

function penaltyReviewDaysUntilStale(row: PenaltyReviewRow, todayIso: string): number | null {
  const rowDate = (row.date ?? "").slice(0, 10);
  if (!rowDate) return null;
  const rowStamp = Date.parse(`${rowDate}T00:00:00Z`);
  const todayStamp = Date.parse(`${todayIso}T00:00:00Z`);
  if (!Number.isFinite(rowStamp) || !Number.isFinite(todayStamp)) return null;
  const ageDays = Math.floor((todayStamp - rowStamp) / 86400000);
  return Math.max(0, 7 - ageDays);
}

function mergePenaltyReviewRows(rows: PenaltyReviewRow[]): PenaltyReviewRow[] {
  const merged = new Map<string, PenaltyReviewRow>();
  for (const row of rows) {
    const key = penaltyReviewIdentity(row);
    if (!key.replace(/\|/g, "")) continue;
    const existing = merged.get(key);
    if (!existing) {
      merged.set(key, row);
      continue;
    }

    const currentPriority = priorityRank(row.review_priority);
    const existingPriority = priorityRank(existing.review_priority);
    const currentSourceRank = penaltyReviewSourceRank(row.review_source);
    const existingSourceRank = penaltyReviewSourceRank(existing.review_source);
    const currentWins =
      currentPriority > existingPriority ||
      (currentPriority === existingPriority && currentSourceRank > existingSourceRank);

    const preferred = currentWins ? row : existing;
    const fallback = currentWins ? existing : row;
    const next = { ...fallback, ...preferred };

    if (!next.minute) next.minute = existing.minute || row.minute || "";
    if (!next.event_type) next.event_type = existing.event_type || row.event_type || "";
    if (!next.event_result) next.event_result = existing.event_result || row.event_result || "";
    if (!next.context_generated_at) next.context_generated_at = existing.context_generated_at || row.context_generated_at || "";
    if (!next.context_source_path) next.context_source_path = existing.context_source_path || row.context_source_path || "";

    merged.set(key, next);
  }
  return [...merged.values()];
}

function penaltyPriorityBadge(priority?: string): string {
  if (priority === "high") return "border-rose-500/30 bg-rose-500/10 text-rose-200";
  if (priority === "medium") return "border-amber-500/30 bg-amber-500/10 text-amber-200";
  return "border-slate-700/80 bg-slate-900/70 text-slate-300";
}

function penaltyReviewTone(reviewType?: string): string {
  if (reviewType === "backup_jump_with_primary_available" || reviewType === "unranked_taker" || reviewType === "multiple_penalties_split") {
    return "border-rose-500/20 bg-rose-500/8";
  }
  if (reviewType === "expected_backup_shift" || reviewType === "needs_manual_review") {
    return "border-amber-500/20 bg-amber-500/8";
  }
  return "border-slate-800/80 bg-slate-950/35";
}

function humanizeToken(value?: string): string {
  return (value ?? "")
    .split("_")
    .filter(Boolean)
    .map((part) => part.charAt(0).toUpperCase() + part.slice(1))
    .join(" ");
}

function formatLineupLabel(row: CsvRow): string {
  const canonical = (row.lineup_status ?? "").trim().toLowerCase();
  if (canonical === "confirmed_starter") return "Confirmed starter";
  if (canonical === "expected_starter") return "FotMob Expected XI";
  if (canonical === "confirmed_bench") return "Confirmed bench";
  if (canonical === "expected_bench") return "Expected bench";
  if (canonical === "not_in_squad") return "Out of squad";
  if (canonical === "expected_out") return "Expected out";
  if (row.lineup_input === "confirmed_xi") return "Confirmed XI";
  if (row.lineup_input === "expected_xi") return "FotMob Expected XI";
  return "No XI yet";
}

function lineupShortLabel(row: CsvRow): string {
  const canonical = (row.lineup_status ?? "").trim().toLowerCase();
  if (canonical === "confirmed_starter") return "✓";
  if (canonical === "expected_starter") return "~";
  if (canonical === "confirmed_bench" || canonical === "expected_bench") return "B";
  if (canonical === "not_in_squad" || canonical === "expected_out") return "✗";
  return "?";
}

function leagueShortLabel(value?: string): string {
  const normalized = (value ?? "").trim().toLowerCase();
  if (normalized.includes("premier league")) return "PL";
  if (normalized.includes("serie a")) return "SA";
  if (normalized.includes("la liga")) return "LL";
  if (normalized.includes("bundesliga")) return "BL";
  if (normalized.includes("ligue 1")) return "L1";
  return (value ?? "n/a").slice(0, 3).toUpperCase();
}

function toneForAction(action?: string): string {
  if (action === "surface") return "text-emerald-300";
  if (action === "shadow_track") return "text-amber-300";
  if (action === "surface_with_caveat") return "text-amber-300";
  return "text-slate-400";
}

const FULL_BACK_POSITION_IDS = new Set([32, 38, 62, 68, 71, 72, 78, 79]);
const CENTRE_BACK_POSITION_IDS = new Set([33, 34, 35, 36, 37]);
const MIDFIELD_POSITION_IDS = new Set([64, 65, 66, 73, 74, 75, 76, 77, 84, 85, 86]);
const ATTACKING_MID_WIDE_POSITION_IDS = new Set([82, 83, 87, 88]);

function positionBand(position?: string, positionId?: number): "gk" | "cb" | "wide" | "mid" | "att" | "util" {
  const text = (position ?? "").split(",")[0].trim().toUpperCase();
  if (!text) return "util";
  if (text.startsWith("GK")) return "gk";
  if (FULL_BACK_POSITION_IDS.has(positionId ?? -1)) return "wide";
  if (CENTRE_BACK_POSITION_IDS.has(positionId ?? -1)) return "cb";
  if (MIDFIELD_POSITION_IDS.has(positionId ?? -1)) return "mid";
  if (ATTACKING_MID_WIDE_POSITION_IDS.has(positionId ?? -1)) return "mid";
  if (text === "DMC" || text === "MID" || text === "AM") return "mid";
  if (text === "DEF") return "cb";
  if (text === "FW") return "att";
  return "util";
}

function positionLabel(position?: string, positionId?: number): string {
  const id = positionId ?? -1;
  const text = (position ?? "").trim().toUpperCase();
  const labels: Record<number, string> = {
    11: "GK",
    32: "RB",
    33: "RCB",
    34: "RCB",
    35: "CB",
    36: "LCB",
    37: "LCB",
    38: "LB",
    62: "RM/WB",
    64: "DM",
    65: "DM",
    66: "DM",
    68: "LM/WB",
    71: "RWB",
    72: "RM",
    73: "RCM",
    74: "CM",
    75: "CM",
    76: "CM",
    77: "LCM",
    78: "LM",
    79: "LWB",
    82: "RAM",
    83: "RW/AM",
    84: "AM",
    85: "AM",
    86: "AM",
    87: "LW/AM",
    88: "LAM",
    103: "RF",
    104: "ST",
    105: "ST",
    106: "ST",
    107: "LF",
    115: "ST",
  };
  if (labels[id]) return labels[id];
  if (text === "DMC") return "DM";
  if (text === "MID") return "MID";
  if (text === "AM") return "AM";
  if (text === "DEF") return "DEF";
  if (text === "FW") return "FW";
  if (text === "GK") return "GK";
  return text || "UTIL";
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

function fixtureHealthKey(leagueKey: string, matchDate?: string, homeTeam?: string, awayTeam?: string): string {
  return `${leagueKey}|${matchDate ?? ""}|${teamKey(homeTeam)}|${teamKey(awayTeam)}`;
}

function fixtureTrustBadgeClass(trustTier?: string): string {
  if (trustTier === "T3") return "border-rose-500/30 bg-rose-500/10 text-rose-200";
  if (trustTier === "T2") return "border-amber-500/30 bg-amber-500/10 text-amber-200";
  return "border-emerald-500/30 bg-emerald-500/10 text-emerald-200";
}

function fixtureTrustLabel(trustTier?: string): string {
  if (trustTier === "T3") return "Lineup Quarantined";
  if (trustTier === "T2") return "Lineup Degraded";
  return "Lineup Clean";
}

function fixtureStatusLabel(fixture?: FixtureHealth): string {
  if (!fixture) return fixtureTrustLabel();
  const corruptionScore = parseFloatMaybe(fixture.corruption_score) ?? 0;
  if (fixture.trust_tier === "T2" && fixture.lineup_input === "expected_xi" && corruptionScore <= 0) {
    return "Expected XI";
  }
  if (fixture.trust_tier === "T2" && fixture.lineup_input === "none") {
    return "Awaiting Lineup";
  }
  return fixtureTrustLabel(fixture.trust_tier);
}

function fixtureHealthSummary(fixture: FixtureHealth): string {
  if (fixture.trust_tier === "T3") {
    return "Structural lineup issue detected. Keep this fixture out of trust-sensitive decisions until the feed is sane again.";
  }
  if (fixture.lineup_input === "none") {
    return "No FotMob lineup payload yet. This fixture stays soft until a real expected or confirmed XI lands.";
  }
  if (fixture.lineup_input === "expected_xi") {
    return "Expected XI only. Useful for monitoring and shadow context, but not confirmed-lineup decisions yet.";
  }
  if ((fixture.corruption_flags ?? []).length > 0) {
    return "Lineup health warning present. The fixture is still visible, but treat it as a monitor-first state.";
  }
  return "This fixture is visible in the monitor, but not in a fully confirmed clean state yet.";
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

function buildFixtureGroups(
  rows: CsvRow[],
  leagueKey: string,
  leagueLabel: string,
  kickoffLookup: Map<string, string>,
): FixtureGroup[] {
  const fixtureMap = new Map<string, FixtureGroup>();
  for (const row of rows) {
    const homeTeam = row.home_team ?? "";
    const awayTeam = row.away_team ?? "";
    if (!homeTeam || !awayTeam) continue;
    const key = `${row.match_date}|${row.bookmaker}|${homeTeam}|${awayTeam}`;
    const rowKickoff = resolveRowKickoff(row, kickoffLookup);
    const existing = fixtureMap.get(key) ?? {
      key,
      leagueKey,
      leagueLabel,
      competition: row.competition ?? leagueLabel,
      matchDate: row.match_date ?? "",
      kickoff: rowKickoff,
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
    if (kickoffSortValue(rowKickoff) < kickoffSortValue(existing.kickoff)) {
      existing.kickoff = rowKickoff;
    }
    fixtureMap.set(key, existing);
  }
  return [...fixtureMap.values()].sort((a, b) => {
    const kickoffDiff = kickoffSortValue(a.kickoff) - kickoffSortValue(b.kickoff);
    if (kickoffDiff !== 0) return kickoffDiff;
    return a.key.localeCompare(b.key);
  });
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

function fixtureInLiveWindow(
  fixture: Pick<FixtureHealth, "match_date">,
  startIso: string,
  endIso: string,
): boolean {
  const matchDate = (fixture.match_date ?? "").slice(0, 10);
  return Boolean(matchDate) && matchDate >= startIso && matchDate <= endIso;
}

function filterActiveRows(rows: CsvRow[]): CsvRow[] {
  const today = isoDateInTimezone("Europe/London");
  const horizon = addDaysIso(today, 3);
  return rows.filter((row) => {
    const matchDate = (row.match_date ?? "").slice(0, 10);
    return Boolean(matchDate) && matchDate >= today && matchDate <= horizon;
  });
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

function leagueOutputStatus(summary: Record<string, string>, hasOutput: boolean): {
  label: string;
  className: string;
  detail?: string;
} {
  if (!hasOutput) {
    return {
      label: "not run yet",
      className: "text-xs text-amber-300",
    };
  }

  const historicalRows = parseIntMaybe(summary["Historical Rows"]) ?? 0;
  const oddsRows = parseIntMaybe(summary["Odds Rows"]) ?? 0;
  const matchedRows = parseIntMaybe(summary["Matched Rows"]) ?? 0;

  if (historicalRows > 0 && oddsRows === 0 && matchedRows === 0) {
    return {
      label: "no ATGS feed",
      className: "text-xs text-amber-300",
      detail: "Source feed returned 0 current ATGS rows for this league window.",
    };
  }

  return {
    label: "live file",
    className: "text-xs text-emerald-300",
  };
}

function isSettledShadowRow(row: CsvRow): boolean {
  const value = (row.settled ?? "").trim().toLowerCase();
  return value === "1" || value === "true" || value === "yes" || value === "settled";
}

function computeShadowSummary(rows: CsvRow[]): ShadowSummary {
  const settled = rows.filter(isSettledShadowRow);
  const pendingRows = rows.filter((row) => !isSettledShadowRow(row) && shadowResultLabel(row) === "PENDING");
  const openRows = rows.filter((row) => !isSettledShadowRow(row) && shadowResultLabel(row) === "OPEN");
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
    pending: pendingRows.length,
    open: openRows.length,
    wins,
    losses,
    voids,
    roi: settled.length > 0 ? (pnlUnits / settled.length) * 100 : 0,
    winRate: settled.length > 0 ? (wins / settled.length) * 100 : 0,
    pnlUnits,
  };
}

function shadowUnsettledCount(summary: ShadowSummary): number {
  return summary.pending + summary.open;
}

function shadowRowActivityTime(row: CsvRow): number {
  const candidates = [row.settled_at, row.compared_at, row.kickoff, row.date];
  for (const candidate of candidates) {
    const parsed = Date.parse(candidate ?? "");
    if (!Number.isNaN(parsed)) return parsed;
  }
  return 0;
}

function shadowResultTone(row: CsvRow): string {
  const outcome = (row.bet_outcome ?? "").trim().toLowerCase();
  if (outcome === "won") return "text-emerald-300";
  if (outcome === "lost") return "text-rose-300";
  if (outcome === "void" || outcome === "push") return "text-slate-300";
  return "text-amber-200";
}

function shadowResultLabel(row: CsvRow): string {
  if (isSettledShadowRow(row)) {
    return (row.bet_outcome ?? "settled").toUpperCase();
  }
  const kickoff = Date.parse(row.kickoff ?? row.date ?? "");
  const hasSettlementNote = ((row.settlement_note ?? "").trim().length || 0) > 0;
  if ((!Number.isNaN(kickoff) && kickoff < Date.now()) || hasSettlementNote) {
    return "PENDING";
  }
  return "OPEN";
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

function MonitorCard({
  title,
  subtitle,
  children,
}: {
  title: string;
  subtitle?: string;
  children: React.ReactNode;
}) {
  return (
    <section className="rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
      <div className="mb-4 flex items-start justify-between gap-4">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-slate-400">{subtitle}</p> : null}
        </div>
      </div>
      {children}
    </section>
  );
}

function statusPillClass(status: GoalscorerMonitorRow["status"]): string {
  return status === "PUBLIC"
    ? "border-emerald-500/30 bg-emerald-500/10 text-emerald-300"
    : "border-slate-700/80 bg-slate-900/80 text-slate-300";
}

function CollapsibleMonitorSection({
  title,
  subtitle,
  defaultOpen = false,
  children,
}: {
  title: string;
  subtitle?: string;
  defaultOpen?: boolean;
  children: React.ReactNode;
}) {
  return (
    <details
      open={defaultOpen}
      className="group rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] shadow-[0_20px_60px_rgba(0,0,0,0.28)] open:border-slate-700"
    >
      <summary className="flex cursor-pointer list-none items-start justify-between gap-4 px-5 py-4 marker:hidden">
        <div>
          <h2 className="text-lg font-semibold text-slate-100">{title}</h2>
          {subtitle ? <p className="mt-1 text-sm text-slate-400">{subtitle}</p> : null}
        </div>
        <span className="inline-flex items-center gap-2 rounded-full border border-slate-700/80 bg-slate-950/50 px-3 py-1 text-[11px] uppercase tracking-[0.18em] text-slate-400">
          <span className="transition-transform group-open:rotate-90">▸</span>
          <span>Details</span>
        </span>
      </summary>
      <div className="border-t border-slate-800 px-5 py-5">{children}</div>
    </details>
  );
}

function LiveBetsTable({
  rows,
  todayIso,
  emptyLabel,
}: {
  rows: GoalscorerMonitorRow[];
  todayIso: string;
  emptyLabel: string;
}) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="text-left text-slate-500">
          <tr className="border-b border-slate-800">
            <th className="px-3 py-3 font-medium">Kickoff</th>
            <th className="px-3 py-3 font-medium">Player</th>
            <th className="px-3 py-3 font-medium">Match</th>
            <th className="px-3 py-3 font-medium">League</th>
            <th className="px-3 py-3 font-medium">XI</th>
            <th className="px-3 py-3 font-medium">Odds</th>
            <th className="px-3 py-3 font-medium">Fair</th>
            <th className="px-3 py-3 font-medium">Edge</th>
            <th className="px-3 py-3 font-medium">Status</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((item) => {
            const urgency = kickoffUrgencyMeta(item.kickoff);
            return (
              <tr key={item.key} className="border-b border-slate-900/80">
                <td className={`px-3 py-3 ${urgency.className}`}>
                  <div>{formatOpsKickoff(item.kickoff, todayIso)}</div>
                  <div className="mt-1 text-[11px] uppercase tracking-[0.16em] text-slate-500">{urgency.label}</div>
                </td>
                <td className="px-3 py-3">
                  <div className="font-medium text-slate-100">{item.player}</div>
                </td>
                <td className="px-3 py-3 text-slate-300">{item.match}</td>
                <td className="px-3 py-3 text-xs text-slate-400">{item.league}</td>
                <td className="px-3 py-3">
                  <span
                    title={item.lineupLabel}
                    className={`inline-flex h-7 w-7 items-center justify-center rounded-full border text-xs font-semibold ${
                      item.lineupShort === "✓"
                        ? "border-emerald-500/25 bg-emerald-500/10 text-emerald-300"
                        : item.lineupShort === "~"
                          ? "border-amber-500/25 bg-amber-500/10 text-amber-200"
                          : item.lineupShort === "✗"
                            ? "border-rose-500/25 bg-rose-500/10 text-rose-300"
                            : "border-slate-700/80 bg-slate-900/80 text-slate-300"
                    }`}
                  >
                    {item.lineupShort}
                  </span>
                </td>
                <td className="px-3 py-3 text-slate-300">{formatDecimal(item.odds, 2)}</td>
                <td className="px-3 py-3 text-slate-300">{formatDecimal(item.fair, 2)}</td>
                <td className={`px-3 py-3 font-medium ${metricTone(item.edgePct)}`}>{formatPct(item.edgePct, 1)}</td>
                <td className="px-3 py-3">
                  <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${statusPillClass(item.status)}`}>
                    {item.status}
                  </span>
                </td>
              </tr>
            );
          })}
          {rows.length === 0 ? (
            <tr>
              <td colSpan={9} className="px-3 py-6 text-center text-slate-500">
                {emptyLabel}
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function SettledRowsTable({ rows }: { rows: CsvRow[] }) {
  return (
    <div className="overflow-x-auto">
      <table className="min-w-full text-sm">
        <thead className="text-left text-slate-500">
          <tr className="border-b border-slate-800">
            <th className="px-3 py-2 font-medium">Time</th>
            <th className="px-3 py-2 font-medium">Player</th>
            <th className="px-3 py-2 font-medium">Match</th>
            <th className="px-3 py-2 font-medium">XI</th>
            <th className="px-3 py-2 font-medium">Odds / Fair</th>
            <th className="px-3 py-2 font-medium">EV</th>
            <th className="px-3 py-2 font-medium">Result</th>
          </tr>
        </thead>
        <tbody>
          {rows.map((row, idx) => (
            <tr key={`settled-${row.date}-${row.player}-${row.match}-${idx}`} className="border-b border-slate-900/80">
              <td className="px-3 py-2 text-xs text-slate-500">{formatDateTime(row.settled_at || row.compared_at || row.kickoff || row.date)}</td>
              <td className="px-3 py-2">
                <div className="font-medium text-slate-100">{row.player || "Unknown player"}</div>
                <div className="text-xs text-slate-500">{row.team || "Unknown team"}</div>
              </td>
              <td className="px-3 py-2 text-slate-300">{row.match || "Unknown match"}</td>
              <td className="px-3 py-2 text-xs text-slate-400">{humanizeToken(row.lineup_state || "unknown")}</td>
              <td className="px-3 py-2 text-slate-300">
                {parseFloatMaybe(row.best_bookmaker_odds) != null ? formatDecimal(parseFloatMaybe(row.best_bookmaker_odds), 2) : "n/a"}
                {" / "}
                {parseFloatMaybe(row.model_fair_odds) != null ? formatDecimal(parseFloatMaybe(row.model_fair_odds), 2) : "n/a"}
              </td>
              <td className={`px-3 py-2 font-medium ${(parseFloatMaybe(row.ev) ?? 0) >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
                {parseFloatMaybe(row.ev) != null ? formatPct((parseFloatMaybe(row.ev) ?? 0) * 100, 1) : "n/a"}
              </td>
              <td className={`px-3 py-2 text-xs font-semibold ${shadowResultTone(row)}`}>{shadowResultLabel(row)}</td>
            </tr>
          ))}
          {rows.length === 0 ? (
            <tr>
              <td colSpan={7} className="px-3 py-6 text-center text-slate-500">
                No settled rows in this window.
              </td>
            </tr>
          ) : null}
        </tbody>
      </table>
    </div>
  );
}

function PenaltyReviewCard({
  row,
  rowId,
  resolvedStatus,
  daysUntilStale,
}: {
  row: PenaltyReviewRow;
  rowId: string;
  resolvedStatus?: "dismissed" | "done";
  daysUntilStale?: number | null;
}) {
  const attempts = Number.parseInt(String(row.penalties_attempted ?? "0"), 10) || 0;
  const scored = Number.parseInt(String(row.penalties_scored ?? "0"), 10) || 0;
  const minuteLabel = (row.minute ?? "").trim();
  const sourceLabel = penaltyReviewSourceLabel(row.review_source);

  return (
    <div className={`rounded-2xl border p-4 ${penaltyReviewTone(row.review_type)}`}>
      <div className="flex flex-wrap items-start justify-between gap-3">
        <div>
          <div className="flex flex-wrap items-center gap-2">
            <div className="text-base font-semibold text-slate-100">{row.actual_taker || "Unknown taker"}</div>
            <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] ${penaltyPriorityBadge(row.review_priority)}`}>
              {row.review_priority || "low"}
            </span>
            <span className="inline-flex rounded-full border border-slate-700/80 bg-slate-950/70 px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-300">
              {sourceLabel}
            </span>
          </div>
          <div className="mt-1 text-sm text-slate-400">
            {row.team || "Unknown team"} vs {row.opponent || "Unknown opponent"} · {formatShortDate(row.date)}
          </div>
        </div>
        <div className="rounded-full border border-slate-700/80 bg-slate-950/70 px-3 py-1 text-xs text-slate-300">
          {humanizeToken(row.review_type)}
        </div>
      </div>

      <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-xl bg-black/15 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Pre-match primary</div>
          <div className="mt-1 text-slate-200">{row.primary_pre_match || "Untracked"}</div>
        </div>
        <div className="rounded-xl bg-black/15 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Pre-match backup</div>
          <div className="mt-1 text-slate-200">{row.secondary_pre_match || "Untracked"}</div>
        </div>
        <div className="rounded-xl bg-black/15 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Actual role</div>
          <div className="mt-1 text-slate-200">{humanizeToken(row.actual_role_pre_match || "none")}</div>
        </div>
        <div className="rounded-xl bg-black/15 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Pens</div>
          <div className="mt-1 text-slate-200">
            {attempts} attempt{attempts === 1 ? "" : "s"} · {scored} scored
          </div>
        </div>
        <div className="rounded-xl bg-black/15 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Minute</div>
          <div className="mt-1 text-slate-200">{minuteLabel || "Awaiting log"}</div>
        </div>
      </div>

      <p className="mt-3 text-sm leading-6 text-slate-300">{row.editorial_note || "No editorial note."}</p>
      <div className="mt-2 flex flex-wrap items-center gap-3 text-xs text-slate-500">
        <span>Auto-hides after 7 days if untouched.</span>
        {daysUntilStale != null ? <span>Ages out in {daysUntilStale}d.</span> : null}
      </div>
      <PenaltyReviewActions rowId={rowId} resolvedStatus={resolvedStatus} />
    </div>
  );
}

function signalRowClass(action?: string, hasRow = true): string {
  if (!hasRow) return "border-dashed border-slate-700/70 bg-slate-950/25";
  if (action === "surface") return "border-emerald-500/20 bg-emerald-500/8";
  if (action === "shadow_track") return "border-amber-500/20 bg-amber-500/8";
  if (action === "surface_with_caveat") return "border-amber-500/20 bg-amber-500/8";
  if (action === "suppress") return "border-slate-800/80 bg-slate-950/30 opacity-80";
  return "border-slate-800/80 bg-slate-950/35";
}

function signalBadge(action?: string): string {
  if (action === "surface") return "border-emerald-500/20 bg-emerald-500/10 text-emerald-300";
  if (action === "shadow_track") return "border-amber-500/20 bg-amber-500/10 text-amber-200";
  if (action === "surface_with_caveat") return "border-amber-500/20 bg-amber-500/10 text-amber-200";
  if (action === "suppress") return "border-slate-700/80 bg-slate-900/80 text-slate-500";
  return "border-slate-700/80 bg-slate-900/80 text-slate-300";
}

function effectiveMonitorAction(row?: CsvRow): string {
  if (!row) return "";
  const publicAction = (row.public_action ?? "").trim().toLowerCase();
  const shadowAction = (row.shadow_action ?? "").trim().toLowerCase();
  const legacyPublicAction = (row.legacy_public_action ?? "").trim().toLowerCase();

  if (publicAction === "surface") return "surface";
  if (shadowAction === "shadow_track") return "shadow_track";
  if (legacyPublicAction === "surface_with_caveat") return "surface_with_caveat";
  if (publicAction === "suppress") return "suppress";
  return "monitor";
}

function effectiveMonitorActionLabel(row?: CsvRow): string {
  const action = effectiveMonitorAction(row);
  if (action === "surface") return "live";
  if (action === "shadow_track") return "shadow";
  if (action === "surface_with_caveat") return "caveat";
  if (action === "suppress") return "suppressed";
  return "monitor";
}

function penaltyRoleLabel(role?: string): string {
  if (!role || role === "none") return "";
  return humanizeToken(role);
}

function penaltyComponentMeta(row?: CsvRow): { compact: string; detail: string } | null {
  if (!row) return null;
  const role = (row.penalty_role ?? "").trim().toLowerCase();
  const penaltyLambda = parseFloatMaybe(row.penalty_lambda) ?? 0;
  const penaltyShare = parseFloatMaybe(row.penalty_share) ?? 0;
  const baselinePenaltyShare = parseFloatMaybe(row.baseline_penalty_share) ?? 0;
  const baselinePenaltySample = parseFloatMaybe(row.baseline_penalty_sample) ?? 0;
  const baselinePenaltySource = (row.baseline_penalty_source ?? "").trim().toLowerCase();
  const careerPlayerPenalties = parseFloatMaybe(row.career_player_penalties) ?? 0;
  const careerTeamPenalties = parseFloatMaybe(row.career_team_penalties) ?? 0;
  const evidenceShare = parseFloatMaybe(row.penalty_evidence_share) ?? 0;
  const evidenceSample = parseFloatMaybe(row.penalty_evidence_sample) ?? 0;
  const evidenceSource = (row.penalty_evidence_source ?? "").trim().toLowerCase();
  const penaltyPrior = parseFloatMaybe(row.penalty_share_prior) ?? 0;
  const penaltyPriorWeight = parseFloatMaybe(row.penalty_share_prior_weight) ?? 0;
  const nonPenLambda = parseFloatMaybe(row.non_pen_lambda) ?? 0;

  if (role === "none" && penaltyLambda <= 0.0001 && baselinePenaltyShare <= 0.0001 && penaltyPrior <= 0.0001) {
    return null;
  }
  if (penaltyShare <= 0.01 && penaltyLambda <= 0.001) {
    return null;
  }
  if ((role === "tertiary" || role === "none") && penaltyShare < 0.08 && penaltyLambda < 0.005) {
    return null;
  }

  const detailBits = [
    role !== "none" ? `pen duty ${penaltyRoleLabel(role)}` : "pen component",
    `share ${(penaltyShare * 100).toFixed(1)}%`,
    `base ${(baselinePenaltyShare * 100).toFixed(1)}%`,
  ];

  if (penaltyPrior > 0) {
    detailBits.push(`prior ${(penaltyPrior * 100).toFixed(1)}%`);
  }
  if (penaltyPriorWeight > 0) {
    detailBits.push(`w ${penaltyPriorWeight.toFixed(1)}`);
  }
  if (baselinePenaltySource && baselinePenaltySource !== "none") {
    detailBits.push(`src ${baselinePenaltySource.replace(/_/g, "+")}`);
  }
  if (baselinePenaltySample > 0) {
    detailBits.push(`sample ${baselinePenaltySample.toFixed(1)}`);
  }
  if (careerPlayerPenalties > 0 && careerTeamPenalties > 0) {
    detailBits.push(`career ${careerPlayerPenalties.toFixed(0)}/${careerTeamPenalties.toFixed(0)}`);
  }
  if (evidenceSample > 0) {
    detailBits.push(`ev ${(evidenceShare * 100).toFixed(1)}%`);
    detailBits.push(`evs ${evidenceSample.toFixed(1)}`);
  }
  if (evidenceSource) {
    detailBits.push(`evsrc ${evidenceSource.replace(/_/g, "+")}`);
  }
  detailBits.push(`λpen ${penaltyLambda.toFixed(3)}`);
  detailBits.push(`λopen ${nonPenLambda.toFixed(3)}`);

  const compactBits = [
    role !== "none" ? `${penaltyRoleLabel(role)} pen` : "Pen angle",
    `${(penaltyShare * 100).toFixed(0)}% share`,
    `λ ${penaltyLambda.toFixed(3)}`,
  ];

  return {
    compact: compactBits.join(" · "),
    detail: detailBits.join(" · "),
  };
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
  const action = effectiveMonitorAction(row);
  const evPct = row ? formatPct((parseFloatMaybe(row.ev) ?? 0) * 100, 1) : "unpriced";
  const penaltyMeta = penaltyComponentMeta(row);

  return (
    <div className={`rounded-xl border px-3 py-2.5 ${signalRowClass(action, hasRow)}`}>
      <div className="flex flex-col gap-2.5 xl:grid xl:grid-cols-[minmax(0,1.45fr)_64px_64px_64px_54px_auto] xl:items-start xl:gap-3">
        <div className="min-w-0">
          <div className="flex flex-wrap items-center gap-2">
            <div className="min-w-0 break-words text-sm font-semibold leading-tight text-slate-100">{name}</div>
            <span className="rounded-full border border-slate-700/80 bg-slate-950/70 px-2 py-0.5 text-[10px] font-semibold uppercase tracking-[0.16em] text-slate-400">
              {position || "UTIL"}
            </span>
          </div>
          {note ? <div className="mt-1 text-xs text-slate-500">{note}</div> : null}
          {penaltyMeta ? (
            <div className="mt-1.5 xl:pr-3" title={penaltyMeta.detail}>
              <span className="inline-flex rounded-full border border-cyan-500/20 bg-cyan-500/8 px-2 py-1 text-[11px] font-medium leading-none text-cyan-200/90">
                {penaltyMeta.compact}
              </span>
            </div>
          ) : null}
        </div>
        <div className="grid grid-cols-2 gap-2 text-sm sm:grid-cols-4 xl:contents">
          <div className="rounded-lg bg-black/15 px-2 py-1.5 xl:bg-transparent xl:px-0 xl:py-0">
            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Odds</div>
            <div className="mt-1 font-semibold text-slate-200">{hasRow ? formatDecimal(parseFloatMaybe(row?.odds_decimal), 2) : "n/a"}</div>
          </div>
          <div className="rounded-lg bg-black/15 px-2 py-1.5 xl:bg-transparent xl:px-0 xl:py-0">
            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Fair</div>
            <div className="mt-1 font-semibold text-slate-300">{hasRow ? formatDecimal(parseFloatMaybe(row?.model_fair_odds_atgs), 2) : "n/a"}</div>
          </div>
          <div className="rounded-lg bg-black/15 px-2 py-1.5 xl:bg-transparent xl:px-0 xl:py-0">
            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">EV</div>
            <div className={`mt-1 font-semibold ${hasRow ? toneForAction(action) : "text-slate-500"}`}>{evPct}</div>
          </div>
          <div className="rounded-lg bg-black/15 px-2 py-1.5 xl:bg-transparent xl:px-0 xl:py-0">
            <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Min</div>
            <div className="mt-1 font-semibold text-slate-500">{hasRow ? formatDecimal(parseFloatMaybe(row?.expected_minutes), 0) : "n/a"}</div>
          </div>
        </div>
        <div className="xl:justify-self-end">
          <span className={`inline-flex rounded-full border px-2 py-1 text-[10px] font-semibold uppercase tracking-[0.18em] ${signalBadge(action)}`}>
            {hasRow ? effectiveMonitorActionLabel(row) : "unpriced"}
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
      <div className="mb-2.5 flex items-center justify-between gap-3">
        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">{title}</div>
        <div className="text-xs text-slate-500">{items.length}</div>
      </div>
      <div className="space-y-2">
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
  const lineupKeeper = lineupRows.find((item) => positionBand(item.lineup.position, item.lineup.positionId) === "gk");
  const lineupOutfield = lineupRows.filter((item) => positionBand(item.lineup.position, item.lineup.positionId) !== "gk");
  const lineupCentreBacks = lineupOutfield.filter((item) => positionBand(item.lineup.position, item.lineup.positionId) === "cb");
  const lineupWidePlayers = lineupOutfield.filter((item) => positionBand(item.lineup.position, item.lineup.positionId) === "wide");
  const lineupMidfielders = lineupOutfield.filter((item) => positionBand(item.lineup.position, item.lineup.positionId) === "mid");
  const lineupAttackers = lineupOutfield.filter((item) => positionBand(item.lineup.position, item.lineup.positionId) === "att");
  const lineupUtilities = lineupOutfield.filter((item) => positionBand(item.lineup.position, item.lineup.positionId) === "util");

  for (const item of lineupUtilities) {
    if (lineupMidfielders.length <= lineupCentreBacks.length && lineupMidfielders.length <= lineupAttackers.length) lineupMidfielders.push(item);
    else if (lineupWidePlayers.length <= lineupCentreBacks.length) lineupWidePlayers.push(item);
    else if (lineupAttackers.length <= lineupCentreBacks.length) lineupAttackers.push(item);
    else lineupCentreBacks.push(item);
  }

  const groupedItems = hasLineup
    ? {
        attackers: lineupAttackers.map(({ lineup, row }) => ({
          key: `${lineup.name}-${lineup.position}-${lineup.positionId ?? ""}`,
          name: lineup.name,
          position: positionLabel(lineup.position || row?.position, lineup.positionId),
          row: row ? { ...row, position: lineup.position || row.position } : undefined,
          note: row ? undefined : "No price matched",
        })),
        midfielders: lineupMidfielders.map(({ lineup, row }) => ({
          key: `${lineup.name}-${lineup.position}-${lineup.positionId ?? ""}`,
          name: lineup.name,
          position: positionLabel(lineup.position || row?.position, lineup.positionId),
          row: row ? { ...row, position: lineup.position || row.position } : undefined,
          note: row ? undefined : "No price matched",
        })),
        widePlayers: lineupWidePlayers.map(({ lineup, row }) => ({
          key: `${lineup.name}-${lineup.position}-${lineup.positionId ?? ""}`,
          name: lineup.name,
          position: positionLabel(lineup.position || row?.position, lineup.positionId),
          row: row ? { ...row, position: lineup.position || row.position } : undefined,
          note: row ? undefined : "No price matched",
        })),
        centreBacks: lineupCentreBacks.map(({ lineup, row }) => ({
          key: `${lineup.name}-${lineup.position}-${lineup.positionId ?? ""}`,
          name: lineup.name,
          position: positionLabel(lineup.position || row?.position, lineup.positionId),
          row: row ? { ...row, position: lineup.position || row.position } : undefined,
          note: row ? undefined : "No price matched",
        })),
        keeper: lineupKeeper
          ? {
              key: `${lineupKeeper.lineup.name}-${lineupKeeper.lineup.position}-${lineupKeeper.lineup.positionId ?? ""}`,
              name: lineupKeeper.lineup.name,
              position: positionLabel(lineupKeeper.lineup.position || "GK", lineupKeeper.lineup.positionId),
              row: lineupKeeper.row ? { ...lineupKeeper.row, position: lineupKeeper.lineup.position || lineupKeeper.row.position } : undefined,
              note: lineupKeeper.row ? undefined : "ATGS not priced",
            }
          : null,
      }
    : {
        attackers: [],
        midfielders: [],
        widePlayers: [],
        centreBacks: [],
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
          <div className="space-y-2.5">
            <GroupBlock title="Attack" items={groupedItems.attackers} />
            <GroupBlock title="Midfield" items={groupedItems.midfielders} />
            <GroupBlock title="Wide / Full-backs" items={groupedItems.widePlayers} />
            <GroupBlock title="Centre-backs" items={groupedItems.centreBacks} />
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
  if (process.env.NODE_ENV === "production" && !MODEL_MONITOR_ENABLED) {
    notFound();
  }

  const [leagueDatasets, shadowDatasets, snapshotGeneratedAt, oddsHistoryText] = await Promise.all([
    Promise.all(
      LIVE_COMPARE_CONFIGS.map(async (config) => {
        const [comparisonJson, comparisonCsv, comparisonTxt, comparisonJsonMtime, comparisonCsvMtime, lineupsJson, penaltyReviewJson, livePenaltyReviewJson] = await Promise.all([
          readGoalscorerLiveJson<LiveBoardPayload>(config.comparisonJson),
          readGoalscorerLiveFile(config.comparisonCsv),
          readGoalscorerLiveFile(config.comparisonTxt),
          readGoalscorerLiveMtime(config.comparisonJson),
          readGoalscorerLiveMtime(config.comparisonCsv),
          readGoalscorerLiveFile(config.lineupsJson),
          readGoalscorerLiveJson<PenaltyReviewPayload>(config.penaltyReviewJson),
          readGoalscorerLiveJson<PenaltyReviewPayload>(config.livePenaltyReviewJson),
        ]);
        const jsonRows = parseLiveBoardRows(comparisonJson);
        const fixtureHealth = parseLiveBoardFixtures(comparisonJson, config.key);
        const rawRows = jsonRows.length > 0 ? jsonRows : comparisonCsv ? parseCsv(comparisonCsv) : [];
        const rows = filterActiveRows(rawRows);
        const lineupFixtures = parseStoredLineups(lineupsJson, config.key);
        const lineupMap = new Map(
          lineupFixtures.map((fixture) => [
            `${config.key}|${fixture.homeKey}|${fixture.awayKey}`,
            fixture,
          ]),
        );

        return {
          ...config,
          comparisonJson,
          comparisonCsv,
          comparisonTxt,
          comparisonMtime: comparisonJsonMtime ?? comparisonCsvMtime,
          lineupsJson,
          rows,
          fixtureHealth,
          lineupMap,
          penaltyReviewRows: Array.isArray(penaltyReviewJson?.rows) ? penaltyReviewJson.rows : [],
          penaltyReviewGeneratedAt: penaltyReviewJson?.generated_at ?? null,
          livePenaltyReviewRows: Array.isArray(livePenaltyReviewJson?.rows) ? livePenaltyReviewJson.rows : [],
          livePenaltyReviewGeneratedAt: livePenaltyReviewJson?.generated_at ?? null,
          summary: parseSummaryMetrics(comparisonTxt),
        };
      }),
    ),
    Promise.all(
      SHADOW_SIGNAL_CONFIGS.map(async (config): Promise<ShadowLeagueDataset> => {
        const [text, mtime] = await Promise.all([
          readGoalscorerLiveFile(config.file),
          readGoalscorerLiveMtime(config.file),
        ]);
        return {
          ...config,
          rows: text ? parseCsv(text) : [],
          mtime,
        };
      }),
    ),
    readGoalscorerLiveSnapshotGeneratedAt(),
    readGoalscorerLiveFile(GOALSCORER_ODDS_HISTORY_FILE),
  ]);

  const rows = leagueDatasets.flatMap((dataset) => dataset.rows);
  const shadowRows = shadowDatasets.flatMap((dataset) => dataset.rows);
  const rowEventIds = new Set(rows.map((row) => extractEventId(row.notes)).filter(Boolean));
  const kickoffLookup = buildKickoffLookup(oddsHistoryText, rowEventIds);
  const latestTrackedRows = [...shadowRows].sort((left, right) => shadowRowActivityTime(right) - shadowRowActivityTime(left));
  const publicRows = rows.filter((row) => (row.public_action ?? "") === "surface");
  const highRows = [...publicRows];
  const caveatRows = rows.filter((row) => (row.shadow_action ?? "") === "shadow_track" && (row.public_action ?? "") !== "surface");
  const suppressedRows = rows.filter((row) => effectiveMonitorAction(row) === "suppress");

  publicRows.sort((a, b) => compareRowsByKickoffThenEv(a, b, kickoffLookup));
  highRows.sort((a, b) => compareRowsByKickoffThenEv(a, b, kickoffLookup));
  caveatRows.sort((a, b) => compareRowsByKickoffThenEv(a, b, kickoffLookup));

  const todayIso = isoDateInTimezone("Europe/London");
  const yesterdayIso = addDaysIso(todayIso, -1);
  const liveMonitorRows: GoalscorerMonitorRow[] = [...highRows, ...caveatRows]
    .map((row) => {
      const kickoff = resolveRowKickoff(row, kickoffLookup);
      return {
        key: `${row.player_name}-${row.match_date}-${row.bookmaker}-${effectiveMonitorAction(row)}`,
        status: ((row.public_action ?? "") === "surface" ? "PUBLIC" : "SHADOW") as GoalscorerMonitorRow["status"],
        league: leagueShortLabel(row.competition || row.league),
        player: row.player_name || "Unknown player",
        match: `${row.player_team || "Unknown team"} vs ${row.opponent || "Unknown opponent"}`,
        kickoff,
        lineupShort: lineupShortLabel(row),
        lineupLabel: formatLineupLabel(row),
        odds: parseFloatMaybe(row.odds_decimal),
        fair: parseFloatMaybe(row.model_fair_odds_atgs),
        edgePct: (parseFloatMaybe(row.ev) ?? 0) * 100,
        row,
      };
    })
    .sort((left, right) => {
      const kickoffDiff = kickoffSortValue(left.kickoff) - kickoffSortValue(right.kickoff);
      if (kickoffDiff !== 0) return kickoffDiff;
      if (left.status !== right.status) return left.status === "PUBLIC" ? -1 : 1;
      return (right.edgePct ?? 0) - (left.edgePct ?? 0);
    });
  const startingSoonRows = liveMonitorRows.filter((item) => kickoffUrgencyMeta(item.kickoff).startsSoon);
  const todayRows = liveMonitorRows.filter(
    (item) => isoDateForValueInTimezone(item.kickoff) === todayIso && !kickoffUrgencyMeta(item.kickoff).startsSoon,
  );
  const laterRows = liveMonitorRows.filter((item) => isoDateForValueInTimezone(item.kickoff) !== todayIso);
  const settledTodayRows = latestTrackedRows.filter(
    (row) => isSettledShadowRow(row) && isoDateForValueInTimezone(row.settled_at || row.date) === todayIso,
  );
  const settledYesterdayRows = latestTrackedRows.filter(
    (row) => isSettledShadowRow(row) && isoDateForValueInTimezone(row.settled_at || row.date) === yesterdayIso,
  );

  const comparedAt = rows
    .map((row) => row.compared_at ?? "")
    .filter(Boolean)
    .sort()
    .at(-1) ?? "n/a";
  const liveWindowStart = todayIso;
  const liveWindowEnd = addDaysIso(liveWindowStart, 3);
  const comparisonMtime =
    leagueDatasets
      .map((dataset) => dataset.comparisonMtime ?? "")
      .filter(Boolean)
      .sort()
      .at(-1) ?? null;
  const comparisonFreshness = freshnessBadge(comparisonMtime);
  const snapshotFreshness = freshnessBadge(snapshotGeneratedAt);
  const fixtureHealthRows = leagueDatasets.flatMap((dataset) => dataset.fixtureHealth);
  const liveWindowFixtureHealthRows = fixtureHealthRows.filter((fixture) =>
    fixtureInLiveWindow(fixture, liveWindowStart, liveWindowEnd),
  );
  const fixtureHealthMap = new Map(
    fixtureHealthRows.map((fixture) => [
      fixtureHealthKey(fixture.league, fixture.match_date, fixture.home_team, fixture.away_team),
      fixture,
    ]),
  );
  const cleanFixtures = liveWindowFixtureHealthRows.filter((fixture) => fixture.trust_tier === "T1").length;
  const degradedFixtures = liveWindowFixtureHealthRows.filter((fixture) => fixture.trust_tier === "T2").length;
  const quarantinedFixtures = liveWindowFixtureHealthRows.filter((fixture) => fixture.trust_tier === "T3").length;
  const hiddenPendingFixtures = liveWindowFixtureHealthRows.filter(
    (fixture) => fixture.trust_tier === "T2" && fixture.lineup_input === "none",
  ).length;
  const hiddenExpectedFixtures = liveWindowFixtureHealthRows.filter(
    (fixture) => fixture.trust_tier === "T2" && fixture.lineup_input === "expected_xi" && (parseFloatMaybe(fixture.corruption_score) ?? 0) <= 0,
  ).length;
  const flaggedFixtures = liveWindowFixtureHealthRows
    .filter((fixture) => {
      if (fixture.trust_tier === "T3") return true;
      if (fixture.trust_tier !== "T2") return false;
      const corruptionScore = parseFloatMaybe(fixture.corruption_score) ?? 0;
      if (fixture.lineup_input === "none") return false;
      if (fixture.lineup_input === "expected_xi" && corruptionScore <= 0) return false;
      return corruptionScore > 0 || (fixture.corruption_flags ?? []).length > 0;
    })
    .sort((left, right) => {
      const leftRank = left.trust_tier === "T3" ? 2 : 1;
      const rightRank = right.trust_tier === "T3" ? 2 : 1;
      if (leftRank !== rightRank) return rightRank - leftRank;
      return `${left.match_date}|${left.home_team}|${left.away_team}`.localeCompare(`${right.match_date}|${right.home_team}|${right.away_team}`);
    });
  const matchedRows = rows.length;
  const avgEv =
    rows.length > 0
      ? rows.reduce((sum, row) => sum + (parseFloatMaybe(row.ev) ?? 0), 0) / rows.length
      : undefined;
  const historyResolved = rows.filter((row) => row.resolver_source === "history").length;
  const rosterResolved = rows.filter((row) => row.resolver_source === "live_roster").length;
  const lowConfidence = rows.filter((row) => row.signal_confidence === "low").length;
  const starterRows = rows.filter((row) => (row.lineup_status ?? "").toLowerCase() === "confirmed_starter").length;
  const expectedStarterRows = rows.filter((row) => (row.lineup_status ?? "").toLowerCase() === "expected_starter").length;
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
  const fixtures = leagueDatasets.flatMap((dataset) =>
    buildFixtureGroups(dataset.rows, dataset.key, dataset.label, kickoffLookup),
  );
  const lineupMap = new Map(
    leagueDatasets.flatMap((dataset) =>
      [...dataset.lineupMap.entries()].map(([key, value]) => [key, value] as const),
    ),
  );
  const liveSummaryAvailable = leagueDatasets.filter((dataset) => dataset.comparisonJson || dataset.comparisonCsv);
  const shadowSummaryByLeague = new Map(
    shadowDatasets.map((dataset) => [dataset.key, computeShadowSummary(dataset.rows)] as const),
  );
  const leagueStatus = leagueDatasets.map((dataset) => {
    const leagueRows = dataset.rows;
    const leaguePublicRows = leagueRows.filter((row) => (row.public_action ?? "") === "surface");
    const leagueShadowRows = leagueRows.filter((row) => (row.shadow_action ?? "") === "shadow_track" && (row.public_action ?? "") !== "surface");
    const leagueFixtures = dataset.fixtureHealth.filter((fixture) =>
      fixtureInLiveWindow(fixture, liveWindowStart, liveWindowEnd),
    );
    const hasOutput = Boolean(dataset.comparisonJson || dataset.comparisonCsv);
    return {
      key: dataset.key,
      label: dataset.label,
      hasOutput,
      hasLineups: Boolean(dataset.lineupsJson),
      rows: leagueRows.length,
      publicHigh: leaguePublicRows.length,
      publicCaveats: leagueShadowRows.length,
      totalPublic: leaguePublicRows.length,
      cleanFixtures: leagueFixtures.filter((fixture) => fixture.trust_tier === "T1").length,
      degradedFixtures: leagueFixtures.filter((fixture) => fixture.trust_tier === "T2").length,
      quarantinedFixtures: leagueFixtures.filter((fixture) => fixture.trust_tier === "T3").length,
      competition: leagueRows[0]?.competition ?? dataset.label,
      updatedAt: dataset.comparisonMtime,
      outputStatus: leagueOutputStatus(dataset.summary, hasOutput),
    };
  });
  const leagueScoreRows: LeagueScoreRow[] = leagueStatus.map((league) => {
    const shadow = shadowSummaryByLeague.get(league.key) ?? computeShadowSummary([]);
    return {
      key: league.key,
      label: league.label,
      statusLabel: league.outputStatus.label,
      statusClassName: league.outputStatus.className,
      statusDetail: league.outputStatus.detail,
      updatedAt: league.updatedAt,
      liveRows: league.rows,
      publicNow: league.totalPublic,
      shadowNow: league.publicCaveats,
      cleanFixtures: league.cleanFixtures,
      degradedFixtures: league.degradedFixtures,
      quarantinedFixtures: league.quarantinedFixtures,
      trackedSignals: shadow.signals,
      settledSignals: shadow.settled,
      openSignals: shadowUnsettledCount(shadow),
      wins: shadow.wins,
      losses: shadow.losses,
      voids: shadow.voids,
      roi: shadow.roi,
      pnlUnits: shadow.pnlUnits,
    };
  });
  const sourceFeedGapLeagues = leagueStatus.filter((league) => league.outputStatus.detail);
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
  const penaltyReviewRows = leagueDatasets
    .flatMap((dataset) =>
      mergePenaltyReviewRows([
        ...dataset.penaltyReviewRows.map((row) => ({
          ...row,
          league: row.league || dataset.key,
        })),
        ...dataset.livePenaltyReviewRows.map((row) => ({
          ...row,
          league: row.league || dataset.key,
        })),
      ]),
    )
    .sort((left, right) => {
      const priorityDiff = priorityRank(right.review_priority) - priorityRank(left.review_priority);
      if (priorityDiff !== 0) return priorityDiff;
      const rightDate = Date.parse(right.date || "");
      const leftDate = Date.parse(left.date || "");
      if (!Number.isNaN(rightDate) && !Number.isNaN(leftDate) && rightDate !== leftDate) {
        return rightDate - leftDate;
      }
      return `${left.team ?? ""}${left.actual_taker ?? ""}`.localeCompare(`${right.team ?? ""}${right.actual_taker ?? ""}`);
    });
  const latestPenaltyReviewAt =
    leagueDatasets
      .flatMap((dataset) => [dataset.penaltyReviewGeneratedAt ?? "", dataset.livePenaltyReviewGeneratedAt ?? ""])
      .filter(Boolean)
      .sort()
      .at(-1) ?? null;
  const penaltyReviewState = await readPenaltyReviewState();
  const penaltyReviewCutoffIso = addDaysIso(todayIso, -7);
  const penaltyReviewRowsWithIds = penaltyReviewRows.map((row) => ({
    row,
    id: penaltyReviewIdentity(row),
  }));
  const resolvedPenaltyReviewRows = penaltyReviewRowsWithIds.filter(({ id }) => Boolean(id && penaltyReviewState[id]));
  const hiddenResolvedPenaltyRows = resolvedPenaltyReviewRows.length;
  const hiddenStalePenaltyRows = penaltyReviewRowsWithIds.filter(
    ({ id, row }) => !penaltyReviewState[id] && penaltyReviewIsOlderThan(row, penaltyReviewCutoffIso),
  ).length;
  const visiblePenaltyReviewRows = penaltyReviewRowsWithIds.filter(
    ({ id, row }) => !penaltyReviewState[id] && !penaltyReviewIsOlderThan(row, penaltyReviewCutoffIso),
  );
  const visibleHighPenaltyReviewRows = visiblePenaltyReviewRows.filter(({ row }) => row.review_priority === "high");
  const visibleMediumPenaltyReviewRows = visiblePenaltyReviewRows.filter(({ row }) => row.review_priority === "medium");
  const visibleLowPenaltyReviewRows = visiblePenaltyReviewRows.filter(({ row }) => row.review_priority === "low");
  const visibleWatchlistRows =
    visibleHighPenaltyReviewRows.length > 0
      ? visiblePenaltyReviewRows.filter(({ row }) => row.review_priority !== "high")
      : visiblePenaltyReviewRows;
  const renderPenaltyWatchlistSection = (defaultOpen: boolean) => (
    <CollapsibleMonitorSection
      title="Penalty duty watchlist"
      subtitle="Editorial review queue for taker hierarchy changes. Treated like a checklist now, with manual clear states and a 7-day stale cutoff."
      defaultOpen={defaultOpen}
    >
      <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
        <div className="rounded-2xl border border-slate-800/80 bg-slate-950/35 px-4 py-3 text-sm text-slate-300">
          <div><span className="text-slate-500">Latest review:</span> {latestPenaltyReviewAt ?? "missing"}</div>
          <div><span className="text-slate-500">Visible rows:</span> {visiblePenaltyReviewRows.length}</div>
          <div><span className="text-slate-500">Resolved hidden:</span> {hiddenResolvedPenaltyRows}</div>
          <div><span className="text-slate-500">Aged out:</span> {hiddenStalePenaltyRows}</div>
        </div>
      </div>

      <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
        <Stat label="High Priority" value={`${visibleHighPenaltyReviewRows.length}`} tone="text-rose-300" />
        <Stat label="Medium Priority" value={`${visibleMediumPenaltyReviewRows.length}`} tone="text-amber-300" />
        <Stat label="Low Priority" value={`${visibleLowPenaltyReviewRows.length}`} tone="text-slate-300" />
        <Stat label="Active Review Rows" value={`${visiblePenaltyReviewRows.length}`} />
      </div>

      <div className="mt-5 space-y-4">
        {visibleWatchlistRows.map(({ row, id }, idx) => (
          <PenaltyReviewCard
            key={`${row.date}-${row.team}-${row.actual_taker}-${idx}`}
            row={row}
            rowId={id}
            daysUntilStale={penaltyReviewDaysUntilStale(row, todayIso)}
          />
        ))}
        {visibleWatchlistRows.length === 0 ? (
          <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-sm text-slate-500">
            {visibleHighPenaltyReviewRows.length > 0
              ? "Only high-priority rows are active right now, and they are surfaced in the block above."
              : "No active penalty-duty review rows. Old untouched rows now age out after 7 days, and manual done/dismiss clears them immediately."}
          </div>
        ) : null}
      </div>
      {resolvedPenaltyReviewRows.length > 0 ? (
        <details className="mt-5 rounded-xl border border-slate-800/80 bg-slate-950/35">
          <summary className="cursor-pointer px-4 py-3 text-sm font-medium text-slate-300">
            Show {resolvedPenaltyReviewRows.length} resolved row{resolvedPenaltyReviewRows.length === 1 ? "" : "s"}
          </summary>
          <div className="space-y-4 border-t border-slate-800 px-4 py-4">
            {resolvedPenaltyReviewRows.map(({ row, id }, idx) => (
              <PenaltyReviewCard
                key={`resolved-${row.date}-${row.team}-${row.actual_taker}-${idx}`}
                row={row}
                rowId={id}
                resolvedStatus={penaltyReviewState[id]?.status}
              />
            ))}
          </div>
        </details>
      ) : null}
    </CollapsibleMonitorSection>
  );

  return (
    <div className="min-h-screen bg-[radial-gradient(circle_at_top_left,_rgba(16,185,129,0.12),_transparent_28%),radial-gradient(circle_at_top_right,_rgba(244,63,94,0.08),_transparent_22%),#0b0f14] text-slate-100">
      <div className="mx-auto max-w-7xl px-4 py-8 sm:px-6 lg:px-8">
        <div className="mb-8 flex flex-wrap items-center gap-3">
          <Link href="/model-monitor" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Model Monitor
          </Link>
          <Link href="/api/model-monitor/betting-archive" className="inline-flex items-center rounded-full border border-cyan-500/25 bg-cyan-500/10 px-3 py-1.5 text-sm text-cyan-200 transition-colors hover:border-cyan-400/40 hover:text-cyan-100">
            Download Bet Archive
          </Link>
          <Link href="/anytime-goalscorer" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Anytime Goalscorer
          </Link>
          <a href="#fixture-lineups" className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300">
            Fixture Lineups
          </a>
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
              <div>
                <span className="text-slate-500">Live board updated:</span> {formatDateTime(comparisonMtime)}{" "}
                <span className={comparisonFreshness.className}>({comparisonFreshness.label})</span>
              </div>
              <div>
                <span className="text-slate-500">Hosted snapshot:</span> {formatDateTime(snapshotGeneratedAt)}{" "}
                <span className={snapshotFreshness.className}>({snapshotFreshness.label})</span>
              </div>
              <div>
                <span className="text-slate-500">Fixture health (live window):</span>{" "}
                <span className="text-emerald-300">{cleanFixtures} clean</span> |{" "}
                <span className="text-amber-300">{degradedFixtures} degraded</span> |{" "}
                <span className="text-rose-300">{quarantinedFixtures} quarantined</span>
              </div>
            </div>
          </div>
        </section>

        {liveSummaryAvailable.length === 0 ? (
          <section className="rounded-2xl border border-amber-500/25 bg-amber-500/10 p-4 text-sm text-amber-100">
            No live comparison files found. Run the goalscorer live compare pipeline locally first.
          </section>
        ) : null}

        <section className="mb-8 grid gap-3 md:grid-cols-2 xl:grid-cols-5">
          <Stat label="Last refresh" value={formatDateTime(comparisonMtime)} tone={comparisonFreshness.className} />
          <Stat label="Public live" value={`${highRows.length}`} tone="text-emerald-300" />
          <Stat label="Shadow live" value={`${caveatRows.length}`} tone="text-slate-300" />
          <Stat label="Starting <60m" value={`${liveMonitorRows.filter((item) => kickoffUrgencyMeta(item.kickoff).label === "<60m" || kickoffUrgencyMeta(item.kickoff).label === "<30m").length}`} tone="text-amber-300" />
          <Stat label="Health" value={`${cleanFixtures}/${degradedFixtures}/${quarantinedFixtures}`} tone="text-slate-200" />
        </section>

        {sourceFeedGapLeagues.length > 0 ? (
          <div className="mb-8 rounded-2xl border border-amber-500/20 bg-amber-500/8 p-4 text-sm leading-6 text-amber-100">
            {sourceFeedGapLeagues.map((league) => league.label).join(", ")} currently has pipeline output and historical logs,
            but the upstream ATGS source feed returned no current events for the live window. That league will stay at zero
            matched prices until the feed comes back.
          </div>
        ) : null}

        <div className="mb-8">
          <MonitorCard
            title="League scoreboard"
            subtitle="Live pipeline on the left, cumulative shadow log on the right. Public and shadow stay separate so you can tell what is live now versus what is just historical tracking."
          >
            <div className="overflow-x-auto">
              <table className="min-w-full text-sm">
                <thead>
                  <tr className="border-b border-slate-800/80 text-left text-[10px] uppercase tracking-[0.22em] text-slate-500">
                    <th className="px-3 py-3 font-semibold" colSpan={6}>Live pipeline — current window</th>
                    <th className="border-l border-slate-700 px-3 py-3 font-semibold bg-slate-950/20" colSpan={6}>Shadow log — cumulative</th>
                  </tr>
                  <tr className="border-b border-slate-800 text-left text-[11px] uppercase tracking-[0.18em] text-slate-500">
                    <th className="px-3 py-3 font-semibold">League</th>
                    <th className="px-3 py-3 font-semibold">Feed</th>
                    <th className="px-3 py-3 font-semibold">Matched</th>
                    <th className="px-3 py-3 font-semibold">Pub now</th>
                    <th className="px-3 py-3 font-semibold">Shadow now</th>
                    <th className="px-3 py-3 font-semibold">Fixtures</th>
                    <th className="border-l border-slate-700 bg-slate-950/20 px-3 py-3 font-semibold">Tracked</th>
                    <th className="bg-slate-950/20 px-3 py-3 font-semibold">Settled</th>
                    <th className="bg-slate-950/20 px-3 py-3 font-semibold">Unsettled</th>
                    <th className="bg-slate-950/20 px-3 py-3 font-semibold">W/L/V</th>
                    <th className="bg-slate-950/20 px-3 py-3 font-semibold">ROI</th>
                    <th className="bg-slate-950/20 px-3 py-3 font-semibold">P/L</th>
                  </tr>
                </thead>
                <tbody>
                  {leagueScoreRows.map((row) => (
                    <tr key={row.key} className="border-b border-slate-900/80 text-slate-200">
                      <td className="px-3 py-3">
                        <div className="font-semibold text-white">{row.label}</div>
                        <div className="mt-1 text-xs text-slate-500">
                          {row.updatedAt ? formatDateTime(row.updatedAt) : "No timestamp"}
                        </div>
                      </td>
                      <td className="px-3 py-3">
                        <span className={`inline-flex rounded-full border px-2.5 py-1 text-[10px] font-semibold uppercase tracking-[0.14em] ${row.statusClassName}`}>
                          {row.statusLabel}
                        </span>
                      </td>
                      <td className="px-3 py-3 font-mono tabular-nums">{row.liveRows}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-emerald-300">{row.publicNow}</td>
                      <td className="px-3 py-3 font-mono tabular-nums text-amber-300">{row.shadowNow}</td>
                      <td className="px-3 py-3 font-mono tabular-nums">
                        <span className="text-emerald-300">{row.cleanFixtures}</span>
                        <span className="px-1 text-slate-600">·</span>
                        <span className="text-amber-300">{row.degradedFixtures}</span>
                        <span className="px-1 text-slate-600">·</span>
                        <span className="text-rose-300">{row.quarantinedFixtures}</span>
                      </td>
                      <td className="border-l border-slate-700 bg-slate-950/20 px-3 py-3 font-mono tabular-nums text-slate-100">{row.trackedSignals}</td>
                      <td className="bg-slate-950/20 px-3 py-3 font-mono tabular-nums text-slate-100">{row.settledSignals}</td>
                      <td className="bg-slate-950/20 px-3 py-3 font-mono tabular-nums text-slate-300">{row.openSignals}</td>
                      <td className="bg-slate-950/20 px-3 py-3 font-mono tabular-nums text-slate-100">{formatWLV(row.wins, row.losses, row.voids)}</td>
                      <td className={`bg-slate-950/20 px-3 py-3 font-mono tabular-nums ${metricTone(row.roi)}`}>{formatPct(row.roi, 1)}</td>
                      <td className={`bg-slate-950/20 px-3 py-3 font-mono tabular-nums ${metricTone(row.pnlUnits)}`}>{formatUnits(row.pnlUnits, 2)}</td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </MonitorCard>
        </div>

        {visibleHighPenaltyReviewRows.length > 0 ? (
          <div className="mb-8 rounded-2xl border border-rose-500/20 bg-rose-500/8 p-5">
            <div className="mb-4 flex flex-wrap items-start justify-between gap-3">
              <div>
                <div className="text-[11px] uppercase tracking-[0.18em] text-rose-200">High-priority watchlist</div>
                <div className="mt-1 text-lg font-semibold text-white">
                  Penalty duty needs manual review before this gets buried under the live board.
                </div>
                <div className="mt-1 text-sm text-rose-100/80">
                  {visibleHighPenaltyReviewRows.length} high-priority row{visibleHighPenaltyReviewRows.length === 1 ? "" : "s"} active.
                </div>
              </div>
            </div>
            <div className="space-y-4">
              {visibleHighPenaltyReviewRows.slice(0, 3).map(({ row, id }, idx) => (
                <PenaltyReviewCard
                  key={`priority-${row.date}-${row.team}-${row.actual_taker}-${idx}`}
                  row={row}
                  rowId={id}
                  daysUntilStale={penaltyReviewDaysUntilStale(row, todayIso)}
                />
              ))}
            </div>
          </div>
        ) : null}

        {visibleHighPenaltyReviewRows.length > 0 ? (
          <div className="mb-8">
            {renderPenaltyWatchlistSection(true)}
          </div>
        ) : null}

        {startingSoonRows.length > 0 ? (
          <div className="mb-8">
            <MonitorCard title="Starting soon" subtitle="Rows kicking off within the next hour. This is the action zone.">
              <LiveBetsTable rows={startingSoonRows} todayIso={todayIso} emptyLabel="No rows starting soon." />
            </MonitorCard>
          </div>
        ) : null}

        <div className="mb-8">
          <MonitorCard title="Live bets" subtitle="Public and shadow rows in one urgency-sorted board, with kickoff first and the rest of the model detail pushed out of the default view.">
            <LiveBetsTable rows={todayRows} todayIso={todayIso} emptyLabel="No active goalscorer rows for today." />
          </MonitorCard>
        </div>

        {laterRows.length > 0 ? (
          <div className="mb-8">
            <CollapsibleMonitorSection
              title="Later window"
              subtitle="Upcoming rows outside today. Useful for planning, but not worth cluttering the main action area."
            >
              <LiveBetsTable rows={laterRows} todayIso={todayIso} emptyLabel="No later rows in the live horizon." />
            </CollapsibleMonitorSection>
          </div>
        ) : null}

        <div className="mb-8 grid gap-6 xl:grid-cols-2">
          <CollapsibleMonitorSection
            title={`Settled today (${todayIso})`}
            subtitle="Closed by default so the live board stays usable during the day."
          >
            <SettledRowsTable rows={settledTodayRows} />
          </CollapsibleMonitorSection>
          <CollapsibleMonitorSection
            title={`Settled yesterday (${yesterdayIso})`}
            subtitle="Quick review block for yesterday without sending you into the archive."
          >
            <SettledRowsTable rows={settledYesterdayRows} />
          </CollapsibleMonitorSection>
        </div>

        <div className="mb-8">
          <CollapsibleMonitorSection
            title="Shadow archive (recent 50)"
            subtitle="Recent shadow log only. The headline stats already live in the scoreboard above, so this stays as a drill-down view."
          >
            <div className="mb-4 flex justify-end">
              <Link
                href="/anytime-goalscorer"
                className="inline-flex items-center rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-sm text-slate-300 transition-colors hover:border-emerald-500/40 hover:text-emerald-300"
              >
                Anytime Goalscorer
              </Link>
            </div>

            {shadowRows.length === 0 ? (
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-4 text-sm leading-6 text-slate-500">
                No goalscorer shadow signals have been logged yet.
              </div>
            ) : (
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3">
                <div className="mb-3 text-[11px] uppercase tracking-[0.18em] text-slate-500">Recent tracked archive</div>
                <div className="max-h-80 overflow-auto">
                  <SettledRowsTable rows={latestTrackedRows.slice(0, 50)} />
                </div>
              </div>
            )}
          </CollapsibleMonitorSection>
        </div>

        <div className="mb-8">
          <CollapsibleMonitorSection
            title="Diagnostics"
            subtitle="Health and resolver checks for when something looks off. Hidden by default so the page stays operational first."
          >
            <div className="mb-5 grid gap-4 md:grid-cols-2 xl:grid-cols-4">
              <Stat label="Matched Prices" value={`${matchedRows}`} />
              <Stat label="Suppressed" value={`${suppressedRows.length}`} tone="text-slate-400" />
              <Stat label="Confirmed XI" value={`${fixturesWithConfirmedLineups}`} tone="text-emerald-300" />
              <Stat label="Expected XI" value={`${fixturesWithExpectedXIs}`} tone="text-cyan-300" />
              <Stat label="History mapped" value={`${historyResolved}`} tone="text-emerald-300" />
              <Stat label="Roster mapped" value={`${rosterResolved}`} tone="text-amber-300" />
              <Stat label="Fallback rows" value={`${fallbackRows}`} tone="text-slate-300" />
              <Stat label="Low confidence" value={`${lowConfidence}`} tone="text-slate-400" />
            </div>

            <div className="mb-5 rounded-2xl border border-slate-800/80 bg-slate-950/35 px-4 py-3 text-sm text-slate-300">
              <div><span className="text-slate-500">Visible issues:</span> {flaggedFixtures.length}</div>
              <div><span className="text-slate-500">Quarantined:</span> {quarantinedFixtures}</div>
              <div><span className="text-slate-500">Hidden expected XIs:</span> {hiddenExpectedFixtures}</div>
              <div><span className="text-slate-500">Hidden pending lineups:</span> {hiddenPendingFixtures}</div>
              <div><span className="text-slate-500">Average EV:</span> {formatPct((avgEv ?? 0) * 100, 1)}</div>
              <div><span className="text-slate-500">Missing player history:</span> {missingHistoryRows}</div>
              <div><span className="text-slate-500">Starter rows:</span> {starterRows}</div>
              <div><span className="text-slate-500">Expected starters:</span> {expectedStarterRows}</div>
            </div>

            {flaggedFixtures.length === 0 ? (
              <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/5 p-4 text-sm text-emerald-200">
                No structural lineup issues in the current live window.
              </div>
            ) : (
              <div className="space-y-4">
                {flaggedFixtures.map((fixture) => (
                  <div
                    key={`trust-${fixtureHealthKey(fixture.league, fixture.match_date, fixture.home_team, fixture.away_team)}`}
                    className={`rounded-xl border p-4 ${fixture.trust_tier === "T3" ? "border-rose-500/20 bg-rose-500/8" : "border-amber-500/20 bg-amber-500/8"}`}
                  >
                    <div className="flex flex-wrap items-start justify-between gap-3">
                      <div>
                        <div className="text-[11px] uppercase tracking-[0.18em] text-slate-400">
                          {fixture.competition || fixture.league}
                        </div>
                        <div className="mt-1 text-base font-semibold text-white">
                          {fixture.home_team} vs {fixture.away_team}
                        </div>
                        <div className="mt-1 text-sm text-slate-300">
                          {fixture.match_date} | corruption score {fixture.corruption_score || "0"}
                        </div>
                        <div className="mt-2 max-w-3xl text-sm leading-6 text-slate-300/90">
                          {fixtureHealthSummary(fixture)}
                        </div>
                      </div>
                      <div className={`rounded-full border px-3 py-1 text-xs font-semibold uppercase tracking-[0.16em] ${fixtureTrustBadgeClass(fixture.trust_tier)}`}>
                        {fixtureStatusLabel(fixture)}
                      </div>
                    </div>
                    <div className="mt-3 flex flex-wrap gap-2">
                      {(fixture.corruption_flags ?? []).slice(0, 8).map((flag) => (
                        <span key={`${fixture.home_team}-${fixture.away_team}-${flag}`} className="rounded-full border border-slate-700/80 bg-slate-950/50 px-2 py-1 text-[11px] text-slate-300">
                          {flag}
                        </span>
                      ))}
                    </div>
                  </div>
                ))}
              </div>
            )}
          </CollapsibleMonitorSection>
        </div>

        {visibleHighPenaltyReviewRows.length === 0 ? (
          <div className="mb-8">
            {renderPenaltyWatchlistSection(false)}
          </div>
        ) : null}

        <div id="fixture-lineups" className="mb-8">
          <CollapsibleMonitorSection
            title="Fixture lineups"
            subtitle="Reference view only. Kept off the main board so the urgent bets are visible without a long scroll."
          >
            <div className="space-y-6">
            {fixtures.map((fixture) => (
              <div key={fixture.key} className="rounded-2xl border border-slate-800/80 bg-slate-950/35 p-4">
                {(() => {
                  const lineup = lineupMap.get(`${fixture.leagueKey}|${teamKey(fixture.homeTeam)}|${teamKey(fixture.awayTeam)}`);
                  const fixtureHealth = fixtureHealthMap.get(
                    fixtureHealthKey(fixture.leagueKey, fixture.matchDate, fixture.homeTeam, fixture.awayTeam),
                  );
                  const isQuarantined = fixtureHealth?.trust_tier === "T3";
                  const isDegraded = fixtureHealth?.trust_tier === "T2";
                  const isAwaitingLineup = fixtureHealth?.trust_tier === "T2" && fixtureHealth?.lineup_input === "none";
                  const hasHomeLineup = (lineup?.homePlayers?.length ?? 0) > 0;
                  const hasAwayLineup = (lineup?.awayPlayers?.length ?? 0) > 0;
                  const hasAnyLineup = hasHomeLineup || hasAwayLineup;
                  return (
                    <>
                      <div className="mb-4 flex flex-wrap items-center justify-between gap-3">
                        <div>
                          <div className="mb-1 text-[11px] uppercase tracking-[0.18em] text-emerald-300">
                            {fixture.competition || fixture.leagueLabel}
                          </div>
                          <h3 className="text-lg font-semibold text-white">{fixture.homeTeam} vs {fixture.awayTeam}</h3>
                          <p className="text-sm text-slate-400">{formatKickoff(fixture.kickoff || fixture.matchDate)} | {fixture.bookmaker}</p>
                        </div>
                        <div className="flex flex-wrap items-center gap-2">
                          {fixtureHealth ? (
                            <div className={`rounded-full border px-3 py-1.5 text-xs font-semibold uppercase tracking-[0.16em] ${fixtureTrustBadgeClass(fixtureHealth.trust_tier)}`}>
                              {fixtureStatusLabel(fixtureHealth)}
                            </div>
                          ) : null}
                          <div className="rounded-full border border-slate-700/80 bg-slate-900/80 px-3 py-1.5 text-xs text-slate-300">
                            {fixture.homeRows.length + fixture.awayRows.length} matched player prices
                          </div>
                        </div>
                      </div>

                      {fixtureHealth && (isQuarantined || (isDegraded && !isAwaitingLineup)) ? (
                        <div className={`mb-4 rounded-xl border p-3 text-sm ${isQuarantined ? "border-rose-500/20 bg-rose-500/8 text-rose-100" : "border-amber-500/20 bg-amber-500/8 text-amber-100"}`}>
                          <div className="font-medium">
                            {isQuarantined
                              ? "This fixture is quarantined from trust-sensitive decisions."
                              : fixtureHealthSummary(fixtureHealth)}
                          </div>
                          {(fixtureHealth.corruption_flags ?? []).length > 0 ? (
                            <div className="mt-2 flex flex-wrap gap-2 text-[11px]">
                              {(fixtureHealth.corruption_flags ?? []).slice(0, 8).map((flag) => (
                                <span key={`${fixture.key}-${flag}`} className="rounded-full border border-slate-700/80 bg-slate-950/45 px-2 py-1 text-slate-200">
                                  {flag}
                                </span>
                              ))}
                            </div>
                          ) : null}
                        </div>
                      ) : null}

                      {isQuarantined ? (
                        <div className="rounded-xl border border-dashed border-rose-500/25 bg-rose-500/5 p-4 text-sm text-rose-100">
                          Player-level output is still stored for audit, but this fixture should not be trusted for public or shadow decisions until the lineup payload is sane again.
                        </div>
                      ) : !hasAnyLineup ? (
                        <div className="rounded-xl border border-dashed border-slate-800/80 bg-slate-950/20 p-4 text-sm text-slate-400">
                          No FotMob lineup has landed for this fixture yet. The monitor still has{" "}
                          <span className="font-medium text-slate-200">{fixture.homeRows.length + fixture.awayRows.length}</span> matched player prices,
                          but the lineup view stays collapsed until a real expected or confirmed XI arrives.
                        </div>
                      ) : (
                        <div className="grid gap-5 xl:grid-cols-2">
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
                        </div>
                      )}
                    </>
                  );
                })()}
              </div>
            ))}
            {fixtures.length === 0 ? (
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-sm text-slate-500">
                No upcoming fixture groups in the next three days.
              </div>
            ) : null}
            </div>
          </CollapsibleMonitorSection>
        </div>

        <CollapsibleMonitorSection
          title="Raw monitor summary"
          subtitle="Direct text output from the latest comparison run. Debug only."
        >
          <pre className="overflow-x-auto whitespace-pre-wrap rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-xs leading-6 text-slate-300">
            {rawMonitorSummary || "Missing goalscorer live summary."}
          </pre>
        </CollapsibleMonitorSection>
      </div>
    </div>
  );
}

