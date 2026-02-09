"use client";

const faqItems = [
  {
    q: "What does this calculator show?",
    a: "It shows how much you would have won or lost if you had followed our settled bets (player props and ATP tennis) with a fixed stake per bet, e.g. £25, £50 or £100 on every bet. Results are based only on our verified track record. No predictions or simulations.",
  },
  {
    q: "Where do the numbers come from?",
    a: "From our verified historical track record: every settled bet we have logged (player props and ATP tennis). We sum profit and total staked from those bets to get ROI, then apply your chosen stake per bet to show what your profit or loss would have been in pounds.",
  },
  {
    q: "Is this a prediction of future results?",
    a: "No. The calculator is based on past performance only. Future results may differ. It is for illustration only. Always bet responsibly and within your means.",
  },
  {
    q: "What if the data is unavailable?",
    a: "If live data is temporarily unavailable, we use the last recorded settled-bets performance and show a notice: \"Data notice: Live updates are temporarily unavailable. Results are calculated using the last recorded settled-bets performance.\"",
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
