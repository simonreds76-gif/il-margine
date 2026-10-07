import Link from "next/link";
import Footer from "@/components/Footer";
import PageHeading from "@/components/PageHeading";
import RelatedLinks from "@/components/RelatedLinks";
import ToolEmblem from "@/components/ToolEmblem";
import ResourceLibrary from "@/components/ResourceLibrary";
import { RESOURCES } from "@/lib/resources";
import { BASE_URL } from "@/lib/config";
import "@/components/resource-guides.css";
import "@/components/resource-library.css";

export default function ResourcesPage() {
  const schema = { "@context": "https://schema.org", "@type": "CollectionPage", name: "Sports betting guides and tools", url: `${BASE_URL}/resources`, mainEntity: { "@type": "ItemList", itemListElement: RESOURCES.map((r,i) => ({ "@type": "ListItem", position: i+1, name:r.title, url:`${BASE_URL}${r.href}` })) } };
  return <div className="guide-page resource-hub"><script type="application/ld+json" dangerouslySetInnerHTML={{ __html: JSON.stringify(schema).replace(/</g, "\\u003c") }} /><div className="guide-container"><PageHeading eyebrow="Practical betting knowledge" title="Understand the bet. Check the numbers." icon="guide" actions={<div className="guide-actions"><a href="#resource-library">Browse all guides & tools ↓</a><Link prefetch={false} href="/tools">Explore betting tools ↗</Link><Link href="/faq">Quick answers ↗</Link></div>}><p>Sports betting guides with everyday examples, clear calculations and tools to try. Start with a question, then work through the answer.</p></PageHeading></div><main className="guide-container"><nav className="resource-paths" aria-label="Choose a learning path"><Link href="/resources/how-to-read-a-tipster-track-record"><ToolEmblem name="record" /><span>Check the evidence</span><h2>Can I trust this track record?</h2><p>Find the complete bet list, test the headline and check the prices.</p></Link><Link href="/resources/closing-line-value"><ToolEmblem name="closing" /><span>Understand the price</span><h2>Did I get good odds?</h2><p>Compare what you took with the close, after removing the margin.</p></Link><Link href="/resources/kelly-criterion-sports-betting"><ToolEmblem name="kelly" /><span>Understand the stake</span><h2>What does Kelly actually do?</h2><p>Work through the numbers and see how a wrong estimate changes them.</p></Link></nav><ResourceLibrary resources={RESOURCES} /><RelatedLinks title="Explore the current research" description="Use the guides to read the evidence, assumptions and dates alongside the numbers." links={[
 {href:"/penalty-takers",title:"Penalty taker hierarchies",description:"First choices, deputies and club evidence.",icon:"penalty"},
 {href:"/fair-odds-lab",title:"Goalscorer Fair Odds Lab",description:"Lineups, estimated fair prices and bookmaker comparisons.",icon:"lab"},
 ]} /></main><Footer /></div>;
}
