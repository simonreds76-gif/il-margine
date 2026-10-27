import Link from "next/link";
import ToolEmblem from "@/components/ToolEmblem";
import { penaltyNews } from "@/lib/penalty-news-data";
import { newsDate, outcomeLabel } from "@/lib/penalty-news";
import styles from "./PenaltyNews.module.css";

export default function ClubPenaltyReports({ clubUrl, club }: { clubUrl: string; club: string }) {
  const reports = penaltyNews.articles.filter(a => a.clubUrl === clubUrl).sort((a, b) => b.kickoff.localeCompare(a.kickoff) || b.eventId.localeCompare(a.eventId, "en", { numeric: true })).slice(0, 3);
  if (!reports.length) return null;
  return <section className={styles.clubReports} aria-labelledby="club-penalty-reports">
    <div className={styles.relatedHeading}><ToolEmblem name="penalty" className={styles.relatedIcon} /><div>
      <h2 id="club-penalty-reports">Latest penalties for {club}</h2>
      <p>Match reports. The current taker order is reviewed separately.</p>
    </div></div>
    <ul className={styles.reportLinks}>{reports.map(a => <li key={a.id}>
      <Link href={`/penalty-news/${a.slug}`} prefetch={false}>
        <span><span className={styles.reportMeta}><time dateTime={a.date}>{newsDate(a.date)}</time> · {outcomeLabel[a.outcome]} · {a.minute}′</span><strong>{a.title}</strong></span>
        <span aria-hidden="true">↗</span>
      </Link>
    </li>)}</ul>
    <Link className={styles.back} href="/penalty-news#reports" prefetch={false}>All penalty reports <span aria-hidden="true">→</span></Link>
  </section>;
}
