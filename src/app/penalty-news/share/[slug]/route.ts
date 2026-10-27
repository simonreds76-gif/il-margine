import { ImageResponse } from "next/og";
import PenaltyNewsSocial from "@/components/PenaltyNewsSocial";
import { penaltyNews } from "@/lib/penalty-news-data";

export const dynamic = "force-static";
export const dynamicParams = false;
export function generateStaticParams() {
  return [{ slug: "index" }, ...penaltyNews.articles.map(a => ({ slug: a.slug }))];
}
export async function GET(_request: Request, { params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const article = penaltyNews.articles.find(a => a.slug === slug);
  if (slug !== "index" && !article) return new Response("Report not found", { status: 404 });
  return new ImageResponse(PenaltyNewsSocial({ article }), { width: 1200, height: 630 });
}
