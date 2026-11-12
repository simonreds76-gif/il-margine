import "server-only";
import { unstable_cache } from "next/cache";
import manifest from "../../data/goalscorer/team-logo-map.json";
import europe from "../../data/team-logos/europe.json";
import national from "../../data/team-logos/national-identities.json";
import { foldNameText } from "./player-name-matching";
import { resolveTeamLogoPath } from "./team-logos";

type Club = { id: number; names: string[]; logo: string };
const nationalTeamIds = new Set(national.teams.map((team) => team.id));
export type SquadPlayer = { id: number; name: string; clubId: number; evidence?: "recent-lineup" };
type Pick = { market: string; category: string; event: string; player: string | null };
const normal = (s: string) => foldNameText(s).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const clubs: Club[] = [
  ...Object.values(manifest.leagues).flatMap((league) => Object.entries(league.teams).map(([name, team]) => ({
    id: team.fotmob_team_id, names: [name, team.fotmob_name, team.fotmob_short_name], logo: team.logo_path,
  }))),
  ...europe.teams.map((team) => ({ id: team.fotmob_team_id, names: [team.name, ...team.aliases], logo: team.logo_path })),
  ...national.teams.map((team) => ({ id: team.id, names: [team.name, ...team.aliases], logo: "" })),
];

export function clubsForPick(pick: Pick): Club[] {
  if (pick.market !== "props" || !pick.player?.trim()) return [];
  const sides = pick.event.split(/\s+(?:vs?\.?|versus)\s+|\s+[–—-]\s+/i).map((s) => s.trim());
  if (sides.length !== 2 || sides.some((s) => !s)) return [];
  const found = sides.map((name) => {
    const logo = resolveTeamLogoPath(name, pick.category);
    const candidates = clubs.filter((club) => club.names.some((n) => normal(n) === normal(name)) || (logo && logo === club.logo));
    const ids = new Set(candidates.map((club) => club.id));
    return ids.size === 1 ? candidates[0] : null;
  });
  if (normal(sides[0]) === normal(sides[1]) || (found[0] && found[0].id === found[1]?.id)) return [];
  // A missing opponent mapping must not erase a recognised club. Resolution
  // with incomplete coverage requires a separate player-profile check below.
  return found.filter((club): club is Club => club !== null);
}

// A recent match squad can identify a full name, but is not a complete club
// roster. Keep that distinction so surname-only matches never use partial data.
function recentLineup(team: any, teamId: number, now: number): SquadPlayer[] {
  const lineup = team?.overview?.lastLineupStats;
  const match = team?.overview?.lastMatch;
  const reference = lineup?.lastMatch;
  const playedAt = Date.parse(match?.status?.utcTime ?? "");
  if (lineup?.id !== teamId || !Number.isSafeInteger(match?.id) || match.id <= 0
    || reference?.matchId !== match.id
    || !Number.isSafeInteger(match?.home?.id) || !Number.isSafeInteger(match?.away?.id)
    || match.home.id <= 0 || match.away.id <= 0 || match.home.id === match.away.id
    || reference?.homeTeamId !== match?.home?.id || reference?.awayTeamId !== match?.away?.id
    || ![match?.home?.id, match?.away?.id].includes(teamId)
    || match?.status?.finished !== true || match.status.cancelled || match.status.awarded
    || !Number.isFinite(playedAt) || playedAt > now || now - playedAt > 30 * 24 * 60 * 60 * 1000
    || !Array.isArray(lineup.starters) || lineup.starters.length !== 11 || !Array.isArray(lineup.subs)) return [];
  const members = [...lineup.starters, ...lineup.subs];
  if (members.some((p) => !Number.isSafeInteger(p?.id) || p.id <= 0 || typeof p.name !== "string" || !p.name.trim())
    || new Set(members.map((p) => p.id)).size !== members.length) return [];
  return members.map((p) => ({ id: p.id, name: p.name.trim(), clubId: teamId, evidence: "recent-lineup" }));
}

export function parseSquad(html: string, teamId: number, now = Date.now()): SquadPlayer[] {
  const script = html.match(/<script\b[^>]*\bid=["']__NEXT_DATA__["'][^>]*>([\s\S]*?)<\/script>/i);
  if (!script) throw new Error("Squad source format unavailable");
  const payload = JSON.parse(script[1]);
  const team = payload?.props?.pageProps?.fallback?.[`team-${teamId}`];
  if (team?.details?.id !== teamId) throw new Error("Squad identity mismatch");
  const groups = team?.squad?.squad;
  // Some covered clubs publish a recent match lineup but no season squad.
  if (groups === null) return recentLineup(team, teamId, now);
  if (!Array.isArray(groups)) throw new Error("Squad unavailable");
  const players: SquadPlayer[] = [];
  for (const group of groups) {
    if (/coach/i.test(String(group.title))) continue;
    for (const member of Array.isArray(group.members) ? group.members : []) {
      if (Number.isSafeInteger(member.id) && member.id > 0 && typeof member.name === "string" && member.name.trim()) {
        players.push({ id: member.id, name: member.name.trim(), clubId: teamId });
      }
    }
  }
  if (players.length < 11) {
    const fallback = recentLineup(team, teamId, now);
    if (fallback.length) return fallback;
    throw new Error("Incomplete squad");
  }
  return players;
}

const aliases: Record<number, string[]> = { 1248662: ["adriel"], 886809: ["javi vasquez"] };

function nameMatches(query: string, player: SquadPlayer): boolean {
  const full = normal(player.name);
  if (full === query || full.endsWith(` ${query}`) || aliases[player.id]?.includes(query)) return true;
  // Explicit initials still identify a player; never use fuzzy spelling.
  const parts = query.split(" "), names = full.split(" ");
  return parts.length > 1 && parts[0].length === 1 && names[0].startsWith(parts[0])
    && names.slice(1).join(" ") === parts.slice(1).join(" ");
}

function candidatePlayer(name: string, squads: SquadPlayer[][]): SquadPlayer | null {
  const query = normal(name);
  if (!query) return null;
  const players = squads.flat();
  const exact = players.filter((p) => normal(p.name) === query);
  const matches = exact.length ? exact : players.filter((p) => nameMatches(query, p));
  return new Set(matches.map((p) => p.id)).size === 1 && new Set(matches.map((p) => p.clubId)).size === 1 ? matches[0] : null;
}

export function uniquePlayer(name: string, squads: SquadPlayer[][]): SquadPlayer | null {
  if (squads.length !== 2 || squads.some((squad) => !squad.length)) return null;
  const query = normal(name);
  const players = squads.flat();
  const candidate = candidatePlayer(name, squads);
  // A missing season roster limits the evidence on either side. Only a unique
  // exact multi-part name is safe; do not infer absent namesakes from a lineup.
  if (players.some((p) => p.evidence === "recent-lineup")) {
    return query.split(" ").length >= 2 && candidate && normal(candidate.name) === query ? candidate : null;
  }
  // Verified public short names/spelling variants; accepted only when the exact
  // player ID occurs in one of the fixture's two current squads.
  return candidate;
}

export function parsePlayerIdentity(html: string, candidate: SquadPlayer): SquadPlayer | null {
  const script = html.match(/<script\b[^>]*\bid=["']__NEXT_DATA__["'][^>]*>([\s\S]*?)<\/script>/i);
  if (!script) throw new Error("Player source format unavailable");
  const player = JSON.parse(script[1])?.props?.pageProps?.data;
  // Corroborate the roster ID, full name and current club independently. A
  // transferred player, namesake, coach or malformed response must not match.
  if (player?.id !== candidate.id || typeof player?.name !== "string"
    || normal(player.name) !== normal(candidate.name) || player?.isCoach !== false) return null;
  if (nationalTeamIds.has(candidate.clubId)) {
    // The primary team is the employer, not the international side. Only an
    // active senior national career entry can corroborate a partial roster.
    const entries = player?.careerHistory?.careerItems?.["national team"]?.teamEntries;
    return Array.isArray(entries) && entries.some((row: any) =>
      row.participantId === candidate.id && row.teamId === candidate.clubId
      && row.teamGender === "male" && row.active === true && row.endDate == null
      && row.hasUncertainData === false) ? candidate : null;
  }
  return player?.primaryTeam?.teamId === candidate.clubId ? candidate : null;
}

const verifyPlayerIdentity = unstable_cache(async (candidate: SquadPlayer) => {
  if (!Number.isSafeInteger(candidate.id) || candidate.id <= 0
    || !clubs.some((club) => club.id === candidate.clubId)) return null;
  const slug = normal(candidate.name).replace(/ /g, "-");
  const response = await fetch(`https://www.fotmob.com/players/${candidate.id}/${slug}`, {
    cache: "no-store", signal: AbortSignal.timeout(4000),
    headers: { Accept: "text/html", "Accept-Language": "en-GB,en;q=0.9" },
  });
  if (!response.ok) throw new Error(`Player source ${response.status}`);
  return parsePlayerIdentity(await response.text(), candidate);
}, ["tip-portrait-player-identity-v2-national"], { revalidate: 6 * 60 * 60 });

// Cache the compact parsed squad, not the large page HTML. Team IDs must come
// from the bundled registry; neither arbitrary URLs nor public name searches run.
const readSquad = unstable_cache(async (teamId: number) => {
  if (!clubs.some((club) => club.id === teamId)) throw new Error("Unknown club");
  const response = await fetch(`https://www.fotmob.com/teams/${teamId}/overview`, {
    cache: "no-store", signal: AbortSignal.timeout(6000),
    headers: { Accept: "text/html", "Accept-Language": "en-GB,en;q=0.9" },
  });
  if (!response.ok) throw new Error(`Squad source ${response.status}`);
  return parseSquad(await response.text(), teamId);
}, ["tip-portrait-squad-v4-national"], { revalidate: 6 * 60 * 60 });

export async function resolveTipPortrait(pick: Pick): Promise<SquadPlayer | null> {
  const pair = clubsForPick(pick);
  if (!pair.length) return null;
  const results = await Promise.allSettled(pair.map((club) => readSquad(club.id)));
  const squads = results.map((result) => result.status === "fulfilled" ? result.value : []);
  const name = pick.player ?? "";
  const complete = uniquePlayer(name, squads);
  if (complete) return complete;
  const candidate = candidatePlayer(name, squads);
  if (!candidate) {
    if (!squads.some((squad) => squad.length) && results.some((result) => result.status === "rejected")) {
      throw new Error("Portrait squads temporarily unavailable");
    }
    return null;
  }
  // A partial lineup is not enough for a bare surname. A complete roster can
  // supply one unique candidate, then the profile verifies their exact identity.
  if (candidate.evidence === "recent-lineup" && normal(name).split(" ").length < 2) return null;
  return verifyPlayerIdentity(candidate);
}

/** Penalty editorial names are full names. Never guess from a shared surname. */
export async function resolveClubPlayerPortrait(clubName: string, league: string, name: string): Promise<SquadPlayer | null> {
  const logo = resolveTeamLogoPath(clubName, league);
  const candidates = clubs.filter((club) => club.names.some((n) => normal(n) === normal(clubName)) || (logo && logo === club.logo));
  if (new Set(candidates.map((club) => club.id)).size !== 1 || !normal(name)) return null;
  const players = await readSquad(candidates[0].id);
  const matches = players.filter((player) => normal(player.name) === normal(name));
  return new Set(matches.map((player) => player.id)).size === 1 ? matches[0] : null;
}

