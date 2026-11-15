import type { Metadata } from 'next';
import Image from 'next/image';
import Link from 'next/link';
import ResearchToolNav from '@/components/ResearchToolNav';
import Footer from '@/components/Footer';
import RelatedLinks from '@/components/RelatedLinks';
import frame from '@/components/ResearchPage.module.css';
import { getTennisMatchday } from '@/lib/tennis-matchday-data';
import TennisMatchdayClient from './TennisMatchdayClient';
import styles from './matchday.module.css';

// The existing capture is read through a shared hourly cache.
export const revalidate = 3600;
const title = 'Tennis Matchday: Upcoming Matches, Results & H2H';
const description = 'Browse upcoming tennis matches and recent results by tournament. Open a match for both players’ recent results and previous meetings.';
export const metadata: Metadata = { title, description,
  alternates: { canonical: '/tennis-matchday' },
  robots: { index: true, follow: true },
  openGraph: { title, description, url: '/tennis-matchday', type: 'website', images: ['/tennis-matchday/opengraph-image'] },
  twitter: { card: 'summary_large_image', title, description, images: ['/tennis-matchday/opengraph-image'] } };

const faqs = [
  ['What am I looking at?', 'Upcoming singles matches from our recorded schedule and completed results from our archive, grouped by tournament. Open a match for both players’ recent results and their previous meetings. This board is research, not a list of recommended bets.'],
  ['Is this the complete career H2H?', 'The record includes available completed competitive singles meetings, including older ATP, Challenger, ITF, qualifying and team matches. Exhibitions, juniors, retirements and unfinished matches are excluded. Missing prices do not hide results, but ROI uses only meetings with recorded odds for both players. Coverage varies by player. An empty record means no eligible meetings were found in our archive.'],
  ['What does the return percentage mean?', 'Hypothetical past returns are collapsed and shown only from five priced meetings. Below that, individual match prices remain visible without an aggregate. The percentage shows the profit or loss from staking the same amount on that player in every priced meeting shown, using each match’s recorded odds. A return of +20% means £20 profit for every £100 staked across those matches. The two players are separate betting strategies. Past returns do not establish value in today’s price.'],
  ['How can both players have a positive H2H return?', 'The odds change from match to match. Several wins at short prices can make one player profitable, while a single win at a big price can cover the other player’s losses. The percentages describe backing each player separately. Open all meetings to see every recorded price.'],
  ['Are the upcoming odds live?', 'They are the latest paired Pinnacle match winner prices in our captured schedule, with the capture time shown above the fixture list and in each opened match. They may have moved since then. Prices older than two hours are hidden, and the board removes matches after their scheduled start. The upcoming prices are separate from the historical odds used for H2H returns.'],
  ['Does choosing a tournament change the H2H record?', 'No. Tournament and date filters choose fixtures only. Each H2H still combines the available completed meetings between those two players across all surfaces and recorded tournaments. It is not a record only at the selected tournament or on its surface.'],
  ['Why is a player comparison or H2H missing?', 'A missing comparison means we have not linked both players to archive profiles. No recorded meetings means the pairing was checked but no eligible previous meeting was found. Recent results are linked independently of priced profiles. A player can have recent results even when the H2H pairing is not yet checked. Neither means the players have never met. Older and lower-level coverage can be incomplete.'],
  ['What do the flag and the coloured dot mean?', 'The flag is the country where the tournament is played, never a player’s nationality. The coloured dot is the verified court type for that edition: outdoor hard, indoor hard, clay or grass. Where either is not verified, the space is left neutral rather than guessed.'],
  ['Which upcoming competitions are covered?', 'The captured schedule currently covers men’s ATP and Challenger singles, including qualifying when supplied. WTA, doubles and ITF fixtures are not part of this upcoming board. Historical H2H coverage is broader than the upcoming schedule.'],
  ['How often does it update?', 'The fixture board checks our existing schedule feed through an hourly cache. Times are provisional and shown in UK time. Started matches disappear from the board; a capture older than 24 hours is withheld. H2H and recent results refresh with the existing daily archive publisher after a verified source update. The Results view shows the last seven completed calendar days, including qualifying; it is not a live scoreboard. The actual source update and coverage dates are shown. A pairing added between archive refreshes may temporarily show missing history. This is not an official order of play or a complete tennis calendar.'],
];

export default async function TennisMatchdayPage() {
  const board = await getTennisMatchday();
  return <><main className={`${frame.page} ${styles.page}`}>
    <div className={styles.shell}>
      <header className={styles.pageHead}>
        <nav className={styles.crumbs} aria-label="Breadcrumb">
          <Link href="/" prefetch={false}>Home</Link><span aria-hidden="true">/</span>
          <Link href="/tools" prefetch={false}>Research tools</Link><span aria-hidden="true">/</span>
          <span aria-current="page">Tennis Matchday</span>
        </nav>
        <div className={styles.brand}>
          <Image className={styles.brandMark} src="/tennis-matchday/mark.svg" alt="" width={36} height={36} priority unoptimized />
          <h1 className={styles.title}>Tennis <span>Matchday</span></h1>
        </div>
        <p className={styles.lede}>Today’s matches and the latest results, by tournament. Open a match for recent form and head-to-head.</p>
      </header>
      <TennisMatchdayClient board={board} renderedAt={new Date().toISOString()} />
      <section className={styles.faq} aria-labelledby="tennis-matchday-faq">
        <h2 id="tennis-matchday-faq">Tennis Matchday explained</h2>
        {faqs.map(([question, answer]) => <details key={question}><summary>{question}</summary><p>{answer}</p></details>)}
      </section>
    </div>
    <ResearchToolNav current="tennis-matchday" />
    <RelatedLinks title="Continue your tennis research" links={[
      { href: '/tennis-matchup', title: 'Matchup Lab', description: 'Playing profiles, serve stats and previous meetings.', icon: 'matchup' },
      { href: '/return-atlas', title: 'Tennis Return Atlas', description: 'Player returns by season, court and price.', icon: 'tennis' },
      { href: '/tennis-tips', title: 'Tennis tips', description: 'Our published tennis selections and results.', icon: 'tennis' },
      { href: '/resources/tennis-retirement-rules', title: 'Retirement rules', description: 'Check how your bookmaker settles a retired match.', icon: 'rules' },
    ]} />
  </main><Footer /></>;
}
