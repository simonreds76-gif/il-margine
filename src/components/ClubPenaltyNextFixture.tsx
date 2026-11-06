'use client';

import { useEffect, useState } from 'react';
import Link from 'next/link';
import { nextClubFixture, type ClubFixtureLink } from '@/lib/penalty-growth-pilot';
import { readConsentSnapshot } from '@/lib/cookie-consent';
import { track } from '@/lib/analytics';
import styles from './ClubPenaltyLog.module.css';

export default function ClubPenaltyNextFixture({ fixtures, checkedAt, expiresAt, clubUrl, renderedAt }: {
  fixtures: ClubFixtureLink[]; checkedAt: string; expiresAt: string; clubUrl: string; renderedAt: number;
}) {
  // Server HTML includes the dated fixture; the browser removes it at kickoff or expiry.
  const [now, setNow] = useState(renderedAt);
  useEffect(() => {
    const update = () => setNow(Date.now());
    const initial = setTimeout(update, 0);
    const timer = setInterval(update, 30000);
    document.addEventListener('visibilitychange', update);
    return () => { clearTimeout(initial); clearInterval(timer); document.removeEventListener('visibilitychange', update); };
  }, []);
  const fixture = nextClubFixture(fixtures, checkedAt, expiresAt, now);
  if (!fixture) return null;
  const date = new Intl.DateTimeFormat('en-GB', { timeZone: 'Europe/London', weekday: 'short', day: 'numeric', month: 'short', hour: '2-digit', minute: '2-digit' }).format(new Date(fixture.kickoff));
  return <section className={styles.fixture} aria-label="Next scheduled league match">
    <div className={styles.fixtureTop}><span>Next scheduled league match</span><time dateTime={fixture.kickoff}>{date} · UK time</time></div>
    <Link className={styles.fixtureLink} href={fixture.href} prefetch={false} onClick={() => {
      if (readConsentSnapshot() === 'accepted' && window.location.hostname === 'ilmargine.bet') {
        track('penalty_tool_click', { club_page: clubUrl, destination: 'matchday', pilot: 'recorded_penalties_v1' });
      }
    }}>
      <span className={styles.crests}>{[fixture.homeCrest, fixture.awayCrest].map((src, i) => src ?
        // eslint-disable-next-line @next/next/no-img-element
        <img key={i} src={src} alt="" width={28} height={28} loading="lazy" /> : null)}</span>
      <span className={styles.fixtureNames}>{fixture.home} <span className="text-slate-500">vs</span> {fixture.away}</span>
      <span className={styles.fixtureAction}>Explore club H2H ↗</span>
    </Link>
    <p className={styles.fixtureNote}>League schedule checked {new Intl.DateTimeFormat('en-GB', { day: 'numeric', month: 'short', timeZone: 'UTC' }).format(new Date(checkedAt))}. Starting lineups and penalty duties are not confirmed.</p>
  </section>;
}
