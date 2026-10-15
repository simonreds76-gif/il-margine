import { supabase } from "@/lib/supabase";
import { parseTipSlugId } from "@/lib/slugify";
import { renderTipShareImage } from "@/lib/tip-share-image";

export const alt = "Il Margine published selection and recorded price";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-static";
export const revalidate = 604800;

export default async function Image({ params }: { params: Promise<{ slugId: string }> }) {
  const { slugId } = await params;
  const id = parseTipSlugId(slugId);
  if (id === null) return renderTipShareImage([]);
  const { data, error } = await supabase.from("bets")
    .select("id,event,market,category,player,selection,odds,stake,match_date").eq("id", id).maybeSingle();
  if (error) throw new Error("Published selection lookup unavailable");
  return renderTipShareImage(data ? [data] : []);
}
