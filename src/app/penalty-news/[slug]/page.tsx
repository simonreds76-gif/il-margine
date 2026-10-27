import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import { notFound } from "next/navigation";
import PageHeading from "@/components/PageHeading";
import Footer from "@/components/Footer";
import { PenaltyNewsCard } from "@/components/PenaltyNewsFeed";
import { newsDate, newsImageUrl, outcomeLabel } from "@/lib/penalty-news";
import { penaltyNews } from "@/lib/penalty-news-data";
import styles from "@/components/PenaltyNews.module.css";

export const dynamic = "force-static";
export const dynamicParams = false;
export function generateStaticParams() { return penaltyNews.articles.map(a => ({ slug: a.slug })); }
export async function generateMetadata({ params }: { params: Promise<{ slug: string }> }): Promise<Metadata> {
  const { slug } = await params;
  const article = penaltyNews.articles.find(a => a.slug === slug);
  if (!article) return { title: "Report not found" };
  const url = `https://ilmargine.bet/penalty-news/${article.slug}`;
  return { title: `${article.title} | Penalty News`, description: article.paragraphs[0], alternates: { canonical: url }, robots: { index: true, follow: true },
    openGraph: { title: article.title, description: article.paragraphs[0], url, type: "article", publishedTime: article.publishedAt, modifiedTime: article.updatedAt, authors: ["Il Margine"], images: [{ url: newsImageUrl(article.slug), width: 1200, height: 630, alt: `${article.player} · ${article.home} ${article.homeScore}–${article.awayScore} ${article.away} · ${article.minute}′ penalty` }] },
    twitter: { card: "summary_large_image", images: [newsImageUrl(article.slug)] } };
}
export default async function PenaltyReport({ params }: { params: Promise<{ slug: string }> }) {
  const { slug } = await params;
  const a = penaltyNews.articles.find(a => a.slug === slug);
  if (!a) notFound();
  const related = penaltyNews.articles.filter(other => other.matchId === a.matchId && other.id !== a.id);
  const schema = { "@context": "https://schema.org", "@type": "NewsArticle", headline: a.title,
    mainEntityOfPage: `https://ilmargine.bet/penalty-news/${a.slug}`, datePublished: a.publishedAt, dateModified: a.updatedAt,
    author: { "@type": "Organization", name: "Il Margine", url: "https://ilmargine.bet" },
    publisher: { "@type": "Organization", name: "Il Margine", url: "https://ilmargine.bet" },
    image: [newsImageUrl(a.slug)], description: a.paragraphs[0], articleBody: a.paragraphs.join("\n\n"), inLanguage: "en-GB", articleSection: "Penalty News" };
  return <><script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }} /><main className={styles.page} data-article-id={a.id}><PageHeading title={a.title} eyebrow={`${a.leagueLabel} · Penalty report`} icon="penalty" parent={{ href: "/penalty-news", label: "Penalty News" }} meta={<><time dateTime={a.date}>{newsDate(a.date)}</time><span>By Il Margine</span></>}>{null}</PageHeading>
    <div className={styles.detailLayout}><PenaltyNewsCard article={a} detail /><aside className={styles.aside}><Image src={a.crest} alt={a.club} width={48} height={48} unoptimized /><h2>Who takes the next one?</h2><p>See {a.club}’s current first choice, alternatives and the evidence behind the order.</p><Link href={a.clubUrl} prefetch={false}>View {a.club}’s takers <span aria-hidden="true">↗</span></Link><Link href="/penalty-news" prefetch={false}>All penalty reports <span aria-hidden="true">→</span></Link></aside></div>
    {related.length > 0 && <section className={styles.relatedReports} aria-labelledby="same-match-reports"><h2 id="same-match-reports">Other penalties in this match</h2><ul className={styles.reportLinks}>{related.map(other => <li key={other.id}><Link href={`/penalty-news/${other.slug}`} prefetch={false}><span><span className={styles.reportMeta}>{other.minute}′ · {outcomeLabel[other.outcome]} · {other.club}</span><strong>{other.title}</strong></span><span aria-hidden="true">→</span></Link></li>)}</ul></section>}
    <Link href="/penalty-news#reports" className={styles.back} prefetch={false}>← Back to Penalty News</Link>
    <details className={styles.method}><summary>How this report was prepared</summary><p>Automatically generated from the completed match’s penalty event, incident commentary and player statistics. Foul winners and handballs are included only when the commentary supports them. Match statistics cover the player’s full appearance. The club’s hierarchy is reviewed separately and is not changed by this report.</p><p>Scheduled checks revisit recent matches for delayed evidence and corrections. <Link href="/contact" prefetch={false}>Report an error</Link> or read <Link href="/penalty-takers/methodology" prefetch={false}>how we review penalty hierarchies</Link>.</p></details>
  </main><Footer /></>;
}
