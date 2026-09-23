import EditorialIcon from "@/components/EditorialIcon";
import Link from "next/link";
import Footer from "@/components/Footer";
import PageHeading from "@/components/PageHeading";
import PriceWorkbench from "@/components/PriceWorkbench";

const STEPS = [
  { n: "01", title: "Start with the evidence", body: "Results, playing time, team news and the conditions of the market inform our estimates. Missing or uncertain inputs matter: a probable starter is not a confirmed starter." },
  { n: "02", title: "Estimate a fair price", body: "A model turns the available evidence into an estimated probability. Fair decimal odds are one divided by that probability. This is an estimate, not a certainty about what will happen." },
  { n: "03", title: "Compare the same bet", body: "Compare the offered price with the model estimate for the same player, event, line and settlement rules. Odds change, so the price and time of a comparison matter as much as the selection." },
  { n: "04", title: "Record and review", body: "Published selections carry a recorded price and stake. Review settled results, sample size and return on investment together. An encouraging short run is a reason to keep measuring, not proof of an enduring edge." },
];

export default function MethodologyPage() {
  return <div className="min-h-screen bg-[#0f1117] text-slate-100"><main className="site-container">
    <PageHeading eyebrow="The Edge · Our methodology" title="How we find the value.">
      <p>The player matters. The price matters just as much. Our approach connects match research, fair odds and a public record of what happens next.</p>
    </PageHeading>
    <PriceWorkbench />
    <div className="method-flow grid gap-4 md:grid-cols-2 xl:grid-cols-4">{STEPS.map(step => <article className="site-card" key={step.n}>
      <span className="method-step-icon" aria-hidden="true"><EditorialIcon name={({"01":"analysis","02":"markets","03":"compare","04":"bankroll"} as const)[step.n as "01" | "02" | "03" | "04"]} className="h-9 w-9" /></span><span className="method-step-number">{step.n}</span><h2 className="mt-4 text-xl font-semibold">{step.title}</h2><p className="mt-3 text-sm text-slate-300">{step.body}</p>
    </article>)}</div>
    <section className="site-section border-t border-slate-800 grid gap-8 lg:grid-cols-2">
      <div><p className="site-eyebrow">Market context</p><h2 className="text-2xl font-semibold">Removing margin is a comparison tool.</h2><p className="mt-3 text-sm text-slate-300">For a complete set of mutually exclusive outcomes, dividing each implied probability by their sum gives a simple proportional no-margin estimate. It describes the market; it does not establish the true probability or an independent betting edge.</p><p className="mt-3 text-sm text-slate-400">Anytime goalscorer outcomes overlap: several players can score. Adding all their implied probabilities and normalising them as if only one player could win is not a valid way to remove the margin.</p><Link href="/calculator" className="site-text-link">Compare margin-removal methods in the calculator →</Link></div>
      <div><div className="margin-visual"><span className="site-eyebrow">Two-outcome illustration</span><h3>1.90 / 1.90</h3><div className="margin-bar"><span>50%</span><span>50%</span><i /></div><p>Implied total <strong>105.26%</strong> · overround <strong>5.26%</strong></p><div className="margin-result"><span>Proportional no-margin estimate</span><strong>2.00 / 2.00</strong></div><p>50% each after removing margin. This is the market’s estimate, not our player model.</p></div><div className="space-y-3">{[
        ["/fair-odds-lab", "Fair Odds Lab", "Compare goalscorer estimates with bookmaker prices and check the lineup status."],
        ["/penalty-takers", "Penalty taker evidence", "Review the order, deputies and supporting evidence for each club."],
        ["/track-record", "Published results", "Inspect the returns and follow through to the individual selection histories."],
      ].map(([href,title,copy]) => <Link key={href} href={href} className="site-card site-card-link block"><h3 className="font-semibold">{title} ↗</h3><p className="mt-1 text-sm text-slate-400">{copy}</p></Link>)}</div></div>
    </section>
    <section className="site-section border-t border-slate-800"><h2 className="text-2xl font-semibold">Using the analysis</h2><div className="mt-4 grid gap-5 text-sm text-slate-300 sm:grid-cols-3"><p><strong className="block mb-1 text-white">Check the current price.</strong>Public results use the recorded odds. A lower price available later can remove the estimated value.</p><p><strong className="block mb-1 text-white">Keep stakes in perspective.</strong>A unit is a way of recording stake size, not a promise of return. The calculator lets you explore different assumptions.</p><p><strong className="block mb-1 text-white">Separate research from results.</strong>Model comparisons and selected winning highlights are not the same as a complete betting record.</p></div><Link href="/resources" className="site-text-link">Explore the research guides →</Link></section>
  </main><Footer /></div>;
}
