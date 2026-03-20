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
  }>;
};

export const WORLD_CUP_PENALTIES_URL = `${BASE_URL}/penalty-takers/world-cup-2026`;

export const CONFEDERATION_ORDER = ["UEFA", "CONMEBOL", "Concacaf", "AFC", "CAF", "OFC"];

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

export async function readWorldCupData(): Promise<WorldCupPenaltyData> {
  const fullPath = path.join(process.cwd(), "data/goalscorer/world-cup-2026-penalty-takers.json");
  const raw = await fs.readFile(fullPath, "utf8");
  return JSON.parse(raw) as WorldCupPenaltyData;
}

export function getWorldCupTeamBySlug(data: WorldCupPenaltyData, slug: string): TeamRow | undefined {
  return data.teams.find((team) => worldCupTeamSlug(team.team) === slug);
}

export function buildWorldCupTeamTitle(team: TeamRow): string {
  return `${team.team} Penalty Taker for FIFA World Cup 2026`;
}

export function buildWorldCupTeamDescription(team: TeamRow): string {
  const primary = team.likely_primary?.trim() || "still being researched";
  const secondary = team.likely_secondary?.trim();
  if (secondary) {
    return `${team.team}'s current World Cup 2026 penalty call: ${primary} leads the order, with ${secondary} the closest challenger. Read the evidence trail and current backup context.`;
  }
  return `${team.team}'s current World Cup 2026 penalty call: ${primary}. Read the latest evidence trail and why the backup order is still thinner than the lead.`;
}

export function buildWorldCupTeamLead(team: TeamRow): string {
  const primary = team.likely_primary?.trim();
  const secondary = team.likely_secondary?.trim();

  if (!primary) {
    return `${team.team}'s board still needs another clean senior penalty signal before we publish a firmer World Cup call.`;
  }

  if (secondary) {
    return `${primary} is the current World Cup penalty lead for ${team.team}, with ${secondary} the closest challenger if the order changes.`;
  }

  return `${primary} is the current World Cup penalty lead for ${team.team}. The board does not name a challenger yet because the backup order is still too thin or too mixed.`;
}
