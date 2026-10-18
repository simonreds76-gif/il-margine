import { getClubPenaltyTeam } from "@/lib/club-penalty-takers";
import { foldNameText } from "@/lib/player-name-matching";
import { resolveClubPlayerPortrait } from "@/lib/tip-portrait-resolver";

export const runtime = "nodejs";
export const maxDuration = 15;

export async function GET(_request: Request, { params }: { params: Promise<{ league: string; club: string; player: string }> }) {
  const { league, club, player } = await params;
  if (!/^[a-z-]{1,30}$/.test(league) || !/^[a-z0-9-]{1,80}$/.test(club) || !/^[a-z0-9]{1,100}$/.test(player)) {
    return new Response(null, { status: 400 });
  }
  try {
    const team = await getClubPenaltyTeam(league, club);
    const name = team && !team.isArchived ? team.verifiedNames.find((name) => foldNameText(name).toLowerCase().replace(/[^a-z0-9]/g, "") === player) : null;
    // Only published, current takers can trigger a cached squad lookup.
    const portrait = name && team ? await resolveClubPlayerPortrait(team.team, league, name) : null;
    if (portrait) return new Response(null, { status: 307, headers: {
      Location: `https://images.fotmob.com/image_resources/playerimages/${portrait.id}.png`,
      "Cache-Control": "public, max-age=300, s-maxage=21600",
      "X-Content-Type-Options": "nosniff",
    } });
    return new Response(null, { status: 404, headers: { "Cache-Control": "public, max-age=60, s-maxage=300" } });
  } catch {
    return new Response(null, { status: 503, headers: { "Cache-Control": "public, max-age=60, s-maxage=300", "Retry-After": "300" } });
  }
}
