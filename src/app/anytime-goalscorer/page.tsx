import Link from "next/link";

const roadmap = [
  {
    step: "1",
    title: "Serie A Data Pipeline",
    text: "FBref player-match logs, team xG/xGA, minutes, shots, non-penalty xG, and penalty events collected chronologically for leakage-safe modelling.",
  },
  {
    step: "2",
    title: "Poisson Probability Engine",
    text: "Anytime-goalscorer probabilities built from expected minutes, non-penalty xG rate, opponent defensive strength, home/away context, and penalty-role adjustment.",
  },
  {
    step: "3",
    title: "Odds Capture",
    text: "Historical and live anytime-goalscorer prices archived so the model can be tested against real bookmaker markets rather than theoretical fair odds only.",
  },
  {
    step: "4",
    title: "Live Value Signals",
    text: "Once calibration is strong and odds capture is stable, the page will surface live goalscorer value spots the same way fair odds does for tennis.",
  },
];

const focusPoints = [
  "Serie A first. Smaller scope, cleaner validation, faster iteration.",
  "Confirmed lineups matter. Minutes are the biggest source of goalscorer-model error.",
  "Penalty-role changes are a real edge source. Markets are slow to react.",
  "Calibration comes before ROI claims. If the probabilities are wrong, nothing else matters.",
];

export default function AnytimeGoalscorerPage() {
  return (
    <div className="min-h-screen bg-[#0f1117] text-slate-100">
      <section className="border-b border-slate-800/50 pt-6 pb-12 md:pt-6 md:pb-16">
        <div className="mx-auto max-w-6xl px-4 sm:px-6 lg:px-8">
          <div className="mb-4 flex items-center gap-2">
            <Link href="/" className="text-sm text-slate-500 hover:text-slate-300">
              Home
            </Link>
            <span className="text-slate-600">/</span>
            <span className="text-sm text-emerald-400">Goalscorer Model</span>
          </div>

          <div className="max-w-4xl">
            <div className="mb-4 inline-flex items-center rounded-full border border-emerald-500/25 bg-emerald-500/10 px-3 py-1 text-xs font-semibold uppercase tracking-[0.24em] text-emerald-300">
              In Development
            </div>
            <h1 className="mb-4 text-3xl font-semibold tracking-tight text-slate-100 sm:text-4xl">
              Goalscorer Model
            </h1>
            <p className="max-w-3xl text-base leading-relaxed text-slate-300 sm:text-lg">
              We&apos;re building a football anytime-goalscorer fair-odds model focused on Serie A. The goal is
              simple: estimate clean scoring probabilities from minutes, shot quality, team context, and penalty
              role, then compare those probabilities against soft-book goalscorer prices.
            </p>
          </div>
        </div>
      </section>

      <section className="py-12 md:py-16">
        <div className="mx-auto grid max-w-6xl gap-6 px-4 sm:px-6 lg:grid-cols-[1.25fr,0.75fr] lg:px-8">
          <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-6 shadow-[0_20px_50px_rgba(0,0,0,0.25)]">
            <div className="mb-5 flex items-center gap-2">
              <span className="text-xs font-mono uppercase tracking-[0.22em] text-emerald-400">Roadmap</span>
            </div>
            <div className="space-y-4">
              {roadmap.map((item) => (
                <div key={item.step} className="rounded-xl border border-slate-800/80 bg-slate-950/35 p-4">
                  <div className="mb-2 flex items-center gap-3">
                    <div className="flex h-8 w-8 items-center justify-center rounded-full bg-emerald-500/15 text-sm font-semibold text-emerald-300">
                      {item.step}
                    </div>
                    <h2 className="text-lg font-semibold text-slate-100">{item.title}</h2>
                  </div>
                  <p className="text-sm leading-6 text-slate-300">{item.text}</p>
                </div>
              ))}
            </div>
          </div>

          <div className="space-y-6">
            <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-6">
              <div className="mb-4 text-xs font-mono uppercase tracking-[0.22em] text-emerald-400">Current Focus</div>
              <ul className="space-y-3 text-sm leading-6 text-slate-300">
                {focusPoints.map((point) => (
                  <li key={point} className="flex gap-3">
                    <span className="mt-1 h-2 w-2 rounded-full bg-emerald-400" />
                    <span>{point}</span>
                  </li>
                ))}
              </ul>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-slate-900/50 p-6">
              <div className="mb-4 text-xs font-mono uppercase tracking-[0.22em] text-emerald-400">Status</div>
              <div className="space-y-3 text-sm text-slate-300">
                <p>
                  The model is not publishing live picks yet. We are still in the build-and-validate stage:
                  scraper quality, probability calibration, and odds capture all need to be right before anything
                  goes live.
                </p>
                <p>
                  When this is ready, this page will show live goalscorer fair odds and value flags, not generic
                  “tips”.
                </p>
              </div>
            </div>

            <div className="rounded-2xl border border-slate-800 bg-[linear-gradient(135deg,rgba(16,185,129,0.12),rgba(15,23,42,0.92))] p-6">
              <h3 className="mb-3 text-lg font-semibold text-slate-100">Why this market matters</h3>
              <p className="mb-5 text-sm leading-6 text-slate-300">
                Goalscorer markets are softer than top-tier tennis moneylines. The opportunity is in player role,
                minutes, and penalty duties, not in pretending we can outguess a sharp closing market with vague
                narrative.
              </p>
              <div className="flex flex-wrap gap-3">
                <Link
                  href="/the-edge"
                  className="inline-flex items-center rounded-lg bg-emerald-500 px-4 py-2.5 text-sm font-semibold text-white transition-colors hover:bg-emerald-400"
                >
                  Read The Edge
                </Link>
                <Link
                  href="/bookmakers"
                  className="inline-flex items-center rounded-lg border border-slate-700 px-4 py-2.5 text-sm font-medium text-slate-200 transition-colors hover:border-slate-500 hover:bg-slate-800/50"
                >
                  Bookmaker Context
                </Link>
              </div>
            </div>
          </div>
        </div>
      </section>
    </div>
  );
}
