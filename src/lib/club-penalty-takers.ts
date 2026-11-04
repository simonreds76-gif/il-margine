import "server-only";
import penaltyPortraits from "../../data/goalscorer/penalty-player-portraits.json";
import { foldNameText } from "@/lib/player-name-matching";
import { correctFootballClubNames } from "@/lib/football-club-names";

import { cache } from "react";
import { promises as fs } from "node:fs";
import { BASE_URL } from "@/lib/config";
import { getKnownProjectFilePath, type KnownProjectFile } from "@/lib/project-file-paths";
import clubPenaltySeason from "../../data/goalscorer/club-penalty-season.json";
import { readPenaltyOverrides } from "@/lib/penalty-editorial-store";
import { penaltyKey } from "@/lib/penalty-editorial";

export const CLUB_PENALTY_SEASON = clubPenaltySeason.label;
export const CLUB_PENALTY_PREVIOUS_SEASON = clubPenaltySeason.previous_label;
export const CLUB_PENALTY_BASE_PATH = "/penalty-takers";

type PenaltyConfidence = "high" | "medium" | "low";
type PenaltyHierarchyStatus = "confirmed" | "probable" | "conditional" | "disputed" | "unknown";

type PenaltyEvidenceRow = {
  id?: string;
  date?: string;
  type?: string;
  match?: string;
  headline?: string;
  context?: string;
  editorial_note?: string;
  affects_hierarchy?: boolean;
  sources?: Array<{ label?: string; url?: string | null; date?: string; note?: string }>;
  review?: { status?: string };
};

type PenaltyTeamRow = {
  primary?: string;
  secondary?: string;
  tertiary?: string;
  last_updated?: string;
  hierarchy_status?: PenaltyHierarchyStatus;
  confidence?: Partial<Record<"primary" | "secondary" | "tertiary", PenaltyConfidence | null>>;
  condition_note?: string;
  last_verified?: { date?: string; by?: string; method?: string };
  last_reviewed?: {
    date?: string;
    by?: string;
    method?: string;
    outcome?: string;
    sources?: string[];
  };
  public_updated_at?: string;
  evidence_log?: PenaltyEvidenceRow[];
  change_log?: Array<{ change_type?: string; changed_at?: string; reason?: string }>;
  flags?: { carryover_from_previous_season?: boolean; weak_evidence?: boolean };
};

type PenaltyFileMeta = {
  schema_version?: number;
  season?: { label?: string; status?: string };
  relegated?: Array<{ team?: string; archived_slug?: string; archive?: string }>;
  last_verified?: string;
  public_updated_at?: string;
};

type PenaltyFile = Record<string, PenaltyTeamRow | PenaltyFileMeta | undefined> & { _meta?: PenaltyFileMeta };

type TeamLogoRow = { logo_path?: string; team_key?: string };
type LogoManifest = {
  leagues?: Record<string, { label?: string; teams?: Record<string, TeamLogoRow> }>;
};

export type ClubPenaltySeason = typeof clubPenaltySeason;

export type ClubLeagueConfig = {
  key: string;
  label: string;
  short: string;
  file: KnownProjectFile;
  archiveFile: KnownProjectFile;
  logoPath: string;
  accent: string;
  surface: string;
  copy: string;
};

export type ClubPenaltyTeam = {
  leagueKey: string;
  leagueLabel: string;
  leagueShort: string;
  leagueLogoPath: string;
  leagueAccent: string;
  leagueSurface: string;
  leagueCopy: string;
  team: string;
  slug: string;
  primary: string;
  secondary: string;
  tertiary: string;
  verifiedNames: string[];
  portraitUrls: (string | null)[];
  hierarchyDepth: 0 | 1 | 2 | 3;
  hierarchyStatus: PenaltyHierarchyStatus;
  primaryConfidence: PenaltyConfidence;
  confidence: Partial<Record<"primary" | "secondary" | "tertiary", PenaltyConfidence | null>>;
  checkedAt: string;
  checkedLabel: string;
  lastUpdated: string;
  lastUpdatedLabel: string;
  publicUpdatedAt: string;
  publicUpdatedLabel: string;
  leagueCheckedAt: string;
  leagueCheckedLabel: string;
  conditionNote: string;
  isCarryover: boolean;
  isArchived: boolean;
  weakEvidence: boolean;
  evidenceCount: number;
  evidenceSources: Array<{ label: string; url: string; date: string; note: string }>;
  evidenceUpdates: ClubPenaltyEvidenceUpdate[];
  seasonLabel: string;
  seasonStatus: string;
  logoPath: string;
  initials: string;
  relativeUrl: string;
  absoluteUrl: string;
};

export type ClubPenaltyEvidenceUpdate = {
  id: string;
  date: string;
  dateLabel: string;
  type: string;
  match: string;
  headline: string;
  summary: string;
  fullSummary: string;
  affectsHierarchy: boolean;
};

export type ClubPenaltyNewsItem = ClubPenaltyEvidenceUpdate & {
  team: string;
  leagueKey: string;
  leagueLabel: string;
  primary: string;
  secondary: string;
  hierarchyStatus: PenaltyHierarchyStatus;
  logoPath: string;
  initials: string;
  relativeUrl: string;
};

export type ClubPenaltyLeague = ClubLeagueConfig & {
  teams: ClubPenaltyTeam[];
  archivedTeams: ClubPenaltyTeam[];
  publicUpdatedAt: string;
  boardCheckedAt: string;
  boardCheckedLabel: string;
  phase: "live" | "preseason";
};

export const CLUB_LEAGUES: ClubLeagueConfig[] = [
  {
    key: "epl",
    label: "Premier League",
    short: "PL",
    file: "data/goalscorer/epl-penalty-takers.json",
    archiveFile: "data/goalscorer/archive/2025-26/epl-penalty-takers.json",
    logoPath: "/league-logos/epl.png",
    accent: "indigo",
    surface: "from-indigo-500/24 via-indigo-400/8 to-slate-950",
    copy: "Premier League penalty roles can change with transfers, team selection and recent spot-kick evidence. We publish only the order supported by the current file.",
  },
  {
    key: "serie-a",
    label: "Serie A",
    short: "SA",
    file: "data/goalscorer/serie-a-penalty-takers.json",
    archiveFile: "data/goalscorer/archive/2025-26/serie-a-penalty-takers.json",
    logoPath: "/league-logos/serie-a.png",
    accent: "emerald",
    surface: "from-emerald-500/24 via-emerald-400/8 to-slate-950",
    copy: "Serie A penalty roles can move quickly around transfers, coaching changes and form. Each filed name must be supported by current evidence.",
  },
  {
    key: "la-liga",
    label: "La Liga",
    short: "LL",
    file: "data/goalscorer/la-liga-penalty-takers.json",
    archiveFile: "data/goalscorer/archive/2025-26/la-liga-penalty-takers.json",
    logoPath: "/league-logos/la-liga.png",
    accent: "amber",
    surface: "from-amber-500/24 via-amber-400/8 to-slate-950",
    copy: "La Liga penalty roles are reviewed against current squad status, match events and specialist reporting. Unverified places are left open rather than guessed.",
  },
  {
    key: "bundesliga",
    label: "Bundesliga",
    short: "BL",
    file: "data/goalscorer/bundesliga-penalty-takers.json",
    archiveFile: "data/goalscorer/archive/2025-26/bundesliga-penalty-takers.json",
    logoPath: "/league-logos/bundesliga.png",
    accent: "rose",
    surface: "from-rose-500/24 via-rose-400/8 to-slate-950",
    copy: "Bundesliga penalty roles can change after a miss, injury, substitution or coaching decision. The page separates verified names from open places.",
  },
  {
    key: "ligue-1",
    label: "Ligue 1",
    short: "L1",
    file: "data/goalscorer/ligue-1-penalty-takers.json",
    archiveFile: "data/goalscorer/archive/2025-26/ligue-1-penalty-takers.json",
    logoPath: "/league-logos/ligue-1.png",
    accent: "cyan",
    surface: "from-cyan-500/24 via-cyan-400/8 to-slate-950",
    copy: "Ligue 1 penalty roles need current evidence rather than reputation. The page shows the verified order and leaves unsupported positions open.",
  },
];

const EMPTY_LOGO_MANIFEST: LogoManifest = { leagues: {} };

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

export function cleanClubPenaltyText(value?: string): string {
  return repairMojibake(
    (value ?? "")
      .trim()
      .replace(/&#0*39;|&#x27;|&apos;/gi, "'")
      .replace(/&amp;/gi, "&")
      .replace(/&quot;/gi, '"')
      .replace(/&nbsp;/gi, " "),
  ).replace(/\s+/g, " ");
}

const UNVERIFIED_TAKER_VALUES = new Set(["", "tbc", "tbd", "n/a", "-", "unknown", "not yet verified"]);

export function isVerifiedTaker(value?: string): boolean {
  return !UNVERIFIED_TAKER_VALUES.has(cleanClubPenaltyText(value).toLowerCase());
}

function truncateClubPenaltyText(value: string, maxLength: number): string {
  if (value.length <= maxLength) return value;
  const clipped = value.slice(0, maxLength + 1);
  const boundary = clipped.lastIndexOf(" ");
  return `${clipped.slice(0, boundary > maxLength * 0.65 ? boundary : maxLength).trimEnd()}...`;
}

export function summarizeClubPenaltyText(value?: string, maxLength = 220): string {
  const cleaned = cleanClubPenaltyText(value).split(/\bConditions?:\s*/i)[0]?.trim() ?? "";
  if (!cleaned) return "";
  const sentences = cleaned.match(/[^.!?]+[.!?]+|[^.!?]+$/g) ?? [cleaned];
  return truncateClubPenaltyText(sentences.slice(0, 2).join(" ").replace(/\s+/g, " ").trim(), maxLength);
}

export function buildClubPenaltyConditionSummary(team: ClubPenaltyTeam): string {
  return summarizeClubPenaltyText(team.conditionNote);
}

export function buildClubPenaltyWatchNote(team: ClubPenaltyTeam): string {
  const match = cleanClubPenaltyText(team.conditionNote).match(/\bConditions?:\s*(.+)$/i);
  return match?.[1] ? truncateClubPenaltyText(match[1], 180) : "";
}

export function normalizeClubPenaltyKey(value: string): string {
  return correctFootballClubNames(cleanClubPenaltyText(value))
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .toLowerCase();
}

export function clubPenaltySlug(value: string): string {
  return normalizeClubPenaltyKey(value).replace(/\s+/g, "-");
}

export function clubPenaltyLeagueRelativeUrl(leagueKey: string): string {
  return `${CLUB_PENALTY_BASE_PATH}/${leagueKey}`;
}

export function clubPenaltyLeagueUrl(leagueKey: string): string {
  return `${BASE_URL}${clubPenaltyLeagueRelativeUrl(leagueKey)}`;
}

export function clubPenaltyTeamRelativeUrl(leagueKey: string, teamSlug: string): string {
  return `${clubPenaltyLeagueRelativeUrl(leagueKey)}/${teamSlug}`;
}

export function clubPenaltyTeamUrl(leagueKey: string, teamSlug: string): string {
  return `${BASE_URL}${clubPenaltyTeamRelativeUrl(leagueKey, teamSlug)}`;
}

function buildInitials(team: string): string {
  const parts = cleanClubPenaltyText(team).replace(/[.'-]/g, " ").split(/\s+/).filter(Boolean);
  if (!parts.length) return "FC";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return parts.slice(0, 2).map((part) => part[0]?.toUpperCase() ?? "").join("");
}

function parseDateOnly(value?: string): number {
  if (!value) return Number.NaN;
  return Date.parse(`${value}T12:00:00Z`);
}

// Reuse the immutable ICU formatter; constructing one for every team/date is expensive.
const clubPenaltyDateFormatter = new Intl.DateTimeFormat("en-GB", {
  timeZone: "Europe/London", day: "numeric", month: "short", year: "numeric",
});

export function formatClubPenaltyDate(value?: string): string {
  const stamp = parseDateOnly(value);
  if (!Number.isFinite(stamp)) return value ?? "";
  return clubPenaltyDateFormatter.format(new Date(stamp));
}

function findLogoPath(leagueKey: string, team: string, manifest: LogoManifest): string {
  const teams = manifest.leagues?.[leagueKey]?.teams ?? {};
  if (teams[team]?.logo_path) return cleanClubPenaltyText(teams[team].logo_path);
  const normalizedTeam = normalizeClubPenaltyKey(team);
  const matched = Object.entries(teams).find(([name]) => normalizeClubPenaltyKey(name) === normalizedTeam);
  return matched?.[1]?.logo_path ? cleanClubPenaltyText(matched[1].logo_path) : "";
}

async function readJson<T>(relativePath: KnownProjectFile): Promise<T> {
  const raw = await fs.readFile(getKnownProjectFilePath(relativePath), "utf8");
  return JSON.parse(raw) as T;
}

async function readLogoManifest(): Promise<LogoManifest> {
  return readJson<LogoManifest>("data/goalscorer/team-logo-map.json").catch(() => EMPTY_LOGO_MANIFEST);
}

function asTeamRow(value: PenaltyTeamRow | PenaltyFileMeta | undefined): PenaltyTeamRow {
  return value && typeof value === "object" ? (value as PenaltyTeamRow) : {};
}

function mapTeam(
  league: ClubLeagueConfig,
  teamName: string,
  entryValue: PenaltyTeamRow | PenaltyFileMeta | undefined,
  manifest: LogoManifest,
  options: { archived?: boolean; leagueCheckedAt?: string } = {},
): ClubPenaltyTeam {
  const entry = asTeamRow(entryValue);
  const team = correctFootballClubNames(cleanClubPenaltyText(teamName));
  const slug = clubPenaltySlug(team);
  const relativeUrl = clubPenaltyTeamRelativeUrl(league.key, slug);
  const lastUpdated = cleanClubPenaltyText(entry.last_updated || entry.last_verified?.date);
  const checkedAt = [entry.last_reviewed?.date, entry.last_verified?.date]
    .map(value => cleanClubPenaltyText(value))
    .filter(value => /^\d{4}-\d{2}-\d{2}$/.test(value))
    .sort().at(-1) || cleanClubPenaltyText(options.leagueCheckedAt);
  const publicUpdatedAt = cleanClubPenaltyText(entry.public_updated_at || entry.last_updated);
  const isArchived = Boolean(options.archived);
  const isCarryover = !isArchived && Boolean(entry.flags?.carryover_from_previous_season);
  const approvedEvidence = (entry.evidence_log ?? []).filter((evidence) => evidence.review?.status === "approved").length;
  const supersedingReviewDates = new Set(
    (entry.evidence_log ?? [])
      .filter(
        (evidence) =>
          evidence.review?.status === "approved" &&
          cleanClubPenaltyText(evidence.type) === "current_season_board_review" &&
          evidence.affects_hierarchy,
      )
      .map((evidence) => cleanClubPenaltyText(evidence.date))
      .filter(Boolean),
  );
  const evidenceUpdates = (entry.evidence_log ?? [])
    .filter((evidence) => evidence.review?.status === "approved")
    .filter((evidence) => {
      const type = cleanClubPenaltyText(evidence.type);
      const date = cleanClubPenaltyText(evidence.date);
      if (type === "roster_integrity_review" && evidence.affects_hierarchy && supersedingReviewDates.has(date)) {
        return false;
      }
      return (
        type.startsWith("competitive_penalty_") ||
        type === "preseason_penalty_assignment" ||
        (type === "editorial_hierarchy_review" && evidence.affects_hierarchy) ||
        type === "roster_integrity_review" ||
        (type === "current_season_board_review" && evidence.affects_hierarchy)
      );
    })
    .map((evidence, index) => {
      const date = cleanClubPenaltyText(evidence.date);
      const fullSummary = cleanClubPenaltyText(evidence.editorial_note || evidence.context);
      const summary = summarizeClubPenaltyText(fullSummary, 210);
      return {
        id: cleanClubPenaltyText(evidence.id) || `${slug}-${date || "undated"}-${index}`,
        date,
        dateLabel: formatClubPenaltyDate(date),
        type: cleanClubPenaltyText(evidence.type),
        match: cleanClubPenaltyText(evidence.match),
        headline: cleanClubPenaltyText(evidence.headline) || `${team} penalty update`,
        summary,
        fullSummary,
        affectsHierarchy: Boolean(evidence.affects_hierarchy),
      } satisfies ClubPenaltyEvidenceUpdate;
    })
    .filter((evidence) => evidence.date && evidence.summary)
    .sort((left, right) => right.date.localeCompare(left.date) || right.id.localeCompare(left.id));
  const approvedSourceEvidence = (entry.evidence_log ?? [])
    .filter((evidence) => evidence.review?.status === "approved" && (evidence.sources ?? []).length > 0)
    .sort((left, right) => cleanClubPenaltyText(right.date).localeCompare(cleanClubPenaltyText(left.date)));
  const latestSourceDate = cleanClubPenaltyText(approvedSourceEvidence[0]?.date);
  const evidenceSources = approvedSourceEvidence
    .filter((evidence) => cleanClubPenaltyText(evidence.date) === latestSourceDate)
    .flatMap((evidence) =>
      (evidence.sources ?? []).map((source) => {
        const sourceLabel = cleanClubPenaltyText(source.label);
        const sourceNote = cleanClubPenaltyText(source.note);
        const genericLabel = sourceLabel.toLowerCase() === "il margine source review";
        return {
          label: genericLabel && sourceNote ? sourceNote : sourceLabel || "Source",
          url: cleanClubPenaltyText(source.url ?? ""),
          date: cleanClubPenaltyText(source.date || evidence.date),
          note: genericLabel ? "" : summarizeClubPenaltyText(sourceNote || evidence.context || evidence.editorial_note, 150),
        };
      }),
    )
    .filter((source) => /^https?:\/\//i.test(source.url))
    .filter((source, index, rows) => rows.findIndex((row) => row.url === source.url) === index)
    .slice(0, 6);
  const hierarchyCandidates = [entry.primary, entry.secondary, entry.tertiary].map((value) => cleanClubPenaltyText(value));
  const verifiedNames: string[] = [];
  for (const candidate of hierarchyCandidates) {
    if (!isVerifiedTaker(candidate)) break;
    verifiedNames.push(candidate);
  }
  const hierarchyDepth = verifiedNames.length as 0 | 1 | 2 | 3;

  return {
    leagueKey: league.key,
    leagueLabel: league.label,
    leagueShort: league.short,
    leagueLogoPath: league.logoPath,
    leagueAccent: league.accent,
    leagueSurface: league.surface,
    leagueCopy: league.copy,
    team,
    slug,
    primary: verifiedNames[0] ?? "",
    secondary: verifiedNames[1] ?? "",
    tertiary: verifiedNames[2] ?? "",
    verifiedNames,
    portraitUrls: verifiedNames.map(name => {
      const key = foldNameText(name).toLowerCase().replace(/[^a-z0-9]/g, "");
      const clubKey = foldNameText(team).toLowerCase().replace(/[^a-z0-9]/g, "");
      const portraits = penaltyPortraits as Record<string, string>;
      const id = portraits[`${league.key}|${clubKey}|${key}`] || portraits[key];
      return id ? `https://images.fotmob.com/image_resources/playerimages/${id}.png`
        : isArchived ? null : `/api/penalty-portrait/${league.key}/${slug}/${key}`;
    }),
    hierarchyDepth,
    hierarchyStatus: isArchived ? "confirmed" : entry.hierarchy_status ?? (entry.primary ? "probable" : "unknown"),
    primaryConfidence: entry.confidence?.primary ?? (entry.primary ? "medium" : "low"),
    confidence: entry.confidence ?? {},
    checkedAt,
    checkedLabel: formatClubPenaltyDate(checkedAt),
    lastUpdated,
    lastUpdatedLabel: formatClubPenaltyDate(lastUpdated),
    publicUpdatedAt,
    publicUpdatedLabel: formatClubPenaltyDate(publicUpdatedAt),
    leagueCheckedAt: cleanClubPenaltyText(options.leagueCheckedAt),
    leagueCheckedLabel: formatClubPenaltyDate(options.leagueCheckedAt),
    conditionNote: cleanClubPenaltyText(entry.condition_note),
    isCarryover,
    isArchived,
    weakEvidence: isArchived ? false : Boolean(entry.flags?.weak_evidence),
    evidenceCount: approvedEvidence,
    evidenceSources,
    evidenceUpdates,
    seasonLabel: isArchived ? CLUB_PENALTY_PREVIOUS_SEASON : CLUB_PENALTY_SEASON,
    seasonStatus: isArchived ? "archived" : clubPenaltySeason.status,
    logoPath: findLogoPath(league.key, teamName, manifest),
    initials: buildInitials(team),
    relativeUrl,
    absoluteUrl: `${BASE_URL}${relativeUrl}`,
  };
}

export function getClubPenaltySeason(): ClubPenaltySeason {
  return clubPenaltySeason;
}

// React cache deduplicates metadata/page reads within a render only. A later
// request still reads current files, preserving local edits and invalidation.
export const readClubPenaltyData = cache(async (): Promise<ClubPenaltyLeague[]> => {
  const [logoManifest, overrides] = await Promise.all([readLogoManifest(), readPenaltyOverrides()]);
  return Promise.all(
    CLUB_LEAGUES.map(async (league) => {
      const [penaltyFile, archiveFile] = await Promise.all([
        readJson<PenaltyFile>(league.file),
        readJson<PenaltyFile>(league.archiveFile),
      ]);
      for (const [teamName, raw] of Object.entries(penaltyFile)) {
        if (teamName.startsWith("_") || !raw) continue;
        const override = overrides[penaltyKey(league.key, correctFootballClubNames(teamName))];
        if (!override || override.season !== CLUB_PENALTY_SEASON) continue;
        const old = raw as PenaltyTeamRow;
        if (override.at.slice(0, 10) > (penaltyFile._meta?.public_updated_at ?? "")) penaltyFile._meta = {...penaltyFile._meta, public_updated_at: override.at.slice(0, 10)};
        penaltyFile[teamName] = {...old, ...override.order, condition_note: override.reason,
          hierarchy_status: "probable", confidence: {primary: "medium", secondary: override.order.secondary ? "medium" : null, tertiary: override.order.tertiary ? "medium" : null},
          last_updated: override.at.slice(0, 10), public_updated_at: override.at.slice(0, 10),
          last_verified: {date: override.at.slice(0, 10), by: "Il Margine editorial", method: "Owner hierarchy review"},
          flags: {...old.flags, carryover_from_previous_season: false},
          evidence_log: [...(old.evidence_log ?? []), {id: `admin-${override.at}`, date: override.at.slice(0, 10), type: "editorial_hierarchy_review", headline: "Penalty order reviewed", context: override.reason, affects_hierarchy: true, review: {status: "approved"}, sources: override.source ? [{label: "Editorial source", url: override.source}] : []}]};
      }
      const meta = penaltyFile._meta ?? {};
      const publicUpdatedAt = cleanClubPenaltyText(meta.public_updated_at) || clubPenaltySeason.published_at;
      const boardCheckedAt = cleanClubPenaltyText(meta.last_verified) || publicUpdatedAt;
      const startDate = clubPenaltySeason.league_start_dates[league.key as keyof typeof clubPenaltySeason.league_start_dates];
      const phase = startDate && Date.now() >= Date.parse(`${startDate}T00:00:00Z`) ? "live" : "preseason";
      const teams = Object.entries(penaltyFile)
        .filter(([teamName]) => !teamName.startsWith("_"))
        .map(([teamName, entry]) => mapTeam(league, teamName, entry, logoManifest, { leagueCheckedAt: boardCheckedAt }))
        .sort((left, right) => left.team.localeCompare(right.team, "en"));
      const archivedNames = new Set((meta.relegated ?? []).map((row) => cleanClubPenaltyText(row.team)));
      const archivedTeams = Object.entries(archiveFile)
        .filter(([teamName]) => archivedNames.has(cleanClubPenaltyText(teamName)))
        .map(([teamName, entry]) => mapTeam(league, teamName, entry, logoManifest, { archived: true }))
        .sort((left, right) => left.team.localeCompare(right.team, "en"));
      return {
        ...league,
        teams,
        archivedTeams,
        publicUpdatedAt,
        boardCheckedAt,
        boardCheckedLabel: formatClubPenaltyDate(boardCheckedAt),
        phase,
      };
    }),
  );
});

export async function readAllClubPenaltyTeams(options: { includeArchived?: boolean } = {}): Promise<ClubPenaltyTeam[]> {
  const leagues = await readClubPenaltyData();
  const includeArchived = options.includeArchived ?? true;
  return leagues.flatMap((league) => includeArchived ? [...league.teams, ...league.archivedTeams] : league.teams);
}

export function getLatestClubPenaltyNews(leagues: ClubPenaltyLeague[], limit = 8): ClubPenaltyNewsItem[] {
  return leagues
    .flatMap((league) =>
      league.teams.flatMap((team) =>
        team.evidenceUpdates.map((update) => ({
          ...update,
          team: team.team,
          leagueKey: team.leagueKey,
          leagueLabel: team.leagueLabel,
          primary: team.primary,
          secondary: team.secondary,
          hierarchyStatus: team.hierarchyStatus,
          logoPath: team.logoPath,
          initials: team.initials,
          relativeUrl: team.relativeUrl,
        })),
      ),
    )
    .sort((left, right) => right.date.localeCompare(left.date) || right.id.localeCompare(left.id))
    .slice(0, Math.max(limit, 0));
}

export async function getClubPenaltyLeague(leagueSlug: string): Promise<ClubPenaltyLeague | undefined> {
  const leagues = await readClubPenaltyData();
  return leagues.find((candidate) => candidate.key === leagueSlug);
}

export async function getClubPenaltyTeam(leagueSlug: string, teamSlug: string): Promise<ClubPenaltyTeam | undefined> {
  const league = await getClubPenaltyLeague(leagueSlug);
  return [...(league?.teams ?? []), ...(league?.archivedTeams ?? [])].find((team) => team.slug === teamSlug);
}

export function buildClubPenaltyTitle(team: ClubPenaltyTeam): string {
  if (team.isArchived) return `${team.team} Penalty Takers ${team.seasonLabel} (Archived)`;
  const question = `Who Takes Penalties for ${team.team}? ${CLUB_PENALTY_SEASON} Penalty Takers`;
  return question.length <= 64 ? question : `${team.team} Penalty Takers ${CLUB_PENALTY_SEASON}`;
}

export function buildClubPenaltyDescription(team: ClubPenaltyTeam): string {
  if (team.isArchived) {
    if (team.hierarchyDepth >= 3) return `Archived ${team.seasonLabel} penalty hierarchy for ${team.team}: ${team.primary} first, ${team.secondary} second and ${team.tertiary} third.`;
    if (team.hierarchyDepth === 2) return `Archived ${team.seasonLabel} penalty hierarchy for ${team.team}: ${team.primary} first and ${team.secondary} second.`;
    if (team.hierarchyDepth === 1) return `Archived ${team.seasonLabel} penalty record for ${team.team}: ${team.primary} was the filed first choice.`;
    return `Archived ${team.seasonLabel} penalty-taker record for ${team.team}.`;
  }
  return buildClubPenaltyLead(team);
}

// Presentation only: never infer a confirmed role from an incomplete record.
export function clubPenaltyOrderStatus(team: ClubPenaltyTeam): "confirmed" | "provisional" | "conditional" | "disputed" | "unknown" {
  if (!team.primary || team.hierarchyDepth === 0 || team.hierarchyStatus === "unknown") return "unknown";
  if (team.hierarchyStatus === "disputed" || team.hierarchyStatus === "conditional") return team.hierarchyStatus;
  if (team.hierarchyStatus === "confirmed" && !team.isCarryover && !team.weakEvidence && team.primaryConfidence !== "low") return "confirmed";
  return "provisional";
}

export function clubPenaltyRankLabels(team: ClubPenaltyTeam): string[] {
  return team.isArchived || clubPenaltyOrderStatus(team) === "confirmed"
    ? ["First choice", "Second choice", "Third choice"]
    : ["Listed primary", "Listed second", "Listed third"];
}

export function buildClubPenaltyLead(team: ClubPenaltyTeam): string {
  if (team.isArchived) {
    return `This is the final archived ${team.seasonLabel} order. ${team.team} is not part of the current ${team.leagueLabel} board.`;
  }
  const status = clubPenaltyOrderStatus(team);
  if (status === "unknown") return `${team.team}'s current penalty order is unconfirmed. See the evidence and any provisional names listed below.`;
  const deputy = team.secondary ? `, with ${team.secondary} listed next` : "";
  if (status === "confirmed") return `${team.primary} is ${team.team}'s first-choice penalty taker${deputy}.`;
  return `${team.team}'s penalty order is ${status}. ${team.primary} leads our listed order${deputy}; the next taker is not confirmed.`;
}

export function buildClubPenaltyHierarchyNote(team: ClubPenaltyTeam): string {
  if (team.isArchived) return `This page preserves the filed ${team.seasonLabel} order and does not present it as a current-season hierarchy.`;
  if (clubPenaltyOrderStatus(team) !== "confirmed") {
    const names = [team.primary, team.secondary, team.tertiary].filter(Boolean);
    return names.length
      ? `Listed order: ${names.join(", ")}. This ${clubPenaltyOrderStatus(team) === "unknown" ? "unconfirmed" : clubPenaltyOrderStatus(team)} order is a projection, not a guaranteed sequence. Read the evidence note for the circumstances behind it.`
      : "No penalty taker is currently filed. The order awaits verified evidence.";
  }
  if (team.hierarchyDepth === 3) return `If ${team.primary} is unavailable, ${team.secondary} is the filed second choice and ${team.tertiary} is third.`;
  if (team.hierarchyDepth === 2) return `If ${team.primary} is unavailable, ${team.secondary} is the filed second choice. No third-choice taker is verified, so the final place remains open.`;
  if (team.hierarchyDepth === 1) return `No backup is verified behind ${team.primary}. If the primary is unavailable, the next penalty is an open assignment rather than a guessed hierarchy.`;
  return `No penalty taker is currently filed. The page will be updated only when direct evidence supports a name.`;
}

export type ClubPenaltyFaqItem = { question: string; answer: string };

export function buildClubPenaltyFaq(team: ClubPenaltyTeam): ClubPenaltyFaqItem[] {
  if (team.isArchived) {
    return [
      {
        question: `Who was ${team.team}'s penalty taker in ${team.seasonLabel}?`,
        answer: team.hierarchyDepth ? `${team.primary} was the filed first choice in the archived ${team.seasonLabel} order.` : `No verified first choice is retained in the archived ${team.seasonLabel} file.`,
      },
      {
        question: `Is this ${team.team} penalty hierarchy current?`,
        answer: `No. This is an archived ${team.seasonLabel} record and is not presented as the current ${team.leagueLabel} order.`,
      },
    ];
  }

  const primaryAnswer = buildClubPenaltyLead(team);
  if (team.hierarchyDepth >= 2) {
    return [
      { question: `Who is ${team.team}'s penalty taker?`, answer: primaryAnswer },
      {
        question: `Who is ${team.team}'s second-choice penalty taker?`,
        answer: buildClubPenaltyHierarchyNote(team),
      },
    ];
  }

  return [
    { question: `Who is ${team.team}'s penalty taker?`, answer: primaryAnswer },
    {
      question: `Does ${team.team} have a verified backup penalty taker?`,
      answer: team.hierarchyDepth === 1
        ? `No backup is listed behind ${team.primary}. ${buildClubPenaltyHierarchyNote(team)}`
        : `No. Neither a first-choice nor a backup penalty taker is currently verified.`,
    },
  ];
}

export function buildClubPenaltyCardSummary(team: ClubPenaltyTeam): string {
  return buildClubPenaltyLead(team);
}

/** Small static search index; no client requests or private evidence payload. */
export function buildPenaltyDirectory(leagues: ClubPenaltyLeague[]) {
  return leagues.map(league => ({ key: league.key, label: league.label, logoPath: league.logoPath,
    teams: league.teams.map(team => ({ name: team.team, url: team.relativeUrl, logoPath: team.logoPath, players: team.verifiedNames, portraits: team.portraitUrls, rankLabels: clubPenaltyRankLabels(team), status: clubPenaltyOrderStatus(team) })),
  }));
}
