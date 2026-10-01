import type { Metadata } from "next";
import Image from "next/image";
import Link from "next/link";
import Footer from "@/components/Footer";
import MatchdayPromo from "@/components/MatchdayPromo";
import { BASE_URL } from "@/lib/config";
import { MATCHUP_FAQS } from "@/lib/tennis-matchup-faq";
import release from "@/data/tennis-matchup-release.json";
import MatchupClient from "./MatchupClient";
import "./matchup.css";

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
  return <><main className="matchup-lab">
    <script type="application/ld+json" dangerouslySetInnerHTML={{__html:JSON.stringify(schema).replace(/</g,"\\u003c")}}/>
    <nav className="matchup-breadcrumb" aria-label="Breadcrumb"><Link href="/">Home</Link><span>/</span><Link href="/tools">Betting tools</Link><span>/</span><span>Tennis Matchup Lab</span></nav>
    <header className="hero"><div><div className="product-signature"><div><span className="product-parent">IL MARGINE / TENNIS RESEARCH</span><strong>Matchup <span>Lab</span></strong></div></div>
      <h1>Tennis players.<br/>A clearer <em>matchup.</em></h1><p className="lead">Compare head-to-head results, serve and return statistics, aces and double faults. Explore how the record changes by surface and location.</p></div>
      <div className="hero-mark" aria-hidden="true"><Image src="/tennis-matchup/court-v1.webp" width={640} height={640} alt="" priority unoptimized/></div></header>
    <div className="intro-note"><span className="note-dot"/><p><strong>Start with two players.</strong> Compare their profiles against all opponents, or switch to their meetings against each other. Open a match to inspect the numbers behind it.</p></div>
    <div className="matchup-freshness"><span>Snapshot <time dateTime={release.checkedAt}>{readable(release.checkedAt)}</time></span><span>Latest result <time dateTime={release.through}>{readable(release.through)}</time></span><span>{release.matches.toLocaleString("en-GB")} archive matches · 2022 onward</span></div>
    <MatchupClient indexUrl={release.indexUrl}/>
    <MatchdayPromo compact />
    <noscript><p>Enable JavaScript to select players and compare their records. The guide, coverage details and FAQs below are available without it.</p></noscript>
    <section className="matchup-faq" id="faq" aria-labelledby="matchup-faq-title"><p className="eyebrow">GET MORE FROM THE NUMBERS</p><h2 id="matchup-faq-title">Tennis Matchup Lab FAQs</h2><p>What the tool shows, how to use the filters, and where the evidence ends.</p>{MATCHUP_FAQS.map(({question,answer})=><details key={question}><summary>{question}</summary><p>{answer}</p></details>)}</section>
    <section className="matchup-next"><h2>Keep the price and the record in view.</h2><p>Compare playing profiles here, investigate historical betting returns in Return Atlas, or read our published tennis selections.</p><nav aria-label="Related tennis research"><Link prefetch={false} href="/return-atlas">Tennis Return Atlas →</Link><Link prefetch={false} href="/tennis-tips">Tennis tips & results →</Link><Link prefetch={false} href="/resources/odds-value-stakes">Understand odds and value →</Link></nav></section>
  </main><Footer/></>;
}
