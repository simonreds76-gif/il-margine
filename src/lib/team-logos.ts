import teamLogoManifest from "../../data/goalscorer/team-logo-map.json";
import europeanLogos from "../../data/team-logos/europe.json";

type TeamEntry = {
  team_key?: string;
  fotmob_name?: string;
  fotmob_short_name?: string;
  logo_path?: string;
};

type LeagueEntry = {
  teams?: Record<string, TeamEntry>;
};

type LogoRow = {
  category: string;
  leagueKey: string;
  logoPath: string;
  aliases: string[];
};

const CATEGORY_TO_LOGO_DIR: Record<string, string> = {
  worldcup: "world-cup",
  pl: "epl",
  seriea: "serie-a",
  laliga: "la-liga",
  bundesliga: "bundesliga",
  ligue1: "ligue-1",
};

const MANIFEST_LEAGUE_TO_CATEGORY: Record<string, string> = {
  epl: "pl",
  "serie-a": "seriea",
  "la-liga": "laliga",
  bundesliga: "bundesliga",
  "ligue-1": "ligue1",
};

const CATEGORY_TO_MANIFEST_LEAGUE = Object.fromEntries(
  Object.entries(MANIFEST_LEAGUE_TO_CATEGORY).map(([league, category]) => [category, league]),
) as Record<string, string>;

const TEAM_LOGO_ALIASES: Record<string, string> = {
  "cape-verde": "cabo-verde",
  "ivory-coast": "cote-d-ivoire",
  "iran": "ir-iran",
  "south-korea": "korea-republic",
  "republic-of-korea": "korea-republic",
  "dr-congo": "congo-dr",
  "democratic-republic-of-congo": "congo-dr",
  "turkey": "turkiye",
  "united-states": "usa",
  "united-states-of-america": "usa",
  "man-city": "manchester-city",
  "man-utd": "manchester-united",
  "man-united": "manchester-united",
  "newcastle": "newcastle-united",
  "nottingham": "nottingham-forest",
  "spurs": "tottenham",
  "tottenham-hotspur": "tottenham",
  "west-ham-united": "west-ham",
  "wolves": "wolves",
  "brighton-and-hove-albion": "brighton",
  "inter-milan": "inter",
  "ac-milan": "milan",
  "psg": "paris-saint-germain",
  "rb-leipzig": "rasenballsport-leipzig",
  "borussia-monchengladbach": "borussia-m-gladbach",
};

const WORLD_CUP_TEAM_KEYS = new Set([
  "algeria",
  "argentina",
  "australia",
  "austria",
  "belgium",
  "bosnia-and-herzegovina",
  "brazil",
  "cabo-verde",
  "canada",
  "colombia",
  "congo-dr",
  "cote-d-ivoire",
  "croatia",
  "curacao",
  "czechia",
  "ecuador",
  "egypt",
  "england",
  "france",
  "germany",
  "ghana",
  "haiti",
  "ir-iran",
  "iraq",
  "japan",
  "jordan",
  "korea-republic",
  "mexico",
  "morocco",
  "netherlands",
  "new-zealand",
  "norway",
  "panama",
  "paraguay",
  "portugal",
  "qatar",
  "saudi-arabia",
  "scotland",
  "senegal",
  "south-africa",
  "spain",
  "sweden",
  "switzerland",
  "tunisia",
  "turkiye",
  "uruguay",
  "usa",
  "uzbekistan",
]);

export function normalizeText(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

function normalizeTeamKey(value: string): string {
  const key = normalizeText(value).replace(/\s+/g, "-");
  return TEAM_LOGO_ALIASES[key] ?? key;
}

const MANIFEST_LOGOS: LogoRow[] = (() => {
  const leagues = (teamLogoManifest as { leagues?: Record<string, LeagueEntry> }).leagues ?? {};
  const rows: LogoRow[] = [];

  for (const [leagueKey, league] of Object.entries(leagues)) {
    const category = MANIFEST_LEAGUE_TO_CATEGORY[leagueKey];
    if (!category) continue;

    for (const [displayName, team] of Object.entries(league.teams ?? {})) {
      if (!team.logo_path) continue;
      const aliases = [displayName, team.team_key, team.fotmob_name, team.fotmob_short_name]
        .filter(Boolean)
        .map((value) => normalizeText(value as string))
        .filter((value, index, all) => value.length >= 2 && all.indexOf(value) === index);
      rows.push({ category, leagueKey, logoPath: team.logo_path, aliases });
    }
  }

  return rows.sort((a, b) => Math.max(...b.aliases.map((alias) => alias.length)) - Math.max(...a.aliases.map((alias) => alias.length)));
})();

function teamLogoPathFromCategory(team: string, category: string): string | null {
  const folder = CATEGORY_TO_LOGO_DIR[category];
  if (!folder) return null;
  return `/team-logos/${folder}/${normalizeTeamKey(team)}.png`;
}

function worldCupTeamLogoPath(team: string): string | null {
  const key = normalizeTeamKey(team);
  return WORLD_CUP_TEAM_KEYS.has(key) ? `/team-logos/world-cup/${key}.png` : null;
}

function resolveManifestLogoPath(team: string, category: string): string | null {
  const normalized = normalizeText(team);
  if (!normalized) return null;

  const preferredLeague = CATEGORY_TO_MANIFEST_LEAGUE[category];
  const isPreferred = (row: LogoRow) => !preferredLeague || row.leagueKey === preferredLeague || row.category === category;
  const exact = MANIFEST_LOGOS.find((row) => isPreferred(row) && row.aliases.includes(normalized));
  if (exact) return exact.logoPath;

  const loose = MANIFEST_LOGOS.find(
    (row) =>
      isPreferred(row) &&
      row.aliases.some((alias) => alias.length >= 5 && (normalized.includes(alias) || alias.includes(normalized))),
  );
  if (loose) return loose.logoPath;

  const anyExact = MANIFEST_LOGOS.find((row) => row.aliases.includes(normalized));
  if (anyExact) return anyExact.logoPath;

  const anyLoose = MANIFEST_LOGOS.find((row) =>
    row.aliases.some((alias) => alias.length >= 5 && (normalized.includes(alias) || alias.includes(normalized))),
  );
  return anyLoose?.logoPath ?? null;
}

export function resolveTeamLogoPath(team: string | null, category: string): string | null {
  if (!team) return null;
  if (category === "worldcup") return worldCupTeamLogoPath(team) ?? teamLogoPathFromCategory(team, category);
  const european = europeanLogos.teams.find((club) => club.aliases.some((alias) => normalizeText(alias) === normalizeText(team)));
  if (european) return european.logo_path;
  return (
    resolveManifestLogoPath(team, category) ??
    teamLogoPathFromCategory(team, category) ??
    worldCupTeamLogoPath(team) ??
    resolveManifestLogoPath(team, "all")
  );
}
