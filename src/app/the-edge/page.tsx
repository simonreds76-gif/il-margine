import Link from "next/link";
import Footer from "@/components/Footer";
import PageHeading from "@/components/PageHeading";

const STEPS = [
  { n: "01", title: "Start with the evidence", body: "Results, playing time, team news and the conditions of the market inform our estimates. Missing or uncertain inputs matter: a probable starter is not a confirmed starter." },
  { n: "02", title: "Estimate a fair price", body: "A model turns the available evidence into an estimated probability. Fair decimal odds are one divided by that probability. This is an estimate, not a certainty about what will happen." },
  { n: "03", title: "Compare the same bet", body: "Compare the offered price with the model estimate for the same player, event, line and settlement rules. Odds change, so the price and time of a comparison matter as much as the selection." },
  { n: "04", title: "Record and review", body: "Published selections carry a recorded price and stake. Review settled results, sample size and return on investment together. An encouraging short run is a reason to keep measuring, not proof of an enduring edge." },
];

export default function MethodologyPage() {
  return <div className="min-h-screen bg-[#0f1117] text-slate-100"><main className="site-container">
    <PageHeading eyebrow="The Edge · Our methodology" title="Evidence. Price. A clear record.">
      <p>Independent betting analysis means explaining the reasoning behind a price and letting the results be judged. Here is how to use our selections and research tools.</p>
    </PageHeading>
    <div className="grid gap-4 md:grid-cols-2">{STEPS.map(step => <article className="site-card" key={step.n}>
      <span className="site-step">{step.n}</span><h2 className="mt-4 text-xl font-semibold">{step.title}</h2><p className="mt-3 text-sm text-slate-300">{step.body}</p>
    </article>)}</div>
    <section className="site-section grid gap-8 lg:grid-cols-2" aria-labelledby="value-example">
      <div><p className="site-eyebrow">A worked example</p><h2 id="value-example" className="text-2xl font-semibold">Value is about the price.</h2><p className="mt-3 text-sm text-slate-300">Suppose a model estimates a 40% chance. Its fair odds are 2.50. At bookmaker odds of 2.75, the estimated return per unit staked is 0.40 × 2.75 − 1 = +10%.</p><p className="mt-3 text-sm text-slate-400">The outcome is still more likely to lose than win. If the 40% estimate is wrong, the apparent value may disappear. Expected return is not realised profit.</p></div>
      <div className="site-card"><p className="site-eyebrow">Illustration only · not a selection</p><dl className="mt-5 grid grid-cols-2 gap-6">{[["Estimated chance", "40%"], ["Model fair odds", "2.50"], ["Offered odds", "2.75"], ["Estimated EV", "+10%"]].map(([label,value]) => <div key={label}><dt className="text-xs text-slate-400">{label}</dt><dd className="mt-1 text-3xl font-semibold tabular-nums">{value}</dd></div>)}</dl></div>
    </section>
    <section className="site-section border-t border-slate-800 grid gap-8 lg:grid-cols-2">
      <div><p className="site-eyebrow">Market context</p><h2 className="text-2xl font-semibold">Removing margin is a comparison tool.</h2><p className="mt-3 text-sm text-slate-300">For a complete set of mutually exclusive outcomes, dividing each implied probability by their sum gives a simple proportional no-margin estimate. It describes the market; it does not establish the true probability or an independent betting edge.</p><p className="mt-3 text-sm text-slate-400">Anytime goalscorer outcomes overlap: several players can score. Adding all their implied probabilities and normalising them as if only one player could win is not a valid way to remove the margin.</p></div>
      <div className="space-y-3">{[
        ["/fair-odds-lab", "Fair Odds Lab", "Compare goalscorer estimates with bookmaker prices and check the lineup status."],
        ["/penalty-takers", "Penalty taker evidence", "Review the order, deputies and supporting evidence for each club."],
        ["/track-record", "Published results", "Inspect the returns and follow through to the individual selection histories."],
      ].map(([href,title,copy]) => <Link key={href} href={href} className="site-card site-card-link block"><h3 className="font-semibold">{title} ↗</h3><p className="mt-1 text-sm text-slate-400">{copy}</p></Link>)}</div>
    </section>
    <section className="site-section border-t border-slate-800"><h2 className="text-2xl font-semibold">Using the analysis</h2><div className="mt-4 grid gap-5 text-sm text-slate-300 sm:grid-cols-3"><p><strong className="block mb-1 text-white">Check the current price.</strong>Public results use the recorded odds. A lower price available later can remove the estimated value.</p><p><strong className="block mb-1 text-white">Keep stakes in perspective.</strong>A unit is a way of recording stake size, not a promise of return. The calculator lets you explore different assumptions.</p><p><strong className="block mb-1 text-white">Separate research from results.</strong>Model comparisons and selected winning highlights are not the same as a complete betting record.</p></div><Link href="/resources" className="site-text-link">Explore the research guides →</Link></section>
  </main><Footer /></div>;
}
