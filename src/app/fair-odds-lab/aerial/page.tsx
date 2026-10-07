import RelatedLinks from "@/components/RelatedLinks";
import PageHeading from "@/components/PageHeading";
import type {Metadata} from 'next';
import Footer from '@/components/Footer';
import AerialBoard from '@/components/aerial/AerialBoard';
import './aerial.css';

export const metadata:Metadata={title:'Air Control: Lineup Height, Headers & Delivery',description:'Compare football starting XIs in height, aerial duels and headed shots. Explore the players and the corners and crosses behind each matchup.',alternates:{canonical:'/fair-odds-lab/aerial'},openGraph:{title:'Air Control | Il Margine',description:'The height. The players. The delivery. Explore the aerial side of the next football fixtures.',url:'/fair-odds-lab/aerial'}};
export const revalidate=86400;
const faqs=[
 ['What does Air Control show?','It brings together reported player heights, recent aerial duels, headed shots, corners and crosses for upcoming league fixtures. Start with the overall size difference, inspect the players, then check how often their teams supply the box.'],
 ['Are these the confirmed starting teams?','Expected XIs come first, with a clear label, and confirmed XIs replace them when available. We currently look for lineups for today and the next three days. The fixture list looks eight days ahead, so matches further away can appear without lineups. If a lineup becomes too old or kickoff passes, its comparison is hidden until it is suitable to show again.'],
 ['Does a taller team have a betting edge?','Height is one part of the picture. Technique, delivery, movement and the opposition matter too. These statistics help you investigate a match; they do not calculate fair odds or establish a profitable bet.'],
 ['Which matches contribute to the statistics?','The archive covers the five major domestic leagues in England, France, Germany, Italy and Spain, starting in 2025/26. Player statistics use up to ten covered appearances and team delivery uses up to five matches, all before the fixture you are viewing. Cups and other leagues are excluded.'],
];
export default async function AerialPage({searchParams}:{searchParams:Promise<Record<string,string|string[]|undefined>>}) {
 const params=process.env.NODE_ENV==='development'?await searchParams:{};
 const example=process.env.NODE_ENV==='development'&&params.example==='1';
 const url=example?'/fair-odds-lab/aerial-check.json':process.env.AERIAL_BOARD_URL||'https://jsuu8rjgs8aaukun.public.blob.vercel-storage.com/fair-odds-lab/aerial.json';
 return <><main className="aerial-page"><PageHeading eyebrow="Lineup research · beta" title="Air Control" icon="aerial" parent={{href:"/tools",label:"Betting tools"}}><p>Height, headers and delivery. Compare the expected starting teams, explore who competes in the air and see how their teammates supply the box. Confirmed XIs replace the expected teams when available.</p></PageHeading>
 <AerialBoard url={url} example={example}/>
 <section className="aerial-faq"><p className="aerial-kicker">HOW TO USE IT</p><h2>From size to involvement.</h2>{faqs.map(([q,a])=><details key={q}><summary>{q}</summary><p>{a}</p></details>)}</section>
 <details className="aerial-method"><summary>Coverage and calculation notes</summary><p>Average height and the three tallest players require all ten outfield heights. Unknown or unresolved heights stay out of the comparison. Every available reported height links to its source in the player detail.</p><p>Aerial duels show contests won out of attempts. Fewer than 20 contests, five appearances or 450 minutes is labelled limited data. Headed shots per 90 uses only matches with shot data and requires three appearances and 270 minutes. A player’s role describes their usual position, not a predicted marking assignment.</p><p>Expected lineups expire after 30 hours and confirmed lineups after two hours, or at kickoff if earlier. The calendar and board also have freshness limits. A failed update keeps the last published snapshot with its original timestamp. The page never collects provider data when you visit.</p><p>Player photos use exact player identities; an unavailable image displays a neutral player icon. This tool is independent of the teams, competitions and data providers shown.</p></details>
 <RelatedLinks title="Keep exploring" label="Related football tools" links={[
 {href:"/fair-odds-lab",title:"Fair Odds Lab",description:"Compare our goalscorer estimates with bookmaker prices.",icon:"lab"},
 {href:"/football-atlas/fixtures",title:"Matchday",description:"Upcoming fixtures with manager and club history.",icon:"matchday"},
 {href:"/football-atlas",title:"Football Return Atlas",description:"Club returns at the recorded odds.",icon:"football"},
 ]} />
 <script type="application/ld+json" dangerouslySetInnerHTML={{__html:JSON.stringify({'@context':'https://schema.org','@type':'FAQPage',mainEntity:faqs.map(([q,a])=>({'@type':'Question',name:q,acceptedAnswer:{'@type':'Answer',text:a}}))}).replace(/</g,'\\u003c')}}/>
 </main><Footer/></>;
}
