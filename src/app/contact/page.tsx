import type { Metadata } from "next";
import Link from "next/link";
import InfoPage from "@/components/InfoPage";
import EditorialIcon from "@/components/EditorialIcon";
import { BASE_URL } from "@/lib/config";

export const metadata: Metadata = {
  title: "Contact Il Margine", description: "Report an error, share evidence or get in touch about our independent betting research.", alternates: { canonical: `${BASE_URL}/contact` }, robots: { index: true, follow: true },
  openGraph: { title: "Contact Il Margine", description: "Report an error, share evidence or get in touch about our independent betting research.", url: `${BASE_URL}/contact`, images: [`${BASE_URL}/brand/20260913/social.png`] },
};
export default function Page() {
  return <InfoPage title={"Contact Il Margine"} intro={"Report an error, share evidence or get in touch about our independent betting research."} icon="about" path="/contact">
<section className="info-card"><EditorialIcon name="guide" className="h-11 w-11" /><h2>Questions, feedback & corrections</h2><p>Spotted a wrong result, a missing club badge or an unclear explanation? Tell us which page you were reading and what needs checking.</p><div className="guide-actions"><a href="mailto:contact@ilmargine.bet">Email contact@ilmargine.bet ↗</a></div><ul><li>Include the page link and the relevant match or player.</li><li>For a result or price issue, add the market, bookmaker, date and time.</li><li>For penalty hierarchies, link the press conference, report or other evidence and say when it was published.</li></ul><p>Public sources help us assess a correction. Please remove account numbers, balances and other personal details from screenshots.</p></section>
<section className="info-card"><EditorialIcon name="compare" className="h-11 w-11" /><h2>Editorial & business enquiries</h2><p>For interviews, research references, tool integrations or commercial proposals, explain the idea and the audience it would serve.</p><div className="guide-actions"><a href="mailto:partners@ilmargine.bet">Email partners@ilmargine.bet ↗</a></div><p>Sending a proposal does not secure an endorsement or a link. Editorial references should help readers understand the subject.</p></section>
<section><h2>Need an answer now?</h2><p>Our FAQs explain how to read selections, compare prices, use Return Atlas and interpret the public record. The guides work through the calculations with examples.</p><div className="guide-actions"><Link href="/faq">Find a quick answer ↗</Link><Link href="/resources">Explore the guides ↗</Link></div></section>
<section><h2>Privacy requests</h2><p>Email <a href="mailto:contact@ilmargine.bet?subject=Privacy%20request">contact@ilmargine.bet</a> with “Privacy request” in the subject. Describe the information or activity concerned. Do not send identity documents unless we ask for what is needed to verify a request.</p></section>
</InfoPage>;
}
