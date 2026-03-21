import Link from "next/link";
import { notFound } from "next/navigation";
import {
  readGoalscorerLiveFile,
  readGoalscorerLiveJson,
  readGoalscorerLiveMtime,
  readGoalscorerLiveSnapshotGeneratedAt,
} from "@/lib/goalscorer-live-files";

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
  open: number;
  wins: number;
  losses: number;
  voids: number;
  roi: number;
  winRate: number;
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

export const dynamic = "force-dynamic";

const MODEL_MONITOR_PUBLIC =
  process.env.MODEL_MONITOR_PUBLIC === "1" ||
  process.env.NEXT_PUBLIC_ENABLE_MODEL_MONITOR === "1";
const MODEL_MONITOR_ENABLED =
  MODEL_MONITOR_PUBLIC || process.env.VERCEL_ENV === "preview";
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
  "tsg hoffenheim": "hoffenheim",
  hoffenheim: "hoffenheim",
  "vfl wolfsburg": "wolfsburg",
  wolfsburg: "wolfsburg",
  "1 fc koln": "fc cologne",
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

function formatSigned(value?: number, digits = 2): string {
  if (value == null || Number.isNaN(value)) return "n/a";
  return `${value >= 0 ? "+" : ""}${value.toFixed(digits)}`;
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

function toneForAction(action?: string): string {
  if (action === "surface") return "text-emerald-300";
  if (action === "shadow_track") return "text-amber-300";
  if (action === "surface_with_caveat") return "text-amber-300";
  return "text-slate-400";
}

function badgeClass(action?: string): string {
  if (action === "surface") return "border-emerald-500/30 bg-emerald-500/10 text-emerald-300";
  if (action === "shadow_track") return "border-amber-500/30 bg-amber-500/10 text-amber-200";
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

  const centreBacks: CsvRow[] = [];
  const widePlayers: CsvRow[] = [];
  const midfielders: CsvRow[] = [];
  const attackers: CsvRow[] = [];
  const utilities: CsvRow[] = [];

  for (const row of outfield) {
    const band = positionBand(row.position);
    if (band === "cb") centreBacks.push(row);
    else if (band === "wide") widePlayers.push(row);
    else if (band === "mid") midfielders.push(row);
    else if (band === "att") attackers.push(row);
    else utilities.push(row);
  }

  for (const row of utilities) {
    if (midfielders.length <= centreBacks.length && midfielders.length <= attackers.length) midfielders.push(row);
    else if (widePlayers.length <= centreBacks.length) widePlayers.push(row);
    else if (attackers.length <= centreBacks.length) attackers.push(row);
    else centreBacks.push(row);
  }

  return {
    keeper,
    centreBacks,
    widePlayers,
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

function shadowStakeLabel(row: CsvRow): string {
  const explicitStake =
    parseFloatMaybe(row.stake_units) ??
    parseFloatMaybe(row.stake) ??
    parseFloatMaybe(row.stake_u);
  if (explicitStake != null) {
    return `${formatDecimal(explicitStake, explicitStake % 1 === 0 ? 0 : 2)}u`;
  }
  return "1u level";
}

function shadowResultTone(row: CsvRow): string {
  const outcome = (row.bet_outcome ?? "").trim().toLowerCase();
  if (outcome === "won") return "text-emerald-300";
  if (outcome === "lost") return "text-rose-300";
  if (outcome === "void" || outcome === "push") return "text-slate-300";
  return "text-amber-200";
}

function ShadowTrackedRowCard({ row }: { row: CsvRow }) {
  const fairOdds = parseFloatMaybe(row.model_fair_odds);
  const bookOdds = parseFloatMaybe(row.best_bookmaker_odds);
  const evPct = parseFloatMaybe(row.ev);
  const pnlUnits = parseFloatMaybe(row.pnl_units);
  const settled = isSettledShadowRow(row);
  const resultLabel = settled ? (row.bet_outcome ?? "settled").toUpperCase() : "OPEN";
  const resultTone = shadowResultTone(row);

  return (
    <div className="rounded-xl border border-slate-800/80 bg-slate-950/50 p-3">
      <div className="flex items-start justify-between gap-3">
        <div>
          <div className="font-medium text-slate-100">{row.player || "Unknown player"}</div>
          <div className="text-sm text-slate-400">{row.match || "Unknown match"}</div>
          <div className="mt-1 text-xs text-slate-500">
            {(row.competition ?? "").trim() || "Goalscorer shadow"}{row.lineup_state ? ` · ${humanizeToken(row.lineup_state)}` : ""}
          </div>
        </div>
        <div className={`text-sm font-medium ${resultTone}`}>{resultLabel}</div>
      </div>

      <div className="mt-3 grid gap-2 text-sm sm:grid-cols-2 xl:grid-cols-4">
        <div className="rounded-lg bg-black/15 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Odds / Fair</div>
          <div className="mt-1 text-slate-200">
            {bookOdds != null ? formatDecimal(bookOdds, 2) : "n/a"} / {fairOdds != null ? formatDecimal(fairOdds, 2) : "n/a"}
          </div>
        </div>
        <div className="rounded-lg bg-black/15 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">Book / Stake</div>
          <div className="mt-1 text-slate-200">
            {(row.best_bookmaker ?? "n/a").trim() || "n/a"} / {shadowStakeLabel(row)}
          </div>
        </div>
        <div className="rounded-lg bg-black/15 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">EV</div>
          <div className={`mt-1 font-medium ${evPct != null && evPct >= 0 ? "text-emerald-300" : "text-rose-300"}`}>
            {evPct != null ? formatPct(evPct * 100, 1) : "n/a"}
          </div>
        </div>
        <div className="rounded-lg bg-black/15 px-3 py-2">
          <div className="text-[10px] uppercase tracking-[0.16em] text-slate-500">P/L</div>
          <div className={`mt-1 font-medium ${pnlUnits != null && pnlUnits >= 0 ? "text-emerald-300" : pnlUnits != null ? "text-rose-300" : "text-slate-400"}`}>
            {pnlUnits != null ? `${formatSigned(pnlUnits, 2)}u` : settled ? "0.00u" : "pending"}
          </div>
        </div>
      </div>
    </div>
  );
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

function PenaltyReviewCard({ row }: { row: PenaltyReviewRow }) {
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

  const [leagueDatasets, shadowContents, snapshotGeneratedAt] = await Promise.all([
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
          comparisonJson,
          comparisonCsv,
          comparisonTxt,
          comparisonMtime: comparisonJsonMtime ?? comparisonCsvMtime,
          lineupsJson,
          rows,
          fixtures,
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
    Promise.all(SHADOW_SIGNAL_FILES.map((file) => readGoalscorerLiveFile(file))),
    readGoalscorerLiveSnapshotGeneratedAt(),
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
  const publicRows = rows.filter((row) => (row.public_action ?? "") === "surface");
  const highRows = [...publicRows];
  const caveatRows = rows.filter((row) => (row.shadow_action ?? "") === "shadow_track" && (row.public_action ?? "") !== "surface");
  const suppressedRows = rows.filter((row) => effectiveMonitorAction(row) === "suppress");

  publicRows.sort((a, b) => (parseFloatMaybe(b.ev) ?? 0) - (parseFloatMaybe(a.ev) ?? 0));
  highRows.sort((a, b) => (parseFloatMaybe(b.ev) ?? 0) - (parseFloatMaybe(a.ev) ?? 0));
  caveatRows.sort((a, b) => (parseFloatMaybe(b.ev) ?? 0) - (parseFloatMaybe(a.ev) ?? 0));

  const comparedAt = rows
    .map((row) => row.compared_at ?? "")
    .filter(Boolean)
    .sort()
    .at(-1) ?? "n/a";
  const liveWindowStart = isoDateInTimezone("Europe/London");
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
  const flaggedFixtures = liveWindowFixtureHealthRows
    .filter((fixture) => fixture.trust_tier === "T3" || (fixture.trust_tier === "T2" && fixture.lineup_input !== "none"))
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
  const benchRows = rows.filter((row) => (row.lineup_status ?? "").toLowerCase() === "confirmed_bench").length;
  const expectedBenchRows = rows.filter((row) => (row.lineup_status ?? "").toLowerCase() === "expected_bench").length;
  const notInSquadRows = rows.filter((row) => (row.lineup_status ?? "").toLowerCase() === "not_in_squad").length;
  const expectedOutRows = rows.filter((row) => (row.lineup_status ?? "").toLowerCase() === "expected_out").length;
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
  const liveSummaryAvailable = leagueDatasets.filter((dataset) => dataset.comparisonJson || dataset.comparisonCsv);
  const leagueStatus = leagueDatasets.map((dataset) => {
    const leagueRows = dataset.rows;
    const leaguePublicRows = leagueRows.filter((row) => (row.public_action ?? "") === "surface");
    const leagueShadowRows = leagueRows.filter((row) => (row.shadow_action ?? "") === "shadow_track" && (row.public_action ?? "") !== "surface");
    const leagueFixtures = dataset.fixtureHealth.filter((fixture) =>
      fixtureInLiveWindow(fixture, liveWindowStart, liveWindowEnd),
    );
    return {
      key: dataset.key,
      label: dataset.label,
      hasOutput: Boolean(dataset.comparisonJson || dataset.comparisonCsv),
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
  const highPenaltyReviewRows = penaltyReviewRows.filter((row) => row.review_priority === "high");
  const mediumPenaltyReviewRows = penaltyReviewRows.filter((row) => row.review_priority === "medium");
  const lowPenaltyReviewRows = penaltyReviewRows.filter((row) => row.review_priority === "low");
  const latestPenaltyReviewAt =
    leagueDatasets
      .flatMap((dataset) => [dataset.penaltyReviewGeneratedAt ?? "", dataset.livePenaltyReviewGeneratedAt ?? ""])
      .filter(Boolean)
      .sort()
      .at(-1) ?? null;

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
              <Stat label="Current Shadow Track" value={`${caveatRows.length}`} tone="text-amber-300" />
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
              <Stat label="Clean Fixtures" value={`${cleanFixtures}`} tone="text-emerald-300" />
              <Stat label="Degraded Fixtures" value={`${degradedFixtures}`} tone="text-amber-300" />
              <Stat label="Quarantined Fixtures" value={`${quarantinedFixtures}`} tone="text-rose-300" />
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
                    public {league.totalPublic} | clean {league.cleanFixtures} | degraded {league.degradedFixtures} | quarantine {league.quarantinedFixtures}
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
                <h2 className="text-lg font-semibold text-slate-100">Current shadow-track rows</h2>
                <p className="mt-1 text-sm text-slate-400">
                  These are the monitor-only rows we still want to follow: expected-starter angles and softer pre-KO ideas that clear the shadow threshold but do not belong on the public page yet.
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
                    <span className={`rounded-full border px-2 py-1 text-[11px] font-semibold uppercase tracking-[0.16em] ${badgeClass(effectiveMonitorAction(row))}`}>
                      {effectiveMonitorActionLabel(row)}
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
                Win rate {formatPct(shadowSummary.winRate, 1)} | ROI sample {shadowSummary.settled} settled picks, so treat the headline ROI as directional only until the book is much larger.
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
                    <ShadowTrackedRowCard key={`open-${row.date}-${row.player}-${row.match}`} row={row} />
                  ))}
                  {settledShadowRows.slice(0, 2).map((row) => (
                    <ShadowTrackedRowCard key={`settled-${row.date}-${row.player}-${row.match}`} row={row} />
                  ))}
                </div>
              )}
            </div>
          </div>
        </section>

        <section className="mb-8 rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Lineup trust watchlist</h2>
              <p className="mt-1 text-sm text-slate-400">
                Fixture-level health checks run before the player-level monitor logic. This watchlist is now trimmed to the
                live window and only shows actionable states: expected-XI fixtures and real structural problems. Empty
                no-payload fixtures stay hidden until there is something worth reviewing.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-800/80 bg-slate-950/35 px-4 py-3 text-sm text-slate-300">
              <div><span className="text-slate-500">Actionable fixtures:</span> {flaggedFixtures.length}</div>
              <div><span className="text-slate-500">Quarantined:</span> {quarantinedFixtures}</div>
              <div><span className="text-slate-500">Hidden pending lineups:</span> {hiddenPendingFixtures}</div>
            </div>
          </div>

          {flaggedFixtures.length === 0 ? (
            <div className="rounded-xl border border-emerald-500/15 bg-emerald-500/5 p-4 text-sm text-emerald-200">
              No degraded or quarantined lineup payloads in the current live window.
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
        </section>

        <section className="mb-8 rounded-2xl border border-slate-800 bg-[linear-gradient(180deg,rgba(20,25,34,0.96),rgba(11,15,21,0.96))] p-5 shadow-[0_20px_60px_rgba(0,0,0,0.28)]">
          <div className="mb-5 flex flex-col gap-3 lg:flex-row lg:items-end lg:justify-between">
            <div>
              <h2 className="text-lg font-semibold text-slate-100">Penalty duty watchlist</h2>
              <p className="mt-1 text-sm text-slate-400">
                This is the daily editorial queue for the penalty-taker boards. It compares who actually took recent penalties
                against the pre-match hierarchy and flags anything that looks like a real shift rather than normal hold behaviour.
              </p>
            </div>
            <div className="rounded-2xl border border-slate-800/80 bg-slate-950/35 px-4 py-3 text-sm text-slate-300">
              <div><span className="text-slate-500">Latest review:</span> {latestPenaltyReviewAt ?? "missing"}</div>
              <div><span className="text-slate-500">Rows:</span> {penaltyReviewRows.length}</div>
            </div>
          </div>

          <div className="grid gap-4 md:grid-cols-2 xl:grid-cols-4">
            <Stat label="High Priority" value={`${highPenaltyReviewRows.length}`} tone="text-rose-300" />
            <Stat label="Medium Priority" value={`${mediumPenaltyReviewRows.length}`} tone="text-amber-300" />
            <Stat label="Low Priority" value={`${lowPenaltyReviewRows.length}`} tone="text-slate-300" />
            <Stat label="Recent Events" value={`${penaltyReviewRows.length}`} />
          </div>

          <div className="mt-5 space-y-4">
            {penaltyReviewRows.map((row, idx) => (
              <PenaltyReviewCard key={`${row.date}-${row.team}-${row.actual_taker}-${idx}`} row={row} />
            ))}
            {penaltyReviewRows.length === 0 ? (
              <div className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-4 text-sm text-slate-500">
                No penalty-duty review rows yet. Once recent league contexts and settled player logs overlap, this fills with
                real hierarchy holds and review flags.
              </div>
            ) : null}
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
                {(() => {
                  const lineup = lineupMap.get(`${fixture.leagueKey}|${teamKey(fixture.homeTeam)}|${teamKey(fixture.awayTeam)}`);
                  const fixtureHealth = fixtureHealthMap.get(
                    fixtureHealthKey(fixture.leagueKey, fixture.matchDate, fixture.homeTeam, fixture.awayTeam),
                  );
                  const isQuarantined = fixtureHealth?.trust_tier === "T3";
                  const isDegraded = fixtureHealth?.trust_tier === "T2";
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
                          <p className="text-sm text-slate-400">{fixture.matchDate} | {fixture.bookmaker}</p>
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

                      {fixtureHealth && (isDegraded || isQuarantined) ? (
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

