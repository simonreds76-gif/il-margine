import { promises as fs } from "fs";
import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";
import { getKnownProjectFilePath, type KnownProjectFile } from "@/lib/project-file-paths";
import PenaltyTakersClient from "./PenaltyTakersClient";

const CURRENT_SEASON = "2025/26";
const PAGE_TITLE = `Penalty Takers ${CURRENT_SEASON}: Serie A, Premier League, La Liga, Bundesliga & Ligue 1`;
const PAGE_DESCRIPTION =
  "Penalty takers 2025/26 for every club in Serie A, the Premier League, La Liga, Bundesliga and Ligue 1. See the current first, second and third-choice penalty taker for all 96 teams in one place.";
const PAGE_URL = `${BASE_URL}/penalty-takers`;

export const revalidate = 43200;

type PenaltyTeamRow = {
  primary?: string;
  secondary?: string;
  tertiary?: string;
  last_updated?: string;
};

type PenaltyFile = Record<string, PenaltyTeamRow>;

type TeamLogoRow = {
  logo_path?: string;
};

type LogoManifest = {
  leagues?: Record<
    string,
    {
      teams?: Record<string, TeamLogoRow>;
    }
  >;
};

type TeamEntry = {
  team: string;
  slug: string;
  primary: string;
  secondary: string;
  tertiary: string;
  lastUpdated: string;
  lastUpdatedLabel: string;
  logoPath: string;
  initials: string;
};

type RecentChange = {
  team: string;
  slug: string;
  leagueKey: string;
  leagueLabel: string;
  leagueShort: string;
  leagueLogoPath: string;
  primary: string;
  secondary: string;
  lastUpdated: string;
  lastUpdatedLabel: string;
  logoPath: string;
  initials: string;
};

type LeagueEntry = {
  key: string;
  label: string;
  short: string;
  file: string;
  logoPath: string;
  tabClasses: string;
  cardGlowClasses: string;
  heading: string;
  intro: string;
  teamCount: number;
  subtitle: string;
  teams: TeamEntry[];
};

type PenaltyDataFile =
  | "data/goalscorer/team-logo-map.json"
  | "data/goalscorer/serie-a-penalty-takers.json"
  | "data/goalscorer/epl-penalty-takers.json"
  | "data/goalscorer/la-liga-penalty-takers.json"
  | "data/goalscorer/bundesliga-penalty-takers.json"
  | "data/goalscorer/ligue-1-penalty-takers.json";

type LeagueConfig = Omit<LeagueEntry, "teamCount" | "subtitle" | "teams"> & {
  file: PenaltyDataFile;
};

const EMPTY_LOGO_MANIFEST: LogoManifest = {
  leagues: {},
};

const LEAGUES: LeagueConfig[] = [
  {
    key: "serie-a",
    label: "Serie A",
    short: "SA",
    file: "data/goalscorer/serie-a-penalty-takers.json",
    logoPath: "/league-logos/serie-a.png",
    tabClasses: "border-emerald-400/80 text-slate-300 hover:border-emerald-300 hover:text-slate-100",
    cardGlowClasses: "hover:shadow-[0_24px_70px_rgba(16,185,129,0.08)]",
    heading: `Serie A penalty takers ${CURRENT_SEASON}`,
    intro:
      "Serie A changes quickly: coaching shifts, transfers and mid-season reshuffles can move a taker from first to third in a week. That makes the full order especially useful when lineups drop and the obvious name is missing.",
  },
  {
    key: "epl",
    label: "Premier League",
    short: "PL",
    file: "data/goalscorer/epl-penalty-takers.json",
    logoPath: "/league-logos/epl.png",
    tabClasses: "border-indigo-300/80 text-slate-300 hover:border-indigo-200 hover:text-slate-100",
    cardGlowClasses: "hover:shadow-[0_24px_70px_rgba(129,140,248,0.08)]",
    heading: `Premier League penalty takers ${CURRENT_SEASON}`,
    intro:
      "The Premier League market is sharp, but the backup order still matters when rotation, suspensions and substitutions bring the second name into play. This is where the full hierarchy matters more than a one-name list.",
  },
  {
    key: "la-liga",
    label: "La Liga",
    short: "LL",
    file: "data/goalscorer/la-liga-penalty-takers.json",
    logoPath: "/league-logos/la-liga.png",
    tabClasses: "border-amber-300/80 text-slate-300 hover:border-amber-200 hover:text-slate-100",
    cardGlowClasses: "hover:shadow-[0_24px_70px_rgba(245,158,11,0.08)]",
    heading: `La Liga penalty takers ${CURRENT_SEASON}`,
    intro:
      "Whether you're checking Atletico, Barcelona, Real Madrid or Villarreal, the key question is not just who takes the first penalty, but who is next if the regular taker is off the pitch. La Liga has enough movement underneath the headline names to make that worth tracking properly.",
  },
  {
    key: "bundesliga",
    label: "Bundesliga",
    short: "BL",
    file: "data/goalscorer/bundesliga-penalty-takers.json",
    logoPath: "/league-logos/bundesliga.png",
    tabClasses: "border-rose-300/80 text-slate-300 hover:border-rose-200 hover:text-slate-100",
    cardGlowClasses: "hover:shadow-[0_24px_70px_rgba(248,113,113,0.08)]",
    heading: `Bundesliga penalty takers ${CURRENT_SEASON}`,
    intro:
      "Bundesliga hierarchies are often cleaner than Serie A, but when they do change they matter immediately. A reliable second name is often the difference between being early and being late when pricing catches up.",
  },
  {
    key: "ligue-1",
    label: "Ligue 1",
    short: "L1",
    file: "data/goalscorer/ligue-1-penalty-takers.json",
    logoPath: "/league-logos/ligue-1.png",
    tabClasses: "border-cyan-300/80 text-slate-300 hover:border-cyan-200 hover:text-slate-100",
    cardGlowClasses: "hover:shadow-[0_24px_70px_rgba(96,165,250,0.08)]",
    heading: `Ligue 1 penalty takers ${CURRENT_SEASON}`,
    intro:
      "Ligue 1 needs freshness more than reputation. If you're checking PSG, Marseille, Monaco, Lyon or Lille, this section is built to give you the current order quickly, including the second name that becomes relevant the moment the headline taker is missing.",
  },
];

export const metadata: Metadata = {
  title: PAGE_TITLE,
  description: PAGE_DESCRIPTION,
  alternates: {
    canonical: PAGE_URL,
  },
  keywords: [
    "penalty takers 2025/26",
    "serie a penalty takers",
    "premier league penalty takers",
    "la liga penalty takers",
    "bundesliga penalty takers",
    "ligue 1 penalty takers",
    "who takes penalties",
    "first second third penalty taker",
  ],
  openGraph: {
    type: "website",
    url: PAGE_URL,
    title: `${PAGE_TITLE} | Il Margine`,
    description: PAGE_DESCRIPTION,
    siteName: "Il Margine",
    images: [
      {
        url: `${BASE_URL}/penalty-takers/opengraph-image`,
        width: 1200,
        height: 630,
        alt: "Penalty Takers 2025/26 | Il Margine",
      },
    ],
  },
  twitter: {
    card: "summary_large_image",
    title: `${PAGE_TITLE} | Il Margine`,
    description: PAGE_DESCRIPTION,
    images: [`${BASE_URL}/penalty-takers/opengraph-image`],
  },
  robots: {
    index: true,
    follow: true,
  },
};

async function readJson<T>(relativePath: PenaltyDataFile | KnownProjectFile): Promise<T> {
  const fullPath = getKnownProjectFilePath(relativePath);
  const raw = await fs.readFile(fullPath, "utf8");
  return JSON.parse(raw) as T;
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

function cleanText(value?: string): string {
  return repairMojibake(
    (value ?? "")
      .trim()
      .replace(/&#0*39;|&#x27;|&apos;/gi, "'")
      .replace(/&amp;/gi, "&")
      .replace(/&quot;/gi, '"')
      .replace(/&nbsp;/gi, " "),
  ).replace(/\s+/g, " ");
}

function normalizeKey(value: string): string {
  return cleanText(value)
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .toLowerCase();
}

function slugify(value: string): string {
  return normalizeKey(value).replace(/\s+/g, "-");
}

function buildInitials(team: string): string {
  const parts = cleanText(team)
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

function formatDateLabel(value?: string): string {
  const stamp = parseDateOnly(value);
  if (!Number.isFinite(stamp)) return value ?? "";

  return new Intl.DateTimeFormat("en-GB", {
    timeZone: "Europe/London",
    day: "numeric",
    month: "short",
    year: "numeric",
  }).format(new Date(stamp));
}

function findLogoPath(
  leagueKey: string,
  team: string,
  manifest: LogoManifest,
): string {
  const teams = manifest.leagues?.[leagueKey]?.teams ?? {};
  if (teams[team]?.logo_path) return cleanText(teams[team].logo_path);

  const normalizedTeam = normalizeKey(team);
  const matched = Object.entries(teams).find(([name]) => normalizeKey(name) === normalizedTeam);
  return matched?.[1]?.logo_path ? cleanText(matched[1].logo_path) : "";
}

export default async function PenaltyTakersPage() {
  const logoManifest = await readJson<LogoManifest>("data/goalscorer/team-logo-map.json").catch(
    () => EMPTY_LOGO_MANIFEST,
  );

  const leagues: LeagueEntry[] = await Promise.all(
    LEAGUES.map(async (league) => {
      const penaltyFile = await readJson<PenaltyFile>(league.file);
      const teams = Object.entries(penaltyFile)
        .map(([teamName, entry]) => {
          const team = cleanText(teamName);

          return {
            team,
            slug: slugify(team),
            primary: cleanText(entry.primary) || "TBC",
            secondary: cleanText(entry.secondary) || "TBC",
            tertiary: cleanText(entry.tertiary),
            lastUpdated: cleanText(entry.last_updated),
            lastUpdatedLabel: formatDateLabel(cleanText(entry.last_updated)),
            logoPath: findLogoPath(league.key, teamName, logoManifest),
            initials: buildInitials(team),
          };
        })
        .sort((left, right) => left.team.localeCompare(right.team, "en"));

      return {
        ...league,
        teamCount: teams.length,
        subtitle: `${teams.length} teams | current hierarchy`,
        teams,
      };
    }),
  );

  const totalTeams = leagues.reduce((sum, league) => sum + league.teamCount, 0);
  const flattenedTeams = leagues.flatMap((league) =>
    league.teams.map((team) => ({
      ...team,
      leagueKey: league.key,
      leagueLabel: league.label,
      leagueShort: league.short,
      leagueLogoPath: league.logoPath,
    })),
  );
  const sortedByUpdate = [...flattenedTeams]
    .filter((team) => team.lastUpdated)
    .sort((left, right) => {
      const rightStamp = parseDateOnly(right.lastUpdated);
      const leftStamp = parseDateOnly(left.lastUpdated);
      if (Number.isFinite(rightStamp) && Number.isFinite(leftStamp) && rightStamp !== leftStamp) {
        return rightStamp - leftStamp;
      }

      if (left.leagueLabel !== right.leagueLabel) {
        return left.leagueLabel.localeCompare(right.leagueLabel, "en");
      }

      return left.team.localeCompare(right.team, "en");
    });
  const latestUpdate = sortedByUpdate[0]?.lastUpdated ?? "";
  const lastUpdatedLabel = formatDateLabel(latestUpdate);
  const recentChanges: RecentChange[] = sortedByUpdate.slice(0, 5).map((team) => ({
    team: team.team,
    slug: team.slug,
    leagueKey: team.leagueKey,
    leagueLabel: team.leagueLabel,
    leagueShort: team.leagueShort,
    leagueLogoPath: team.leagueLogoPath,
    primary: team.primary,
    secondary: team.secondary,
    lastUpdated: team.lastUpdated,
    lastUpdatedLabel: formatDateLabel(team.lastUpdated),
    logoPath: team.logoPath,
    initials: team.initials,
  }));
  const breadcrumbData = {
    "@context": "https://schema.org",
    "@type": "BreadcrumbList",
    itemListElement: [
      {
        "@type": "ListItem",
        position: 1,
        name: "Home",
        item: BASE_URL,
      },
      {
        "@type": "ListItem",
        position: 2,
        name: `Penalty Takers ${CURRENT_SEASON}`,
        item: PAGE_URL,
      },
    ],
  };

  const webPageData = {
    "@context": "https://schema.org",
    "@type": "WebPage",
    name: PAGE_TITLE,
    description: PAGE_DESCRIPTION,
    url: PAGE_URL,
    inLanguage: "en-GB",
    dateModified: latestUpdate || undefined,
    isPartOf: {
      "@type": "WebSite",
      name: "Il Margine",
      url: BASE_URL,
    },
    hasPart: leagues.map((league) => ({
      "@type": "WebPageElement",
      name: league.heading,
      url: `${PAGE_URL}#${league.key}`,
    })),
  };

  const itemListData = {
    "@context": "https://schema.org",
    "@type": "ItemList",
    name: `${CURRENT_SEASON} penalty takers by league`,
    numberOfItems: leagues.length,
    itemListElement: leagues.map((league, leagueIndex) => ({
        "@type": "ListItem",
        position: leagueIndex + 1,
        url: `${PAGE_URL}#${league.key}`,
        name: league.heading,
        description: `${league.teamCount} teams tracked in ${league.label}.`,
      })),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbData) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(webPageData) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListData) }}
      />
      <PenaltyTakersClient
        leagues={leagues}
        totalTeams={totalTeams}
        currentSeason={CURRENT_SEASON}
        lastUpdatedLabel={lastUpdatedLabel}
        lastUpdatedIso={latestUpdate}
        recentChanges={recentChanges}
      />
    </>
  );
}
