import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHeading from "@/components/PageHeading";
import ToolEmblem from "@/components/ToolEmblem";
import PenaltyNewsFeed from "@/components/PenaltyNewsFeed";
import { newsDate, newsImageUrl } from "@/lib/penalty-news";
import { penaltyNews } from "@/lib/penalty-news-data";
import styles from "@/components/PenaltyNews.module.css";

export const dynamic = "force-static";
export const metadata: Metadata = {
  title: "Penalty News | Latest penalty takers, goals and misses",
  description: "Who took the penalty, what happened and where to check the club hierarchy. Penalty reports from the Premier League, Serie A, La Liga, Bundesliga and Ligue 1.",
  alternates: { canonical: "https://ilmargine.bet/penalty-news" },
  openGraph: { title: "Penalty News | Il Margine", description: "The foul, the decision, the finish. Penalty reports and club taker guides across Europe’s top five leagues.", url: "https://ilmargine.bet/penalty-news", type: "website", images: [{ url: newsImageUrl(), width: 1200, height: 630, alt: "Penalty News — the incident, the outcome, the club's current takers" }] },
  twitter: { card: "summary_large_image", images: [newsImageUrl()] },
  robots: { index: true, follow: true },
};

export default function PenaltyNewsPage() {
  return <><main className={styles.page} data-news-version={penaltyNews.generatedAt}><PageHeading title="Penalty News" eyebrow="Football · From the spot" icon="penalty" introClassName={styles.intro} meta={<span>Reports from {newsDate(penaltyNews.coverageStart)} · Automatic reports after completed matches</span>}><p>The foul, the decision, the finish. Follow every reported penalty across Europe’s top five leagues, with the match context and a direct route to each club’s current takers.</p></PageHeading>
    <div className={styles.overview}><div><strong>From the incident to the next taker</strong></div><Link href="/penalty-takers" prefetch={false}><ToolEmblem name="penalty" className={styles.routeIcon} />Club penalty takers <span aria-hidden="true">↗</span></Link></div>
    <PenaltyNewsFeed articles={penaltyNews.articles} />
    <details className={styles.method}><summary>About these reports</summary><p>Each report covers a recorded penalty in a completed league match. The result, taker and outcome come from verified match evidence. We distinguish saved attempts, misses and shots against the woodwork. Cup matches and shootouts are excluded.</p><p>These reports are generated automatically from verified event data independently of our hierarchy reviews. A penalty does not automatically change a club’s taker order. We only name the player who won a penalty when the incident evidence identifies them; handballs are reported separately. Match statistics describe the full appearance, not just the penalty.</p><p>The archive starts on {newsDate(penaltyNews.coverageStart)}. Scheduled post-match checks publish new reports in batches and revisit recent fixtures for delayed details or corrections. Reports do not wait for hierarchy reviews.</p><p><Link href="/penalty-takers/methodology" prefetch={false}>How we review penalty hierarchies</Link> · <Link href="/contact" prefetch={false}>Report an error or request a correction</Link></p></details>
  </main><Footer /></>;
}
