import type { Metadata } from "next";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHeading from "@/components/PageHeading";
import ToolEmblem from "@/components/ToolEmblem";
import PenaltyNewsFeed from "@/components/PenaltyNewsFeed";
import { penaltyNews, newsDate } from "@/lib/penalty-news";
import styles from "@/components/PenaltyNews.module.css";

export const dynamic = "force-static";
export const metadata: Metadata = {
  title: "Penalty News | Latest penalty takers, goals and misses",
  description: "Who took the penalty, what happened and where to check the club hierarchy. Penalty reports from the Premier League, Serie A, La Liga, Bundesliga and Ligue 1.",
  robots: { index: false, follow: false },
};

export default function PenaltyNewsPage() {
  return <><main className={styles.page}><PageHeading title="Penalty News" eyebrow="Football · From the spot" icon="penalty" introClassName={styles.intro} meta={<><span className={styles.preview}>Preview</span><span>Match coverage {newsDate(penaltyNews.coverageStart)} to {newsDate(penaltyNews.checkedThrough)}</span></>}><p>The foul, the decision, the finish. Follow every reported penalty across Europe’s top five leagues, with the match context and a direct route to each club’s current takers.</p></PageHeading>
    <div className={styles.overview}><div><strong>From the incident to the next taker</strong></div><Link href="/penalty-takers" prefetch={false}><ToolEmblem name="penalty" className={styles.routeIcon} />Club penalty takers <span aria-hidden="true">↗</span></Link></div>
    <PenaltyNewsFeed articles={penaltyNews.articles} />
    <details className={styles.method}><summary>About these reports</summary><p>Each report covers a recorded penalty in a completed league match. The result, taker and outcome come from the match evidence linked on the report. We distinguish saved attempts, misses and shots against the woodwork. Cup matches and shootouts are excluded.</p><p>Reports are generated from verified event data independently of our hierarchy reviews. A penalty does not automatically change a club’s taker order. We only name the player who won a penalty when the incident evidence identifies them; handballs are reported separately. Match statistics describe the full appearance, not just the penalty.</p><p>This preview contains matches from {newsDate(penaltyNews.coverageStart)} to {newsDate(penaltyNews.checkedThrough)}. It is not a complete season archive.</p></details>
  </main><Footer /></>;
}
