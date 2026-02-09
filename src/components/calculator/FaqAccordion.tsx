"use client";

const faqItems = [
  {
    q: "What is the unit system?",
    a: "We recommend stakes in units (1u, 2u, etc.). A unit is a fixed percentage of your bankroll, typically 1 to 2%. Example: £2,500 bankroll at 1% means 1u = £25. A 2u pick = £50 stake.",
  },
  {
    q: "How are returns calculated?",
    a: "Returns use our historical ROI applied to your total stake in units. Expected profit (units) = total stake × (ROI ÷ 100). If you enter bankroll and unit size, we also show expected profit in £ and an illustrative ending bankroll.",
  },
  {
    q: "Is this a prediction of future results?",
    a: "No. The calculator is based on past performance only. Future results may differ. Variance is not modelled. Always bet responsibly and within your means.",
  },
  {
    q: "Where does the ROI come from?",
    a: "ROI is derived from our verified track record (player props and ATP tennis), combined with baseline historical data. It updates as new bets are settled. If live data is unavailable, we use the last known ROI and show a notice.",
  },
];

export default function FaqAccordion() {
  return (
    <section className="max-w-6xl mx-auto" aria-labelledby="calculator-faq-heading">
      <h2 id="calculator-faq-heading" className="text-2xl sm:text-[28px] font-semibold text-slate-100 mb-6">
        Calculator FAQ
      </h2>
      <div className="space-y-2">
        {faqItems.map((item, i) => (
          <details
            key={i}
            className="group rounded-xl bg-slate-800/40 border border-slate-700/50 overflow-hidden"
          >
            <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-4 text-left font-medium text-slate-200 hover:bg-slate-700/30 transition-colors focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500">
              <span className="flex-1">{item.q}</span>
              <span className="text-emerald-400 shrink-0 transition-transform group-open:rotate-180" aria-hidden>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </span>
            </summary>
            <div className="border-t border-slate-700/50 px-5 py-4 bg-slate-800/20">
              <p className="text-sm text-slate-400 leading-relaxed">{item.a}</p>
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}
