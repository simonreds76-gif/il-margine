import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import Footer from '@/components/Footer';
import FixtureBoard from '@/components/football-atlas/fixtures/FixtureBoard';
import MatchdayIcon from '@/components/football-atlas/fixtures/MatchdayIcon';
import type { FixtureBoard as Board } from '@/components/football-atlas/fixtures/types';
import snapshot from '@/data/atlas-fixtures.json';
import { matchdayFaqs } from '@/data/matchday-faq';
import portraitCredits from '../../../../public/manager-atlas/portraits.json';
import './fixtures.css';

export const dynamic = 'force-static';
export const revalidate = false;
const url = 'https://ilmargine.bet/football-atlas/fixtures';
const title = 'Return Atlas Matchday | Upcoming Fixtures & H2H Returns';
const description = 'Compare upcoming football fixtures with past manager and club meetings. Explore home win, draw and away win returns, and find outcomes with positive history in both records.';
export const metadata: Metadata = { title, description, alternates: { canonical: url }, robots: { index: true, follow: true }, openGraph: { title, description, url, type: 'website', images: [{ url: 'https://ilmargine.bet/football-atlas/matchday/share-v1.png', width: 1200, height: 630, alt: 'Return Atlas Matchday: upcoming football fixtures, manager H2H and club returns' }] }, twitter: { card: 'summary_large_image', title, description, images: ['https://ilmargine.bet/football-atlas/matchday/share-v1.png'] } };

export default function FixturesPage() {
  const used = new Set(snapshot.fixtures.flatMap(f => [f.home.manager?.id, f.away.manager?.id]));
  const credits = Object.entries(portraitCredits).filter(([id]) => used.has(id));
  return <><main className="atlas-fixtures">
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({ '@context': 'https://schema.org', '@type': 'FAQPage', mainEntity: matchdayFaqs.map(({ question, answer }) => ({ '@type': 'Question', name: question, acceptedAnswer: { '@type': 'Answer', text: answer } })) }) }} />
    <header className="af-hero">
      <nav className="af-breadcrumb" aria-label="Atlas navigation">
        <Link href="/football-atlas" prefetch={false}>Return Atlas Football</Link><span>/</span><span aria-current="page">Matchday</span>
        <Link className="af-manager-link" href="/manager-atlas" prefetch={false}>Manager Atlas ↗</Link>
      </nav>
      <div className="af-hero-content">
        <div>
          <div className="af-brand" aria-label="Return Atlas Matchday">
            <Image src="/football-atlas/matchday/mark-v1.svg" alt="" width={58} height={58} unoptimized priority />
            <span><small>RETURN ATLAS</small><strong>Matchday<span>.</span></strong></span>
          </div>
          <h1>Upcoming fixtures.<br /><em>Past meetings. Real odds.</em></h1>
          <p className="af-intro">Before these teams meet again, see what happened last time. Compare previous meetings between their clubs and managers, and what backing a win or draw returned at the recorded odds.</p>
          <p className="af-intro af-intro-filter">Want to narrow it down? <strong>Both positive</strong> finds the same outcome with profitable history in both records. Open any fixture to see the matches behind the numbers.</p>
          <div className="af-hero-tags"><span>Five European leagues</span><span>Managers &amp; clubs</span><a href="#fixture-guide">Read the board ↓</a></div>
        </div>
        <div className="af-hero-art" aria-hidden="true">
          <div className="af-pitch">
            <span className="af-pitch-circle" /><span className="af-pitch-line" /><span className="af-pitch-box af-box-left" /><span className="af-pitch-box af-box-right" />
            <div className="af-art-mark"><Image src="/football-atlas/matchday/mark-v1.svg" alt="" width={144} height={144} unoptimized /><span>THE FIXTURE. THE HISTORY. THE RETURN.</span></div>
            <div className="af-art-outcomes"><span>1 <small>HOME</small></span><span>× <small>DRAW</small></span><span>2 <small>AWAY</small></span></div>
          </div>
        </div>
      </div>
    </header>
    <FixtureBoard board={snapshot as Board} />
    <section className="af-guide af-faq" aria-labelledby="matchday-faq-title"><p className="af-eyebrow">USING MATCHDAY</p><h2 id="matchday-faq-title">Two questions to get started.</h2>{matchdayFaqs.map(({ question, answer }) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</section>
    <section className="af-guide" id="fixture-guide"><p className="af-eyebrow">A QUICK READ</p><h2>Know what you’re looking at.</h2><div className="af-guide-grid"><div><span className="af-guide-icon"><MatchdayIcon kind="histories" /></span><h3>One fixture. Two histories.</h3><p>Manager history follows these two coaches across clubs. Club history follows these two teams whoever was in charge. Shared meetings appear in both records, so the two returns are not independent evidence.</p></div><div><span className="af-guide-icon"><MatchdayIcon kind="outcomes" /></span><h3>Three ways to read the return.</h3><p>Home win follows today’s home side or its manager through previous meetings. Draw backs the draw. Away win follows today’s away side or its manager. Historical venues can differ. Each return uses the actual recorded price.</p></div><div><span className="af-guide-icon"><MatchdayIcon kind="returns" /></span><h3>The numbers behind the colour.</h3><p>Mint highlights positive historical ROI from at least three meetings. Both positive keeps fixtures where manager and club history are positive on the same outcome, with at least three meetings in each. Shared meetings are shown so you can see where the records overlap. These are browsing aids, not forecasts. A unit is a fixed stake: +2u from ten 1u bets is +20% ROI. Expand a card to see exactly which matches produced it.</p></div></div><details><summary>What history is covered?</summary><p>Priced matches in the Premier League, Serie A, La Liga, Bundesliga and Ligue 1 from 2012/13 onwards. Cups, European competitions, missing prices and unresolved matches are excluded. These are the meetings in our archive, not every meeting in a manager’s career. The full available archive is used consistently rather than selecting each pairing’s most profitable period.</p><p>Historical prices are closing or verified last prematch quotes as labelled in each match list. They are not current offers. Histories include only result dates before the snapshot date. Upcoming appointments are checked against current rosters and can change before kickoff. Schedule checks expire after seven days, when highlights and positive filters pause until the next refresh. This timer checks the schedule snapshot, not the age of the last league result. The archive coverage dates are shown separately above the fixtures.</p></details><details><summary>What does “odds suggested” mean?</summary><p>We convert all three recorded prices into probabilities and remove their combined margin. Adding those probabilities gives the number of wins or draws the historical market expected. It provides context alongside the actual count and ROI, without predicting the next match.</p></details><details className="af-photo-credits"><summary>Photo credits</summary><ul>{credits.map(([id, photo]) => <li key={id}><a href={photo.source} target="_blank" rel="noopener noreferrer">{photo.name}</a> · {photo.credit} · <a href={photo.licenseUrl} target="_blank" rel="noopener noreferrer">{photo.license}</a><small>{photo.changes}</small></li>)}</ul></details><p className="af-final-note">Past returns at past prices. Explore the evidence before drawing a conclusion.</p></section>
  </main><Footer /></>;
}
