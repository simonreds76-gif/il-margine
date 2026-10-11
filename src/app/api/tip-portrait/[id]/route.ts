import { unstable_cache } from "next/cache";
import { getSupabaseAdmin } from "@/lib/supabase-server";
import { resolveTipPortrait } from "@/lib/tip-portrait-resolver";

export const runtime = "nodejs";
export const maxDuration = 15;

const readPick = unstable_cache(async (id: number) => {
  const { data, error } = await getSupabaseAdmin().from("bets")
    .select("market, category, event, player").eq("id", id).maybeSingle();
  if (error) throw new Error("Pick lookup unavailable");
  return data;
}, ["tip-portrait-pick-v1"], { revalidate: 60 });

export async function GET(_request: Request, { params }: { params: Promise<{ id: string }> }) {
  const { id } = await params;
  if (!/^[1-9]\d{0,9}$/.test(id)) return new Response(null, { status: 400 });
  try {
    const pick = await readPick(Number(id));
    const player = pick ? await resolveTipPortrait(pick) : null;
    if (player) return new Response(null, {
      status: 307,
      headers: {
        Location: `https://images.fotmob.com/image_resources/playerimages/${player.id}.png`,
        "Cache-Control": "public, max-age=300, s-maxage=21600",
        "X-Content-Type-Options": "nosniff",
      },
    });
    return new Response(null, { status: 404, headers: { "Cache-Control": "public, max-age=60, s-maxage=300" } });
  } catch {
    // A source outage must not prevent publishing a tip or break the page.
    // A later image request retries; do not permanently save an empty portrait.
    return new Response(null, { status: 503, headers: { "Cache-Control": "public, max-age=60, s-maxage=300", "Retry-After": "300" } });
  }
}
