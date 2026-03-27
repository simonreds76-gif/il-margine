"use client";

const returnsSteps = [
  {
    title: "Set your stake",
    body: "Pick a flat stake per bet and optionally add a starting bankroll to see how the same settled record would have played out in pounds.",
  },
  {
    title: "Use verified results",
    body: "The calculator uses our settled player props and ATP tennis record only. It is a tracking tool, not a forecast.",
  },
  {
    title: "Read the output",
    body: "You get total staked, profit or loss, ROI, and optional bankroll growth from the same run of settled bets.",
  },
] as const;

const kellySteps = [
  {
    title: "Enter bankroll and odds",
    body: "Start with your bankroll and the current decimal price you can actually bet, not the number you wish you had.",
  },
  {
    title: "Estimate your win probability",
    body: "This is where your edge lives. If your probability estimate is wrong, the Kelly output will be wrong too.",
  },
  {
    title: "Choose a fraction",
    body: "Use one-tenth Kelly for prop-style markets and quarter Kelly for tennis or match markets to control variance.",
  },
] as const;

function StepList({
  title,
  description,
  steps,
}: {
  title: string;
  description: string;
  steps: readonly { title: string; body: string }[];
}) {
  return (
    <div className="rounded-2xl border border-slate-700/50 bg-slate-800/40 p-6 shadow-sm">
      <h3 className="text-lg font-semibold text-slate-100">{title}</h3>
      <p className="mt-2 text-sm leading-relaxed text-slate-400">{description}</p>
      <div className="mt-6 space-y-4">
        {steps.map((step, index) => (
          <div key={step.title} className="flex gap-4">
            <span className="mt-0.5 flex h-9 w-9 shrink-0 items-center justify-center rounded-lg bg-emerald-500/10 font-mono text-sm text-emerald-300">
              {index + 1}
            </span>
            <div>
              <h4 className="text-sm font-semibold text-slate-100">{step.title}</h4>
              <p className="mt-1 text-sm leading-relaxed text-slate-400">{step.body}</p>
            </div>
          </div>
        ))}
      </div>
    </div>
  );
}

export default function HowItWorks() {
  return (
    <section className="max-w-6xl mx-auto" aria-labelledby="how-it-works-heading">
      <h2 id="how-it-works-heading" className="text-2xl font-semibold text-slate-100 sm:text-[28px]">
        How it works
      </h2>
      <p className="mt-3 max-w-3xl text-sm leading-relaxed text-slate-400 sm:text-base">
        Two different tools, two different jobs: one tracks what a flat-stake approach would have returned on our settled record, the other helps size a stake when you think you have an edge.
      </p>

      <div className="mt-8 grid gap-6 lg:grid-cols-2">
        <StepList
          title="Returns calculator"
          description="Use this to stress-test your own stake size against our settled record."
          steps={returnsSteps}
        />
        <StepList
          title="Kelly calculator"
          description="Use this to size a stake for any price once you have your own probability estimate."
          steps={kellySteps}
        />
      </div>
    </section>
  );
}
