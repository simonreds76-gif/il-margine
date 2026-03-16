import { promises as fs } from "fs";
import path from "path";
import type { Metadata } from "next";
import { BASE_URL } from "@/lib/config";
import PenaltyTakersClient from "./PenaltyTakersClient";

const CURRENT_SEASON = "2025/26";
const PAGE_TITLE = `Penalty Takers ${CURRENT_SEASON}: Serie A, Premier League, La Liga, Bundesliga & Ligue 1`;
const PAGE_DESCRIPTION =
  "Penalty takers 2025/26 for every club in Serie A, the Premier League, La Liga, Bundesliga and Ligue 1. See the current first, second and third-choice penalty taker for all 96 teams in one place.";
const PAGE_URL = `${BASE_URL}/penalty-takers`;

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
  lastUpdatedIso: string;
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
  summary: string;
  paragraphs: string[];
  teamCount: number;
  updatedLabel: string;
  updatedIso: string;
  teams: TeamEntry[];
};

type LeagueConfig = Omit<LeagueEntry, "teamCount" | "updatedLabel" | "updatedIso" | "teams">;

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
    tabClasses: "border-emerald-400/80 text-stone-300 hover:border-emerald-300 hover:text-stone-100",
    cardGlowClasses: "hover:shadow-[0_24px_70px_rgba(16,185,129,0.08)]",
    heading: `Serie A penalty takers ${CURRENT_SEASON}`,
    summary:
      "Serie A is the most volatile hierarchy on the page: coaching changes, veteran transfers and mid-season reshuffles can move a taker from first to third in a week.",
    paragraphs: [
      "Serie A is usually the best place to track a full three-man hierarchy rather than just a single name. Clubs such as Juventus, Fiorentina, Genoa and Pisa have already needed adjustments because the first answer in August was no longer the right answer by spring.",
      "That matters for fantasy, but it matters even more for live goalscorer markets. If the first-choice taker is missing from the confirmed XI, you want to know immediately who moves up and who sits behind him. This section is built around that exact use case.",
    ],
  },
  {
    key: "epl",
    label: "Premier League",
    short: "PL",
    file: "data/goalscorer/epl-penalty-takers.json",
    logoPath: "/league-logos/epl.png",
    tabClasses: "border-indigo-300/80 text-stone-300 hover:border-indigo-200 hover:text-stone-100",
    cardGlowClasses: "hover:shadow-[0_24px_70px_rgba(129,140,248,0.08)]",
    heading: `Premier League penalty takers ${CURRENT_SEASON}`,
    summary:
      "The Premier League is the sharpest market here, but it is still worth tracking the full order because backup takers become relevant the moment a star attacker is rested or taken off the pitch.",
    paragraphs: [
      "Most public penalty-taker pages stop at one name. That is rarely enough in the Premier League, where substitutions come early, rotations are heavier in busy weeks and multiple clubs have a clear first and second option rather than one untouchable taker.",
      "The point of this section is not just to tell you who takes the next penalty in a vacuum. It is to tell you who the hierarchy becomes when the regular taker is benched, suspended or simply no longer on the field.",
    ],
  },
  {
    key: "la-liga",
    label: "La Liga",
    short: "LL",
    file: "data/goalscorer/la-liga-penalty-takers.json",
    logoPath: "/league-logos/la-liga.png",
    tabClasses: "border-amber-300/80 text-stone-300 hover:border-amber-200 hover:text-stone-100",
    cardGlowClasses: "hover:shadow-[0_24px_70px_rgba(245,158,11,0.08)]",
    heading: `La Liga penalty takers ${CURRENT_SEASON}`,
    summary:
      "La Liga gives you both obvious elite names and a long tail of clubs where the backup order matters because the designated taker is less stable than the market assumes.",
    paragraphs: [
      "At the top end the hierarchy is straightforward, but the league gets more interesting lower down. Several teams have already shown that the second and third line matter when injuries, missed penalties or coach preference changes the order.",
      "For searchers looking for who takes penalties for Atletico Madrid, Barcelona, Real Madrid or Villarreal, this section is meant to answer the question in one visit without sending you through multiple thin pages.",
    ],
  },
  {
    key: "bundesliga",
    label: "Bundesliga",
    short: "BL",
    file: "data/goalscorer/bundesliga-penalty-takers.json",
    logoPath: "/league-logos/bundesliga.png",
    tabClasses: "border-rose-300/80 text-stone-300 hover:border-rose-200 hover:text-stone-100",
    cardGlowClasses: "hover:shadow-[0_24px_70px_rgba(248,113,113,0.08)]",
    heading: `Bundesliga penalty takers ${CURRENT_SEASON}`,
    summary:
      "Bundesliga penalty hierarchies are often cleaner than Serie A, but when they do change they tend to change quickly and matter immediately in pricing.",
    paragraphs: [
      "Bundesliga teams often have clearer first-choice takers, yet the second and third slots still matter because injuries and tactical rotations can create short windows where a backup becomes relevant before the broader market catches up.",
      "This section keeps the hierarchy compact and readable: first, second and third-choice penalty takers for every club, with no need to bounce between separate club articles.",
    ],
  },
  {
    key: "ligue-1",
    label: "Ligue 1",
    short: "L1",
    file: "data/goalscorer/ligue-1-penalty-takers.json",
    logoPath: "/league-logos/ligue-1.png",
    tabClasses: "border-cyan-300/80 text-stone-300 hover:border-cyan-200 hover:text-stone-100",
    cardGlowClasses: "hover:shadow-[0_24px_70px_rgba(96,165,250,0.08)]",
    heading: `Ligue 1 penalty takers ${CURRENT_SEASON}`,
    summary:
      "Ligue 1 is useful because the public penalty-taker coverage is thinner, which makes a clear, updated hierarchy more valuable for both research and market prep.",
    paragraphs: [
      "Ligue 1 is less saturated with good reference pages than the Premier League or Serie A, which makes freshness more important. If you are checking who takes penalties for PSG, Marseille, Monaco, Lyon or Lille, you should be able to land here and get the answer immediately.",
      "The goal is simple: keep the page strong enough to work as a top-level reference, while still staying practical for people who need the second and third names as much as the headline taker.",
    ],
  },
];

export const metadata: Metadata = {
  title: `${PAGE_TITLE} | Il Margine`,
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
  },
  twitter: {
    card: "summary_large_image",
    title: `${PAGE_TITLE} | Il Margine`,
    description: PAGE_DESCRIPTION,
  },
  robots: {
    index: true,
    follow: true,
  },
};

async function readJson<T>(relativePath: string): Promise<T> {
  const fullPath = path.join(process.cwd(), relativePath);
  const raw = await fs.readFile(fullPath, "utf8");
  return JSON.parse(raw) as T;
}

function repairMojibake(value: string): string {
  if (!value) return value;
  const normalized = value.normalize("NFC");
  if (!/[ÃÂâ]/.test(normalized)) return normalized;

  try {
    const repaired = Buffer.from(normalized, "latin1").toString("utf8").normalize("NFC");
    const penaltyScore = (text: string) => (text.match(/[ÃÂâ�]/g) ?? []).length;
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

function formatDate(value?: string): string {
  if (!value) return "Unknown";
  const stamp = Date.parse(value);
  if (!Number.isFinite(stamp)) return cleanText(value);
  return new Intl.DateTimeFormat("en-GB", {
    month: "short",
    day: "numeric",
  }).format(new Date(stamp));
}

function formatDateLong(value?: string): string {
  if (!value) return "";
  const stamp = Date.parse(value);
  if (!Number.isFinite(stamp)) return cleanText(value);
  return new Intl.DateTimeFormat("en-GB", {
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
      const latestStamp = Object.values(penaltyFile)
        .map((entry) => Date.parse(entry.last_updated || ""))
        .filter((value) => Number.isFinite(value))
        .sort((left, right) => right - left)[0];

      const teams = Object.entries(penaltyFile)
        .map(([teamName, entry]) => {
          const team = cleanText(teamName);
          const lastUpdatedIso = entry.last_updated || "";

          return {
            team,
            slug: slugify(team),
            primary: cleanText(entry.primary) || "TBC",
            secondary: cleanText(entry.secondary) || "TBC",
            tertiary: cleanText(entry.tertiary),
            lastUpdated: formatDate(lastUpdatedIso),
            lastUpdatedIso,
            logoPath: findLogoPath(league.key, teamName, logoManifest),
            initials: buildInitials(team),
          };
        })
        .sort((left, right) => left.team.localeCompare(right.team, "en"));

      const updatedIso = Number.isFinite(latestStamp) ? new Date(latestStamp).toISOString() : "";

      return {
        ...league,
        teamCount: teams.length,
        updatedLabel: updatedIso ? formatDateLong(updatedIso) : "Updated weekly",
        updatedIso,
        teams,
      };
    }),
  );

  const totalTeams = leagues.reduce((sum, league) => sum + league.teamCount, 0);
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

  const collectionData = {
    "@context": "https://schema.org",
    "@type": "CollectionPage",
    name: PAGE_TITLE,
    description: PAGE_DESCRIPTION,
    url: PAGE_URL,
    inLanguage: "en-GB",
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
    name: `${CURRENT_SEASON} penalty takers by team`,
    numberOfItems: totalTeams,
    itemListElement: leagues.flatMap((league, leagueIndex) =>
      league.teams.map((team, teamIndex) => ({
        "@type": "ListItem",
        position: leagueIndex * 100 + teamIndex + 1,
        url: `${PAGE_URL}#${league.key}-${team.slug}`,
        name: `${team.team} penalty takers`,
        description: [team.primary, team.secondary, team.tertiary].filter(Boolean).join(", "),
      })),
    ),
  };

  return (
    <>
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(breadcrumbData) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(collectionData) }}
      />
      <script
        type="application/ld+json"
        dangerouslySetInnerHTML={{ __html: JSON.stringify(itemListData) }}
      />
      <PenaltyTakersClient leagues={leagues} totalTeams={totalTeams} currentSeason={CURRENT_SEASON} />
    </>
  );
}
