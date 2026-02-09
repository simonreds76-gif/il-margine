"use client";

export default function HowItWorks() {
  const steps = [
    {
      title: "Choose your stake per bet",
      body: "Pick £25, £50, £100 or enter any amount. This is the amount you would have staked on each of our settled bets.",
      icon: (
        <svg className="w-8 h-8 text-emerald-400/90" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M12 8c-1.657 0-3 .895-3 2s1.343 2 3 2 3 .895 3 2-1.343 2-3 2m0-8c1.11 0 2.08.402 2.599 1M12 8V7m0 1v8m0 0v1m0-1c-1.11 0-2.08-.402-2.599-1M21 12a9 9 0 11-18 0 9 9 0 0118 0z" />
        </svg>
      ),
    },
    {
      title: "See your result",
      body: "The calculator shows total staked, profit or loss, and ROI based on our verified settled bets (player props + ATP tennis).",
      icon: (
        <svg className="w-8 h-8 text-emerald-400/90" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 01-2 2h-2a2 2 0 01-2-2z" />
        </svg>
      ),
    },
    {
      title: "Optional: add your bankroll",
      body: "Enter a starting bankroll to see what your balance would be after the same run of bets. For illustration only.",
      icon: (
        <svg className="w-8 h-8 text-emerald-400/90" fill="none" stroke="currentColor" viewBox="0 0 24 24" aria-hidden>
          <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={1.5} d="M9 7h6m0 10v-3m-3 3h.01M9 17h.01M9 14h.01M12 14h.01M15 11h.01M12 11h.01M9 11h.01M7 21h10a2 2 0 002-2V5a2 2 0 00-2-2H7a2 2 0 00-2 2v14a2 2 0 002 2z" />
        </svg>
      ),
    },
  ];

  return (
    <section className="max-w-6xl mx-auto" aria-labelledby="how-it-works-heading">
      <h2 id="how-it-works-heading" className="text-2xl sm:text-[28px] font-semibold text-slate-100 mb-8">
        How it works
      </h2>
      <div className="grid sm:grid-cols-3 gap-6">
        {steps.map((step, i) => (
          <div
            key={i}
            className="rounded-xl border border-slate-700/50 bg-slate-800/40 p-6 shadow-sm"
          >
            <div className="flex items-center gap-4 mb-3">
              <span className="flex items-center justify-center w-12 h-12 rounded-lg bg-emerald-500/10 shrink-0">
                {step.icon}
              </span>
              <span className="text-slate-500 font-mono text-sm">{i + 1}. </span>
            </div>
            <h3 className="text-lg font-semibold text-slate-100 mb-2">{step.title}</h3>
            <p className="text-sm text-slate-400 leading-relaxed max-w-prose">{step.body}</p>
          </div>
        ))}
      </div>
    </section>
  );
}
