import type { Metadata } from 'next';
import AtlasPageHeader from '@/components/AtlasPageHeader';
import Footer from '@/components/Footer';
import RelatedLinks from '@/components/RelatedLinks';
import frame from '@/components/ResearchPage.module.css';
import { getTennisMatchday } from '@/lib/tennis-matchday-data';
import TennisMatchdayClient from './TennisMatchdayClient';
import styles from './matchday.module.css';

// The existing capture is read through a shared hourly cache.
export const revalidate = 3600;
const title = 'Tennis Matchday: Upcoming Matches & H2H';
const description = 'Explore upcoming tennis matches, previous meetings and historical betting returns. Open both players in Matchup Lab and Return Atlas.';
export const metadata: Metadata = { title, description,
  alternates: { canonical: '/tennis-matchday' },
  robots: { index: true, follow: true },
  openGraph: { title, description, url: '/tennis-matchday', type: 'website', images: ['/tennis-matchday/opengraph-image'] },
  twitter: { card: 'summary_large_image', title, description, images: ['/tennis-matchday/opengraph-image'] } };

const faqs = [
  ['What am I looking at?', 'Upcoming singles matches from our recorded schedule, with the previous meetings found in Matchup Lab. Use the H2H as a starting point, then compare the players and explore their wider records. This board is research, not a list of recommended bets.'],
  ['Is this the complete career H2H?', 'No. The record uses completed ATP main draw matches with prices in our archive from 2021 onward. Qualifying, Challenger, team events and retirements are not included in that history. An empty record means no meetings were found in this archive, not that the players have never met.'],
  ['What does the return percentage mean?', 'It shows the profit or loss from staking the same amount on that player in every priced meeting shown, using each match’s recorded odds. A return of +20% means £20 profit for every £100 staked across those matches. The two players are separate betting strategies. Past returns do not establish value in today’s price.'],
  ['How can both players have a positive H2H return?', 'The odds change from match to match. Several wins at short prices can make one player profitable, while a single win at a big price can cover the other player’s losses. The percentages describe backing each player separately. Open all meetings to see every recorded price and the profit or loss from a £10 bet.'],
  ['Are the upcoming odds live?', 'They are the latest paired Pinnacle match winner prices in our captured schedule, with the capture time shown on each card. They may have moved since then. Prices older than two hours are hidden, and the board removes matches after their scheduled start. The upcoming prices are separate from the historical odds used for H2H returns.'],
  ['Why do some Challenger matches have no comparison?', 'The upcoming schedule includes available Challenger and qualifying singles. Our historical research currently covers ATP main draws, so some players and previous meetings are outside its scope. Those fixtures remain visible with their coverage clearly marked.'],
  ['How often does it update?', 'The fixture board checks our existing schedule feed through an hourly cache. Times are provisional and shown in UK time. Started matches disappear from the board; a capture older than 24 hours is withheld. Historical results update with the tennis archive refresh. This is not an official order of play or a complete tennis calendar.'],
];

export default async function TennisMatchdayPage() {
  const board = await getTennisMatchday();
  return <><main className={`${frame.page} ${styles.page}`}>
    <AtlasPageHeader edition="tennis-matchday" description="Start with the next tennis matches. See each pair’s past meetings and betting returns, then open their player stats and full records." />
    <TennisMatchdayClient board={board} renderedAt={new Date().toISOString()} />
    <section className={styles.guide} aria-labelledby="tennis-matchday-guide"><p className={styles.eyebrow}>THE NEXT MATCH, WITH CONTEXT</p><h2 id="tennis-matchday-guide">From the fixture to the full picture.</h2>
      <div className={styles.steps}><article><span>01</span><h3>Find the pairing</h3><p>Choose today, tomorrow or the next three days. Search a player or tournament.</p></article><article><span>02</span><h3>Check the meetings</h3><p>See who won and how betting on each player returned. The match count keeps the numbers in context.</p></article><article><span>03</span><h3>Go beyond the score</h3><p>Open the same two players in Matchup Lab for serve, return, aces and double faults.</p></article></div>
    </section>
    <section className={styles.faq} aria-labelledby="tennis-matchday-faq"><h2 id="tennis-matchday-faq">Tennis Matchday explained</h2>{faqs.map(([question, answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</section>
    <RelatedLinks title="Continue your tennis research" links={[
      { href: '/tennis-matchup', title: 'Matchup Lab', description: 'Playing profiles, serve stats and previous meetings.', icon: 'matchup' },
      { href: '/return-atlas', title: 'Tennis Return Atlas', description: 'Player returns by season, court and price.', icon: 'tennis' },
      { href: '/tennis-tips', title: 'Tennis tips', description: 'Our published tennis selections and results.', icon: 'tennis' },
      { href: '/resources/tennis-retirement-rules', title: 'Retirement rules', description: 'Check how your bookmaker settles a retired match.', icon: 'rules' },
    ]} />
  </main><Footer /></>;
}
