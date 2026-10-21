import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import PageHeading from "@/components/PageHeading";
import Footer from "@/components/Footer";
import { PenaltyNewsCard } from "@/components/PenaltyNewsFeed";
import { penaltyNews, newsDate } from "@/lib/penalty-news";
import styles from "@/components/PenaltyNews.module.css";

export const dynamic = "force-static";
export const dynamicParams = false;
export function generateStaticParams() { return penaltyNews.articles.map(a => ({ slug: a.slug })); }
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const article = penaltyNews.articles.find(a => a.slug === slug);
  if (!article) return { title: "Report not found" };
  return { title: `${article.title} | Penalty News`, description: article.sentences.join(" "), robots: { index: false, follow: false } };
}
export default async function PenaltyReport({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const a = penaltyNews.articles.find(a => a.slug === slug);
  if (!a) notFound();
  return <><main className={styles.page}><PageHeading title={a.title} eyebrow={`${a.leagueLabel} · Penalty report`} icon="penalty" parent={{ href: "/penalty-news", label: "Penalty News" }} meta={<><span className={styles.preview}>Preview</span><time dateTime={a.date}>{newsDate(a.date)}</time><span>By Il Margine</span></>}><p>A short report from the spot, with the match result and a link to the club’s current penalty takers.</p></PageHeading>
    <div className={styles.detailLayout}><PenaltyNewsCard article={a} detail /><aside className={styles.aside}><Image src={a.crest} alt={a.club} width={48} height={48} unoptimized /><h2>Who takes the next one?</h2><p>See {a.club}’s current first choice, alternatives and the evidence behind the order.</p><Link href={a.clubUrl} prefetch={false}>View {a.club}’s takers <span aria-hidden="true">↗</span></Link><Link href="/penalty-news" prefetch={false}>All penalty reports <span aria-hidden="true">→</span></Link></aside></div>
    <Link href="/penalty-news#reports" className={styles.back} prefetch={false}>← Back to Penalty News</Link>
    <details className={styles.method}><summary>How this report was prepared</summary><p>Generated from the completed match’s penalty event and final score. The source does not consistently identify who won the penalty, so we have not added an unverified name. The club’s hierarchy is reviewed separately and is not changed by this report.</p></details>
  </main><Footer /></>;
}
