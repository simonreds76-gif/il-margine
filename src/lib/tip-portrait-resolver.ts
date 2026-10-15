import "server-only";
import { unstable_cache } from "next/cache";
import manifest from "../../data/goalscorer/team-logo-map.json";
import europe from "../../data/team-logos/europe.json";
import { foldNameText } from "./player-name-matching";
import { resolveTeamLogoPath } from "./team-logos";

type Club = { id: number; names: string[]; logo: string };
export type SquadPlayer = { id: number; name: string; clubId: number };
type Pick = { market: string; category: string; event: string; player: string | null };
const normal = (s: string) => foldNameText(s).toLowerCase().replace(/[^a-z0-9]+/g, " ").trim();
const clubs: Club[] = [
  ...Object.values(manifest.leagues).flatMap((league) => Object.entries(league.teams).map(([name, team]) => ({
    id: team.fotmob_team_id, names: [name, team.fotmob_name, team.fotmob_short_name], logo: team.logo_path,
  }))),
  ...europe.teams.map((team) => ({ id: team.fotmob_team_id, names: [team.name, ...team.aliases], logo: team.logo_path })),
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
  // Both squads are required: a surname might occur on either side.
  return found.every((club): club is Club => club !== null) && found[0].id !== found[1].id ? found : [];
}

export function parseSquad(html: string, teamId: number): SquadPlayer[] {
  const script = html.match(/<script\b[^>]*\bid=["']__NEXT_DATA__["'][^>]*>([\s\S]*?)<\/script>/i);
  if (!script) throw new Error("Squad source format unavailable");
  const payload = JSON.parse(script[1]);
  const team = payload?.props?.pageProps?.fallback?.[`team-${teamId}`];
  if (team?.details?.id !== teamId) throw new Error("Squad identity mismatch");
  const groups = team?.squad?.squad;
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
  if (players.length < 11) throw new Error("Incomplete squad");
  return players;
}

export function uniquePlayer(name: string, squads: SquadPlayer[][]): SquadPlayer | null {
  if (squads.length !== 2 || squads.some((squad) => !squad.length)) return null;
  const query = normal(name);
  if (!query) return null;
  const players = squads.flat();
  const exact = players.filter((p) => normal(p.name) === query);
  // Verified public short names/spelling variants; accepted only when the exact
  // player ID occurs in one of the fixture's two current squads.
  const aliases: Record<number, string[]> = { 1248662: ["adriel"], 886809: ["javi vasquez"] };
  const matches = exact.length ? exact : players.filter((p) => normal(p.name).endsWith(` ${query}`) || aliases[p.id]?.includes(query));
  const ids = new Set(matches.map((p) => p.id));
  return ids.size === 1 ? matches[0] : null;
}

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
}, ["tip-portrait-squad-v1"], { revalidate: 6 * 60 * 60 });

export async function resolveTipPortrait(pick: Pick): Promise<SquadPlayer | null> {
  const pair = clubsForPick(pick);
  if (pair.length !== 2) return null;
  const squads = await Promise.all(pair.map((club) => readSquad(club.id)));
  return uniquePlayer(pick.player ?? "", squads);
}
