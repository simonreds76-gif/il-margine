import { fetchSeoTipFixture } from "@/lib/tip-seo-server";
import { renderTipShareImage } from "@/lib/tip-share-image";
export const alt = "Il Margine published match selections and recorded prices";
export const size = { width: 1200, height: 630 };
export const contentType = "image/png";
export const dynamic = "force-static";
export const revalidate = 604800;
export default async function Image({ params }: { params: Promise<{ slugId: string }> }) {
  const { slugId } = await params;
  const fixture = await fetchSeoTipFixture(slugId);
  return renderTipShareImage(fixture?.bets ?? []);
}
