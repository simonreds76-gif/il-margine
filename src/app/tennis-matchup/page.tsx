import RelatedLinks from "@/components/RelatedLinks";
import TennisMatchdayPromo from "@/components/TennisMatchdayPromo";
import AtlasPageHeader from "@/components/AtlasPageHeader";
import frame from "@/components/ResearchPage.module.css";
import type { Metadata } from "next";
import Footer from "@/components/Footer";
import MatchdayPromo from "@/components/MatchdayPromo";
import { BASE_URL } from "@/lib/config";
import { MATCHUP_FAQS } from "@/lib/tennis-matchup-faq";
import release from "@/data/tennis-matchup-release.json";
import MatchupClient from "./MatchupClient";
import "./matchup.css";
import "./comparison.css";

export const dynamic="force-static";
const title="Tennis Matchup Lab: H2H, Aces & Player Statistics";
const description="Compare ATP tennis players by surface and location. Explore head-to-head results, aces, double faults, serve and return statistics, and historical pre-match odds.";
export const metadata: Metadata={title,description,alternates:{canonical:`${BASE_URL}/tennis-matchup`},robots:{index:true,follow:true},
  openGraph:{title,description,url:`${BASE_URL}/tennis-matchup`,type:"website",images:[{url:"/tennis-matchup/share-v1.png",width:1200,height:630,alt:"Tennis Matchup Lab by Il Margine — compare the players, understand the matchup"}]},
  twitter:{card:"summary_large_image",title,description,images:["/tennis-matchup/share-v1.png"]}};
const readable=(date:string)=>new Intl.DateTimeFormat("en-GB",{day:"numeric",month:"long",year:"numeric",timeZone:"UTC"}).format(new Date(`${date}T12:00:00Z`));

export default function TennisMatchupPage(){
  const schema=[{"@context":"https://schema.org","@type":"WebApplication",name:"Tennis Matchup Lab",url:`${BASE_URL}/tennis-matchup`,description,applicationCategory:"SportsApplication",operatingSystem:"Any",isAccessibleForFree:true},
    {"@context":"https://schema.org","@type":"FAQPage",mainEntity:MATCHUP_FAQS.map(({question,answer})=>({"@type":"Question",name:question,acceptedAnswer:{"@type":"Answer",text:answer}}))},
    {"@context":"https://schema.org","@type":"BreadcrumbList",itemListElement:[{ "@type":"ListItem",position:1,name:"Home",item:BASE_URL},{"@type":"ListItem",position:2,name:"Betting tools",item:`${BASE_URL}/tools`},{"@type":"ListItem",position:3,name:"Tennis Matchup Lab",item:`${BASE_URL}/tennis-matchup`}]}];
  return <><main className={`matchup-lab ${frame.page}`}>
    <script type="application/ld+json" dangerouslySetInnerHTML={{__html:JSON.stringify(schema).replace(/</g,"\\u003c")}}/>
    <AtlasPageHeader edition="matchup" description="Compare ATP players through past meetings, serve and return stats, aces and double faults. Filter by surface or location.">
      <details className={frame.help}><summary>How it works &amp; coverage</summary><p>Start with two players. Compare their profiles against all opponents, or switch to their meetings against each other. Open a match to inspect the numbers behind it.</p><p>Snapshot {readable(release.checkedAt)}. Latest result {readable(release.through)}. {release.matches.toLocaleString("en-GB")} archive matches from 2021 onward. <a href="#faq">Read the FAQs ↓</a></p></details>
    </AtlasPageHeader>
    <TennisMatchdayPromo />
    <MatchupClient indexUrl={release.indexUrl}/>
    <MatchdayPromo compact />
    <noscript><p>Enable JavaScript to select players and compare their records. The guide, coverage details and FAQs below are available without it.</p></noscript>
    <section className="matchup-faq" id="faq" aria-labelledby="matchup-faq-title"><p className="eyebrow">GET MORE FROM THE NUMBERS</p><h2 id="matchup-faq-title">Tennis Matchup Lab FAQs</h2><p>What the tool shows, how to use the filters, and where the evidence ends.</p>{MATCHUP_FAQS.map(({question,answer})=><details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</section>
    <RelatedLinks id="explore-tennis" title="Keep the price and the record in view." description="Explore the player profile, compare historical returns and check the rules behind your bet." label="Related tennis research" links={[
      {href:"/return-atlas",title:"Tennis Return Atlas",description:"Player returns by season, surface and odds.",icon:"tennis"},
      {href:"/tennis-tips",title:"Tennis tips & results",description:"Published selections and competition records.",icon:"tennis"},
      {href:"/resources/tennis-retirement-rules",title:"Tennis retirement rules",description:"Check when a bookmaker pays, loses or refunds a bet.",icon:"rules"},
      {href:"/resources/odds-value-stakes",title:"Understand odds and value",description:"Work through a price, its probability and the stake.",icon:"price"},
    ]} />
  </main><Footer/></>;
}
