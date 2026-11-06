import Link from 'next/link';
import ToolEmblem from './ToolEmblem';
import FixturePhoto from './FixturePhoto';
import { penaltyNews } from '@/lib/penalty-news-data';
import { newsDate, outcomeLabel } from '@/lib/penalty-news';
import { recordedClubPenalties } from '@/lib/penalty-growth-pilot';
import styles from './ClubPenaltyLog.module.css';

export default function ClubPenaltyLog({ clubUrl, club }: { clubUrl: string; club: string }) {
  const reports = recordedClubPenalties(penaltyNews.articles, clubUrl, penaltyNews.coverageStart);
  const takers = new Map<string, number>();
  for (const report of reports) takers.set(report.player, (takers.get(report.player) ?? 0) + 1);
  return <section id="recorded-penalties" className={styles.log} aria-labelledby="penalty-log-heading">
    <header className={styles.heading}><ToolEmblem name="penalty" className={styles.emblem} /><div>
      <p className={styles.eyebrow}>The match evidence</p>
      <h2 id="penalty-log-heading">Penalty reports for {club}</h2>
      <p>Published reports since <time dateTime={penaltyNews.coverageStart}>{newsDate(penaltyNews.coverageStart)}</time>. This is not a complete season total.</p>
    </div></header>
    {reports.length ? <>
      <dl className={styles.stats}>
        <div><dt>Published reports</dt><dd>{reports.length}</dd></div>
        <div><dt>Recorded as scored</dt><dd>{reports.filter(a => a.outcome === 'scored').length}</dd></div>
        <div><dt>Different takers</dt><dd>{takers.size}</dd></div>
      </dl>
      <p className={styles.takers}><strong>Takers in these reports:</strong> {[...takers].map(([name, count]) => `${name} (${count})`).join(' · ')}</p>
      <ol className={styles.rows}>{reports.map(a => <li key={`${a.matchId}:${a.eventId}`}>
        <Link prefetch={false} href={`/penalty-news/${a.slug}`} className={styles.row}>
          <FixturePhoto src={a.portrait} size={48} className={styles.portrait} fallback={<span aria-hidden="true">{a.player.split(/\s+/).map(word => word[0]).slice(0, 2).join('')}</span>} />
          <div className={styles.detail}>
            <span className={styles.meta}><time dateTime={a.date}>{newsDate(a.date)}</time> · {a.leagueLabel}</span>
            <strong className={styles.player}>{a.player}</strong>
            <span className={styles.match}>{a.home} {a.homeScore}–{a.awayScore} {a.away}</span>
          </div>
          <div className={styles.result}><span className={a.outcome === 'scored' ? styles.scored : styles.notScored}>{outcomeLabel[a.outcome] ?? 'See report'}</span><span>{a.minute}′</span><span className={styles.open}>Read report ↗</span></div>
        </Link>
      </li>)}</ol>
      <p className={styles.footnote}>Each row is a reported incident; separately reported retakes remain separate. These results do not automatically change the hierarchy above.</p>
    </> : <p className={styles.empty}>No {club} penalty reports are filed in this window. This does not mean the club has taken no penalties this season.</p>}
    <Link href="/penalty-news#reports" prefetch={false} className={styles.archive}>Browse all Penalty News <span aria-hidden="true">→</span></Link>
  </section>;
}
