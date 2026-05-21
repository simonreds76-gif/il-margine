import teamLogoManifest from "../../data/goalscorer/team-logo-map.json";

type BetCategoryInput = {
  market?: string | null;
  category?: string | null;
  event?: string | null;
};

type TeamEntry = {
  team_key?: string;
  fotmob_name?: string;
  fotmob_short_name?: string;
};

type LeagueEntry = {
  teams?: Record<string, TeamEntry>;
};

const FOOTBALL_MARKETS = new Set(["props", "betbuilders", "atg"]);

const MANIFEST_LEAGUE_TO_CATEGORY: Record<string, string> = {
  epl: "pl",
  "serie-a": "seriea",
  "la-liga": "laliga",
  bundesliga: "bundesliga",
  "ligue-1": "ligue1",
};

const LEAGUE_LABELS: Record<string, string> = {
  pl: "Premier League",
  seriea: "Serie A",
  laliga: "La Liga",
  bundesliga: "Bundesliga",
  ligue1: "Ligue 1",
  ucl: "Champions League",
  worldcup: "World Cup",
  other: "Other football",
};

function normalizeText(value: string) {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/&/g, " and ")
    .replace(/[^a-z0-9]+/gi, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, " ");
}

export function normalizeBetCategory(value?: string | null): string {
  const raw = normalizeText(value ?? "");
  if (!raw) return "other";
  const compact = raw.replace(/\s+/g, "");

  if (["pl", "epl", "premierleague", "englishpremierleague"].includes(compact)) return "pl";
  if (["seriea", "italianseriea", "seriaa"].includes(compact)) return "seriea";
  if (["laliga", "spanishlaliga", "primeradivision"].includes(compact)) return "laliga";
  if (["bundesliga", "germanbundesliga"].includes(compact)) return "bundesliga";
  if (["ligue1", "ligueone", "frenchligue1"].includes(compact)) return "ligue1";
  if (["ucl", "championsleague", "uefachampionsleague"].includes(compact)) return "ucl";
  if (["worldcup", "worldcup2026", "fifaworldcup", "fifaworldcup2026", "wc", "wc2026"].includes(compact)) return "worldcup";
  if (["uel", "europaleague", "uefaeuropaleague", "uecl", "conferenceleague", "uefaconferenceleague"].includes(compact)) {
    return "other";
  }
  if (["ausopen", "australianopen"].includes(compact)) return "ausopen";
  if (["rolandgarros", "frenchopen"].includes(compact)) return "rolandgarros";
  if (["atp", "challenger", "wimbledon", "usopen"].includes(compact)) return compact;

  return compact;
}

const TEAM_ALIASES = (() => {
  const leagues = (teamLogoManifest as { leagues?: Record<string, LeagueEntry> }).leagues ?? {};
  const rows: Array<{ alias: string; category: string }> = [];

  for (const [leagueKey, league] of Object.entries(leagues)) {
    const category = MANIFEST_LEAGUE_TO_CATEGORY[leagueKey];
    if (!category) continue;

    for (const [displayName, team] of Object.entries(league.teams ?? {})) {
      const candidates = [displayName, team.team_key, team.fotmob_name, team.fotmob_short_name].filter(Boolean) as string[];
      for (const candidate of candidates) {
        const alias = normalizeText(candidate);
        if (alias.length >= 3) rows.push({ alias, category });
      }
    }
  }

  return rows
    .filter((row, index, all) => all.findIndex((candidate) => candidate.alias === row.alias && candidate.category === row.category) === index)
    .sort((a, b) => b.alias.length - a.alias.length);
})();

function splitMatchEvent(event?: string | null): [string, string] | null {
  const normalized = (event ?? "").replace(/\s+/g, " ").trim();
  if (!normalized) return null;

  const parts = normalized.split(/\s+(?:vs|v|at)\s+/i);
  if (parts.length < 2) return null;
  return [parts[0], parts.slice(1).join(" ")];
}

function resolveTeamCategory(teamName: string): string | null {
  const normalized = normalizeText(teamName);
  if (!normalized) return null;

  for (const row of TEAM_ALIASES) {
    if (normalized === row.alias) return row.category;
    if (row.alias.length >= 5 && (normalized.includes(row.alias) || row.alias.includes(normalized))) {
      return row.category;
    }
  }

  return null;
}

function inferDomesticCategoryFromEvent(event?: string | null): string | null {
  const teams = splitMatchEvent(event);
  if (!teams) return null;

  const homeCategory = resolveTeamCategory(teams[0]);
  const awayCategory = resolveTeamCategory(teams[1]);

  // Only auto-upgrade "Other" when both sides point to the same domestic league.
  // Cross-league matches stay Other because they are usually Europe/friendlies.
  if (homeCategory && homeCategory === awayCategory) return homeCategory;
  return null;
}

export function getDisplayBetCategory({ market, category, event }: BetCategoryInput): string {
  const marketKey = normalizeText(market ?? "");
  const normalizedCategory = normalizeBetCategory(category);
  const eventText = normalizeText(event ?? "");

  if (marketKey === "tennis") return normalizedCategory;
  if (!FOOTBALL_MARKETS.has(marketKey)) return normalizedCategory;
  if (normalizedCategory !== "other") return normalizedCategory;
  if (/\b(world cup|fifa world cup|wc 2026)\b/i.test(event ?? "") || eventText.includes("world cup")) return "worldcup";

  return inferDomesticCategoryFromEvent(event) ?? normalizedCategory;
}

export function getDisplayBetCategoryLabel(input: BetCategoryInput): string {
  const category = getDisplayBetCategory(input);
  return LEAGUE_LABELS[category] ?? category;
}
