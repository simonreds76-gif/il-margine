"use client";

const faqItems = [
  {
    q: "What does this calculator show?",
    a: "The Returns Calculator shows what you would have won or lost following our settled bets at a chosen stake. The Kelly Calculator computes a recommended stake for any bet based on your bankroll, the odds, and your estimated win probability. Both tools use real data and standard mathematics. Neither is a prediction of future results.",
  },
  {
    q: "What if the data is unavailable?",
    a: 'If live track-record data is temporarily unavailable, we fall back to the last recorded settled results and show a clear data notice on the page. The calculator still works, but the record is not updating live in that moment.',
  },
];

export default function FaqAccordion() {
  return (
    <section className="max-w-6xl mx-auto" aria-labelledby="calculator-faq-heading">
      <h2 id="calculator-faq-heading" className="text-2xl font-semibold text-slate-100 sm:text-[28px]">
        Calculator FAQ
      </h2>
      <div className="mt-6 space-y-2">
        {faqItems.map((item) => (
          <details
            key={item.q}
            className="group overflow-hidden rounded-xl border border-slate-700/50 bg-slate-800/40"
          >
            <summary className="flex cursor-pointer list-none items-center gap-2 px-5 py-4 text-left font-medium text-slate-200 transition-colors hover:bg-slate-700/30 focus-visible:outline focus-visible:outline-2 focus-visible:outline-offset-2 focus-visible:outline-emerald-500">
              <span className="flex-1">{item.q}</span>
              <span className="shrink-0 text-emerald-400 transition-transform group-open:rotate-180" aria-hidden>
                <svg className="w-5 h-5" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                  <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M19 9l-7 7-7-7" />
                </svg>
              </span>
            </summary>
            <div className="border-t border-slate-700/50 bg-slate-800/20 px-5 py-4">
              <p className="text-sm leading-relaxed text-slate-400">{item.a}</p>
            </div>
          </details>
        ))}
      </div>
    </section>
  );
}
