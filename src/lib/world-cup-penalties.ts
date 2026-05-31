import { promises as fs } from "fs";
import path from "path";
import { BASE_URL } from "@/lib/config";

export type ResearchStatus = "reviewed" | "researching";
export type Confidence = "high" | "medium" | "researching";
export type SquadStatus = "final_announced" | "preliminary_or_reduced" | "final_pending" | "listed_unclear" | "no_section_found";
export type CallupStatus =
  | "confirmed_final_squad"
  | "listed_preliminary"
  | "final_pending_unverified"
  | "not_in_final_squad"
  | "not_listed_preliminary"
  | "unknown";

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
  squad_verified_at?: string;
  squad_status?: SquadStatus;
  squad_count?: number | null;
  primary_callup_status?: CallupStatus;
  secondary_callup_status?: CallupStatus;
  squad_note?: string;
  squad_source_urls?: string[];
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

export const WORLD_CUP_GROUPS: Record<string, string[]> = {
  A: ["Mexico", "Korea Republic", "South Africa", "Czechia"],
  B: ["Canada", "Qatar", "Switzerland", "Bosnia and Herzegovina"],
  C: ["Brazil", "Morocco", "Scotland", "Haiti"],
  D: ["USA", "Paraguay", "Australia", "Turkiye"],
  E: ["Germany", "Cote d'Ivoire", "Ecuador", "Curacao"],
  F: ["Netherlands", "Japan", "Tunisia", "Sweden"],
  G: ["Belgium", "Egypt", "IR Iran", "New Zealand"],
  H: ["Spain", "Saudi Arabia", "Uruguay", "Cabo Verde"],
  I: ["France", "Senegal", "Norway", "Iraq"],
  J: ["Argentina", "Algeria", "Austria", "Jordan"],
  K: ["Portugal", "Uzbekistan", "Colombia", "Congo DR"],
  L: ["England", "Ghana", "Panama", "Croatia"],
};

export const TEAM_FLAG_CODES: Record<string, string> = {
  Algeria: "DZ",
  Argentina: "AR",
  Australia: "AU",
  Austria: "AT",
  Belgium: "BE",
  Bolivia: "BO",
  "Bosnia and Herzegovina": "BA",
  Brazil: "BR",
  "Cabo Verde": "CV",
  Canada: "CA",
  Czechia: "CZ",
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
  Sweden: "SE",
  Suriname: "SR",
  Switzerland: "CH",
  Tunisia: "TN",
  Turkiye: "TR",
  "Türkiye": "TR",
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

export function teamCrestImageUrl(team: string): string {
  return `/team-logos/world-cup/${normalizeKey(team)}.png`;
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

export function publicPenaltyEvidenceText(value: string | undefined, fallback = "Il Margine file still being built from the current cycle."): string {
  const text = (value || fallback).trim();
  if (!text) return fallback;

  return text
    .replace(/https?:\/\/\S+/gi, "")
    .replace(/\bAPF\s*\/\s*Sofascore:/gi, "Il Margine audit:")
    .replace(/\bUEFA reported\b/gi, "The match record shows")
    .replace(/\bFIFA reported\b/gi, "The match record shows")
    .replace(/\bTransfermarkt's\s+/gi, "The ")
    .replace(/\b(?:Transfermarkt|SofaScore|Sofascore|FotMob|WhoScored|FBref|Opta|LigaInsider|fantasyfootballscout|understat|goal\.com|fantacalcio\.it|sosfanta|as\.com|futbolfantasy\.com|ligue1\.com|bundesliga\.com|kicker\.de)\b/gi, "Il Margine audit")
    .replace(/\b(?:transfermarkt_penalty_log|understat_2025_26_attempts|manual_update_[\w-]+|manual_review)\b/gi, "Il Margine audit")
    .replace(/\bsource urls?\b/gi, "evidence checks")
    .replace(/\bsources?\b/gi, "checks")
    .replace(/\s+([.,;:])/g, "$1")
    .replace(/\s{2,}/g, " ")
    .trim();
}

export function publicSquadStatusText(team: TeamRow): string {
  const primary = team.likely_primary?.trim();
  const secondary = team.likely_secondary?.trim();
  const primaryStatus = team.primary_callup_status;
  const secondaryStatus = team.secondary_callup_status;
  const squadCount = team.squad_count ? `${team.squad_count}-man` : "";

  if (team.squad_status === "final_announced") {
    if (primaryStatus === "confirmed_final_squad" && (!secondary || secondaryStatus === "confirmed_final_squad")) {
      return `Squad check: ${primary}${secondary ? ` and ${secondary}` : ""} ${secondary ? "are" : "is"} named in the ${squadCount || "final"} World Cup squad.`;
    }
    if (primaryStatus === "confirmed_final_squad" && secondaryStatus === "not_in_final_squad") {
      return `Squad check: ${primary} is in the final World Cup squad, but the previous backup is not. The backup line has been reworked inside the named squad.`;
    }
    if (primaryStatus === "not_in_final_squad") {
      return "Squad check: the previous first-choice call is not in the final World Cup squad, so this team needs immediate manual review.";
    }
    return "Squad check: final squad announced; the penalty order is being checked against the named 26.";
  }

  if (team.squad_status === "preliminary_or_reduced") {
    if (primaryStatus === "listed_preliminary" && (!secondary || secondaryStatus === "listed_preliminary")) {
      return `Squad check: ${primary}${secondary ? ` and ${secondary}` : ""} ${secondary ? "are" : "is"} listed in the current preliminary/reduced squad, but FIFA-final confirmation is still pending.`;
    }
    return "Squad check: preliminary squad only, so this penalty hierarchy stays under review until the final cut is public.";
  }

  if (team.squad_status === "final_pending") {
    if (primaryStatus === "listed_preliminary" || secondaryStatus === "listed_preliminary") {
      return "Squad check: at least one named taker appears on the current wider squad list, but the final 26 is still pending.";
    }
    return "Squad check: final squad announcement is still pending, so call-up confirmation must be re-run after the federation list drops.";
  }

  return "Squad check: final squad cross-check still needs a manual source before the call-up status can be treated as clean.";
}

export function getGroupForTeam(team: string): string | undefined {
  return WORLD_CUP_GROUP_ORDER.find((group) => WORLD_CUP_GROUPS[group]?.includes(team));
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
    playoff_teams: parsed.playoff_teams,
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
