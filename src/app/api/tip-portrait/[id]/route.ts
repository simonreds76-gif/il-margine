import { unstable_cache } from "next/cache";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { resolveTipPortrait } from "@/lib/tip-portrait-resolver";
import { getTipArtwork } from "@/lib/tip-artwork";

export const runtime = "nodejs";
export const maxDuration = 15;

const readPick = (id: number) => unstable_cache(async () => {
  const { data, error } = await getSupabaseAdmin().from("bets")
    .select("market, category, event, player").eq("id", id).maybeSingle();
  if (error) throw new Error("Pick lookup unavailable");
  return data;
}, ["tip-portrait-pick-v2", String(id)], { revalidate: 60, tags: [`tip-portrait:${id}`] })();

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[1-9]\d{0,9}$/.test(id)) return new Response(null, { status: 400 });
  try {
    const pick = await readPick(Number(id));
    // Previously rendered tip URLs may outlive their dynamic lookup. Reuse a
    // verified identity first, without an id that could point back to this API.
    const artwork = pick ? getTipArtwork(pick) : [];
    const known = artwork.length === 1 && artwork[0].kind === "player" ? artwork[0].src : null;
    if (known && /^https:\/\/images\.fotmob\.com\/image_resources\/playerimages\/\d+\.png$/.test(known)) {
      return new Response(null, { status: 307, headers: {
        Location: known,
        "Cache-Control": "public, max-age=300, s-maxage=21600",
        "X-Content-Type-Options": "nosniff",
      } });
    }
    const player = pick ? await resolveTipPortrait(pick) : null;
    if (player) return new Response(null, {
      status: 307,
      headers: {
        Location: `https://images.fotmob.com/image_resources/playerimages/${player.id}.png`,
        "Cache-Control": "public, max-age=300, s-maxage=21600",
        "X-Content-Type-Options": "nosniff",
      },
    });
    return new Response(null, { status: 404, headers: { "Cache-Control": "no-store" } });
  } catch {
    // A source outage must not prevent publishing a tip or break the page.
    // A later image request retries; do not permanently save an empty portrait.
    return new Response(null, { status: 503, headers: { "Cache-Control": "no-store", "Retry-After": "60" } });
  }
}
