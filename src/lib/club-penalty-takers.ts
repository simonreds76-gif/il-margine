import "server-only";

import { promises as fs } from "node:fs";
import { BASE_URL } from "@/lib/config";
import { getKnownProjectFilePath, type KnownProjectFile } from "@/lib/project-file-paths";

export const CLUB_PENALTY_SEASON = "2025/26";
export const CLUB_PENALTY_BASE_PATH = "/penalty-takers";

type PenaltyTeamRow = {
  primary?: string;
  secondary?: string;
  tertiary?: string;
  last_updated?: string;
  source?: string;
  cross_check?: string;
};

type PenaltyFile = Record<string, PenaltyTeamRow>;

type TeamLogoRow = {
  logo_path?: string;
  team_key?: string;
};

type LogoManifest = {
  leagues?: Record<
    string,
    {
      label?: string;
      teams?: Record<string, TeamLogoRow>;
    }
  >;
};

export type ClubLeagueConfig = {
  key: string;
  label: string;
  short: string;
  file: KnownProjectFile;
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
  lastUpdated: string;
  lastUpdatedLabel: string;
  source: string;
  crossCheck: string;
  logoPath: string;
  initials: string;
  relativeUrl: string;
  absoluteUrl: string;
};

export type ClubPenaltyLeague = ClubLeagueConfig & {
  teams: ClubPenaltyTeam[];
};

export const CLUB_LEAGUES: ClubLeagueConfig[] = [
  {
    key: "serie-a",
    label: "Serie A",
    short: "SA",
    file: "data/goalscorer/serie-a-penalty-takers.json",
    logoPath: "/league-logos/serie-a.png",
    accent: "emerald",
    surface: "from-emerald-500/24 via-emerald-400/8 to-slate-950",
    copy: "Serie A penalty orders move quickly around transfers, coaching changes and form. We keep the backup line visible because the second name is often the value edge when the regular taker is off the pitch.",
  },
  {
    key: "epl",
    label: "Premier League",
    short: "PL",
    file: "data/goalscorer/epl-penalty-takers.json",
    logoPath: "/league-logos/epl.png",
    accent: "indigo",
    surface: "from-indigo-500/24 via-indigo-400/8 to-slate-950",
    copy: "Premier League markets react quickly to the obvious taker, so the useful reference is the full order: who steps up first, who follows, and who becomes live if team news removes the headline name.",
  },
  {
    key: "la-liga",
    label: "La Liga",
    short: "LL",
    file: "data/goalscorer/la-liga-penalty-takers.json",
    logoPath: "/league-logos/la-liga.png",
    accent: "amber",
    surface: "from-amber-500/24 via-amber-400/8 to-slate-950",
    copy: "La Liga penalty boards often have a clear first choice but a less obvious backup. The second and third names are kept visible for lineup-driven goalscorer and fantasy decisions.",
  },
  {
    key: "bundesliga",
    label: "Bundesliga",
    short: "BL",
    file: "data/goalscorer/bundesliga-penalty-takers.json",
    logoPath: "/league-logos/bundesliga.png",
    accent: "rose",
    surface: "from-rose-500/24 via-rose-400/8 to-slate-950",
    copy: "Bundesliga hierarchies can look stable until one missed penalty, injury or substitution reshuffles the live order. We track the full ladder rather than a single stale name.",
  },
  {
    key: "ligue-1",
    label: "Ligue 1",
    short: "L1",
    file: "data/goalscorer/ligue-1-penalty-takers.json",
    logoPath: "/league-logos/ligue-1.png",
    accent: "cyan",
    surface: "from-cyan-500/24 via-cyan-400/8 to-slate-950",
    copy: "Ligue 1 needs freshness more than reputation. This page is built to show the current order quickly, including the backup name that matters when the expected starter is missing.",
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

export function normalizeClubPenaltyKey(value: string): string {
  return cleanClubPenaltyText(value)
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

export function clubPenaltyTeamRelativeUrl(leagueKey: string, teamSlug: string): string {
  return `${CLUB_PENALTY_BASE_PATH}/${leagueKey}/${teamSlug}`;
}

export function clubPenaltyTeamUrl(leagueKey: string, teamSlug: string): string {
  return `${BASE_URL}${clubPenaltyTeamRelativeUrl(leagueKey, teamSlug)}`;
}

function buildInitials(team: string): string {
  const parts = cleanClubPenaltyText(team)
    .replace(/[.'-]/g, " ")
    .split(/\s+/)
    .filter(Boolean);

  if (!parts.length) return "FC";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

function parseDateOnly(value?: string): number {
  if (!value) return Number.NaN;
  return Date.parse(`${value}T12:00:00Z`);
}

export function formatClubPenaltyDate(value?: string): string {
  const stamp = parseDateOnly(value);
  if (!Number.isFinite(stamp)) return value ?? "";

  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(stamp));
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

export async function readClubPenaltyData(): Promise<ClubPenaltyLeague[]> {
  const logoManifest = await readLogoManifest();

  return Promise.all(
    CLUB_LEAGUES.map(async (league) => {
      const penaltyFile = await readJson<PenaltyFile>(league.file);
      const teams = Object.entries(penaltyFile)
        .map(([teamName, entry]) => {
          const team = cleanClubPenaltyText(teamName);
          const slug = clubPenaltySlug(team);
          const relativeUrl = clubPenaltyTeamRelativeUrl(league.key, slug);

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
            primary: cleanClubPenaltyText(entry.primary) || "TBC",
            secondary: cleanClubPenaltyText(entry.secondary) || "TBC",
            tertiary: cleanClubPenaltyText(entry.tertiary),
            lastUpdated: cleanClubPenaltyText(entry.last_updated),
            lastUpdatedLabel: formatClubPenaltyDate(cleanClubPenaltyText(entry.last_updated)),
            source: cleanClubPenaltyText(entry.source),
            crossCheck: cleanClubPenaltyText(entry.cross_check),
            logoPath: findLogoPath(league.key, teamName, logoManifest),
            initials: buildInitials(team),
            relativeUrl,
            absoluteUrl: `${BASE_URL}${relativeUrl}`,
          } satisfies ClubPenaltyTeam;
        })
        .sort((left, right) => left.team.localeCompare(right.team, "en"));

      return { ...league, teams };
    }),
  );
}

export async function readAllClubPenaltyTeams(): Promise<ClubPenaltyTeam[]> {
  const leagues = await readClubPenaltyData();
  return leagues.flatMap((league) => league.teams);
}

export async function getClubPenaltyTeam(leagueSlug: string, teamSlug: string): Promise<ClubPenaltyTeam | undefined> {
  const leagues = await readClubPenaltyData();
  const league = leagues.find((candidate) => candidate.key === leagueSlug);
  return league?.teams.find((team) => team.slug === teamSlug);
}

export function buildClubPenaltyTitle(team: ClubPenaltyTeam): string {
  return `${team.team} Penalty Taker ${CLUB_PENALTY_SEASON}`;
}

export function buildClubPenaltyDescription(team: ClubPenaltyTeam): string {
  const primary = team.primary && team.primary !== "TBC" ? team.primary : "still to be confirmed";
  const secondary = team.secondary && team.secondary !== "TBC" ? team.secondary : "the backup order still being monitored";
  return `Who is ${team.team}'s penalty taker? ${primary} is listed as current first choice for ${team.leagueLabel}, with ${secondary} next in line. Updated ${team.lastUpdatedLabel || CLUB_PENALTY_SEASON}.`;
}

export function buildClubPenaltyLead(team: ClubPenaltyTeam): string {
  if (!team.primary || team.primary === "TBC") {
    return `We are still building the ${team.team} penalty order and need another clean signal before naming a firm first-choice taker.`;
  }

  if (team.secondary && team.secondary !== "TBC") {
    return `${team.primary} is our current ${team.team} penalty taker call, with ${team.secondary} next in line if the order changes or the first choice is not on the pitch.`;
  }

  return `${team.primary} is our current ${team.team} penalty taker call. We do not name a firm backup yet because the second-choice trail is still thin.`;
}

export function buildSourceLabel(team: ClubPenaltyTeam): string {
  if (team.source && team.crossCheck) return `${team.source}; ${team.crossCheck}`;
  return team.source || team.crossCheck || "Manual hierarchy file";
}
