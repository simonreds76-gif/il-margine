import type { Metadata } from "next";
import { notFound, permanentRedirect } from "next/navigation";
import Footer from "@/components/Footer";
import PageHeading from "@/components/PageHeading";
import PenaltyNewsFeed from "@/components/PenaltyNewsFeed";
import { penaltyNews } from "@/lib/penalty-news-data";
import { newsPagePath, NEWS_PAGE_SIZE } from "@/lib/penalty-news";
import styles from "@/components/PenaltyNews.module.css";

export const dynamic = "force-static";
export const dynamicParams = false;
const pageCount = Math.ceil(penaltyNews.articles.length / NEWS_PAGE_SIZE);
type Props = { params: Promise<{ pageNumber: string }> };
export function generateStaticParams() {
  return Array.from({ length: pageCount }, (_, i) => ({ pageNumber: String(i + 1) }));
}
function validPage(raw: string) {
  const page = Number(raw);
  return /^\d+$/.test(raw) && String(page) === raw && page >= 1 && page <= pageCount ? page : null;
}
export async function generateMetadata({ params }: Props): Promise<Metadata> {
  const page = validPage((await params).pageNumber);
  if (!page) return { title: "Archive not found", robots: { index: false } };
  return { title: `Penalty News archive — page ${page}`, description: "Earlier penalty reports, match outcomes and links to club penalty-taker guides.", alternates: { canonical: `https://ilmargine.bet${newsPagePath(page)}` } };
}
export default async function PenaltyNewsArchive({ params }: Props) {
  const page = validPage((await params).pageNumber);
  if (!page) notFound();
  if (page === 1) permanentRedirect("/penalty-news");
  return <><main className={styles.page}><PageHeading title="Penalty News archive" eyebrow={`From the spot · Page ${page} of ${pageCount}`} icon="penalty" parent={{ href: "/penalty-news", label: "Latest penalty reports" }}><p>Earlier reports from completed league matches. Filters search the full collection.</p></PageHeading><PenaltyNewsFeed articles={penaltyNews.articles} page={page} /></main><Footer /></>;
}
