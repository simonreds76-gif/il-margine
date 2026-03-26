import { promises as fs } from "fs";
import path from "path";
import { BASE_URL } from "@/lib/config";

export type ResearchStatus = "reviewed" | "researching";
export type Confidence = "high" | "medium" | "researching";

export type TeamRow = {
  team: string;
  confederation: string;
  group?: string;
  status: "qualified" | "playoff";
  research_status: ResearchStatus;
  confidence: Confidence;
  likely_primary?: string;
  likely_secondary?: string;
  last_evidence?: string;
  evidence_log?: string[];
  note?: string;
  source_urls?: string[];
};

export type WorldCupPenaltyData = {
  tournament: string;
  season: string;
  last_verified: string;
  qualified_count: number;
  playoff_count: number;
  teams: TeamRow[];
  playoff_teams: Array<{
    team: string;
    confederation: string;
    status: "playoff";
    slot?: string;
    group?: string;
  }>;
};

export const WORLD_CUP_PENALTIES_URL = `${BASE_URL}/penalty-takers/world-cup-2026`;

export const CONFEDERATION_ORDER = ["UEFA", "CONMEBOL", "Concacaf", "AFC", "CAF", "OFC"];
export const WORLD_CUP_GROUP_ORDER = ["A", "B", "C", "D", "E", "F", "G", "H", "I", "J", "K", "L"];

export const UEFA_PLAYOFF_PATHS = [
  {
    path: "Path A",
    destinationGroup: "B",
    fixtures: ["Italy vs Northern Ireland", "Wales vs Bosnia and Herzegovina"],
  },
  {
    path: "Path B",
    destinationGroup: "F",
    fixtures: ["Ukraine vs Sweden", "Poland vs Albania"],
  },
  {
    path: "Path C",
    destinationGroup: "D",
    fixtures: ["Turkey vs Romania", "Slovakia vs Kosovo"],
  },
  {
    path: "Path D",
    destinationGroup: "A",
    fixtures: ["Denmark vs North Macedonia", "Czechia vs Republic of Ireland"],
  },
] as const;

export const INTERCONTINENTAL_PLAYOFF_SLOTS = [
  {
    slot: "Intercontinental Play-Off 1",
    label: "Intercontinental Play-Off 1 winner",
    destinationGroup: "K",
    teams: ["Bolivia", "Iraq", "Suriname"],
  },
  {
    slot: "Intercontinental Play-Off 2",
    label: "Intercontinental Play-Off 2 winner",
    destinationGroup: "I",
    teams: ["Congo DR", "Jamaica", "New Caledonia"],
  },
] as const;

export const WORLD_CUP_GROUPS: Record<string, string[]> = {
  A: ["Mexico", "Korea Republic", "South Africa", "UEFA Path D winner"],
  B: ["Canada", "Qatar", "Switzerland", "UEFA Path A winner"],
  C: ["Brazil", "Morocco", "Scotland", "Haiti"],
  D: ["USA", "Paraguay", "Australia", "UEFA Path C winner"],
  E: ["Germany", "Cote d'Ivoire", "Ecuador", "Curacao"],
  F: ["Netherlands", "Japan", "Tunisia", "UEFA Path B winner"],
  G: ["Belgium", "Egypt", "IR Iran", "New Zealand"],
  H: ["Spain", "Saudi Arabia", "Uruguay", "Cabo Verde"],
  I: ["France", "Senegal", "Norway", "Intercontinental Play-Off 2 winner"],
  J: ["Argentina", "Algeria", "Austria", "Jordan"],
  K: ["Portugal", "Uzbekistan", "Colombia", "Intercontinental Play-Off 1 winner"],
  L: ["England", "Ghana", "Panama", "Croatia"],
};

export const TEAM_FLAG_CODES: Record<string, string> = {
  Algeria: "DZ",
  Argentina: "AR",
  Australia: "AU",
  Austria: "AT",
  Belgium: "BE",
  Bolivia: "BO",
  Brazil: "BR",
  "Cabo Verde": "CV",
  Canada: "CA",
  Chile: "CL",
  Colombia: "CO",
  "Congo DR": "CD",
  Croatia: "HR",
  Curacao: "CW",
  "Cote d'Ivoire": "CI",
  Ecuador: "EC",
  Egypt: "EG",
  England: "ENG",
  France: "FR",
  Germany: "DE",
  Ghana: "GH",
  Haiti: "HT",
  "IR Iran": "IR",
  Iraq: "IQ",
  Japan: "JP",
  Jamaica: "JM",
  Jordan: "JO",
  Mexico: "MX",
  Morocco: "MA",
  Netherlands: "NL",
  "New Caledonia": "NC",
  "New Zealand": "NZ",
  Norway: "NO",
  Panama: "PA",
  Paraguay: "PY",
  Portugal: "PT",
  Qatar: "QA",
  "Korea Republic": "KR",
  "Saudi Arabia": "SA",
  Scotland: "SCO",
  Senegal: "SN",
  "South Africa": "ZA",
  Spain: "ES",
  Suriname: "SR",
  Switzerland: "CH",
  Tunisia: "TN",
  Uruguay: "UY",
  USA: "US",
  Uzbekistan: "UZ",
};

export function normalizeKey(value: string): string {
  return value
    .normalize("NFKD")
    .replace(/[\u0300-\u036f]/g, "")
    .replace(/[^a-zA-Z0-9]+/g, " ")
    .trim()
    .toLowerCase()
    .replace(/\s+/g, "-");
}

export function flagImageUrl(team: string): string {
  const code = TEAM_FLAG_CODES[team];
  if (!code) return "";
  if (code === "ENG") return "https://upload.wikimedia.org/wikipedia/en/b/be/Flag_of_England.svg";
  if (code === "SCO") return "https://upload.wikimedia.org/wikipedia/commons/1/10/Flag_of_Scotland.svg";
  return `https://flagcdn.com/w80/${code.toLowerCase()}.png`;
}

export function initials(team: string): string {
  const parts = team
    .replace(/[.'-]/g, " ")
    .split(/\s+/)
    .filter(Boolean);
  if (parts.length === 0) return "WC";
  if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
  return parts
    .slice(0, 2)
    .map((part) => part[0]?.toUpperCase() ?? "")
    .join("");
}

export function worldCupTeamSlug(team: string): string {
  return normalizeKey(team);
}

export function worldCupTeamUrl(team: string): string {
  return `${WORLD_CUP_PENALTIES_URL}/${worldCupTeamSlug(team)}`;
}

export function getGroupForTeam(team: string): string | undefined {
  return WORLD_CUP_GROUP_ORDER.find((group) => WORLD_CUP_GROUPS[group]?.includes(team));
}

export function getIntercontinentalSlotForTeam(team: string): { slot?: string; group?: string } {
  const match = INTERCONTINENTAL_PLAYOFF_SLOTS.find((slot) => (slot.teams as readonly string[]).includes(team));
  if (!match) return {};
  return { slot: match.slot, group: match.destinationGroup };
}

export async function readWorldCupData(): Promise<WorldCupPenaltyData> {
  const fullPath = path.join(process.cwd(), "data/goalscorer/world-cup-2026-penalty-takers.json");
  const raw = await fs.readFile(fullPath, "utf8");
  const parsed = JSON.parse(raw) as WorldCupPenaltyData;

  return {
    ...parsed,
    teams: parsed.teams.map((team) => ({
      ...team,
      group: team.group ?? getGroupForTeam(team.team),
    })),
    playoff_teams: parsed.playoff_teams.map((team) => ({
      ...team,
      ...getIntercontinentalSlotForTeam(team.team),
    })),
  };
}

export function getWorldCupTeamBySlug(data: WorldCupPenaltyData, slug: string): TeamRow | undefined {
  return data.teams.find((team) => worldCupTeamSlug(team.team) === slug);
}

export function buildWorldCupTeamTitle(team: TeamRow): string {
  return `${team.team} Penalty Taker | World Cup 2026`;
}

export function buildWorldCupTeamDescription(team: TeamRow): string {
  const primary = team.likely_primary?.trim() || "still being researched";
  const secondary = team.likely_secondary?.trim();
  if (secondary) {
    return `Who is ${team.team}'s penalty taker for the 2026 World Cup? ${primary} is the current first-choice call, with ${secondary} next in line if the order shifts. Read the evidence trail and backup context.`;
  }
  return `Who is ${team.team}'s penalty taker for the 2026 World Cup? ${primary} is the current first-choice call. Read the latest evidence trail and why the backup order is still thinner than the lead.`;
}

export function buildWorldCupTeamLead(team: TeamRow): string {
  const primary = team.likely_primary?.trim();
  const secondary = team.likely_secondary?.trim();

  if (!primary) {
    return `We are still building the ${team.team} penalty taker file for World Cup 2026 and need another clean senior signal before we publish a firmer first-choice call.`;
  }

  if (secondary) {
    return `${primary} is our current ${team.team} penalty taker call for World Cup 2026, with ${secondary} the closest backup if the order changes.`;
  }

  return `${primary} is our current ${team.team} penalty taker call for World Cup 2026. We do not name a backup yet because the secondary order is still too thin or too mixed.`;
}
