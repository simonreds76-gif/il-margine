import ResearchToolNav from "@/components/ResearchToolNav";
import AtlasPageHeader from "@/components/AtlasPageHeader";
import frame from "@/components/ResearchPage.module.css";
import type { Metadata } from 'next';
import Link from 'next/link';
import Footer from '@/components/Footer';
import FixtureHistoryBoard from '@/components/football-atlas/fixtures/FixtureHistoryBoard';
import MatchdayIcon from '@/components/football-atlas/fixtures/MatchdayIcon';
import type { FixtureBoard as Board } from '@/components/football-atlas/fixtures/types';
import snapshot from '@/data/atlas-fixtures.json';
import { matchdayFaqs } from '@/data/matchday-faq';
import portraitCredits from '../../../../public/manager-atlas/portraits.json';
import './fixtures.css';

export const dynamic = 'force-static';
export const revalidate = false;
// Stable build timestamp for the static HTML and its first hydrated render.
const renderedAt = Date.now();
const url = 'https://ilmargine.bet/football-atlas/fixtures';
const title = 'Return Atlas Matchday | Upcoming Fixtures & H2H Returns';
const description = 'Find upcoming matches across Europe’s top five leagues. Compare club head to head at both venues, manager meetings across clubs, and historical betting returns.';
export const metadata: Metadata = { title, description, alternates: { canonical: url }, robots: { index: true, follow: true }, openGraph: { title, description, url, type: 'website', images: [{ url: 'https://ilmargine.bet/football-atlas/matchday/share-v1.png', width: 1200, height: 630, alt: 'Return Atlas Matchday: upcoming football fixtures, manager H2H and club returns' }] }, twitter: { card: 'summary_large_image', title, description, images: ['https://ilmargine.bet/football-atlas/matchday/share-v1.png'] } };

export default function FixturesPage() {
  const used = new Set(snapshot.fixtures.flatMap(f => [f.home.manager?.id, f.away.manager?.id]));
  const credits = Object.entries(portraitCredits).filter(([id]) => used.has(id));
  return <><main className={`atlas-fixtures ${frame.page}`}>
    <script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify({ '@context': 'https://schema.org', '@type': 'FAQPage', mainEntity: matchdayFaqs.map(({ question, answer }) => ({ '@type': 'Question', name: question, acceptedAnswer: { '@type': 'Answer', text: answer } })) }) }} />
    <AtlasPageHeader edition="matchday" showNavigation={false} description="Find your next fixture. Compare the clubs’ home-and-away record and the managers’ past meetings." />
    <FixtureHistoryBoard board={snapshot as Board} renderedAt={renderedAt} />
    <ResearchToolNav current="matchday" />
    <section className="af-guide af-faq" aria-labelledby="matchday-faq-title"><p className="af-eyebrow">USING MATCHDAY</p><h2 id="matchday-faq-title">Read the records.</h2>{matchdayFaqs.map(({ question, answer }) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</section>
    <p className="af-final-note"><Link href="/fair-odds-lab/aerial">Explore lineup heights, aerial duels and delivery in Air Control ↗</Link></p><section className="af-guide" id="fixture-guide"><p className="af-eyebrow">A QUICK READ</p><h2>Know what you’re looking at.</h2><div className="af-guide-grid"><div><span className="af-guide-icon"><MatchdayIcon kind="histories" /></span><h3>One fixture. Two histories.</h3><p>Manager history follows these two coaches across clubs. Club history follows these two teams whoever was in charge. Shared meetings appear in both records, so the two returns are not independent evidence.</p></div><div><span className="af-guide-icon"><MatchdayIcon kind="outcomes" /></span><h3>Three ways to read the return.</h3><p>Each team column follows that club or its current manager through previous meetings, at either venue and, for managers, across different clubs. Draw backs the draw. Each return uses the actual recorded price.</p></div><div><span className="af-guide-icon"><MatchdayIcon kind="returns" /></span><h3>The numbers behind the colour.</h3><p>Mint and blue identify the two sides; grey identifies draws. Green ROI boxes highlight positive historical ROI from at least three priced meetings. Both positive keeps fixtures where manager and club history are positive on the same outcome, with at least three priced meetings in each. Shared meetings are shown so you can see where the records overlap. These are browsing aids, not forecasts. A unit is a fixed stake: +2u from ten 1u bets is +20% ROI. Expand a card to see exactly which matches produced it.</p></div></div><details><summary>What history is covered?</summary><p>Verified results in the Premier League, Serie A, La Liga, Bundesliga and Ligue 1 from 2012/13 onwards. The optional Championship view adds regular-season club meetings, while manager records remain top-five only. Cups, playoffs, Europe, other lower divisions and unresolved matches remain excluded. A verified result without odds still counts as a meeting, but is excluded from ROI and market expectations. These are the meetings in our archive, not every meeting in a manager’s career. The full available archive is used consistently rather than selecting each pairing’s most profitable period.</p><p>Historical prices are closing or verified last prematch quotes as labelled in each match list. They are not current offers. Histories include only result dates before the snapshot date. Upcoming appointments are checked against current rosters and can change before kickoff. Schedule checks expire after seven days, when highlights and positive filters pause until the next refresh. This timer checks the schedule snapshot, not the age of the last league result. The archive coverage dates are shown separately above the fixtures.</p></details><details><summary>What does “expected by the odds” mean?</summary><p>We convert all three recorded prices into probabilities and remove their combined margin. Adding those probabilities gives the number of wins or draws the historical market expected. It provides context alongside the actual count and ROI, without predicting the next match.</p></details><details className="af-photo-credits"><summary>Photo credits</summary><ul>{credits.map(([id, photo]) => <li key={id}><a href={photo.source} target="_blank" rel="noopener noreferrer">{photo.name}</a> · {photo.credit} · <a href={photo.licenseUrl} target="_blank" rel="noopener noreferrer">{photo.license}</a><small>{photo.changes}</small></li>)}</ul></details><p className="af-final-note">Past returns at past prices. Explore the evidence before drawing a conclusion.</p></section>
  </main><Footer /></>;
}
